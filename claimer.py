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
ACTIVATE_BUTTON_XPATH = "//button[contains(text(), 'Activate offer')]"

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
    chrome_options.add_argument("--headless=new")  # Use new headless mode
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
    chrome_options.add_argument("--disable-javascript")  # Only if the site works without JS
    
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
            service = Service()  # Let selenium find it
            logging.info("Using system chromedriver")
        
        # Set service timeout
        service.start()
        
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Set timeouts
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(10)
        
        # Anti-detection script
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Test the driver
        driver.get("about:blank")
        
        return driver
        
    except Exception as e:
        logging.error(f"Failed to setup Chrome driver (attempt {retry_count + 1}): {e}")
        
        # Clean up temp directory
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
                logging.info(f"Cleaned up temp dir: {temp_dir}")
            except:
                pass
    except:
        pass

def human_type(element, text):
    """Type text like a human with random delays"""
    element.clear()
    time.sleep(random.uniform(0.1, 0.3))
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.15))

def human_wait(min_seconds=2, max_seconds=4):
    """Wait for a random human-like duration"""
    time.sleep(random.uniform(min_seconds, max_seconds))

def login_to_octopus(driver, max_retries=3):
    """Login to Octopus Energy account using stealth techniques"""
    for attempt in range(max_retries):
        try:
            logging.info(f"Starting stealth login (attempt {attempt + 1}/{max_retries})...")
            
            # Navigate to login page
            driver.get("https://octopus.energy/login/")
            human_wait(3, 5)
            
            # Check if page loaded properly
            if "octopus.energy" not in driver.current_url:
                raise Exception("Failed to load Octopus Energy login page")

            # Wait for and find email field
            email_field = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, LOGIN_EMAIL_SELECTOR))
            )
            human_wait(1, 2)
            human_type(email_field, OCTOPUS_EMAIL)

            # Find and fill password field
            password_field = WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, LOGIN_PASSWORD_SELECTOR))
            )
            human_wait(1, 2)
            human_type(password_field, OCTOPUS_PASSWORD)

            # Submit form
            submit_btn = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, LOGIN_SUBMIT_SELECTOR))
            )
            human_wait(1, 2)
            ActionChains(driver).move_to_element(submit_btn).pause(random.uniform(0.5, 1.5)).click().perform()
            
            # Wait for successful login with longer timeout
            WebDriverWait(driver, 30).until(
                lambda d: "dashboard" in d.current_url or "account" in d.current_url
            )
            logging.info("✅ Login successful")
            return True
            
        except TimeoutException as e:
            logging.warning(f"⚠️  Login timeout on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                human_wait(5, 10)  # Wait longer between retries
                continue
            else:
                logging.error(f"❌ Login failed after {max_retries} attempts")
                return False
                
        except WebDriverException as e:
            logging.warning(f"⚠️  WebDriver error on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                human_wait(5, 10)
                continue
            else:
                logging.error(f"❌ Login failed after {max_retries} attempts due to WebDriver errors")
                return False
                
        except Exception as e:
            logging.error(f"❌ Login failed on attempt {attempt + 1}: {e}")
            if attempt < max_retries - 1:
                human_wait(5, 10)
                continue
            else:
                return False
    
    return False

def activate_caffe_nero_offer(driver):
    """Navigate to Caffè Nero offer page and activate the offer"""
    try:
        offer_url = f"https://octopus.energy/dashboard/new/accounts/{ACCOUNT_ID}/octoplus/partner/offers/caffe-nero"
        logging.info("Navigating to Caffè Nero offer page...")
        driver.get(offer_url)
        human_wait(3, 5)

        # Check if offer is available
        page_text = driver.page_source.lower()
        unavailable_phrases = [
            "more codes tomorrow",
            "can't be claimed at the moment",
            "no codes available",
            "try again tomorrow"
        ]
        
        if any(phrase in page_text for phrase in unavailable_phrases):
            logging.info("ℹ️  Offer not available today. Will try again tomorrow.")
            return False

        # Look for activate button
        try:
            activate_button = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, ACTIVATE_BUTTON_XPATH))
            )
        except TimeoutException:
            # Try alternative selectors
            alternative_selectors = [
                "//button[contains(text(), 'Claim')]",
                "//button[contains(text(), 'Get code')]",
                "//a[contains(text(), 'Activate')]",
                "button[data-testid*='activate']"
            ]
            
            activate_button = None
            for selector in alternative_selectors:
                try:
                    if selector.startswith("//"):
                        activate_button = driver.find_element(By.XPATH, selector)
                    else:
                        activate_button = driver.find_element(By.CSS_SELECTOR, selector)
                    break
                except NoSuchElementException:
                    continue
            
            if not activate_button:
                logging.error("❌ Could not find activate button")
                return False
        
        # Click the button
        human_wait(1, 2)
        ActionChains(driver).move_to_element(activate_button).pause(random.uniform(0.5, 1.5)).click().perform()
        logging.info("🎯 Clicked activate offer button!")
        human_wait(3, 5)
        
        # Check for success indicators
        success_phrases = [
            "successfully activated",
            "code has been sent",
            "enjoy your coffee",
            "offer activated"
        ]
        
        updated_page_text = driver.page_source.lower()
        if any(phrase in updated_page_text for phrase in success_phrases):
            logging.info("✅ Successfully activated today's Caffè Nero offer!")
            return True
        else:
            logging.warning("⚠️  Activation may have failed - no success message found")
            return False
            
    except Exception as e:
        logging.error(f"❌ Failed to activate Caffè Nero offer: {e}")
        return False

