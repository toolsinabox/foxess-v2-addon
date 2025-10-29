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
    options.add_argument('--window-size=1920,1080')
    
    # Use system chromedriver
    from selenium.webdriver.chrome.service import Service
    service = Service(executable_path='/usr/bin/chromedriver')
    
    driver = webdriver.Chrome(service=service, options=options)
    
    # Login
    _LOGGER.info("Logging in...")
    driver.get('https://www.foxesscloud.com/v2/')
    time.sleep(8)  # Wait for page to fully load
    
    # Save screenshot for debugging
    try:
        driver.save_screenshot('/tmp/foxess_page.png')
        _LOGGER.info("Screenshot saved to /tmp/foxess_page.png")
    except:
        pass
    
    # Find and fill username
    _LOGGER.info("Finding username field...")
    username_input = driver.find_element(By.CSS_SELECTOR, 'input[type="text"], input[type="email"]')
    username_input.clear()
    username_input.send_keys(USERNAME)
    time.sleep(1)
    
    # Find and fill password  
    _LOGGER.info("Finding password field...")
    password_input = driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')
    password_input.clear()
    password_input.send_keys(PASSWORD)
    time.sleep(2)
    
    # Find all buttons and log them
    all_buttons = driver.find_elements(By.TAG_NAME, 'button')
    _LOGGER.info(f"Found {len(all_buttons)} buttons on page")
    for i, btn in enumerate(all_buttons):
        _LOGGER.info(f"Button {i}: text='{btn.text}', type={btn.get_attribute('type')}, class={btn.get_attribute('class')}")
    
    # Try to find login button by text
    login_button = None
    for btn in all_buttons:
        btn_text = btn.text.lower()
        if 'log' in btn_text or 'sign' in btn_text or btn.get_attribute('type') == 'submit':
            login_button = btn
            _LOGGER.info(f"Selected button: '{btn.text}'")
            break
    
    if not login_button and all_buttons:
        # Just click the first button
        login_button = all_buttons[0]
        _LOGGER.info("Using first button as fallback")
    
    if not login_button:
        _LOGGER.error("Could not find any login button")
        raise Exception("Login button not found")
    
    _LOGGER.info("Clicking login button...")
    login_button.click()
    time.sleep(12)  # Wait longer for login
    
    current_url = driver.current_url
    _LOGGER.info(f"After login, URL is: {current_url}")
    
    if 'login' in current_url.lower():
        _LOGGER.error("Login failed - still on login page")
        try:
            driver.save_screenshot('/tmp/foxess_after_login.png')
            _LOGGER.info("After-login screenshot saved")
        except:
            pass
        raise Exception("Login failed - still on login page")
    
    _LOGGER.info("Login successful!")
    last_login = current_time
    
    return driver


def scrape_data():
    """Scrape data from dashboard."""
    _LOGGER.info("Scraping data...")
    
    driver = get_driver()
    time.sleep(3)
    
    # Extract data using JavaScript - get ALL text elements
    data = driver.execute_script("""
        const result = {};
        const allText = [];
        
        // Get all visible text elements
        document.querySelectorAll('div, span, p').forEach((el) => {
            const text = el.textContent.trim();
            if (text && text.length < 100 && text.length > 0) {
                allText.push(text);
            }
        });
        
        result.all_text = allText;
        return result;
    """)
    
    # Parse data
    parsed = parse_foxess_data(data)
    
    _LOGGER.info(f"Scraped: {parsed}")
    return parsed


def parse_foxess_data(raw_data):
    """Parse raw data."""
    all_text = raw_data.get('all_text', [])
    
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
    
    _LOGGER.info(f"Found {len(all_text)} text elements")
    
    for i, text in enumerate(all_text):
        text_lower = text.lower()
        
        # Battery SOC - look for percentage
        if '%' in text and len(text) < 10:
            try:
                soc = float(text.replace('%', '').strip())
                if 0 <= soc <= 100:
                    result['battery_soc'] = soc
                    _LOGGER.debug(f"Found SOC: {soc}%")
            except:
                pass
        
        # Power values - look for kW or W
        if 'kw' in text_lower:
            try:
                # Extract number before kW
                import re
                match = re.search(r'([-+]?\d*\.?\d+)\s*kw', text_lower)
                if match:
                    value = float(match.group(1))
                    
                    # Determine what this power value represents based on nearby text
                    context = ' '.join(all_text[max(0, i-2):min(len(all_text), i+3)]).lower()
                    
                    if 'pv' in context or 'solar' in context or 'generation' in context:
                        result['pv_power'] = abs(value)
                        _LOGGER.debug(f"Found PV Power: {value} kW")
                    elif 'battery' in context or 'bat' in context:
                        result['battery_power'] = value  # Can be negative (discharging)
                        _LOGGER.debug(f"Found Battery Power: {value} kW")
                    elif 'grid' in context or 'mains' in context:
                        result['grid_power'] = value  # Negative = export, Positive = import
                        _LOGGER.debug(f"Found Grid Power: {value} kW")
                    elif 'load' in context or 'consumption' in context or 'home' in context:
                        result['load_power'] = abs(value)
                        _LOGGER.debug(f"Found Load Power: {value} kW")
                    elif 'inverter' in context:
                        result['inverter_power'] = abs(value)
                        _LOGGER.debug(f"Found Inverter Power: {value} kW")
            except Exception as e:
                _LOGGER.debug(f"Error parsing kW value '{text}': {e}")
        
        # Energy values - look for kWh with "today" or "total"
        if 'kwh' in text_lower:
            try:
                import re
                match = re.search(r'(\d*\.?\d+)\s*kwh', text_lower)
                if match:
                    value = float(match.group(1))
                    
                    # Look at surrounding context
                    context = ' '.join(all_text[max(0, i-3):min(len(all_text), i+3)]).lower()
                    
                    if 'today' in context or 'day' in context:
                        if 'yield' in context or 'generation' in context or 'pv' in context:
                            result['energy_today'] = value
                            _LOGGER.debug(f"Found Energy Today: {value} kWh")
                        elif 'feed' in context or 'export' in context:
                            result['feed_in_energy_today'] = value
                            _LOGGER.debug(f"Found Feed-in Today: {value} kWh")
                        elif 'consumption' in context or 'import' in context or 'grid' in context:
                            result['grid_consumption_today'] = value
                            _LOGGER.debug(f"Found Grid Consumption Today: {value} kWh")
                        elif 'charge' in context and 'battery' in context:
                            result['battery_charge_today'] = value
                            _LOGGER.debug(f"Found Battery Charge Today: {value} kWh")
                        elif 'discharge' in context and 'battery' in context:
                            result['battery_discharge_today'] = value
                            _LOGGER.debug(f"Found Battery Discharge Today: {value} kWh")
                    elif 'total' in context:
                        if 'yield' in context or 'generation' in context:
                            result['energy_total'] = value
                            _LOGGER.debug(f"Found Energy Total: {value} kWh")
            except Exception as e:
                _LOGGER.debug(f"Error parsing kWh value '{text}': {e}")
    
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
