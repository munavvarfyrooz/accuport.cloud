#!/bin/bash
#==============================================================================
# Accuport Datafetcher Cron Wrapper
# Runs data fetch from Labcom API
#==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$INSTALL_DIR/venv"
LOG_FILE="$SCRIPT_DIR/fetch.log"

# Log start
echo "========================================" >> "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting data fetch..." >> "$LOG_FILE"

# Activate venv and run fetch
cd "$SCRIPT_DIR/src"
"$VENV_DIR/bin/python" fetch_labcom_data.py --all >> "$LOG_FILE" 2>&1

# Log completion
EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Data fetch completed successfully" >> "$LOG_FILE"
else
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Data fetch failed with exit code $EXIT_CODE" >> "$LOG_FILE"
fi
