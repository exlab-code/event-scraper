# Event Scraper & Management System

A comprehensive system for collecting, analyzing, moderating, and sharing events relevant to non-profit organizations.

## Overview

This project is a complete event management system that:

1. **Scrapes Events**: Collects event information from various websites
2. **Analyzes with AI**: Uses LLM to extract structured data and determine event relevance
3. **Provides Moderation**: Web interface for reviewing and approving events
4. **Syncs to Calendar**: Synchronizes approved events with a Nextcloud calendar
5. **Displays Events**: Website for showcasing approved events

## Documentation

Detailed documentation for each component of the system is available in the `docs` directory:

- [Installation Guide](docs/installation.md) - Complete guide to setting up and using the system
- [Scraper Documentation](docs/scraper.md) - Details on the event scraper component
- [Analyzer Documentation](docs/analyzer.md) - Information about the LLM analysis component
- [Sync Documentation](docs/sync.md) - Details on the Directus-Nextcloud sync
- [Moderation Interface](docs/moderation.md) - Guide to the moderation web interface
- [Website Documentation](docs/website.md) - Information about the website component
- [CSS Customization](docs/customization.md) - How to customize the website appearance

## System Requirements

- Python 3.6+
- [Directus](https://directus.io/) instance for data storage
- [Nextcloud](https://nextcloud.com/) with Calendar app for event sharing
- OpenAI API key for LLM analysis
- Web server for hosting the moderation interface (optional)

## Quick Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/yourusername/Event-Scraper.git
   cd Event-Scraper
   ```

2. **Install dependencies**:
   ```bash
   # Create a virtual environment (recommended)
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate

   # Install required packages
   pip install -r requirements.txt
   ```

3. **Create a `.env` file** with your credentials (see `.env.example` for template)

4. **Run the system components**:
   ```bash
   # Run the scraper
   python event_scraper.py
   
   # Run the LLM analysis
   python event_analyzer.py
   
   # Start the moderation interface
   cd event-moderation-interface && python serve.py
   
   # Sync to Nextcloud
   python calendar_sync.py
   ```

## Command Line Arguments

### Master Script (run_system.sh)

The master script provides a convenient way to run all components:

```bash
./run_system.sh {command}
```

Available commands:
- `scrape` - Run the scraper once
- `analyze` - Run the LLM analysis once
- `sync` - Start the sync service (continuous)
- `sync-once` - Run the sync service once and exit
- `clean` - Clean the Nextcloud calendar
- `all` - Run scraper and analysis, then start sync service in background
- `stop` - Stop all background services
- `status` - Check the status of all services
- `setup-cron` - Set up cron jobs for automation
- `remove-cron` - Remove cron jobs

### Scraper (event_scraper.py)

```bash
python event_scraper.py [options]
```

Options:
- `--config`, `-c` - Path to configuration file (default: config/sources.json)
- `--directus-config`, `-d` - Path to Directus configuration file (default: config/directus.json)
- `--output`, `-o` - Output directory for scraped data (default: data)
- `--max-events`, `-m` - Maximum events to scrape per source (-1 for all)
- `--verbose`, `-v` - Enable verbose logging
- `--no-directus` - Disable Directus database integration
- `--save-html` - Save HTML files to disk
- `--cache-dir` - Directory to store cache files (default: .cache)
- `--clear-cache` - Clear URL cache before running

### LLM Analysis (event_analyzer.py)

```bash
python event_analyzer.py [options]
```

Options:
- `--limit`, `-l` - Maximum number of items to process (default: 10)
- `--batch`, `-b` - Batch size for processing (default: 3)
- `--flag-mismatches`, `-f` - Flag events where LLM determination doesn't match human feedback
- `--only-flag`, `-o` - Only flag mismatches without processing new events
- `--log-file` - Path to log file for LLM extraction results (default: llm_extraction.log)

### Sync Events (calendar_sync.py)

```bash
python calendar_sync.py [options]
```

Options:
- `--clean` - Clean Nextcloud calendar by removing all non-Directus events
- `--sync-once` - Run sync once and exit (this is now the default behavior)
- `--schedule` - Enable hourly scheduling (disabled by default)

### Moderation Interface Server (event-moderation-interface/serve.py)

```bash
python event-moderation-interface/serve.py
```

The server runs on port 9000 by default and will automatically try the next available port if 9000 is in use.

### CORS Proxy (event-moderation-interface/proxy.py)

```bash
python event-moderation-interface/proxy.py
```

The proxy runs on port 9090 by default and will automatically try the next available port if 9090 is in use.

## Project Structure

- `event_scraper.py` - Main scraper script (formerly scraper-directus-optimized.py)
- `event_analyzer.py` - LLM analysis script (formerly data-analysis-save-gpt-v2.py)
- `calendar_sync.py` - Nextcloud calendar sync script (formerly sync-events.py)
- `run_system.sh` - Master script to run all components (formerly run-event-system.sh)
- `run_scraper.sh` / `run_scraper.bat` - Helper scripts to run the scraper
- `config/` - Configuration files for scrapers and sources
- `docs/` - Comprehensive documentation for all components
- `event-moderation-interface/` - Web interface for event moderation
- `website/` - Svelte-based website for displaying events
- `archives/` - Archive of historical data
- `deprecated/` - Deprecated code and scripts
- `scripts/` - Additional utility scripts

## Recent Updates (April 2025)

### Migrated from Categories to Tags-Based System

The event categorization system has been completely redesigned:
- Removed the legacy category-based system in favor of a more flexible tag-based approach
- Updated the LLM prompt to generate normalized, consistent tags
- Implemented tag grouping (topic, format, audience, cost)
- Added tag frequency filtering to show only commonly used tags
- Improved the UI with consistent styling for tags and time filters
- Enhanced the event cards to display end times alongside start times
- Fixed currency display to use proper Euro symbol (€)

These changes provide a more intuitive and flexible way to organize and filter events.

### Improved Date Extraction in LLM Analysis

The date extraction in the LLM analysis script has been improved:
- Removed regex-based date extraction to rely solely on the LLM's extraction capabilities
- Fixed registration link extraction to only match valid URLs
- Added comprehensive logging for better debugging
- Improved override logic to prioritize LLM-extracted dates

### Modified Sync Script Behavior

The calendar_sync.py script behavior has been changed:
- Now runs once and exits by default (no continuous scheduling)
- Added `--schedule` flag to explicitly enable hourly scheduling if needed
- Updated documentation in docs/sync.md with new options and examples
- Added instructions for stopping the sync service if it's running in the background

See [Sync Documentation](docs/sync.md) for more details on these changes.

### Project Reorganization

The project has been reorganized for better clarity and maintainability:
- Renamed scripts to follow consistent naming conventions
- Consolidated documentation into a central `docs` directory
- Archived obsolete files and deprecated code
- Updated file references in documentation and scripts

## License

[MIT License](LICENSE)
