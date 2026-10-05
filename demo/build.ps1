# demo/build.ps1 — builds both demos into demo/out/{net,native}. Needs the .NET 8+ SDK and MSVC (VS 2022 C++).
$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
dotnet publish "$here/DemoFlasher.NET/DemoFlasher/DemoFlasher.csproj" -c Release -o "$here/out/net" --nologo -v q
if ($LASTEXITCODE) { throw "dotnet publish failed" }
$vs = & "${env:ProgramFiles(x86)}\Microsoft Visual Studio\Installer\vswhere.exe" -latest -products * -property installationPath
$out = "$here/out/native"; New-Item -ItemType Directory -Force $out | Out-Null
$cmd = "`"$vs\VC\Auxiliary\Build\vcvars64.bat`" >nul && cd /d `"$out`" && " +
       "cl /nologo /EHsc /LD /Fe:flashcore_native.dll `"$here\DemoFlasher.Native\flashcore.cpp`" && " +
       "cl /nologo /EHsc /Fe:DemoFlasherNative.exe `"$here\DemoFlasher.Native\app.cpp`" flashcore_native.lib user32.lib comdlg32.lib /link /SUBSYSTEM:WINDOWS"
cmd /c $cmd
if ($LASTEXITCODE) { throw "MSVC build failed" }
