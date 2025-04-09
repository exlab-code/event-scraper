# Directus and Nextcloud Calendar Two-Way Sync

This script provides two-way synchronization between a Directus database and a Nextcloud calendar. It's designed to run as a background service, periodically syncing events between the two systems.

> **Important Note**: This script has been updated to use environment variables from a `.env` file instead of hardcoded credentials or JSON configuration files. This makes it safer to publish and easier to configure.

## Features

- Two-way sync between Directus and Nextcloud
- Only approved events from Directus are displayed in Nextcloud
- Events created in Nextcloud are added to Directus (as unapproved by default)
- Automatic removal of events from Nextcloud when they are no longer approved in Directus
- Automatic creation of calendar if it doesn't exist
- Detailed event information including description, organizer, cost, category, and website
- Deduplication to avoid creating duplicate events
- Hourly sync schedule
- Comprehensive logging

## Requirements

- Python 3.6+
- Directus API access
- Nextcloud account with CalDAV access
- Required Python packages (see `requirements.txt`)

## Installation

1. Ensure you have all required Python packages installed:

```bash
pip install -r requirements.txt
```

2. Configure the script using one of the following methods:

### Method 1: Environment Variables

Create a `.env` file in the project root with the following variables:

```
# Directus Configuration
DIRECTUS_API_URL=https://your-directus-api-url
DIRECTUS_API_TOKEN=your-api-token-here

# Nextcloud Configuration
NEXTCLOUD_URL=https://your-nextcloud-instance/remote.php/dav/calendars/username/
NEXTCLOUD_USERNAME=your-username
NEXTCLOUD_PASSWORD=your-app-password
NEXTCLOUD_CALENDAR_NAME=nonprofit-events
```

### Method 2: Configuration Files

Create the following configuration files:

**config/directus.json**:
```json
{
  "url": "https://your-directus-api-url",
  "token": "your-api-token-here"
}
```

**config/nextcloud.json**:
```json
{
  "url": "https://your-nextcloud-instance/remote.php/dav/calendars/username/",
  "username": "your-username",
  "password": "your-app-password",
  "calendar_name": "nonprofit-events"
}
```

## Usage

Run the script:

```bash
python sync-events.py [options]
```

### Command-line Options

- `--clean`: Clean the Nextcloud calendar by removing all events that don't exist in Directus
- `--sync-once`: Run the sync once and exit (this is now the default behavior)
- `--schedule`: Enable hourly scheduling (disabled by default)

### Examples

**Standard usage (run once and exit):**
```bash
python sync-events.py
```

**Enable continuous hourly sync:**
```bash
python sync-events.py --schedule
```

**Clean the calendar and exit:**
```bash
python sync-events.py --clean
```

**Clean the calendar and enable continuous sync:**
```bash
python sync-events.py --clean --schedule
```

The script will:
1. Connect to Nextcloud and fetch all events
2. Add any new events from Nextcloud to Directus (as unapproved by default)
3. Connect to Directus and fetch all approved events
4. Add approved events to Nextcloud and remove any that are no longer approved
5. Exit after completion (unless `--schedule` is specified, in which case it will continue running in the background, syncing hourly)

To run the script as a service, you can use systemd (Linux), launchd (macOS), or Task Scheduler (Windows).

## Logging

Logs are written to `logs/sync.log` and also output to the console. The log includes information about:
- Script startup and configuration
- Events found and synced
- Errors encountered during sync
- Calendar creation and event addition

## Security Notes

- Never commit your actual configuration files or `.env` file to version control
- Use an app-specific password for Nextcloud rather than your main account password
- Consider using a dedicated API token for Directus with limited permissions

## Limitations

- Events created in Nextcloud are added to Directus as unapproved by default
- Only basic event information is synced (title, dates, description, website, location)
- Events deleted in Nextcloud will not be automatically deleted in Directus
- The script assumes events have at minimum a title and start_date field
- Updates to events in Nextcloud won't update existing events in Directus (to avoid overwriting moderated content)

## Recent Changes

The script has been updated with the following improvements:

### April 2025 Updates
- **Changed default behavior**: The script now runs once and exits by default
- **Added `--schedule` flag**: To enable the previous behavior of continuous hourly syncing
- **Improved documentation**: Updated README with new command-line options and examples

### Security Enhancements
- Removed hardcoded credentials from the script
- Added support for loading credentials from a `.env` file
- Created example configuration files for reference
- Updated the `.gitignore` file to prevent accidental commits of sensitive data

### New Features
- Added command-line arguments for better control:
  - `--clean`: Removes all events from Nextcloud that don't exist in Directus
  - `--sync-once`: Runs the sync once and exits (now the default behavior)
  - `--schedule`: Enables hourly scheduling (the previous default behavior)
- Implemented graceful shutdown with proper error handling
- Added detailed logging for better troubleshooting

### Two-Way Sync Improvements
- Fixed bug in iCalendar event parsing
- Enhanced event deduplication logic
- Improved handling of events that no longer exist in Directus

## Stopping the Sync Service

If you have the sync service running in the background or as a cron job, you can stop it using the following methods:

### If Running as a Background Process

If you started the sync script using `./run-event-system.sh sync` or `./run-event-system.sh all`, you can stop it with:

```bash
./run-event-system.sh stop
```

### If Running as a Cron Job

If you set up cron jobs using `./run-event-system.sh setup-cron`, you can remove them with:

```bash
./run-event-system.sh remove-cron
```

### Checking What's Running

To check if the sync script is running as a background process:

```bash
./run-event-system.sh status
```

To check if it's running as a cron job:

```bash
crontab -l | grep "sync-events.py"
```
