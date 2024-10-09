@echo off
echo Starting application...

REM Activate the virtual environment (adjust the path if necessary)
echo Activating virtual environment...
call .venv\Scripts\activate.bat
if %ERRORLEVEL% neq 0 (
    echo Failed to activate virtual environment. Make sure it exists and the path is correct.
    pause
    exit /b 1
)

REM Set environment variables (if needed)
echo Setting environment variables...
set PROFILE=true

REM Start the FastAPI application
echo Starting FastAPI application...
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
if %ERRORLEVEL% neq 0 (
    echo Failed to start the application. Check if all dependencies are installed and the main.py file exists.
    pause
    exit /b 1
)

REM Deactivate the virtual environment
echo Deactivating virtual environment...
call deactivate

echo Application stopped.
pause