#!/bin/bash
#==============================================================================
# Accuport Deployment Script v1.0.0
# One-click deployment for Accuport Dashboard + Datafetcher
# Supports: Ubuntu/Debian, CentOS/RHEL, macOS
#==============================================================================

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Get script directory (where accuport is installed)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/venv"
DASHBOARD_DIR="${SCRIPT_DIR}/dashbored"
DATAFETCHER_DIR="${SCRIPT_DIR}/datafetcher"
CONFIG_DIR="${SCRIPT_DIR}/config"

# Logging
log_info() { echo -e "${BLUE}[INFO]${NC} $1"; }
log_success() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Print banner
print_banner() {
    echo ""
    echo -e "${BLUE}================================================${NC}"
    echo -e "${BLUE}   Accuport Deployment Script v1.0.0${NC}"
    echo -e "${BLUE}   Marine Chemical Test Solutions${NC}"
    echo -e "${BLUE}================================================${NC}"
    echo ""
}

# Detect operating system
detect_os() {
    log_info "Detecting operating system..."
    
    if [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macos"
        PKG_MANAGER="brew"
    elif [ -f /etc/debian_version ]; then
        OS="debian"
        PKG_MANAGER="apt"
    elif [ -f /etc/redhat-release ]; then
        OS="rhel"
        PKG_MANAGER="yum"
    else
        OS="unknown"
        PKG_MANAGER="unknown"
    fi
    
    log_success "Detected OS: $OS (package manager: $PKG_MANAGER)"
}

# Install system dependencies (skip if python3 already available)
install_system_deps() {
    # Check if python3 and venv are already available
    if command -v python3 &> /dev/null && python3 -m venv --help &> /dev/null; then
        log_success "Python3 and venv already available, skipping system package installation"
        return 0
    fi

    log_info "Installing system dependencies..."

    case $OS in
        debian)
            sudo apt-get update -qq
            sudo apt-get install -y -qq python3 python3-venv python3-pip cron
            ;;
        rhel)
            sudo yum install -y -q python3 python3-pip cronie
            sudo systemctl enable crond
            sudo systemctl start crond
            ;;
        macos)
            if ! command -v brew &> /dev/null; then
                log_error "Homebrew not installed. Please install it first."
                exit 1
            fi
            brew install python3 2>/dev/null || true
            ;;
        *)
            log_error "Unsupported OS. Please install Python 3 manually."
            exit 1
            ;;
    esac
    
    log_success "System dependencies installed"
}

# Create virtual environment
setup_venv() {
    log_info "Setting up Python virtual environment..."
    
    if [ -d "$VENV_DIR" ]; then
        log_warn "Virtual environment exists. Removing old one..."
        rm -rf "$VENV_DIR"
    fi
    
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    
    pip install --upgrade pip -q
    pip install -r "$SCRIPT_DIR/requirements.txt" -q
    
    deactivate
    
    log_success "Virtual environment created at $VENV_DIR"
}

# Start dashboard directly (when no sudo available)
start_dashboard_direct() {
    log_info "Starting dashboard directly..."

    # Set SECRET_KEY - use persistent key from file or generate new one
    SECRET_KEY_FILE="$SCRIPT_DIR/.secret_key"
    if [ -z "$SECRET_KEY" ]; then
        if [ -f "$SECRET_KEY_FILE" ]; then
            export SECRET_KEY="$(cat "$SECRET_KEY_FILE")"
            log_success "Using persistent SECRET_KEY"
        else
            export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
            echo "$SECRET_KEY" > "$SECRET_KEY_FILE"
            chmod 600 "$SECRET_KEY_FILE"
            log_warn "Generated and saved new SECRET_KEY"
        fi
    fi

    cd "$DASHBOARD_DIR"
    "$VENV_DIR/bin/python" app.py &
    DASHBOARD_PID=$!

    sleep 3

    if ps -p $DASHBOARD_PID > /dev/null 2>&1; then
        log_success "Dashboard started (PID: $DASHBOARD_PID)"
        echo ""
        echo "  URL: http://localhost:5001"
        echo "  To stop: kill $DASHBOARD_PID"
        echo ""
    else
        log_error "Failed to start dashboard"
    fi
}

# Setup systemd service (Linux only)
setup_systemd_service() {
    if [[ "$OS" == "macos" ]]; then
        setup_launchd_service
        return
    fi

    # Check if we can use sudo (will prompt for password if needed)
    if ! sudo true; then
        log_warn "No sudo access - skipping systemd service setup"
        log_info "Starting dashboard directly instead..."
        start_dashboard_direct
        return
    fi

    log_info "Setting up systemd service..."

    # Generate SECRET_KEY for production
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    log_info "Generated SECRET_KEY for service"

    # Create service file from template
    SERVICE_FILE="/etc/systemd/system/accuport.service"

    sudo tee $SERVICE_FILE > /dev/null << EOF
[Unit]
Description=Accuport Dashboard - Marine Chemical Test Solutions
After=network.target

[Service]
Type=simple
User=$(whoami)
Group=$(whoami)
WorkingDirectory=$DASHBOARD_DIR
Environment="PATH=$VENV_DIR/bin"
Environment="SECRET_KEY=$SECRET_KEY"
ExecStart=$VENV_DIR/bin/gunicorn --bind 0.0.0.0:5001 --workers 2 --access-logfile - --error-logfile - app:app
Restart=always
RestartSec=10
StandardOutput=append:$DASHBOARD_DIR/app.log
StandardError=append:$DASHBOARD_DIR/app.log

[Install]
WantedBy=multi-user.target
EOF

    sudo systemctl daemon-reload
    sudo systemctl enable accuport
    sudo systemctl restart accuport
    
    log_success "Systemd service installed and started"
}

