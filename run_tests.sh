#!/bin/bash
set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

VENV_DIR=".venv"

if [ ! -d "$VENV_DIR" ]; then
    echo -e "${BLUE}Creating virtual environment in $VENV_DIR...${NC}"
    python3 -m venv $VENV_DIR
fi

echo -e "${BLUE}Activating virtual environment...${NC}"
source $VENV_DIR/bin/activate

echo -e "${GREEN}Installing test dependencies...${NC}"
pip install --upgrade pip
pip install pytest pytest-cov pytest-mock pytest-xdist pytest-playwright playwright httpx pytest-asyncio pytest-md-report
# Project dependencies
pip install fastapi uvicorn requests numpy websockets

echo -e "${GREEN}Installing Playwright browsers...${NC}"
playwright install chromium

echo -e "${GREEN}Running Backend Integration Tests...${NC}"
pytest tests/test_backend_integration.py -v

echo -e "${GREEN}Running Frontend (GUI) Logic Tests...${NC}"
pytest tests/test_gui_unit.py -v

echo -e "${GREEN}Running E2E API Tests...${NC}"
pytest tests/test_e2e_playwright.py -v

echo -e "${GREEN}Running All Tests with Coverage and Parallelism...${NC}"
# -n auto: use all available CPUs
# --dist loadscope: group tests by module/class to avoid side effects if any
# Generate Markdown report
pytest -n auto --dist loadscope --cov=server --cov-report=term-missing --md-report --md-report-output=report.md
