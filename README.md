# Foxess V2 Home Assistant Add-ons

Home Assistant add-on repository for Foxess V2 solar inverter integration.

## Installation

1. In Home Assistant, go to **Settings → Add-ons → Add-on Store**
2. Click **⋮** (three dots, top right) → **Repositories**
3. Add this URL: `https://github.com/toolsinabox/foxess-v2-addon`
4. Click **Add**
5. Refresh the add-on store
6. Install **Foxess V2 Scraper**

## Add-ons

### Foxess V2 Scraper

Browser-based scraper that logs into Foxess Cloud V2 and extracts solar data.

**Features:**
- Headless Chrome browser automation
- Automatic login and session management
- HTTP API for integration access
- Real-time solar data extraction

**Configuration:**
- `username`: Your Foxess Cloud email
- `password`: Your Foxess Cloud password
- `port`: API port (default: 8099)

## Support

For issues, visit: https://github.com/toolsinabox/foxess-v2-addon/issues

## License

MIT License
