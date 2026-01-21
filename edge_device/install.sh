#!/bin/bash
# AAS Plug-and-Play Edge Agent Installation Script
# =================================================
#
# This script installs the bootstrap agent as a systemd service
# that starts automatically on boot.
#
# Usage:
#   sudo ./install.sh [--uninstall]
#
# What this script does:
# 1. Installs Python dependencies
# 2. Creates a systemd service file
# 3. Enables the service to start on boot
# 4. Starts the service immediately
#
# Prerequisites:
# - Python 3.7+
# - Docker installed and running
# - pip installed

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SERVICE_NAME="aas-pnp-agent"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_BIN="${PYTHON_BIN:-python3}"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo "========================================"
echo "AAS Plug-and-Play Agent Installer"
echo "========================================"
echo ""

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    echo -e "${RED}Error: This script must be run as root (sudo)${NC}"
    exit 1
fi

# Handle uninstall
if [ "$1" = "--uninstall" ] || [ "$1" = "-u" ]; then
    echo "Uninstalling ${SERVICE_NAME}..."
    
    # Stop and disable service
    systemctl stop ${SERVICE_NAME} 2>/dev/null || true
    systemctl disable ${SERVICE_NAME} 2>/dev/null || true
    
    # Remove service file
    rm -f ${SERVICE_FILE}
    
    # Remove mDNS service file if exists
    rm -f /etc/avahi/services/aas-pnp.service 2>/dev/null || true
    
    # Reload systemd
    systemctl daemon-reload
    
    echo -e "${GREEN}Uninstallation complete${NC}"
    exit 0
fi

# Check prerequisites
echo "Checking prerequisites..."

# Check Python
if ! command -v ${PYTHON_BIN} &> /dev/null; then
    echo -e "${RED}Error: Python 3 not found${NC}"
    echo "Install with: sudo apt install python3 python3-pip"
    exit 1
fi

PYTHON_VERSION=$(${PYTHON_BIN} --version 2>&1 | cut -d' ' -f2)
echo "  Python: ${PYTHON_VERSION}"

# Check Docker
if ! command -v docker &> /dev/null; then
    echo -e "${RED}Error: Docker not found${NC}"
    echo "Install Docker first: https://docs.docker.com/engine/install/"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo -e "${RED}Error: Docker daemon not running${NC}"
    echo "Start Docker with: sudo systemctl start docker"
    exit 1
fi

DOCKER_VERSION=$(docker --version | cut -d' ' -f3 | tr -d ',')
echo "  Docker: ${DOCKER_VERSION}"

# Check pip
if ! command -v pip3 &> /dev/null; then
    echo -e "${YELLOW}Warning: pip3 not found, trying pip${NC}"
    PIP_BIN="pip"
else
    PIP_BIN="pip3"
fi

echo ""
echo "Installing Python dependencies..."
${PIP_BIN} install -r ${SCRIPT_DIR}/requirements.txt

echo ""
echo "Creating systemd service..."

# Determine the user who invoked sudo (or root if run directly)
REAL_USER="${SUDO_USER:-root}"
REAL_GROUP=$(id -gn ${REAL_USER})

# Create the service file
cat > ${SERVICE_FILE} << EOF
[Unit]
Description=AAS Plug-and-Play Bootstrap Agent
Documentation=https://github.com/your-repo/aas-pnp
After=network-online.target docker.service
Wants=network-online.target
Requires=docker.service

[Service]
Type=simple
User=root
Group=root
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${PYTHON_BIN} -u ${SCRIPT_DIR}/bootstrap_agent.py
Restart=always
RestartSec=10

# Environment variables (can be overridden in /etc/default/${SERVICE_NAME})
Environment="PYTHONUNBUFFERED=1"
EnvironmentFile=-/etc/default/${SERVICE_NAME}

# Logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

# Security hardening (optional - comment out if causing issues)
# NoNewPrivileges=false  # Disabled because we need Docker access
# ProtectSystem=false     # Disabled because we need to write Avahi service files

[Install]
WantedBy=multi-user.target
EOF

echo "  Created: ${SERVICE_FILE}"

# Create default environment file
ENV_FILE="/etc/default/${SERVICE_NAME}"
if [ ! -f ${ENV_FILE} ]; then
    cat > ${ENV_FILE} << EOF
# AAS Plug-and-Play Agent Configuration
# Edit this file to override default settings

# Cloud proxy URL (REQUIRED - set to your Host PC's IP)
CLOUD_REPO_URL=http://192.168.137.1:5000

# Edge device identifier
EDGE_ID=pi-01

# AAS server port
AAS_SERVER_PORT=8080

# Log level (DEBUG, INFO, WARNING, ERROR)
LOG_LEVEL=INFO
EOF
    echo "  Created: ${ENV_FILE}"
    echo ""
    echo -e "${YELLOW}IMPORTANT: Edit ${ENV_FILE} to set your Host PC's IP address${NC}"
fi

# Reload systemd
echo ""
echo "Enabling service..."
systemctl daemon-reload
systemctl enable ${SERVICE_NAME}

echo ""
echo "Starting service..."
systemctl start ${SERVICE_NAME}

# Wait a moment and check status
sleep 2

if systemctl is-active --quiet ${SERVICE_NAME}; then
    echo -e "${GREEN}✓ Service started successfully${NC}"
else
    echo -e "${RED}✗ Service failed to start${NC}"
    echo ""
    echo "Check logs with: journalctl -u ${SERVICE_NAME} -f"
    exit 1
fi

echo ""
echo "========================================"
echo -e "${GREEN}Installation complete!${NC}"
echo "========================================"
echo ""
echo "Useful commands:"
echo "  View logs:      journalctl -u ${SERVICE_NAME} -f"
echo "  Check status:   systemctl status ${SERVICE_NAME}"
echo "  Restart:        systemctl restart ${SERVICE_NAME}"
echo "  Stop:           systemctl stop ${SERVICE_NAME}"
echo "  Edit config:    sudo nano /etc/default/${SERVICE_NAME}"
echo "  Uninstall:      sudo ./install.sh --uninstall"
echo ""
echo -e "${YELLOW}Remember to edit /etc/default/${SERVICE_NAME} with your Host PC's IP!${NC}"
echo ""
