#!/bin/bash
# Setup script for Event Scraper
# This script creates a virtual environment, installs dependencies,
# and provides instructions for running the scraper

# Colors for better readability
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}Setting up environment for Event Scraper...${NC}"

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo -e "${YELLOW}Python 3 is not installed. Please install Python 3 and try again.${NC}"
    exit 1
fi

# Check if virtual environment already exists
if [ ! -d "venv" ]; then
    echo -e "${GREEN}Creating virtual environment...${NC}"
    python3 -m venv venv
    if [ $? -ne 0 ]; then
        echo -e "${YELLOW}Failed to create virtual environment. Please install venv package and try again.${NC}"
        echo "You can install it with: pip3 install virtualenv"
        exit 1
    fi
else
    echo -e "${GREEN}Virtual environment already exists.${NC}"
fi

# Activate virtual environment
echo -e "${GREEN}Activating virtual environment...${NC}"
source venv/bin/activate

# Install dependencies
echo -e "${GREEN}Installing dependencies...${NC}"
pip install -r requirements.txt

# Create .env file if it doesn't exist
if [ ! -f ".env" ]; then
    echo -e "${GREEN}Creating .env file for environment variables...${NC}"
    cat > .env << EOL
# Directus API configuration
DIRECTUS_API_URL=https://your-directus-api-url
DIRECTUS_API_TOKEN=your-api-token-here
DIRECTUS_COLLECTION=scraped_data
EOL
    echo -e "${YELLOW}Please edit the .env file with your actual API credentials.${NC}"
fi

# Create config directory if it doesn't exist
if [ ! -d "config" ]; then
    echo -e "${GREEN}Creating config directory...${NC}"
    mkdir -p config
fi

# Print instructions
echo -e "\n${GREEN}Setup complete!${NC}"
echo -e "\n${YELLOW}To run the scraper:${NC}"
echo -e "1. Activate the virtual environment (if not already activated):"
echo -e "   ${GREEN}source venv/bin/activate${NC}"
echo -e "2. Run the scraper:"
echo -e "   ${GREEN}python scraper-directus-optimized.py${NC}"
echo -e "\n${YELLOW}To deactivate the virtual environment when done:${NC}"
echo -e "   ${GREEN}deactivate${NC}"
echo -e "\n${YELLOW}Next time you want to run the scraper, you only need to:${NC}"
echo -e "   ${GREEN}source venv/bin/activate${NC}"
echo -e "   ${GREEN}python scraper-directus-optimized.py${NC}"

# Keep the virtual environment activated for the current session
echo -e "\n${GREEN}Virtual environment is now active for this terminal session.${NC}"
echo -e "${GREEN}You can now run the scraper with: python scraper-directus-optimized.py${NC}"
