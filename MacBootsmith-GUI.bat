@echo off
REM Starts the MacBootsmith window. The terminal menu stays in OpCore-Simplify.bat.
set "thisDir=%~dp0"

setlocal enableDelayedExpansion
set "script=!thisDir!MacBootsmith.pyw"
set "pyexe="

if not exist "!script!" (
    echo Could not find MacBootsmith.pyw next to this file.
    echo.
    echo Press [enter] to quit.
    pause > nul
    exit /b 1
)

for /f "USEBACKQ tokens=*" %%x in (`where.exe py 2^> nul`) do (
    if not defined pyexe call :checklauncher "%%x"
)
for /f "USEBACKQ tokens=*" %%x in (`where.exe python 2^> nul`) do (
    if not defined pyexe call :checkpy "%%x"
)
for /f "USEBACKQ tokens=*" %%x in (`where.exe python3 2^> nul`) do (
    if not defined pyexe call :checkpy "%%x"
)

if not defined pyexe (
    echo Python 3 was not found on the system or in the PATH var.
    echo Run OpCore-Simplify.bat once: it offers to install Python, then start this file again.
    echo.
    echo Press [enter] to quit.
    pause > nul
    exit /b 1
)

for %%d in ("!pyexe!") do set "pydir=%%~dpd"
if exist "!pydir!pythonw.exe" (
    start "" "!pydir!pythonw.exe" "!script!" %*
    exit /b 0
)

REM No pythonw next to this interpreter: run with a console window instead.
"!pyexe!" "!script!" %*
if not "!errorlevel!" == "0" (
    echo.
    echo MacBootsmith exited with error code: !errorlevel!
    echo.
    echo Press [enter] to exit...
    pause > nul
)
exit /b

:checklauncher <path>
for /f "USEBACKQ tokens=*" %%y in (`"%~1" -3 -c "import sys; print(sys.executable)" 2^> nul`) do (
    if not defined pyexe call :checkpy "%%y"
)
goto :EOF

:checkpy <path>
set "version="
for /f "USEBACKQ tokens=2* delims= " %%a in (`"%~1" -V 2^>^&1`) do set "version=%%a"
if not defined version goto :EOF
if "!version:~0,2!" == "3." set "pyexe=%~1"
goto :EOF
