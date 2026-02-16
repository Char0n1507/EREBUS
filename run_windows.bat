@echo off
setlocal enabledelayedexpansion
TITLE Argus Launcher
CLS

ECHO ====================================================
ECHO      Argus: AI-Powered Dark Web OSINT Tool
ECHO ====================================================
ECHO.

:: Check for Python
python --version >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    ECHO [ERROR] Python is not installed or not in PATH.
    PAUSE
    EXIT /B
)

:: Check for Tor Port (9050 vs 9150)
netstat -an | find "9150" >nul
IF %ERRORLEVEL% EQU 0 (
    ECHO [INFO] Detected Tor on port 9150 (Tor Browser Mode).
    SET TOR_PROXY_URL=socks5h://127.0.0.1:9150
    GOTO :CHECK_OLLAMA
)

netstat -an | find "9050" >nul
IF %ERRORLEVEL% EQU 0 (
    ECHO [INFO] Detected Tor on port 9050 (System Mode).
    SET TOR_PROXY_URL=socks5h://127.0.0.1:9050
    GOTO :CHECK_OLLAMA
)

ECHO [WARNING] Tor does not seem to be running on port 9050 or 9150.
ECHO           Please ensure Tor Browser is open or Tor service is running.
ECHO.

:CHECK_OLLAMA
:: Check for Ollama
curl -s http://localhost:11434/api/tags >nul 2>&1
IF %ERRORLEVEL% NEQ 0 (
    ECHO [WARNING] Ollama does not seem to be running on port 11434.
    ECHO           AI features will not work. Run 'ollama serve' in another terminal.
    ECHO.
) ELSE (
    ECHO [INFO] Ollama is active.
)

ECHO.
ECHO Starting Argus Dashboard...
python -m streamlit run app.py

PAUSE
