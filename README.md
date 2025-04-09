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

Detailed documentation for each component of the system:

- [Quick Start Guide](HOWTO.md) - Complete guide to setting up and using the system
- [Sync Events Documentation](sync-events-README.md) - Details on the Directus-Nextcloud sync
- [Event Moderation Interface](event-moderation-interface/README.md) - Guide to the moderation web interface
- [Website CSS Customization](website/public/custom-css-readme.md) - How to customize the website appearance

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
   python scraper-directus-optimized.py
   
   # Run the LLM analysis
   python data-analysis-save-gpt-v2.py
   
   # Start the moderation interface
   cd event-moderation-interface && python serve.py
   
   # Sync to Nextcloud
   python sync-events.py
   ```

## Project Structure

- `scraper-directus-optimized.py` - Main scraper script
- `data-analysis-save-gpt-v2.py` - LLM analysis script
- `sync-events.py` - Nextcloud calendar sync script
- `config/` - Configuration files for scrapers and sources
- `event-moderation-interface/` - Web interface for event moderation
- `website/` - Svelte-based website for displaying events
- `run-event-system.sh` - Helper script to run all components

## License

[MIT License](LICENSE)
