#!/bin/bash
#==============================================================================
# Accuport Uninstall Script
# Removes services and optionally cleans up files
#==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }

echo ""
echo -e "${YELLOW}================================================${NC}"
echo -e "${YELLOW}   Accuport Uninstall Script${NC}"
echo -e "${YELLOW}================================================${NC}"
echo ""

# Detect OS
if [[ "$OSTYPE" == "darwin"* ]]; then
    OS="macos"
else
    OS="linux"
fi

# Stop and disable systemd service (Linux)
if [[ "$OS" == "linux" ]]; then
    log_info "Stopping systemd service..."
    sudo systemctl stop accuport 2>/dev/null || true
    sudo systemctl disable accuport 2>/dev/null || true
    sudo rm -f /etc/systemd/system/accuport.service
    sudo systemctl daemon-reload
    log_success "Systemd service removed"
fi

# Stop and remove launchd service (macOS)
if [[ "$OS" == "macos" ]]; then
    log_info "Stopping launchd service..."
    PLIST="$HOME/Library/LaunchAgents/com.accuport.dashboard.plist"
    launchctl unload "$PLIST" 2>/dev/null || true
    rm -f "$PLIST"
    log_success "Launchd service removed"
fi

# Remove cron job
log_info "Removing cron job..."
crontab -l 2>/dev/null | grep -v "fetch_cron.sh" | crontab - 2>/dev/null || true
log_success "Cron job removed"

# Ask about venv removal
echo ""
read -p "Remove virtual environment (venv/)? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -rf "$SCRIPT_DIR/venv"
    log_success "Virtual environment removed"
fi

# Ask about data removal
echo ""
read -p "Remove data files (databases, logs)? [y/N] " -n 1 -r
echo ""
if [[ $REPLY =~ ^[Yy]$ ]]; then
    rm -f "$SCRIPT_DIR/dashbored/app.log"
    rm -f "$SCRIPT_DIR/datafetcher/fetch.log"
    log_warn "Log files removed. Database files preserved for safety."
fi

echo ""
echo -e "${GREEN}================================================${NC}"
echo -e "${GREEN}   Uninstall Complete${NC}"
echo -e "${GREEN}================================================${NC}"
echo ""
echo "The application files remain in: $SCRIPT_DIR"
echo "To fully remove, delete the directory manually."
echo ""
