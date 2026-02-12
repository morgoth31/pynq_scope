#!/bin/bash
set -e

# Configuration
TARGET_IP="192.168.144.26"
TARGET_USER="xilinx"
TARGET_PASS="xilinx"
TARGET_DIR="/home/xilinx/pynq_scope_run"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
NC='\033[0m'

# Check for sshpass
if ! command -v sshpass &> /dev/null; then
    echo -e "${RED}Error: sshpass is not installed. Please install it (e.g., sudo apt install sshpass).${NC}"
    # We proceed but user might need to enter password
    SSH_CMD="ssh"
    RSYNC_CMD="rsync"
else
    SSH_CMD="sshpass -p ${TARGET_PASS} ssh"
    RSYNC_CMD="sshpass -p ${TARGET_PASS} rsync"
fi

# Cleanup function to kill remote server on exit
cleanup() {
    echo -e "\n${BLUE}Stopping remote server...${NC}"
    $SSH_CMD -o StrictHostKeyChecking=no ${TARGET_USER}@${TARGET_IP} "pkill -f pynq_scope_server.py || true"
    echo -e "${GREEN}Cleanup complete.${NC}"
}
trap cleanup EXIT

echo -e "${BLUE}1. Syncing code to ${TARGET_IP}...${NC}"
$SSH_CMD -o StrictHostKeyChecking=no ${TARGET_USER}@${TARGET_IP} "mkdir -p ${TARGET_DIR}"
$RSYNC_CMD -avz --exclude '.venv' --exclude '__pycache__' --exclude '.git' \
    ./server \
    ${TARGET_USER}@${TARGET_IP}:${TARGET_DIR}

echo -e "${BLUE}2. Installing dependencies on remote...${NC}"
$SSH_CMD -o StrictHostKeyChecking=no ${TARGET_USER}@${TARGET_IP} "cd ${TARGET_DIR} && pip3 install -r server/requirements.txt"

echo -e "${BLUE}3. Starting Remote Server...${NC}"
# Run server in background, redirect output to a log file
CMD="cd ${TARGET_DIR} && nohup python3 server/pynq_scope_server.py > server.log 2>&1 & echo \$!"
SERVER_PID=$($SSH_CMD -o StrictHostKeyChecking=no ${TARGET_USER}@${TARGET_IP} "${CMD}")
echo -e "${GREEN}Server started with PID ${SERVER_PID}${NC}"

echo -e "${BLUE}3. Waiting for server to be ready...${NC}"
sleep 5 # Give it a moment to bind port

echo -e "${BLUE}4. Launching Local GUI...${NC}"
# Ensure we are in venv if it exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# Update config.yml to point to remote server temporarily? 
# Or just rely on user input. For better UX, let's update/check config.
# (Optional: sed -i ... config.yml)

echo -e "${GREEN}GUI Running. Close GUI to stop everything.${NC}"
python3 gui/pynq_scope_gui.py

# Cleanup trap will handle stopping the server
