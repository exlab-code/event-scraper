#!/bin/bash
# run-event-system.sh - Master script for managing the Event Scraper system

# Set up environment
cd "$(dirname "$0")"  # Change to the directory of this script
if [ -d "venv" ]; then
    source venv/bin/activate
fi

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
        echo "Running scraper..."
        python event_scraper.py
        ;;
    analyze)
        echo "Running LLM analysis..."
        python event_analyzer.py
        ;;
    sync)
        echo "Starting sync service..."
        python calendar_sync.py
        ;;
    sync-once)
        echo "Running one-time sync..."
        python calendar_sync.py --sync-once
        ;;
    clean)
        echo "Cleaning Nextcloud calendar..."
        python calendar_sync.py --clean --sync-once
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
        echo "View logs in the logs/ directory."
        ;;
    stop)
        echo "Stopping all components..."
        for pid_file in logs/*.pid; do
            if [ -f "$pid_file" ]; then
                pid=$(cat "$pid_file")
                component=$(basename "$pid_file" .pid)
                echo "Stopping $component (PID: $pid)..."
                kill $pid 2>/dev/null || echo "Process already stopped"
                rm "$pid_file"
            fi
        done
        echo "All components stopped."
        ;;
    status)
        echo "Component status:"
        if [ ! "$(ls -A logs/*.pid 2>/dev/null)" ]; then
            echo "No components are currently running."
        else
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
        fi
        ;;
    setup-cron)
        echo "Setting up cron jobs..."
        (crontab -l 2>/dev/null; echo "# Event Scraper System - Added $(date)") | crontab -
        (crontab -l 2>/dev/null; echo "0 1 * * * cd $(pwd) && $(pwd)/run-event-system.sh scrape >> $(pwd)/logs/scraper-cron.log 2>&1") | crontab -
        (crontab -l 2>/dev/null; echo "0 2 * * * cd $(pwd) && $(pwd)/run-event-system.sh analyze >> $(pwd)/logs/analysis-cron.log 2>&1") | crontab -
        (crontab -l 2>/dev/null; echo "0 * * * * pgrep -f \"python.*calendar_sync.py\" || cd $(pwd) && $(pwd)/run-event-system.sh sync >> $(pwd)/logs/sync-cron.log 2>&1") | crontab -
        echo "Cron jobs set up. Use 'crontab -l' to view them."
        ;;
    remove-cron)
        echo "Removing cron jobs..."
        crontab -l | grep -v "Event Scraper System\|run-event-system.sh" | crontab -
        echo "Cron jobs removed."
        ;;
    *)
        echo "Event Scraper System Management Script"
        echo "-------------------------------------"
        echo "Usage: $0 {command}"
        echo ""
        echo "Commands:"
        echo "  scrape       Run the scraper once"
        echo "  analyze      Run the LLM analysis once"
        echo "  sync         Start the sync service (continuous)"
        echo "  sync-once    Run the sync service once and exit"
        echo "  clean        Clean the Nextcloud calendar"
        echo "  all          Run scraper and analysis, then start sync service in background"
        echo "  stop         Stop all background services"
        echo "  status       Check the status of all services"
        echo "  setup-cron   Set up cron jobs for automation"
        echo "  remove-cron  Remove cron jobs"
        echo ""
        echo "Examples:"
        echo "  $0 all       # Start all services in the background"
        echo "  $0 status    # Check which services are running"
        echo "  $0 stop      # Stop all running services"
        exit 1
        ;;
esac

exit 0
