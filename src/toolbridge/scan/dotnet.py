# src/toolbridge/scan/dotnet.py
"""Read a .NET assembly without running it: public methods, and which WinForms control
calls which method (InitializeComponent wiring -> handler body -> non-framework calls)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import dnfile
from dncil.cil.body import CilMethodBody
from dncil.cil.body.reader import CilMethodBodyReaderBase
from dncil.clr.token import Token

_FRAMEWORK = ("System.", "Microsoft.", "<")
_PRIM = {0x01: "void", 0x02: "bool", 0x03: "char", 0x04: "sbyte", 0x05: "byte", 0x06: "short",
         0x07: "ushort", 0x08: "int", 0x09: "uint", 0x0A: "long", 0x0B: "ulong", 0x0C: "float",
         0x0D: "double", 0x0E: "string", 0x18: "IntPtr", 0x1C: "object"}
_TBL_FIELD, _TBL_METHODDEF, _TBL_MEMBERREF = 0x04, 0x06, 0x0A


@dataclass
class Method:
    type: str
    name: str
    params: list[tuple[str, str]]
    returns: str
    static: bool
    public: bool

    @property
    def full_name(self) -> str:
        return f"{self.type}.{self.name}"

    @property
    def signature(self) -> str:
        args = ", ".join(f"{t} {n}" for t, n in self.params)
        return f"{self.full_name}({args}) -> {self.returns}"


@dataclass
class Wiring:
    control: str
    event: str
    handler: str
    calls: list[str]


class _Reader(CilMethodBodyReaderBase):
    def __init__(self, pe: dnfile.dnPE, rva: int):
        self.pe, self.offset = pe, pe.get_offset_from_rva(rva)

    def read(self, n: int) -> bytes:
        data = self.pe.get_data(self.pe.get_rva_from_offset(self.offset), n)
        self.offset += n
        return data

    def tell(self) -> int:
        return self.offset

    def seek(self, offset: int) -> int:
        self.offset = offset
        return offset


def _type_name(row) -> str:
    if not hasattr(row, "TypeNamespace"):     # TypeSpec (generic instance) or other: not a plain type
        return "<spec>"
    ns = str(getattr(row, "TypeNamespace", "") or "")
    return f"{ns}.{row.TypeName}" if ns else str(row.TypeName)


class _Sig:
    """Decodes a MethodDefSig blob (ECMA-335 II.23.2.1) into type names."""

    def __init__(self, pe: dnfile.dnPE, blob: bytes):
        self.pe, self.b, self.i = pe, blob, 0

    def u(self) -> int:
        b = self.b[self.i]
        if b & 0x80 == 0:
            self.i += 1; return b
        if b & 0xC0 == 0x80:
            v = ((b & 0x3F) << 8) | self.b[self.i + 1]; self.i += 2; return v
        v = ((b & 0x1F) << 24) | (self.b[self.i + 1] << 16) | (self.b[self.i + 2] << 8) | self.b[self.i + 3]
        self.i += 4; return v

    def typedef_or_ref(self) -> str:
        coded = self.u()
        table, rid = coded & 0x3, coded >> 2
        md = self.pe.net.mdtables
        rows = {0: md.TypeDef, 1: md.TypeRef}.get(table)
        return _type_name(rows[rid - 1]) if rows else "?"

    def type(self) -> str:
        et = self.u()
        if et in _PRIM:
            return _PRIM[et]
        if et in (0x11, 0x12):
            name = self.typedef_or_ref()
            return name.split(".")[-1].split("`")[0] if name.startswith("System.") else name
        if et == 0x1D:
            return self.type() + "[]"
        if et == 0x15:
            self.u()                               # class/valuetype marker
            base = self.typedef_or_ref().split(".")[-1].split("`")[0]
            args = [self.type() for _ in range(self.u())]
            return f"{base}<{', '.join(args)}>"
        if et in (0x13, 0x1E):
            return f"T{self.u()}"
        if et == 0x10:
            return "ref " + self.type()
        return f"type0x{et:x}"

    def method(self) -> tuple[list[str], str]:
        conv = self.u()
        if conv & 0x10:
            self.u()                               # generic param count
        n = self.u()
        ret = self.type()
        return [self.type() for _ in range(n)], ret


def _open(dll: Path) -> dnfile.dnPE:
    return dnfile.dnPE(str(dll))


def _methods_by_type(pe):
    """Yields (typedef_row, methoddef_index0) using TypeDef.MethodList ranges."""
    md = pe.net.mdtables
    for t in md.TypeDef:
        for ref in t.MethodList or []:
            yield t, ref.row_index - 1


def list_methods(dll: Path, public_only: bool = True) -> list[Method]:
    pe = _open(dll)
    md = pe.net.mdtables
    out = []
    for t, idx in _methods_by_type(pe):
        m = md.MethodDef[idx]
        name = str(m.Name)
        public = bool(m.Flags.mdPublic)
        if (public_only and not public) or "<" in name or name.startswith((".", "get_", "set_", "add_", "remove_")):
            continue
        if public_only and not t.Flags.tdPublic:
            continue
        ptypes, ret = _Sig(pe, bytes(m.Signature.value)).method()
        pnames = [str(p.row.Name) for p in (m.ParamList or []) if p.row.Sequence > 0]
        pnames += [f"arg{i}" for i in range(len(pnames), len(ptypes))]
        out.append(Method(_type_name(t), name, list(zip(ptypes, pnames)), ret,
                          bool(m.Flags.mdStatic), public))
    pe.close()
    return out


def _tok(operand) -> Token:
    return operand if isinstance(operand, Token) else Token(int(operand))


def _callee(pe, operand) -> str | None:
    tok = _tok(operand)
    md = pe.net.mdtables
    if tok.table == _TBL_MEMBERREF:
        r = md.MemberRef[tok.rid - 1]
        return f"{_type_name(r.Class.row)}.{r.Name}"
    if tok.table == _TBL_METHODDEF:
        for t, idx in _methods_by_type(pe):
            if idx == tok.rid - 1:
                return f"{_type_name(t)}.{md.MethodDef[idx].Name}"
    return None


def _body(pe, idx: int):
    m = pe.net.mdtables.MethodDef[idx]
    return CilMethodBody(_Reader(pe, m.Rva)).instructions if m.Rva else []


def trace_winforms(dll: Path) -> list[Wiring]:
    pe = _open(dll)
    md = pe.net.mdtables
    by_name = {}
    for t, idx in _methods_by_type(pe):
        by_name.setdefault(str(md.MethodDef[idx].Name), []).append((t, idx))
    wirings = []
    for t, idx in by_name.get("InitializeComponent", []):
        field = handler = None
        for ins in _body(pe, idx):
            op = ins.opcode.name
            if op == "ldfld" and _tok(ins.operand).table == _TBL_FIELD:
                field = str(md.Field[_tok(ins.operand).rid - 1].Name)
            elif op == "ldftn":
                handler = (_callee(pe, ins.operand) or "").rsplit(".", 1)[-1]
            elif op == "callvirt" and handler and field:
                callee = _callee(pe, ins.operand) or ""
                event = callee.rsplit(".", 1)[-1]
                if event.startswith("add_"):
                    wirings.append(Wiring(field, event[4:], handler, _handler_calls(pe, by_name, handler)))
                    handler = None
    pe.close()
    return wirings


def _handler_calls(pe, by_name, handler: str) -> list[str]:
    md = pe.net.mdtables
    bodies = [idx for _, idx in by_name.get(handler, [])]
    # compiler-generated code that belongs to the handler: async state machines
    # (<handler>d__N.MoveNext) and lambdas (<handler>b__N, e.g. Task.Run(() => ...))
    for t, idx in _methods_by_type(pe):
        mname = str(md.MethodDef[idx].Name)
        if (str(t.TypeName).startswith(f"<{handler}>") and mname == "MoveNext") or                 mname.startswith(f"<{handler}>b__"):
            bodies.append(idx)
    calls = []
    for idx in bodies:
        for ins in _body(pe, idx):
            if ins.opcode.name in ("call", "callvirt", "newobj"):
                name = _callee(pe, ins.operand)
                if name and not name.startswith(_FRAMEWORK) and ".<" not in name and "+<" not in name \
                        and not name.rsplit(".", 1)[-1].startswith((".", "get_", "set_", "<")) and name not in calls:
                    calls.append(name)
    return calls
