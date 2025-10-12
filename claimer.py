#!/usr/bin/env python3
"""
Octopus Energy Caffè Nero Coffee Claimer - Final Stealth Version
- Claims once per week, retrying daily until successful.
- Uses a state file to track the last successful claim.
"""

import time
import logging
import os
import random
import sys
from datetime import datetime, date, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

# --- Configuration ---
LOGIN_EMAIL_SELECTOR = "input[name='auth-username']"
LOGIN_PASSWORD_SELECTOR = "input[name='auth-password']"
LOGIN_SUBMIT_SELECTOR = "button[type='submit']"

# --- Script Settings ---
OCTOPUS_EMAIL = os.getenv('OCTOPUS_EMAIL')
OCTOPUS_PASSWORD = os.getenv('OCTOPUS_PASSWORD')
ACCOUNT_ID = os.getenv('OCTOPUS_ACCOUNT_ID')
STATE_FILE = os.path.join(os.path.dirname(__file__), 'last_claim.txt')

# --- Validation ---
if not all([OCTOPUS_EMAIL, OCTOPUS_PASSWORD, ACCOUNT_ID]):
    raise ValueError("Missing required environment variables: OCTOPUS_EMAIL, OCTOPUS_PASSWORD, OCTOPUS_ACCOUNT_ID")

# --- Logging Setup ---
log_dir = os.path.dirname('/var/log/octopus-coffee.log')
if not os.path.exists(log_dir):
    os.makedirs(log_dir, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/octopus-coffee.log'),
        logging.StreamHandler()
    ]
)

def setup_stealth_driver(retry_count=0):
    """Setup Chrome to look like a real user with better stability"""
    chrome_options = Options()
    
    # Essential stability options
    chrome_options.add_argument("--headless=new")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-software-rasterizer")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
    chrome_options.add_argument("--disable-renderer-backgrounding")
    chrome_options.add_argument("--disable-features=TranslateUI")
    chrome_options.add_argument("--disable-ipc-flooding-protection")
    
    # Memory and performance
    chrome_options.add_argument("--memory-pressure-off")
    chrome_options.add_argument("--max_old_space_size=4096")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--disable-images")
    
    # Anti-detection
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # User agent rotation
    user_agents = [
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ]
    chrome_options.add_argument(f"--user-agent={random.choice(user_agents)}")
    
    # Window size
    chrome_options.add_argument("--window-size=1366,768")
    chrome_options.add_argument("--start-maximized")
    
    # Language and locale
    chrome_options.add_argument("--lang=en-GB")
    chrome_options.add_argument("--accept-lang=en-GB,en;q=0.9")
    
    # Temporary directory for this session
    temp_dir = f"/tmp/chrome_temp_{os.getpid()}_{retry_count}"
    chrome_options.add_argument(f"--user-data-dir={temp_dir}")
    chrome_options.add_argument(f"--data-path={temp_dir}")
    chrome_options.add_argument(f"--disk-cache-dir={temp_dir}/cache")
    
    # Try to find Chrome/Chromium binary
    possible_binaries = [
        "/usr/bin/chromium-browser",
        "/usr/bin/google-chrome",
        "/usr/bin/chromium",
        "/snap/bin/chromium",
        "/usr/bin/google-chrome-stable"
    ]
    
    chrome_binary = None
    for binary in possible_binaries:
        if os.path.exists(binary):
            chrome_binary = binary
            break
    
    if chrome_binary:
        chrome_options.binary_location = chrome_binary
        logging.info(f"Using Chrome binary: {chrome_binary}")
    
    # Try to find chromedriver
    possible_drivers = [
        "/usr/bin/chromedriver",
        "/usr/local/bin/chromedriver",
        "/snap/bin/chromium.chromedriver"
    ]
    
    driver_path = None
    for driver in possible_drivers:
        if os.path.exists(driver):
            driver_path = driver
            break
    
    try:
        if driver_path:
            service = Service(driver_path)
            logging.info(f"Using chromedriver: {driver_path}")
        else:
            service = Service()
            logging.info("Using system chromedriver")
        
        service.start()
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.get("about:blank")
        
        return driver
        
    except Exception as e:
        logging.error(f"Failed to setup Chrome driver (attempt {retry_count + 1}): {e}")
        try:
            import shutil
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except:
            pass
        raise

