#!/usr/bin/env bash
set -e

echo "Starting Foxess V2 Scraper..."

# Read config from /data/options.json (Home Assistant standard)
CONFIG_PATH=/data/options.json

if [ -f "$CONFIG_PATH" ]; then
    export FOXESS_USERNAME=$(jq -r '.username' $CONFIG_PATH)
    export FOXESS_PASSWORD=$(jq -r '.password' $CONFIG_PATH)
    export FOXESS_PORT=$(jq -r '.port // 8099' $CONFIG_PATH)
else
    echo "Config file not found, using defaults"
    export FOXESS_USERNAME=""
    export FOXESS_PASSWORD=""
    export FOXESS_PORT="8099"
fi

echo "Starting scraper on port $FOXESS_PORT"

# Run the scraper
python3 /app/scraper.py
