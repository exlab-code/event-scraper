#!/bin/bash
# Script to force install requirements globally on macOS
# WARNING: This approach can potentially break your system Python installation
# Use at your own risk

echo "WARNING: This script will force install packages globally using --break-system-packages"
echo "This approach is not recommended by Python and could potentially break your system Python installation"
echo "A safer approach is to use a virtual environment (./setup.sh) or install with --user flag (./install-global.sh)"
echo ""
read -p "Do you want to continue? (y/n) " -n 1 -r
echo ""

if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Installation aborted."
    exit 1
fi

echo "Force installing requirements globally on macOS..."

# Check if pip3 is installed
if ! command -v pip3 &> /dev/null; then
    echo "Error: pip3 is not installed. Please install pip3 first."
    echo "You can install it with: brew install python3"
    exit 1
fi

# Install requirements globally with --break-system-packages flag
echo "Installing required packages globally..."
pip3 install --break-system-packages requests beautifulsoup4 python-dotenv

if [ $? -eq 0 ]; then
    echo "Installation complete! You can now run the scraper directly with:"
    echo "python3 scraper-directus-optimized.py"
else
    echo "Installation failed. Please try the safer approaches:"
    echo "1. Use a virtual environment: ./setup.sh"
    echo "2. Install with --user flag: ./install-global.sh"
fi
