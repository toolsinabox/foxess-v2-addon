#!/usr/bin/with-contenv bashio

bashio::log.info "Starting Foxess V2 Scraper..."

# Get options from config
USERNAME=$(bashio::config 'username')
PASSWORD=$(bashio::config 'password')
PORT=$(bashio::config 'port')

export FOXESS_USERNAME="$USERNAME"
export FOXESS_PASSWORD="$PASSWORD"
export FOXESS_PORT="$PORT"

bashio::log.info "Starting scraper on port $PORT"

# Run the scraper
python3 /app/scraper.py
