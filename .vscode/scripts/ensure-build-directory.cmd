@echo off
rem Keep the original entrypoint for callers outside VS Code.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0ensure-build-directory.ps1" -WorkspaceFolder "%~1" -CMake "%~2"
exit /b %ERRORLEVEL%