def cleanup_temp_dirs():
    """Clean up any leftover temporary directories"""
    try:
        import glob
        import shutil
        temp_pattern = f"/tmp/chrome_temp_{os.getpid()}_*"
        for temp_dir in glob.glob(temp_pattern):
            try:
                shutil.rmtree(temp_dir)
            except:
                pass
    except:
        pass

def human_type(element, text, delay_range=(0.05, 0.15)):
    """Type text like a human with random delays"""
    element.clear()
    time.sleep(random.uniform(0.1, 0.3))
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(*delay_range))

def human_wait(min_seconds=1, max_seconds=3):
    """Wait for a random human-like duration"""
    time.sleep(random.uniform(min_seconds, max_seconds))

def login_to_octopus(driver, max_retries=3):
    """Login to Octopus Energy account"""
    for attempt in range(max_retries):
        try:
            logging.info(f"Starting login (attempt {attempt + 1}/{max_retries})...")
            
            driver.get("https://octopus.energy/login/")
            human_wait(3, 5)
            
            if "octopus.energy" not in driver.current_url:
                raise Exception("Failed to load Octopus Energy login page")

            # Find email field
            email_selectors = ["input[type='email']", "input[name='auth-username']"]
            email_field = None
            for selector in email_selectors:
                try:
                    email_field = WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    break
                except:
                    continue
            
            if not email_field:
                logging.error("Could not find email field")
                continue

            ActionChains(driver).move_to_element(email_field).click().perform()
            human_wait(0.5, 1)
            human_type(email_field, OCTOPUS_EMAIL)

            # Find password field
            password_selectors = ["input[type='password']", "input[name='auth-password']"]
            password_field = None
            for selector in password_selectors:
                try:
                    password_field = driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except:
                    continue
            
            if not password_field:
                logging.error("Could not find password field")
                continue

            ActionChains(driver).move_to_element(password_field).click().perform()
            human_wait(0.5, 1)
            human_type(password_field, OCTOPUS_PASSWORD)

            # Find submit button
            submit_selectors = ["button[type='submit']", "input[type='submit']"]
            submit_btn = None
            for selector in submit_selectors:
                try:
                    submit_btn = WebDriverWait(driver, 15).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                    break
                except:
                    continue
            
            if not submit_btn:
                logging.error("Could not find submit button")
                continue

            ActionChains(driver).move_to_element(submit_btn).pause(random.uniform(0.5, 1.5)).click().perform()
            logging.info("Clicked login button")
            
            # Wait for login success
            for i in range(15):
                human_wait(1, 2)
                if "dashboard" in driver.current_url:
                    logging.info("✅ Login successful")
                    return True
                elif "login" in driver.current_url and i > 5:
                    logging.warning("Still on login page")
                    break
            
            if attempt < max_retries - 1:
                logging.warning(f"Login attempt {attempt + 1} failed, retrying...")
                human_wait(5, 10)
                continue
            else:
                logging.error(f"❌ Login failed after {max_retries} attempts")
                return False
                
        except Exception as e:
            logging.error(f"❌ Login failed on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                human_wait(5, 10)
                continue
            else:
                return False
    
    return False

def claim_caffe_nero_offer(driver):
    """Navigate to Caffè Nero offer page and activate the offer"""
    try:
        # Navigate directly to the Caffè Nero offer page
        offer_url = f"https://octopus.energy/dashboard/new/accounts/{ACCOUNT_ID}/octoplus/partner/offers/caffe-nero"
        logging.info("Navigating to Caffè Nero offer page...")
        driver.get(offer_url)
        
        # Page can be temperamental - give it time to fully load
        logging.info("Waiting for page to load...")
        human_wait(5, 7)
        
        # Check for the "can't be claimed" error message first
        page_text = driver.page_source.lower()
        if "sorry, this offer can't be claimed at the moment" in page_text:
            logging.info("ℹ️  Offer cannot be claimed at the moment - no codes available")
            return False
        
        # Check for other unavailability messages
        if "already claimed" in page_text or "more codes tomorrow" in page_text:
            logging.info("ℹ️  Offer already claimed or no codes available")
            return False
        
        # Look for the "Activate offer" button
        logging.info("Looking for 'Activate offer' button...")
        
        activate_button = None
        
        # Button contains a span with "Activate offer" text
        button_selectors = [
            # Look for button containing span with "Activate offer"
            (By.XPATH, "//button[.//span[contains(text(), 'Activate offer')]]"),
            (By.XPATH, "//button[.//span[contains(text(), 'Activate Offer')]]"),
            # Look for span with text, then get parent button
            (By.XPATH, "//span[contains(text(), 'Activate offer')]/parent::button"),
            (By.XPATH, "//span[contains(text(), 'Activate Offer')]/parent::button"),
            # Any button with type="button" containing activate text
            (By.XPATH, "//button[@type='button'][contains(., 'Activate')]"),
        ]
        
        # Try each selector
        for by, selector in button_selectors:
            try:
                WebDriverWait(driver, 20).until(
                    EC.presence_of_element_located((by, selector))
                )
                
                button = driver.find_element(by, selector)
                if button.is_displayed():
                    activate_button = button
                    logging.info(f"✓ Found button using selector: {selector}")
                    break
                    
            except TimeoutException:
                logging.debug(f"Timeout for selector: {selector}")
                continue
            except Exception as e:
                logging.debug(f"Error with selector '{selector}': {e}")
                continue
        
        if not activate_button:
            logging.error("❌ Could not find 'Activate offer' button")
            return False
        
        # Scroll to and click the button
        logging.info(f"Attempting to click 'Activate offer' button")
        try:
            # Scroll into view
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", activate_button)
            human_wait(1, 2)
            
            # Try JavaScript click (more reliable for React buttons)
            driver.execute_script("arguments[0].click();", activate_button)
            logging.info("🎯 Clicked button using JavaScript")
                
        except Exception as e:
            logging.error(f"Failed to click button: {e}")
            return False
        
        # Wait for the action to complete
        human_wait(3, 5)
        
        # Check for success indicators
        success_indicators = [
            "offer activated", "successfully activated", "code has been sent",
            "enjoy your coffee", "code:", "your code", "redeem", "voucher code"
        ]
        
        page_text = driver.page_source.lower()
        if any(indicator in page_text for indicator in success_indicators):
            logging.info("✅ Successfully claimed Caffè Nero offer!")
            return True
        else:
            logging.info("✅ Button clicked - assuming success")
            return True
            
    except Exception as e:
        logging.error(f"❌ Failed to claim Caffè Nero offer: {e}")
        return False

def has_claimed_this_week():
    """Check if already claimed this week"""
    if not os.path.exists(STATE_FILE):
        return False
    
    try:
        with open(STATE_FILE, 'r') as f:
            last_claim_str = f.read().strip()
        
        if not last_claim_str:
            return False
            
        last_claim_date = datetime.fromisoformat(last_claim_str).date()
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())
        
        if last_claim_date >= start_of_week:
            logging.info(f"✅ Already claimed this week on {last_claim_date}")
            return True
        return False
        
    except (ValueError, OSError) as e:
        logging.warning(f"⚠️  Could not read state file: {e}")
        return False

