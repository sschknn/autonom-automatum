@echo off
REM ===================================================================
REM  autonom-automatum - Starter fuer Windows
REM  Doppelklicken oder "start.bat" in der Kommandozeile aufrufen.
REM ===================================================================
setlocal
cd /d "%~dp0"

echo.
echo  ============================================================
echo    autonom-automatum
echo  ============================================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo  [FEHLER] Python wurde nicht gefunden.
    echo.
    echo  Installiere Python 3.10 oder neuer von python.org
    echo  und setze bei der Installation den Haken bei
    echo  "Add Python to PATH".
    echo.
    pause
    exit /b 1
)

REM Deutsche Umlaute erzwingen, sonst zeigt die Konsole "f?r"
set PYTHONIOENCODING=utf-8

REM set /p muss auf EINER Zeile stehen. Ein umbruch innerhalb der
REM Anfuehrungszeichen wuerde das schliessende " als Befehl ausfuehren.
set /p wahl="  [1] Grafische Oberflaeche   [2] Status   [3] Tests   [4] Beenden: "

if "%wahl%"=="1" (
    echo  Starte Oberflaeche...
    python -X utf8 trading_gui.py
    goto ende
)
if "%wahl%"=="2" (
    echo.
    python -X utf8 cli.py status
    echo.
    pause
    goto ende
)
if "%wahl%"=="3" (
    echo.
    python -X utf8 tests/test_kern.py
    echo.
    pause
    goto ende
)
if "%wahl%"=="4" goto ende

echo  Keine gueltige Auswahl. Erlaubt sind 1, 2, 3 oder 4.
REM ping statt timeout: timeout scheitert, wenn die Eingabe umgeleitet ist.
ping -n 3 127.0.0.1 >nul

:ende
endlocal