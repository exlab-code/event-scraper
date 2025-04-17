#!/bin/bash
# Run script for Event Scraper
# This script activates the virtual environment and runs the scraper

# Colors for better readability
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo -e "${YELLOW}Virtual environment not found. Running setup script first...${NC}"
    ./setup.sh
else
    # Activate virtual environment
    echo -e "${GREEN}Activating virtual environment...${NC}"
    source venv/bin/activate
fi

# Run the scraper
echo -e "${GREEN}Running the scraper...${NC}"
python event_scraper.py "$@"

# Deactivate virtual environment
deactivate
echo -e "${GREEN}Done! Virtual environment deactivated.${NC}"
