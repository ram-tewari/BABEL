@echo off
REM BABEL FastAPI Server Startup Script (Windows)

echo ========================================
echo   BABEL API Server
echo ========================================
echo.

REM Check if virtual environment exists
if not exist ".venv\Scripts\activate.bat" (
    echo ERROR: Virtual environment not found!
    echo Please run: python -m venv .venv
    echo Then: .venv\Scripts\activate
    echo Then: pip install -r requirements.txt
    pause
    exit /b 1
)

REM Activate virtual environment
echo Activating virtual environment...
call .venv\Scripts\activate.bat

REM Check if FastAPI is installed
python -c "import fastapi" 2>nul
if errorlevel 1 (
    echo.
    echo ERROR: FastAPI not installed!
    echo Installing dependencies...
    pip install fastapi uvicorn[standard] python-multipart
)

REM Start the server
echo.
echo Starting BABEL API Server...
echo.
echo API Documentation: http://localhost:8000/docs
echo Health Check: http://localhost:8000/health
echo.
echo Press Ctrl+C to stop the server
echo.

python babel_server.py

pause
