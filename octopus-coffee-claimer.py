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
from datetime import datetime, date, timedelta
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains

# --- Configuration ---
# For maximum efficiency, replace these with the specific selectors from your browser's "Inspect" tool.
LOGIN_EMAIL_SELECTOR = "input[name='auth-username']"
LOGIN_PASSWORD_SELECTOR = "input[name='auth-password']"
LOGIN_SUBMIT_SELECTOR = "button[type='submit']"
ACTIVATE_BUTTON_XPATH = "//button[contains(text(), 'Activate offer')]"

# --- Script Settings ---
OCTOPUS_EMAIL = os.getenv('OCTOPUS_EMAIL')
OCTOPUS_PASSWORD = os.getenv('OCTOPUS_PASSWORD')
ACCOUNT_ID = os.getenv('OCTOPUS_ACCOUNT_ID')
STATE_FILE = os.path.join(os.path.dirname(__file__), 'last_claim.txt')

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('/var/log/octopus-coffee.log'),
        logging.StreamHandler()
    ]
)

def setup_stealth_driver():
    """Setup Chrome to look like a real user"""
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    chrome_options.add_argument("--window-size=1366,768")
    chrome_options.binary_location = "/usr/bin/chromium-browser"
    service = Service('/usr/bin/chromedriver')
    driver = webdriver.Chrome(service=service, options=chrome_options)
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    return driver

def human_type(element, text):
    """Type text like a human with random delays"""
    element.clear()
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(0.05, 0.15))

def human_wait(min_seconds=2, max_seconds=4):
    """Wait for a random human-like duration"""
    time.sleep(random.uniform(min_seconds, max_seconds))

def login_to_octopus(driver):
    """Login to Octopus Energy account using stealth techniques"""
    try:
        logging.info("Starting stealth login...")
        driver.get("https://octopus.energy/login/")
        human_wait()

        email_field = WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, LOGIN_EMAIL_SELECTOR))
        )
        human_type(email_field, OCTOPUS_EMAIL)

        password_field = driver.find_element(By.CSS_SELECTOR, LOGIN_PASSWORD_SELECTOR)
        human_type(password_field, OCTOPUS_PASSWORD)

        submit_btn = driver.find_element(By.CSS_SELECTOR, LOGIN_SUBMIT_SELECTOR)
        ActionChains(driver).move_to_element(submit_btn).pause(random.uniform(0.5, 1.5)).click().perform()
        
        WebDriverWait(driver, 20).until(lambda d: "dashboard" in d.current_url)
        logging.info("✅ Login successful")
        return True
    except Exception as e:
        logging.error(f"❌ Login failed: {e}")
        return False

def activate_caffe_nero_offer(driver):
    """Navigate to Caffè Nero offer page and activate the offer"""
    try:
        offer_url = f"https://octopus.energy/dashboard/new/accounts/{ACCOUNT_ID}/octoplus/partner/offers/caffe-nero"
        logging.info("Navigating to Caffè Nero offer page...")
        driver.get(offer_url)
        human_wait()

        page_text = driver.page_source.lower()
        if "more codes tomorrow" in page_text or "can't be claimed at the moment" in page_text:
            logging.info("ℹ️  Offer not available today. Will try again tomorrow.")
            return False # Return False because the claim was not successful

        activate_button = WebDriverWait(driver, 15).until(
            EC.element_to_be_clickable((By.XPATH, ACTIVATE_BUTTON_XPATH))
        )
        
        ActionChains(driver).move_to_element(activate_button).pause(random.uniform(0.5, 1.5)).click().perform()
        logging.info("🎯 Clicked activate offer button!")
        human_wait()
        
        logging.info("✅ Successfully activated today's Caffè Nero offer!")
        return True
    except Exception as e:
        logging.error(f"❌ Failed to activate Caffè Nero offer: {e}")
        return False

def has_claimed_this_week():
    """Check the state file to see if a claim has been made this week (since Monday)."""
    if not os.path.exists(STATE_FILE):
        return False
    
    with open(STATE_FILE, 'r') as f:
        last_claim_str = f.read().strip()
    
    try:
        last_claim_date = datetime.fromisoformat(last_claim_str).date()
        today = date.today()
        start_of_week = today - timedelta(days=today.weekday()) # Monday is 0
        
        if last_claim_date >= start_of_week:
            logging.info(f"✅ Already claimed this week on {last_claim_date}. No action needed.")
            return True
        return False
    except:
        return False

def record_successful_claim():
    """Write the current timestamp to the state file."""
    with open(STATE_FILE, 'w') as f:
        f.write(datetime.now().isoformat())
    logging.info(f"📝 Recorded successful claim in {STATE_FILE}")

def main():
    """Main execution with weekly claim logic."""
    if has_claimed_this_week():
        return # Exit if we've already claimed this week

    logging.info("🚀 Starting weekly Caffè Nero claim attempt...")
    driver = None
    try:
        driver = setup_stealth_driver()
        if login_to_octopus(driver):
            if activate_caffe_nero_offer(driver):
                record_successful_claim()
                logging.info("✅ Claim process completed successfully for the week.")
            else:
                logging.info("❌ Claim attempt failed, will retry on the next run.")
        else:
            logging.error("❌ Login failed, aborting.")
    except Exception as e:
        logging.error(f"❌ An unexpected error occurred: {e}")
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