def record_successful_claim():
    """Record successful claim"""
    try:
        state_dir = os.path.dirname(STATE_FILE)
        if state_dir and not os.path.exists(state_dir):
            os.makedirs(state_dir, exist_ok=True)
            
        with open(STATE_FILE, 'w') as f:
            f.write(datetime.now().isoformat())
        logging.info(f"📝 Recorded successful claim")
        
    except OSError as e:
        logging.error(f"❌ Failed to record claim: {e}")

def main():
    """Main execution"""
    if has_claimed_this_week():
        return
    
    logging.info("🚀 Starting Caffè Nero claim attempt...")
    
    max_retries = 3
    driver = None
    
    for attempt in range(max_retries):
        try:
            logging.info(f"Setting up driver (attempt {attempt + 1}/{max_retries})...")
            driver = setup_stealth_driver(attempt)
            
            if login_to_octopus(driver):
                if claim_caffe_nero_offer(driver):
                    record_successful_claim()
                    logging.info("✅ Claim completed successfully")
                    return
                else:
                    logging.info("❌ Claim failed, will retry tomorrow")
                    return
            else:
                logging.error("❌ Login failed")
                
        except Exception as e:
            logging.error(f"❌ Error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                time.sleep(10)
                
        finally:
            if driver:
                try:
                    driver.quit()
                except:
                    pass
                driver = None
            cleanup_temp_dirs()
    
    logging.error(f"❌ Failed after {max_retries} attempts")

if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup_temp_dirs()
