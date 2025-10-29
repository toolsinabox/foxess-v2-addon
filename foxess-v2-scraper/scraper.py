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
    """Parse raw data from Foxess dashboard."""
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
    
    _LOGGER.info(f"Parsing {len(all_text)} text elements")
    
    import re
    
    for i, text in enumerate(all_text):
        text_lower = text.lower().strip()
        
        # Get context (previous and next text elements)
        prev_text = all_text[i-1].lower() if i > 0 else ""
        next_text = all_text[i+1].lower() if i < len(all_text) - 1 else ""
        prev2_text = all_text[i-2].lower() if i > 1 else ""
        
        # Battery SOC - look for "SOC: 85 %" or just "85%"
        if 'soc' in prev_text or 'soc' in text_lower:
            match = re.search(r'(\d+)\s*%', text)
            if match:
                result['battery_soc'] = float(match.group(1))
                _LOGGER.debug(f"Found Battery SOC: {match.group(1)}%")
        
        # Solar/PV Power - look for "Solar" label followed by kW value
        if 'solar' in prev_text or 'solar' in prev2_text:
            match = re.search(r'([\d.]+)\s*kw', text_lower)
            if match:
                result['pv_power'] = float(match.group(1))
                _LOGGER.debug(f"Found Solar Power: {match.group(1)} kW")
        
        # Load Power - look for "Load" label followed by kW value
        if 'load' in prev_text or 'load' in prev2_text:
            match = re.search(r'([\d.]+)\s*kw', text_lower)
            if match:
                result['load_power'] = float(match.group(1))
                _LOGGER.debug(f"Found Load Power: {match.group(1)} kW")
        
        # Grid Power - look for "Grid Importing" or "Grid Exporting"
        if 'grid' in prev_text and ('import' in prev_text or 'export' in prev_text):
            # Can be in W or kW
            match_kw = re.search(r'([\d.]+)\s*kw', text_lower)
            match_w = re.search(r'([\d.]+)\s*w', text_lower)
            if match_kw:
                # Positive for import, negative for export
                value = float(match_kw.group(1))
                result['grid_power'] = value if 'import' in prev_text else -value
                _LOGGER.debug(f"Found Grid Power: {value} kW ({'import' if 'import' in prev_text else 'export'})")
            elif match_w and not match_kw:  # Only if not kW
                value = float(match_w.group(1)) / 1000  # Convert W to kW
                result['grid_power'] = value if 'import' in prev_text else -value
                _LOGGER.debug(f"Found Grid Power: {value} kW (from W)")
        
        # Battery Charging/Discharging Power
        if 'charging' in prev_text or 'charging' in text_lower:
            match = re.search(r'([\d.]+)\s*kw', text_lower)
            if match:
                result['battery_power'] = float(match.group(1))  # Positive = charging
                _LOGGER.debug(f"Found Battery Charging: {match.group(1)} kW")
        elif 'discharging' in prev_text or 'discharging' in text_lower:
            match = re.search(r'([\d.]+)\s*kw', text_lower)
            if match:
                result['battery_power'] = -float(match.group(1))  # Negative = discharging
                _LOGGER.debug(f"Found Battery Discharging: {match.group(1)} kW")
        
        # PV Yield - look for "PV Yield" or "PV Yield Today/Total"
        if 'pv yield' in prev_text or 'pv yield' in prev2_text:
            # Format: "3.8 / 8.8" (Today / Total)
            match = re.search(r'([\d.]+)\s*/\s*([\d.]+)', text)
            if match:
                result['energy_today'] = float(match.group(1))
                result['energy_total'] = float(match.group(2))
                _LOGGER.debug(f"Found PV Yield: {match.group(1)} / {match.group(2)} kWh")
        
        # Feed-in Energy
        if 'feed' in prev_text or 'feed-in' in prev_text:
            match = re.search(r'([\d.]+)\s*/\s*([\d.]+)', text)
            if match:
                result['feed_in_energy_today'] = float(match.group(1))
                _LOGGER.debug(f"Found Feed-in: {match.group(1)} kWh today")
        
        # Consumption
        if 'consumption' in prev_text:
            match = re.search(r'([\d.]+)\s*/\s*([\d.]+)', text)
            if match:
                result['grid_consumption_today'] = float(match.group(1))
                _LOGGER.debug(f"Found Consumption: {match.group(1)} kWh today")
    
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
