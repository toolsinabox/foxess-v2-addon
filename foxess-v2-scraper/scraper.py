"""Foxess V2 Scraper Add-on - Web API."""
import asyncio
import os
import json
from aiohttp import web
from playwright.async_api import async_playwright
import logging

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)

# Get config from environment
USERNAME = os.getenv('FOXESS_USERNAME')
PASSWORD = os.getenv('FOXESS_PASSWORD')
PORT = int(os.getenv('FOXESS_PORT', 8099))

# Cache for browser session
browser_instance = None
page_instance = None
last_login_time = 0


async def get_browser_page():
    """Get or create browser page."""
    global browser_instance, page_instance, last_login_time
    
    current_time = asyncio.get_event_loop().time()
    
    # Reuse session if less than 4 minutes old
    if page_instance and (current_time - last_login_time) < 240:
        return page_instance
    
    # Close old session
    if page_instance:
        try:
            await page_instance.close()
        except:
            pass
    
    if browser_instance:
        try:
            await browser_instance.close()
        except:
            pass
    
    # Create new browser session
    _LOGGER.info("Starting new browser session...")
    playwright = await async_playwright().start()
    
    browser_instance = await playwright.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
    )
    
    context = await browser_instance.new_context(
        viewport={'width': 1920, 'height': 1080},
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
    )
    
    page_instance = await context.new_page()
    
    # Login
    _LOGGER.info("Logging in to Foxess V2...")
    await page_instance.goto('https://www.foxesscloud.com/v2/', wait_until='networkidle', timeout=60000)
    await asyncio.sleep(3)
    
    await page_instance.fill('input[type="text"], input[type="email"]', USERNAME)
    await page_instance.fill('input[type="password"]', PASSWORD)
    await asyncio.sleep(1)
    
    await page_instance.click('button:has-text("Log In"), button:has-text("Login"), button[type="submit"]')
    await asyncio.sleep(8)
    
    current_url = page_instance.url
    if 'login' in current_url.lower():
        _LOGGER.error("Login failed!")
        raise Exception("Login failed")
    
    _LOGGER.info("Login successful!")
    last_login_time = current_time
    
    return page_instance


async def scrape_data(page):
    """Scrape data from dashboard."""
    _LOGGER.info("Scraping data...")
    
    await asyncio.sleep(3)
    
    data = await page.evaluate("""
        () => {
            const result = {};
            
            // Extract all text data
            const textData = {};
            document.querySelectorAll('[class*="value"], [class*="data"], [class*="power"]').forEach((el, i) => {
                const text = el.textContent.trim();
                if (text && text.length < 50) {
                    textData[`element_${i}`] = text;
                }
            });
            
            result.text_data = textData;
            return result;
        }
    """)
    
    # Parse the data
    parsed = parse_foxess_data(data)
    
    _LOGGER.info(f"Scraped data: {parsed}")
    return parsed


def parse_foxess_data(raw_data):
    """Parse raw data into structured format."""
    text_data = raw_data.get('text_data', {})
    
    result = {
        'pv_power': 0.0,
        'battery_soc': 0.0,
        'battery_power': 0.0,
        'grid_power': 0.0,
        'load_power': 0.0,
        'inverter_power': 0.0,
        'energy_today': 0.0,
        'energy_total': 0.0,
        'feed_in_energy_today': 0.0,
        'grid_consumption_today': 0.0,
        'battery_charge_today': 0.0,
        'battery_discharge_today': 0.0,
    }
    
    # Parse values from text_data
    for key, value in text_data.items():
        value_str = str(value).lower()
        
        # Battery SOC
        if 'soc:' in value_str and '%' in value_str:
            try:
                soc_value = value_str.replace('soc:', '').replace('%', '').strip()
                result['battery_soc'] = float(soc_value)
            except:
                pass
        
        # PV Power (look for kW values)
        if 'kw' in value_str and 'pv' not in value_str:
            try:
                power = value_str.replace('kw', '').strip()
                if '/' not in power:
                    result['pv_power'] = float(power)
            except:
                pass
        
        # Extract energy values
        if '/' in value_str and 'kwh' in value_str.lower():
            try:
                parts = value_str.split('/')
                if len(parts) == 2:
                    today = float(parts[0].replace('kwh', '').strip())
                    total = float(parts[1].replace('kwh', '').strip())
                    
                    # Determine which energy type based on context
                    prev_key_idx = int(key.split('_')[1]) - 1
                    prev_text = text_data.get(f'element_{prev_key_idx}', '').lower()
                    
                    if 'pv' in prev_text or 'yield' in prev_text:
                        result['energy_today'] = today
                        result['energy_total'] = total
                    elif 'feed' in prev_text:
                        result['feed_in_energy_today'] = today
                    elif 'consumption' in prev_text:
                        result['grid_consumption_today'] = today
            except:
                pass
    
    return result


async def handle_get_data(request):
    """Handle GET /data request."""
    try:
        page = await get_browser_page()
        data = await scrape_data(page)
        
        return web.json_response({
            'status': 'success',
            'data': data
        })
    
    except Exception as e:
        _LOGGER.error(f"Error getting data: {e}")
        return web.json_response({
            'status': 'error',
            'message': str(e)
        }, status=500)


async def handle_health(request):
    """Handle GET /health request."""
    return web.json_response({'status': 'ok'})


async def main():
    """Start the web server."""
    app = web.Application()
    app.router.add_get('/data', handle_get_data)
    app.router.add_get('/health', handle_health)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    _LOGGER.info(f"Foxess V2 Scraper running on port {PORT}")
    _LOGGER.info(f"Username: {USERNAME}")
    
    # Keep running
    await asyncio.Event().wait()


if __name__ == '__main__':
    asyncio.run(main())
