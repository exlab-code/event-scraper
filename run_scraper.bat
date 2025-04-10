@echo off
:: Run script for Event Scraper (Windows version)
:: This script activates the virtual environment and runs the scraper

echo Running Event Scraper...

:: Check if virtual environment exists
if not exist venv (
    echo Virtual environment not found. Running setup script first...
    call setup.bat
) else (
    :: Activate virtual environment
    echo Activating virtual environment...
    call venv\Scripts\activate.bat
)

:: Run the scraper
echo Running the scraper...
python event_scraper.py %*

:: Deactivate virtual environment
call deactivate
echo Done! Virtual environment deactivated.
