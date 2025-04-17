# Event Scraper Setup and Usage Guide

This guide explains how to set up and use the Event Scraper for Non-Profit Digitalization Events.

## Quick Start (Easiest Method)

### On macOS/Linux:

Simply run:
```bash
./run-scraper.sh
```

This script will:
1. Check if a virtual environment exists, and create one if needed
2. Activate the virtual environment
3. Run the scraper
4. Deactivate the virtual environment when done

You can pass command line arguments to the scraper:
```bash
./run-scraper.sh --verbose --max-events 5
```

### On Windows:

Simply run:
```
run-scraper.bat
```

This script will:
1. Check if a virtual environment exists, and create one if needed
2. Activate the virtual environment
3. Run the scraper
4. Deactivate the virtual environment when done

You can pass command line arguments to the scraper:
```
run-scraper.bat --verbose --max-events 5
```

## Alternative Setup Method

### On macOS/Linux:

1. Run the setup script to create a virtual environment and install dependencies:
   ```bash
   ./setup.sh
   ```

2. The script will automatically activate the virtual environment for the current session.

3. Run the scraper:
   ```bash
   python event_scraper.py
   ```

### On Windows:

1. Run the setup script to create a virtual environment and install dependencies:
   ```
   setup.bat
   ```

2. The script will automatically activate the virtual environment for the current session.

3. Run the scraper:
   ```
   python scraper-directus-optimized.py
   ```

## Manual Setup (if the setup scripts don't work)

1. Create a virtual environment:
   ```bash
   python -m venv venv
   ```

2. Activate the virtual environment:
   - On macOS/Linux: `source venv/bin/activate`
   - On Windows: `venv\Scripts\activate.bat`

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Run the scraper:
   ```bash
   python scraper-directus-optimized.py
   ```

## Configuration

The scraper uses two configuration files:

1. `config/sources.json` - Contains the sources to scrape
2. `config/directus.json` - Contains Directus API configuration

These files will be created automatically with default values if they don't exist.

You can also set environment variables in a `.env` file:
```
DIRECTUS_API_URL=https://your-directus-api-url
DIRECTUS_API_TOKEN=your-api-token-here
DIRECTUS_COLLECTION=scraped_data
```

## Command Line Options

```
python event_scraper.py --help
```

Available options:
- `--config`, `-c`: Path to configuration file (default: config/sources.json)
- `--directus-config`, `-d`: Path to Directus configuration file (default: config/directus.json)
- `--output`, `-o`: Output directory for scraped data (default: data)
- `--max-events`, `-m`: Maximum events to scrape per source (-1 for all)
- `--verbose`, `-v`: Enable verbose logging
- `--no-directus`: Disable Directus database integration
- `--save-html`: Save HTML files to disk
- `--cache-dir`: Directory to store cache files (default: .cache)
- `--clear-cache`: Clear URL cache before running

## Next Time You Run the Scraper

Once the setup is complete, you only need to:

1. Activate the virtual environment:
   - On macOS/Linux: `source venv/bin/activate`
   - On Windows: `venv\Scripts\activate.bat`

2. Run the scraper:
   ```bash
   python event_scraper.py
   ```

## Troubleshooting

If you encounter any issues:

1. Make sure Python 3 is installed and in your PATH
2. Check that you have activated the virtual environment
3. Try running the setup script again
4. Check the logs in the `logs` directory
