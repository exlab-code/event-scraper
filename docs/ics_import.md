# ICS Calendar Import

This document explains how to use the ICS Calendar Import script to add events from HumHub and other ICS calendars to your event system.

## Overview

The `ics_import.py` script allows you to import events from ICS calendar files into your Directus database. These events will then be processed by the existing `event_analyzer.py` script, just like events from other sources.

## Configuration

Events are imported from sources defined in `config/ics_sources.json`. The file has the following structure:

```json
{
  "sources": [
    {
      "name": "HumHub - Civic Data Cafe",
      "url": "https://community.civic-data.de/ical/humhub-event-3916e1fa-d9ab-44cc-8090-31179a4d/base.ics",
      "enabled": true
    }
  ]
}
```

Each source has the following properties:

- `name`: A descriptive name for the source
- `url`: The URL of the ICS calendar file
- `enabled`: Whether the source is enabled (true/false)

## Adding New Sources

To add a new ICS calendar source:

1. Open `config/ics_sources.json` in a text editor
2. Add a new entry to the `sources` array:

```json
{
  "sources": [
    {
      "name": "HumHub - Civic Data Cafe",
      "url": "https://community.civic-data.de/ical/humhub-event-3916e1fa-d9ab-44cc-8090-31179a4d/base.ics",
      "enabled": true
    },
    {
      "name": "New Calendar",
      "url": "https://example.com/calendar.ics",
      "enabled": true
    }
  ]
}
```

## Requirements

The script requires the `icalendar` package, which is included in the `requirements.txt` file. If you've already set up the main event scraper, you can install it with:

```bash
pip install -r requirements.txt
```

## Usage

To run the script:

```bash
python ics_import.py [options]
```

Or on Unix-like systems:

```bash
./ics_import.py [options]
```

### Command Line Options

```
python ics_import.py --help
```

Available options:
- `--config`, `-c`: Path to configuration file (default: config/ics_sources.json)
- `--verbose`, `-v`: Enable verbose output
- `--dry-run`, `-d`: Parse events but don't save to database
- `--source`, `-s`: Process only the specified source by name
- `--file`, `-f`: Import events from a local ICS file instead of using the config
- `--source-name`, `-n`: Custom source name for imported events (used with --file)
- `--future-only`, `-F`: Only import future events (default: True)
- `--include-past`: Include past events in the import

### Examples

```bash
# Run with default settings
python ics_import.py

# Run with verbose output
python ics_import.py --verbose

# Test without saving to database
python ics_import.py --dry-run

# Process only a specific source
python ics_import.py --source "HumHub - Civic Data Cafe"

# Use a different configuration file
python ics_import.py --config custom_sources.json

# Import events from a local ICS file
python ics_import.py --file calendar.ics

# Import events from a local ICS file with a custom source name
python ics_import.py --file calendar.ics --source-name "HumHub Calendar"

# Import events from a local ICS file without saving to database
python ics_import.py --file calendar.ics --dry-run

# Import all events, including past events
python ics_import.py --include-past

# Import only future events (this is the default)
python ics_import.py --future-only
```

The script will:

1. Load the configuration from the specified file
2. Download and parse each enabled ICS source
3. Add events to your Directus database as unprocessed events (unless in dry-run mode)
4. Print a summary of the results

## Integration with Event Analyzer

After running the ICS import script, you can run the event analyzer to process the imported events:

```bash
python event_analyzer.py
```

## Automation

You can automate the import process by adding the script to your cron jobs or scheduled tasks. For example, to run the import daily at 6 AM:

```bash
0 6 * * * cd /path/to/your/project && python ics_import.py && python event_analyzer.py
```

## Enhanced Event Data Extraction

The script now extracts and stores comprehensive event data from ICS files:

- **Complete Event Information**: All properties from the ICS file are preserved
- **Structured Data Format**: Date/time information is properly formatted
- **Detailed Debugging**: Verbose output shows all extracted fields

### Extracted Fields

The following fields are extracted and stored for each event:

- **Basic Information**:
  - Title (summary)
  - Description
  - Location
  - URL

- **Date/Time Information**:
  - Start date/time (dtstart)
  - End date/time (dtend)
  - Creation date (created)
  - Last modified date (last-modified)

- **Identification**:
  - Unique identifier (uid)
  - Source name

- **All Properties**:
  - All other properties from the ICS file are preserved in the `ics_data` field

### Viewing Extracted Data

To see all the data that's being extracted, use the `--verbose` and `--dry-run` flags:

```bash
python ics_import.py --file calendar.ics --verbose --dry-run
```

This will show all the properties extracted from each event without saving to the database.

## Using Local ICS Files

If the ICS calendar requires authentication or is not directly accessible via URL, you can:

1. Download the ICS file manually (e.g., from the HumHub calendar export)
2. Save it to your local filesystem
3. Use the `--file` option to import events from the local file:

```bash
python ics_import.py --file path/to/calendar.ics
```

This approach is useful for:
- Calendars that require authentication (like HumHub)
- Private calendars that are not publicly accessible
- Testing with sample ICS files
- Offline operation when you don't have access to the original calendar

### Custom Source Names

When importing from a local file, by default the script uses the filename as the source name. This can result in source names like "calendar.ics" in your database, which isn't very descriptive.

To specify a more meaningful source name, use the `--source-name` option:

```bash
python ics_import.py --file calendar.ics --source-name "HumHub - Civic Data Lab"
```

This will:
- Import events from the local file
- Set the source name to "HumHub - Civic Data Lab" for all imported events
- Make it easier to identify the origin of events in the database and moderation interface

If you don't specify a source name, the script will:
- Use the filename as the source name
- Display a message suggesting to use the `--source-name` option

## Future Events Filter

By default, the script only imports events that are in the future (events with a start date/time that is later than the current date/time). This helps keep your database focused on upcoming events that are still relevant.

### How It Works

- The script checks the start date/time of each event in the ICS file
- If the start date/time is in the past, the event is skipped
- The script counts and reports the number of past events that were skipped

### Including Past Events

If you need to import past events (for archival purposes or historical data), you can use the `--include-past` option:

```bash
# Import all events, including past ones
python ics_import.py --include-past

# Import all events from a specific source
python ics_import.py --source "HumHub - Civic Data Cafe" --include-past

# Import all events from a local file
python ics_import.py --file calendar.ics --include-past
```

### Benefits of Future-Only Filtering

- Reduces database clutter by focusing on relevant upcoming events
- Improves performance by processing fewer events
- Saves resources for the event analyzer
- Keeps the moderation interface focused on current events

## Troubleshooting

If you encounter any issues:

1. Check that your `.env` file contains the correct Directus API URL and token
2. Verify that the ICS URL is accessible and returns a valid ICS file
3. For authentication issues, try using a local ICS file instead
4. Check the console output for error messages
