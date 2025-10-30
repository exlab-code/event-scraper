#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fördermittel Monitoring Script

Runs the complete monitoring workflow:
1. Scrape all sources (checks for new, changed, removed programs)
2. Analyze new/changed programs with LLM
3. Generate change report

This script should be run regularly (e.g., weekly via cron) to monitor
funding program websites for changes.
"""

import subprocess
import logging
import sys
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("foerdermittel-monitor")


def run_command(cmd, description):
    """Run a command and log results.

    Args:
        cmd (list): Command and arguments to run
        description (str): Description of what the command does

    Returns:
        bool: True if command succeeded, False otherwise
    """
    logger.info(f"Starting: {description}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        logger.error(f"{description} failed:")
        logger.error(result.stderr)
        return False

    logger.info(f"{description} completed successfully")
    if result.stdout:
        print(result.stdout)
    return True


def main():
    """Run the complete monitoring workflow."""
    logger.info(f"=== Fördermittel Monitoring Run: {datetime.now()} ===")

    # Step 1: Run scraper
    if not run_command(
        ["python3", "foerdermittel/foerdermittel_scraper.py", "--max-programs", "-1"],
        "Scraper (checking for changes)"
    ):
        logger.error("Scraper failed - aborting monitoring run")
        sys.exit(1)

    # Step 2: Run analyzer
    if not run_command(
        ["python3", "foerdermittel/foerdermittel_analyzer.py", "--limit", "50"],
        "Analyzer (processing new/changed programs)"
    ):
        logger.error("Analyzer failed - check logs for details")
        sys.exit(1)

    logger.info("=== Monitoring run completed successfully ===")


if __name__ == "__main__":
    main()
