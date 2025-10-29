# Foxess V2 Scraper Add-on

Browser-based scraper for Foxess V2 solar inverter data.

## About

This add-on uses Playwright and Chromium to log into your Foxess V2 account and scrape real-time solar data. It provides a simple HTTP API that the Foxess V2 integration uses to fetch your solar system information.

## Installation

1. Add this repository to your Home Assistant add-on store
2. Install the "Foxess V2 Scraper" add-on
3. Configure with your Foxess credentials
4. Start the add-on
5. Install the Foxess V2 integration from HACS

## Configuration

**username** (required): Your Foxess Cloud email address

**password** (required): Your Foxess Cloud password

**port** (optional): Port for the API server (default: 8099)

### Example configuration:

```yaml
username: your.email@example.com
password: YourPassword123
port: 8099
```

## How it works

1. The add-on starts a headless Chrome browser
2. Logs into https://www.foxesscloud.com/v2/ with your credentials
3. Keeps the session alive (refreshes every 4 minutes)
4. Provides HTTP endpoints for the integration to fetch data
5. Runs continuously in the background

## API Endpoints

- `GET /health` - Health check
- `GET /data` - Get current solar data

## Data Provided

The add-on extracts:
- PV Power (solar generation)
- Battery State of Charge (%)
- Battery Power (charge/discharge)
- Grid Power (import/export)
- Load Power (home consumption)
- Inverter Power
- Daily energy totals
- Feed-in energy
- Grid consumption

## Support

For issues, please visit:
https://github.com/yourusername/foxess-v2-addon/issues

## License

MIT License
