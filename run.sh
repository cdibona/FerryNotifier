#!/bin/bash
# Quick start script for FerryTrmnl development server

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "FerryTrmnl - Washington State Ferry Status Webhook"
echo "===================================================="
echo ""

# Check if .env file exists
if [ ! -f .env ]; then
    echo -e "${YELLOW}Warning: .env file not found!${NC}"
    echo "Creating .env from .env.template..."
    cp .env.template .env
    echo -e "${YELLOW}Please edit .env and add your WSDOT_API_KEY before running again.${NC}"
    exit 1
fi

# Check if WSDOT_API_KEY is set
source .env
if [ -z "$WSDOT_API_KEY" ] || [ "$WSDOT_API_KEY" = "your_wsdot_api_key_here" ]; then
    echo -e "${RED}Error: WSDOT_API_KEY not configured!${NC}"
    echo "Please edit .env and add your WSDOT API key."
    exit 1
fi

# Check if Python dependencies are installed
if ! python3 -c "import flask" 2>/dev/null; then
    echo -e "${YELLOW}Installing Python dependencies...${NC}"
    pip install -r requirements.txt
fi

echo -e "${GREEN}Starting FerryTrmnl webhook server...${NC}"
echo ""
echo "Server will be available at:"
echo "  - http://localhost:${FLASK_PORT:-5050}/webhook"
echo "  - http://localhost:${FLASK_PORT:-5050}/api/ferry-status"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

# Run the Flask app
python3 app.py