def has_claimed_this_week():
    """Check the state file to see if a claim has been made this week (since Monday)."""
    if not os.path.exists(STATE_FILE):
        return False
    
    try:
        with open(STATE_FILE, 'r') as f:
            last_claim_str = f.read().strip()
        
        if not last_claim_str:
            return False
            
        last_claim_date = datetime.fromisoformat(last_claim_str).date()
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday())  # Monday is 0
        
        if last_claim_date >= start_of_week:
            logging.info(f"✅ Already claimed this week on {last_claim_date}. No action needed.")
            return True
        return False
        
    except (ValueError, OSError) as e:
        logging.warning(f"⚠️  Could not read state file: {e}")
        return False

def record_successful_claim():
    """Write the current timestamp to the state file."""
    try:
        # Ensure directory exists
        state_dir = os.path.dirname(STATE_FILE)
        if state_dir and not os.path.exists(state_dir):
            os.makedirs(state_dir, exist_ok=True)
            
        with open(STATE_FILE, 'w') as f:
            f.write(datetime.now().isoformat())
        logging.info(f"📝 Recorded successful claim in {STATE_FILE}")
        
    except OSError as e:
        logging.error(f"❌ Failed to record claim: {e}")

def main():
    """Main execution with weekly claim logic and retry mechanism."""
    if has_claimed_this_week():
        return  # Exit if we've already claimed this week

    logging.info("🚀 Starting weekly Caffè Nero claim attempt...")
    
    max_driver_retries = 3
    driver = None
    
    for driver_attempt in range(max_driver_retries):
        try:
            logging.info(f"Setting up driver (attempt {driver_attempt + 1}/{max_driver_retries})...")
            driver = setup_stealth_driver(driver_attempt)
            
            if login_to_octopus(driver):
                if activate_caffe_nero_offer(driver):
                    record_successful_claim()
                    logging.info("✅ Claim process completed successfully for the week.")
                    return  # Success, exit
                else:
                    logging.info("❌ Claim attempt failed, will retry on the next run.")
                    return  # Login worked but claim failed, don't retry driver
            else:
                logging.error("❌ Login failed")
                # Continue to retry with new driver
                
        except WebDriverException as e:
            logging.error(f"❌ WebDriver error on attempt {driver_attempt + 1}: {e}")
            if driver_attempt < max_driver_retries - 1:
                logging.info("Retrying with new driver...")
                time.sleep(10)  # Wait before retry
            
        except Exception as e:
            logging.error(f"❌ Unexpected error on attempt {driver_attempt + 1}: {e}")
            if driver_attempt < max_driver_retries - 1:
                logging.info("Retrying with new driver...")
                time.sleep(10)
                
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception as e:
                    logging.warning(f"⚠️  Error closing driver: {e}")
                driver = None
            
            # Clean up temp directories
            cleanup_temp_dirs()
    
    logging.error(f"❌ Failed after {max_driver_retries} driver attempts")

if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup_temp_dirs()
