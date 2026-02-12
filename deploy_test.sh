#!/bin/bash
set -e

# Configuration
TARGET_IP="192.168.144.26"
TARGET_USER="xilinx"
TARGET_PASS="xilinx" # Note: sshpass is used to handle password
TARGET_DIR="/home/xilinx/pynq_scope_tests"

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Deploying code to ${TARGET_USER}@${TARGET_IP}:${TARGET_DIR}...${NC}"

# Check for sshpass
if ! command -v sshpass &> /dev/null; then
    echo "sshpass could not be found. Installing..."
    # Attempt to install, but this might fail if user is not sudo. 
    # Fallback to manual password entry if needed, but for now we assume we can install or it's there.
    # In this environment, we can't easily install system packages.
    echo "WARNING: sshpass is missing. You may need to enter password multiple times."
    SSH_CMD="ssh"
    SCP_CMD="scp"
    RSYNC_CMD="rsync"
else
    SSH_CMD="sshpass -p ${TARGET_PASS} ssh"
    SCP_CMD="sshpass -p ${TARGET_PASS} scp"
    RSYNC_CMD="sshpass -p ${TARGET_PASS} rsync"
fi

# Create target directory
$SSH_CMD -o StrictHostKeyChecking=no ${TARGET_USER}@${TARGET_IP} "mkdir -p ${TARGET_DIR}"

# Sync code (server, tests, config)
# Exclude venv, __pycache__, and git
$RSYNC_CMD -avz --exclude '.venv' --exclude '__pycache__' --exclude '.git' \
    ./server ./tests ./pytest.ini ./run_tests.sh \
    ${TARGET_USER}@${TARGET_IP}:${TARGET_DIR}

echo -e "${BLUE}Running tests on remote target...${NC}"

# Command to run on the target
# 1. Install dependencies (we assume pip is available)
# 2. Run ONLY backend integration tests (Playwright won't work easily on headless ARM)
# 3. Set PYNQ_SCOPE_REAL_HW=1 to disable mocking
REMOTE_CMD="
cd ${TARGET_DIR} && \
echo 'Installing test dependencies...' && \
pip3 install pytest pytest-asyncio pytest-cov httpx fastapi uvicorn requests numpy websockets pytest-md-report && \
echo 'Running Backend Integration Tests on HARDWARE...' && \
PYNQ_SCOPE_REAL_HW=1 pytest tests/test_backend_integration.py -v --md-report --md-report-output=report.md
"

$SSH_CMD -o StrictHostKeyChecking=no ${TARGET_USER}@${TARGET_IP} "${REMOTE_CMD}"

echo -e "${GREEN}Remote testing completed!${NC}"
