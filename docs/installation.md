# Quick Start Guide: Non-Profit Event Scraper & Management System

This guide provides a quick overview of how to set up and use the complete Non-Profit Event Scraper and Management System.

## What This Project Does

This project is a comprehensive system for collecting, analyzing, moderating, and sharing events relevant to non-profit organizations:

1. **Scraper**: Collects event information from various websites
2. **LLM Analysis**: Uses AI to extract structured data and determine event relevance
3. **Moderation Interface**: Web interface for reviewing and approving events
4. **Calendar Sync**: Synchronizes approved events with a Nextcloud calendar

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

3. **Create a `.env` file** with your credentials:
   ```
   # Directus Configuration
   DIRECTUS_API_URL=https://your-directus-api-url
   DIRECTUS_API_TOKEN=your-api-token-here
   
   # Nextcloud Configuration
   NEXTCLOUD_URL=https://your-nextcloud-instance/remote.php/dav/calendars/username/
   NEXTCLOUD_USERNAME=your-username
   NEXTCLOUD_PASSWORD=your-app-password
   NEXTCLOUD_CALENDAR_NAME=your-calendar-name
   
   # OpenAI API Configuration
   OPENAI_API_KEY=your-openai-api-key
   ```

## Complete Workflow

### 1. Scraping Events

The scraper collects event information from configured websites:

```bash
python event_scraper.py
```

- Events are scraped based on configurations in the `config/` directory
- Each source has its own configuration file (e.g., `config/bitkom_akademie_config.json`)
- Scraped events are saved to the Directus database

To add a new source:
1. Create a new configuration file in the `config/` directory
2. Add the source to `config/sources.json`
3. Run the scraper

### 2. LLM Analysis

After scraping, you can run the LLM analysis to enhance event data:

```bash
python event_analyzer.py
```

This script:
- Processes events that haven't been analyzed yet
- Uses OpenAI's API to extract structured data
- Determines event relevance for non-profit organizations
- Updates events in the Directus database with enhanced information

### 3. Event Moderation

The moderation interface allows you to review and approve events. It runs on the server and is accessible through a web browser.

In the moderation interface, you can:
- View all scraped events
- Edit event details
- Approve or reject events
- Filter events by source, category, or approval status

### 4. Calendar Synchronization

Finally, sync approved events to your Nextcloud calendar:

```bash
python calendar_sync.py
```

Options:
- `--clean`: Remove all events from Nextcloud that don't exist in Directus
- `--sync-once`: Run once and exit (instead of running continuously)

## Common Use Cases

### Initial Setup

For a fresh installation:

1. Set up your `.env` file with all credentials
2. Run the scraper: `python event_scraper.py`
3. Run the LLM analysis: `python event_analyzer.py`
4. Review and approve events in Directus admin: https://calapi.buerofalk.de/admin
5. Sync to Nextcloud: `python calendar_sync.py --sync-once`

### Regular Maintenance

For ongoing operation:

1. Schedule the scraper to run daily: `cron job or task scheduler`
2. Schedule the LLM analysis to run after scraping
3. Moderate events regularly through the web interface
4. Keep the sync script running continuously: `python calendar_sync.py`

### Calendar Cleanup

If your Nextcloud calendar has unwanted events:

```bash
python calendar_sync.py --clean --sync-once
```

## Troubleshooting

### Scraper Issues
- Check source configurations in `config/` directory
- Verify Directus API connection
- Look for errors in the console output

### LLM Analysis Issues
- Verify your OpenAI API key is correct
- Check API rate limits
- Look for errors in the console output

### Moderation Interface Issues
- Ensure `config-secrets.js` is properly configured
- Check browser console for JavaScript errors
- Verify Directus API connection

### Sync Issues
- Check the logs in `logs/sync.log`
- Verify Nextcloud and Directus credentials
- Ensure events have required fields (title, start date)

## Automating the Project

To make the constant running of this project easier, you can use several approaches:

### 1. Using Systemd Services (Linux)

Create systemd service files for each component to run them as background services that start automatically on boot:

**Example for calendar_sync.py:**

Create a file at `/etc/systemd/system/event-sync.service`:
```
[Unit]
Description=Event Sync Service
After=network.target

[Service]
Type=simple
User=yourusername
WorkingDirectory=/path/to/Event-Scraper
ExecStart=/path/to/Event-Scraper/venv/bin/python /path/to/Event-Scraper/calendar_sync.py
Restart=on-failure
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
```

Then enable and start the service:
```bash
sudo systemctl enable event-sync.service
sudo systemctl start event-sync.service
```

Create similar service files for the scraper, LLM analysis, and moderation interface.

### 2. Using Docker

Containerize the application for easier deployment and management:

1. Create a `Dockerfile` for each component
2. Use Docker Compose to orchestrate all services
3. Set up volume mounts for persistent data