# Setup launchd service (macOS only)
setup_launchd_service() {
    log_info "Setting up launchd service (macOS)..."

    # Generate SECRET_KEY for production
    SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")
    log_info "Generated SECRET_KEY for service"

    PLIST_FILE="$HOME/Library/LaunchAgents/com.accuport.dashboard.plist"
    mkdir -p "$HOME/Library/LaunchAgents"

    cat > "$PLIST_FILE" << EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.accuport.dashboard</string>
    <key>ProgramArguments</key>
    <array>
        <string>$VENV_DIR/bin/python</string>
        <string>$DASHBOARD_DIR/app.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>$DASHBOARD_DIR</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>SECRET_KEY</key>
        <string>$SECRET_KEY</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>$DASHBOARD_DIR/app.log</string>
    <key>StandardErrorPath</key>
    <string>$DASHBOARD_DIR/app.log</string>
</dict>
</plist>
EOF

    launchctl unload "$PLIST_FILE" 2>/dev/null || true
    launchctl load "$PLIST_FILE"
    
    log_success "Launchd service installed and started"
}

# Setup cron job for datafetcher
setup_cron() {
    log_info "Setting up datafetcher cron job (every 6 hours)..."
    
    # Create fetch wrapper script
    FETCH_SCRIPT="$DATAFETCHER_DIR/fetch_cron.sh"
    
    cat > "$FETCH_SCRIPT" << EOF
#!/bin/bash
# Accuport Datafetcher Cron Wrapper
cd $DATAFETCHER_DIR/src
$VENV_DIR/bin/python fetch_labcom_data.py --all
EOF

    chmod +x "$FETCH_SCRIPT"
    
    # Add cron entry (every 6 hours)
    CRON_ENTRY="0 */6 * * * $FETCH_SCRIPT >> $DATAFETCHER_DIR/fetch.log 2>&1"
    
    # Remove existing accuport cron entries and add new one
    (crontab -l 2>/dev/null | grep -v "fetch_cron.sh"; echo "$CRON_ENTRY") | crontab -
    
    log_success "Cron job configured (runs every 6 hours)"
}

# Create config directory and templates
setup_config() {
    log_info "Setting up configuration..."
    
    mkdir -p "$CONFIG_DIR"
    
    # Save service template for reference
    cat > "$CONFIG_DIR/accuport.service.template" << EOF
[Unit]
Description=Accuport Dashboard - Marine Chemical Test Solutions
After=network.target

[Service]
Type=simple
User=DEPLOY_USER
WorkingDirectory=INSTALL_PATH/dashbored
Environment="PATH=INSTALL_PATH/venv/bin"
ExecStart=INSTALL_PATH/venv/bin/python app.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    log_success "Configuration templates saved"
}

# Print final summary
print_summary() {
    echo ""
    echo -e "${GREEN}================================================${NC}"
    echo -e "${GREEN}   Deployment Complete!${NC}"
    echo -e "${GREEN}================================================${NC}"
    echo ""
    echo -e "Dashboard URL:    ${BLUE}http://localhost:5001${NC}"
    echo -e "Dashboard logs:   ${YELLOW}$DASHBOARD_DIR/app.log${NC}"
    echo -e "Datafetcher logs: ${YELLOW}$DATAFETCHER_DIR/fetch.log${NC}"
    echo ""
    echo "Commands:"
    if [[ "$OS" != "macos" ]]; then
        echo "  Check status:   sudo systemctl status accuport"
        echo "  Restart:        sudo systemctl restart accuport"
        echo "  Stop:           sudo systemctl stop accuport"
    else
        echo "  Check status:   launchctl list | grep accuport"
        echo "  Restart:        launchctl kickstart -k gui/$(id -u)/com.accuport.dashboard"
    fi
    echo "  View logs:      tail -f $DASHBOARD_DIR/app.log"
    echo "  Run fetch now:  $DATAFETCHER_DIR/fetch_cron.sh"
    echo ""
}

# Main deployment function
main() {
    print_banner
    
    # Verify we're in the right directory
    if [ ! -f "$SCRIPT_DIR/requirements.txt" ]; then
        log_error "requirements.txt not found. Are you in the accuport directory?"
        exit 1
    fi
    
    detect_os
    install_system_deps
    setup_venv
    setup_config
    setup_systemd_service
    setup_cron
    print_summary
}

# Run main
main "$@"
