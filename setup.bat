@echo off
:: Setup script for Event Scraper (Windows version)
:: This script creates a virtual environment, installs dependencies,
:: and provides instructions for running the scraper

echo Setting up environment for Event Scraper...

:: Check if Python 3 is installed
python --version 2>NUL
if %ERRORLEVEL% NEQ 0 (
    echo Python is not installed or not in PATH. Please install Python 3 and try again.
    exit /b 1
)

:: Check if virtual environment already exists
if not exist venv (
    echo Creating virtual environment...
    python -m venv venv
    if %ERRORLEVEL% NEQ 0 (
        echo Failed to create virtual environment. Please install venv package and try again.
        echo You can install it with: pip install virtualenv
        exit /b 1
    )
) else (
    echo Virtual environment already exists.
)

:: Activate virtual environment
echo Activating virtual environment...
call venv\Scripts\activate.bat

:: Install dependencies
echo Installing dependencies...
pip install -r requirements.txt

:: Create .env file if it doesn't exist
if not exist .env (
    echo Creating .env file for environment variables...
    (
        echo # Directus API configuration
        echo DIRECTUS_API_URL=https://your-directus-api-url
        echo DIRECTUS_API_TOKEN=your-api-token-here
        echo DIRECTUS_COLLECTION=scraped_data
    ) > .env
    echo Please edit the .env file with your actual API credentials.
)

:: Create config directory if it doesn't exist
if not exist config (
    echo Creating config directory...
    mkdir config
)

:: Print instructions
echo.
echo Setup complete!
echo.
echo To run the scraper:
echo 1. Activate the virtual environment (if not already activated):
echo    venv\Scripts\activate.bat
echo 2. Run the scraper:
echo    python scraper-directus-optimized.py
echo.
echo To deactivate the virtual environment when done:
echo    deactivate
echo.
echo Next time you want to run the scraper, you only need to:
echo    venv\Scripts\activate.bat
echo    python scraper-directus-optimized.py
echo.
echo Virtual environment is now active for this terminal session.
echo You can now run the scraper with: python scraper-directus-optimized.py
