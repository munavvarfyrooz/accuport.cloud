#!/bin/bash
#==============================================================================
# Accuport Quick Start - Self-contained launcher
# Creates venv if needed, installs deps, starts dashboard
# Does NOT modify system (no services, no cron jobs)
# For full deployment with service setup, use deploy.sh instead
#==============================================================================

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"
DASHBOARD_DIR="$SCRIPT_DIR/dashbored"
REQUIREMENTS="$SCRIPT_DIR/requirements.txt"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo ""
echo -e "${BLUE}Accuport Quick Start${NC}"
echo "==================="
echo ""

# Check if dashboard exists
if [ ! -f "$DASHBOARD_DIR/app.py" ]; then
    echo -e "${RED}Error: Dashboard not found at $DASHBOARD_DIR/app.py${NC}"
    exit 1
fi

# Check if venv exists, create if not
if [ ! -d "$VENV_DIR" ]; then
    echo -e "${YELLOW}Virtual environment not found. Creating...${NC}"
    
    # Check for python3
    if ! command -v python3 &> /dev/null; then
        echo -e "${RED}Error: python3 not found. Please install Python 3.8+${NC}"
        exit 1
    fi
    
    # Create venv
    echo "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    
    if [ $? -ne 0 ]; then
        echo -e "${RED}Failed to create virtual environment${NC}"
        echo "Try: sudo apt-get install python3-venv (Debian/Ubuntu)"
        echo "  or: sudo yum install python3-virtualenv (RHEL/CentOS)"
        exit 1
    fi
    
    echo -e "${GREEN}Virtual environment created${NC}"
    
    # Install dependencies
    if [ -f "$REQUIREMENTS" ]; then
        echo "Installing dependencies (this may take a minute)..."
        "$VENV_DIR/bin/pip" install --upgrade pip -q
        "$VENV_DIR/bin/pip" install -r "$REQUIREMENTS" -q
        
        if [ $? -ne 0 ]; then
            echo -e "${RED}Failed to install dependencies${NC}"
            exit 1
        fi
        echo -e "${GREEN}Dependencies installed${NC}"
    else
        echo -e "${YELLOW}Warning: requirements.txt not found${NC}"
    fi
    
    echo ""
fi

# Set SECRET_KEY - use persistent key from file or generate new one
SECRET_KEY_FILE="$SCRIPT_DIR/.secret_key"
if [ -z "$SECRET_KEY" ]; then
    if [ -f "$SECRET_KEY_FILE" ]; then
        export SECRET_KEY="$(cat "$SECRET_KEY_FILE")"
        echo -e "${GREEN}Using persistent SECRET_KEY${NC}"
    else
        export SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
        echo "$SECRET_KEY" > "$SECRET_KEY_FILE"
        chmod 600 "$SECRET_KEY_FILE"
        echo -e "${YELLOW}Generated and saved new SECRET_KEY${NC}"
    fi
fi

# Start dashboard
echo "Starting dashboard..."
cd "$DASHBOARD_DIR"
"$VENV_DIR/bin/python" app.py &
DASHBOARD_PID=$!

# Wait a moment for startup
sleep 3

# Check if started successfully
if ps -p $DASHBOARD_PID > /dev/null 2>&1; then
    echo ""
    echo -e "${GREEN}Dashboard started successfully!${NC}"
    echo ""
    echo -e "  URL:  ${BLUE}http://localhost:5001${NC}"
    echo "  PID:  $DASHBOARD_PID"
    echo "  Logs: $DASHBOARD_DIR/app.log"
    echo ""
    echo "To stop: kill $DASHBOARD_PID"
    echo ""
else
    echo -e "${RED}Failed to start dashboard. Check $DASHBOARD_DIR/app.log${NC}"
    cat "$DASHBOARD_DIR/app.log" 2>/dev/null | tail -10
    exit 1
fi