Example `docker-compose.yml`:
```yaml
version: '3'
services:
  scraper:
    build: 
      context: .
      dockerfile: Dockerfile.scraper
    volumes:
      - ./.env:/app/.env
    restart: unless-stopped
    command: python event_scraper.py
  
  analysis:
    build:
      context: .
      dockerfile: Dockerfile.analysis
    volumes:
      - ./.env:/app/.env
    restart: unless-stopped
    command: python event_analyzer.py
  
  sync:
    build:
      context: .
      dockerfile: Dockerfile.sync
    volumes:
      - ./.env:/app/.env
      - ./logs:/app/logs
    restart: unless-stopped
    command: python calendar_sync.py
  
  moderation:
    build:
```

**Note**: The custom moderation interface has been removed. Event moderation is now handled through the Directus admin interface at https://calapi.buerofalk.de/admin.

### 3. Using Process Managers

Process managers like PM2 (for Node.js) or Supervisor can help manage and monitor your Python scripts:

**Using Supervisor:**

Install Supervisor:
```bash
sudo apt-get install supervisor
```

Create a configuration file at `/etc/supervisor/conf.d/event-scraper.conf`:
```
[program:event-sync]
command=/path/to/Event-Scraper/venv/bin/python /path/to/Event-Scraper/calendar_sync.py
directory=/path/to/Event-Scraper
user=yourusername
autostart=true
autorestart=true
stderr_logfile=/var/log/event-sync.err.log
stdout_logfile=/var/log/event-sync.out.log
```

Then update and restart Supervisor:
```bash
sudo supervisorctl reread
sudo supervisorctl update
```

### 4. Creating a Master Script

Create a shell script that manages all components:

```bash
#!/bin/bash
# run-event-system.sh

# Set up environment
cd /path/to/Event-Scraper
source venv/bin/activate

# Function to run a component in the background
run_component() {
    echo "Starting $1..."
    $2 > logs/$1.log 2>&1 &
    echo $! > logs/$1.pid
    echo "$1 started with PID $(cat logs/$1.pid)"
}

# Create logs directory if it doesn't exist
mkdir -p logs

# Start components
case "$1" in
    scrape)
        python event_scraper.py
        ;;
    analyze)
        python event_analyzer.py
        ;;
    sync)
        python calendar_sync.py
        ;;
    all)
        # Run scraper and analysis once
        echo "Running scraper..."
        python event_scraper.py > logs/scraper.log 2>&1
        echo "Running LLM analysis..."
        python event_analyzer.py > logs/analysis.log 2>&1
        
        # Start sync service in the background
        run_component "sync" "python calendar_sync.py"
        echo "All components executed. Scraper and analysis completed. Sync service running in background."
        echo "Use './run-event-system.sh stop' to stop all components."
        ;;
    stop)
        echo "Stopping all components..."
        for pid_file in logs/*.pid; do
            if [ -f "$pid_file" ]; then
                pid=$(cat "$pid_file")
                component=$(basename "$pid_file" .pid)
                echo "Stopping $component (PID: $pid)..."
                kill $pid
                rm "$pid_file"
            fi
        done
        echo "All components stopped."
        ;;
    status)
        echo "Component status:"
        for pid_file in logs/*.pid; do
            if [ -f "$pid_file" ]; then
                pid=$(cat "$pid_file")
                component=$(basename "$pid_file" .pid)
                if ps -p $pid > /dev/null; then
                    echo "$component: Running (PID: $pid)"
                else
                    echo "$component: Not running (stale PID file)"
                    rm "$pid_file"
                fi
            fi
        done
        ;;
    *)
        echo "Usage: $0 {scrape|analyze|sync|all|stop|status}"
        exit 1
        ;;
esac

exit 0
```

Make it executable and use it:
```bash
chmod +x run-event-system.sh
./run-event-system.sh all    # Run scraper and analysis, then start sync service in background
./run-event-system.sh status # Check status of running components
./run-event-system.sh stop   # Stop all running components
```

### 5. Scheduling with Cron

For components that don't need to run continuously, use cron jobs:

```bash
# Edit crontab
crontab -e

# Add these lines:
# Run scraper daily at 1 AM
0 1 * * * cd /path/to/Event-Scraper && /path/to/Event-Scraper/venv/bin/python /path/to/Event-Scraper/event_scraper.py >> /path/to/Event-Scraper/logs/scraper.log 2>&1

# Run LLM analysis daily at 2 AM
0 2 * * * cd /path/to/Event-Scraper && /path/to/Event-Scraper/venv/bin/python /path/to/Event-Scraper/event_analyzer.py >> /path/to/Event-Scraper/logs/analysis.log 2>&1

# Ensure sync is running (restart if needed) every hour
0 * * * * pgrep -f "python.*calendar_sync.py" || cd /path/to/Event-Scraper && /path/to/Event-Scraper/venv/bin/python /path/to/Event-Scraper/calendar_sync.py >> /path/to/Event-Scraper/logs/sync.log 2>&1
```

## Additional Resources

- [Directus Documentation](https://docs.directus.io/)
- [Nextcloud CalDAV Documentation](https://docs.nextcloud.com/server/latest/developer_manual/client_apis/WebDAV/caldav.html)
- [OpenAI API Documentation](https://platform.openai.com/docs/api-reference)
- [Systemd Service Documentation](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [Docker Documentation](https://docs.docker.com/)
- [Supervisor Documentation](http://supervisord.org/introduction.html)
