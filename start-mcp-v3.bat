@echo off
REM MI Hands v3.0 MCP Server - Start Script
REM Usage: start-mcp-v3.bat

echo Starting MI Hands v3.0 MCP Server...
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found. Please install Python 3.10+
    pause
    exit /b 1
)

REM Check MIMO_API_KEY
if "%MIMO_API_KEY%"=="" (
    echo [WARNING] MIMO_API_KEY not set. AI features will be limited.
    echo.
)

REM Start MCP Server
echo Starting MCP Server...
python -m src.v3.mcp.plugin

pause
