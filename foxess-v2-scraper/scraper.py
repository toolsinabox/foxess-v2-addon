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
    """Get or create Selenium driver with robust login."""
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
    wait = WebDriverWait(driver, 20)
    
    # Login
    _LOGGER.info("Logging in to Foxess V2...")
    driver.get('https://www.foxesscloud.com/v2/')
    
    # Wait for page to fully load
    time.sleep(8)
    
    try:
        # Wait for username field to be visible
        _LOGGER.info("Waiting for login form...")
        username_input = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="text"], input[type="email"]')))
        password_input = driver.find_element(By.CSS_SELECTOR, 'input[type="password"]')
        
        _LOGGER.info("Filling credentials...")
        username_input.clear()
        username_input.send_keys(USERNAME)
        time.sleep(1)
        
        password_input.clear()
        password_input.send_keys(PASSWORD)
        time.sleep(2)
        
        # Method 1: Find and click the "Log In" button using multiple approaches
        login_success = False
        
        # Try 1: Click button with text "Log In"
        try:
            _LOGGER.info("Attempt 1: Finding 'Log In' button by text...")
            buttons = driver.find_elements(By.TAG_NAME, 'button')
            for btn in buttons:
                if 'log' in btn.text.lower() and 'in' in btn.text.lower():
                    _LOGGER.info(f"Found button with text: '{btn.text}'")
                    btn.click()
                    login_success = True
                    break
        except Exception as e:
            _LOGGER.debug(f"Method 1 failed: {e}")
        
        # Try 2: JavaScript click on button
        if not login_success:
            try:
                _LOGGER.info("Attempt 2: JavaScript click...")
                buttons = driver.find_elements(By.TAG_NAME, 'button')
                for btn in buttons:
                    if 'log' in btn.text.lower() and 'in' in btn.text.lower():
                        driver.execute_script("arguments[0].click();", btn)
                        login_success = True
                        break
            except Exception as e:
                _LOGGER.debug(f"Method 2 failed: {e}")
        
        # Try 3: Submit form directly
        if not login_success:
            try:
                _LOGGER.info("Attempt 3: Submitting form...")
                form = driver.find_element(By.TAG_NAME, 'form')
                form.submit()
                login_success = True
            except Exception as e:
                _LOGGER.debug(f"Method 3 failed: {e}")
        
        # Try 4: Press Enter on password field
        if not login_success:
            try:
                _LOGGER.info("Attempt 4: Pressing Enter on password field...")
                from selenium.webdriver.common.keys import Keys
                password_input.send_keys(Keys.RETURN)
                login_success = True
            except Exception as e:
                _LOGGER.debug(f"Method 4 failed: {e}")
        
        if not login_success:
            raise Exception("All login methods failed")
        
        _LOGGER.info("Login button clicked, waiting for redirect...")
        time.sleep(15)  # Wait for login to complete
        
        current_url = driver.current_url
        _LOGGER.info(f"After login, URL is: {current_url}")
        
        # Check if login was successful
        if 'login' in current_url.lower():
            # Try one more time with longer wait
            _LOGGER.warning("Still on login page, waiting longer...")
            time.sleep(10)
            current_url = driver.current_url
            
            if 'login' in current_url.lower():
                _LOGGER.error("Login failed - still on login page after 25 seconds")
                try:
                    driver.save_screenshot('/tmp/foxess_login_failed.png')
                except:
                    pass
                raise Exception("Login failed - credentials may be incorrect or site changed")
        
        _LOGGER.info("✓ Login successful!")
        last_login = current_time
        
        return driver
        
    except Exception as e:
        _LOGGER.error(f"Login error: {e}")
        if driver:
            try:
                driver.quit()
            except:
                pass
        raise


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
        text_stripped = text.strip()
        text_lower = text_stripped.lower()
        
        # Get context
        prev_text = all_text[i-1].lower() if i > 0 else ""
        next_text = all_text[i+1].lower() if i < len(all_text) - 1 else ""
        prev2_text = all_text[i-2].lower() if i > 1 else ""
        
        # Battery SOC - look for percentage with "SOC" or "soc" nearby
        if '%' in text_stripped:
            if 'soc' in text_lower or 'soc' in prev_text or 'soc' in prev2_text:
                match = re.search(r'(\d+)\s*%', text_stripped)
                if match:
                    result['battery_soc'] = float(match.group(1))
                    _LOGGER.debug(f"Found Battery SOC: {match.group(1)}%")
        
        # Solar Power - look for "Solar" label, get NEXT element (not capacity!)
        # Avoid "PV Capacity" which is in kWp
        if 'solar' in text_lower and 'capacity' not in text_lower and 'kwp' not in next_text:
            # Check next element for kW value
            if i < len(all_text) - 1:
                next_elem = all_text[i+1]
                match = re.search(r'([\d.]+)\s*kw', next_elem.lower())
                if match and 'kwp' not in next_elem.lower():
                    result['pv_power'] = float(match.group(1))
                    _LOGGER.debug(f"Found Solar Power: {match.group(1)} kW")
        
        # Load Power
        if 'load' in text_lower and 'kw' not in text_lower:
            if i < len(all_text) - 1:
                next_elem = all_text[i+1]
                match = re.search(r'([\d.]+)\s*kw', next_elem.lower())
                if match:
                    result['load_power'] = float(match.group(1))
                    _LOGGER.debug(f"Found Load Power: {match.group(1)} kW")
        
        # Grid Importing/Exporting
        if 'grid' in text_lower and ('import' in text_lower or 'export' in text_lower):
            if i < len(all_text) - 1:
                next_elem = all_text[i+1]
                # Can be W or kW
                match_kw = re.search(r'([\d.]+)\s*kw', next_elem.lower())
                match_w = re.search(r'([\d.]+)\s*w\b', next_elem.lower())
                
                if match_kw:
                    value = float(match_kw.group(1))
                    result['grid_power'] = value if 'import' in text_lower else -value
                    _LOGGER.debug(f"Found Grid Power: {value} kW")
                elif match_w and not match_kw:
                    value = float(match_w.group(1)) / 1000
                    result['grid_power'] = value if 'import' in text_lower else -value
                    _LOGGER.debug(f"Found Grid Power: {value} kW (from W)")
        
        # Battery Charging/Discharging
        if 'charging' in text_lower:
            if i < len(all_text) - 1:
                next_elem = all_text[i+1]
                match = re.search(r'([\d.]+)\s*kw', next_elem.lower())
                if match:
                    result['battery_power'] = float(match.group(1))
                    _LOGGER.debug(f"Found Battery Charging: {match.group(1)} kW")
        elif 'discharging' in text_lower:
            if i < len(all_text) - 1:
                next_elem = all_text[i+1]
                match = re.search(r'([\d.]+)\s*kw', next_elem.lower())
                if match:
                    result['battery_power'] = -float(match.group(1))
                    _LOGGER.debug(f"Found Battery Discharging: {match.group(1)} kW")
        
        # PV Yield - format "3.8 / 8.8" with "Today/Total (kWh)" label
        if 'pv yield' in text_lower or ('pv' in prev_text and 'yield' in prev_text):
            # Look for slash pattern in next few elements
            for j in range(i, min(i+3, len(all_text))):
                elem = all_text[j]
                match = re.search(r'([\d.]+)\s*/\s*([\d.]+)', elem)
                if match:
                    result['energy_today'] = float(match.group(1))
                    result['energy_total'] = float(match.group(2))
                    _LOGGER.debug(f"Found PV Yield: Today={match.group(1)}, Total={match.group(2)} kWh")
                    break
        
        # Feed-in Energy - format "0.1 / 5.9"
        if 'feed' in text_lower and 'in' in text_lower:
            for j in range(i, min(i+3, len(all_text))):
                elem = all_text[j]
                match = re.search(r'([\d.]+)\s*/\s*([\d.]+)', elem)
                if match:
                    result['feed_in_energy_today'] = float(match.group(1))
                    _LOGGER.debug(f"Found Feed-in: {match.group(1)} kWh today")
                    break
        
        # Consumption - format "0.1 / 39.0"
        if 'consumption' in text_lower:
            for j in range(i, min(i+3, len(all_text))):
                elem = all_text[j]
                match = re.search(r'([\d.]+)\s*/\s*([\d.]+)', elem)
                if match:
                    result['grid_consumption_today'] = float(match.group(1))
                    _LOGGER.debug(f"Found Consumption: {match.group(1)} kWh today")
                    break
    
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
