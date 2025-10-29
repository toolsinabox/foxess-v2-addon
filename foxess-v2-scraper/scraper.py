"""Foxess V2 Scraper Add-on using Selenium."""
import asyncio
import os
import json
import time
from aiohttp import web
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
import logging

logging.basicConfig(level=logging.INFO)
_LOGGER = logging.getLogger(__name__)

# Get config
USERNAME = os.getenv('FOXESS_USERNAME')
PASSWORD = os.getenv('FOXESS_PASSWORD')
PORT = int(os.getenv('FOXESS_PORT', 8099))

# Browser instance
driver = None
last_login = 0


def get_driver():
    """Get or create Selenium driver."""
    global driver, last_login
    
    current_time = time.time()
    
    # Reuse if less than 4 minutes old
    if driver and (current_time - last_login) < 240:
        return driver
    
    # Close old
    if driver:
        try:
            driver.quit()
        except:
            pass
    
    _LOGGER.info("Starting browser...")
    
    options = Options()
    options.add_argument('--headless')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    
    # Use system chromedriver
    from selenium.webdriver.chrome.service import Service
    service = Service(executable_path='/usr/bin/chromedriver')
    
    driver = webdriver.Chrome(service=service, options=options)
    
    # Login
    _LOGGER.info("Logging in...")
    driver.get('https://www.foxesscloud.com/v2/')
    time.sleep(5)
    
    # Find and fill username
    username_input = driver.find_element(By.CSS_SELECTOR, 'input[type="text"], input[type="email"]')
    username_input.send_keys(USERNAME)
    
    # Find and fill password  
    password_input = driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')
    password_input.send_keys(PASSWORD)
    
    time.sleep(2)
    
    # Try multiple selectors for login button
    login_button = None
    button_selectors = [
        'button[type="submit"]',
        'button:contains("Log In")',
        'button:contains("Login")',
        '//button[contains(text(), "Log")]',
        '//button',
    ]
    
    for selector in button_selectors:
        try:
            if selector.startswith('//'):
                login_button = driver.find_element(By.XPATH, selector)
            else:
                login_button = driver.find_element(By.CSS_SELECTOR, selector)
            
            if login_button:
                _LOGGER.info(f"Found login button with selector: {selector}")
                break
        except:
            continue
    
    if not login_button:
        _LOGGER.error("Could not find login button")
        raise Exception("Login button not found")
    
    login_button.click()
    time.sleep(10)
    
    if 'login' in driver.current_url.lower():
        raise Exception("Login failed - still on login page")
    
    _LOGGER.info("Login successful!")
    last_login = current_time
    
    return driver


def scrape_data():
    """Scrape data from dashboard."""
    _LOGGER.info("Scraping data...")
    
    driver = get_driver()
    time.sleep(3)
    
    # Extract data using JavaScript
    data = driver.execute_script("""
        const result = {};
        const textData = {};
        document.querySelectorAll('[class*="value"], [class*="data"], [class*="power"]').forEach((el, i) => {
            const text = el.textContent.trim();
            if (text && text.length < 50) {
                textData[`element_${i}`] = text;
            }
        });
        result.text_data = textData;
        return result;
    """)
    
    # Parse data
    parsed = parse_foxess_data(data)
    
    _LOGGER.info(f"Scraped: {parsed}")
    return parsed


def parse_foxess_data(raw_data):
    """Parse raw data."""
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
    
    for key, value in text_data.items():
        value_str = str(value).lower()
        
        if 'soc:' in value_str and '%' in value_str:
            try:
                result['battery_soc'] = float(value_str.replace('soc:', '').replace('%', '').strip())
            except:
                pass
        
        if 'kw' in value_str:
            try:
                power = value_str.replace('kw', '').strip()
                if '/' not in power:
                    result['pv_power'] = float(power)
            except:
                pass
    
    return result


async def handle_get_data(request):
    """Handle GET /data."""
    try:
        data = await asyncio.get_event_loop().run_in_executor(None, scrape_data)
        return web.json_response({'status': 'success', 'data': data})
    except Exception as e:
        _LOGGER.error(f"Error: {e}")
        return web.json_response({'status': 'error', 'message': str(e)}, status=500)


async def handle_health(request):
    """Handle GET /health."""
    return web.json_response({'status': 'ok'})


async def main():
    """Start server."""
    app = web.Application()
    app.router.add_get('/data', handle_get_data)
    app.router.add_get('/health', handle_health)
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    _LOGGER.info(f"Scraper running on port {PORT}")
    await asyncio.Event().wait()


if __name__ == '__main__':
    asyncio.run(main())
