#!/bin/bash
# Script to install requirements for the Event Scraper on macOS
# Handles externally managed environments (PEP 668)

echo "Installing requirements for Event Scraper on macOS..."

# Check if brew is installed
if ! command -v brew &> /dev/null; then
    echo "Homebrew is not installed. It's recommended for managing packages on macOS."
    echo "Visit https://brew.sh to install Homebrew."
    echo "Alternatively, we'll try to install with pip --user."
    USE_BREW=false
else
    USE_BREW=true
fi

# Function to install with pip --user
install_with_pip_user() {
    echo "Installing packages with pip --user..."
    python3 -m pip install --user requests beautifulsoup4 python-dotenv
    
    if [ $? -eq 0 ]; then
        echo "Installation complete!"
        echo "You can now run the scraper with: python3 event_scraper.py"
    else
        echo "Installation with pip --user failed."
        echo "Please use the virtual environment approach instead:"
        echo "./setup.sh"
    fi
}

# Function to install with pipx
install_with_pipx() {
    echo "Installing packages with pipx..."
    
    # Check if pipx is installed
    if ! command -v pipx &> /dev/null; then
        echo "Installing pipx with Homebrew..."
        brew install pipx
        pipx ensurepath
    fi
    
    # Create a venv for the scraper
    echo "Creating a managed environment with pipx..."
    pipx install requests beautifulsoup4 python-dotenv --include-deps
    
    if [ $? -eq 0 ]; then
        echo "Installation complete!"
        echo "You can now run the scraper with: python3 event_scraper.py"
    else
        echo "Installation with pipx failed."
        echo "Please use the virtual environment approach instead:"
        echo "./setup.sh"
    fi
}

# Try to install with Homebrew first if available
if [ "$USE_BREW" = true ]; then
    echo "Attempting to install packages with Homebrew..."
    brew install python-requests
    
    # Check if we need to install other packages
    echo "Some packages may not be available via Homebrew."
    echo "Installing remaining packages with pip --user..."
    python3 -m pip install --user beautifulsoup4 python-dotenv
    
    if [ $? -eq 0 ]; then
        echo "Installation complete!"
        echo "You can now run the scraper with: python3 event_scraper.py"
    else
        echo "Installation with pip --user failed after Homebrew."
        echo "Trying alternative approach..."
        install_with_pip_user
    fi
else
    # If Homebrew is not available, try pip --user
    install_with_pip_user
fi

echo ""
echo "NOTE: If you encounter any issues, the most reliable method is to use a virtual environment:"
echo "1. Run: ./setup.sh"
echo "2. This will create a virtual environment and install all dependencies"
echo "3. Then you can run: ./run-scraper.sh"
