# Foxess V2 Scraper Add-on

Browser-based scraper for Foxess V2 solar inverter data using Selenium.

## Configuration

**username**: Your Foxess Cloud email

**password**: Your Foxess Cloud password

**port**: API port (default: 8099)

## How it works

1. Starts headless Chrome browser
2. Logs into Foxess V2 with your credentials
3. Scrapes dashboard data
4. Provides HTTP API for integration

## API Endpoints

- `GET /health` - Health check
- `GET /data` - Get current solar data
