# tests/test_direct.py
import pytest
from conftest import OUT
from toolbridge import ToolBridgeError
from toolbridge.direct import call, check_bitness


def test_static_call():
    assert list(call(OUT / "net/FlashCore.dll", "FlashCore.FlashService.KnownEcus")) == ["ECU1", "ECU2", "Gateway"]


def test_instance_call_returns_bytes_written(tmp_path):
    f = tmp_path / "a.hex"; f.write_bytes(b"x" * 4096)
    assert call(OUT / "net/FlashCore.dll", "FlashCore.FlashService.Program", str(f), "ECU1", None) == 4096


def test_exception_becomes_error():
    with pytest.raises(ToolBridgeError, match="not found"):
        call(OUT / "net/FlashCore.dll", "FlashCore.FlashService.Program", "C:/nope.hex", "ECU1", None)


def test_bitness_mismatch_message():
    import struct
    other = "x86" if struct.calcsize("P") == 8 else "x64"
    with pytest.raises(ToolBridgeError, match="GUI version"):
        check_bitness(other)
    check_bitness("any")
