#!/usr/bin/env python3
"""
Octopus Energy Caffè Nero Coffee Claimer
"""

import time
import logging
import os
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import TimeoutException

# Configuration
OCTOPUS_EMAIL = os.getenv('OCTOPUS_EMAIL', 'your-email@example.com')
OCTOPUS_PASSWORD = os.getenv('OCTOPUS_PASSWORD', 'your-password')
ACCOUNT_ID = os.getenv('OCTOPUS_ACCOUNT_ID', 'ACCOUNT-ID')

# Setup logging
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
    
    # Essential options
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    
    # Anti-detection options
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    # Real user agent
    chrome_options.add_argument("--user-agent=Mozilla/5.0 (X11; Linux aarch64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    
    # Normal window size
    chrome_options.add_argument("--window-size=1366,768")
    
    # Language and locale
    chrome_options.add_argument("--lang=en-GB")
    chrome_options.add_argument("--accept-lang=en-GB,en;q=0.9")
    
    chrome_options.binary_location = "/usr/bin/chromium-browser"
    service = Service('/usr/bin/chromedriver')
    
    driver = webdriver.Chrome(service=service, options=chrome_options)
    
    # Execute script to hide webdriver property
    driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
    
    return driver

def human_type(element, text, delay_range=(0.05, 0.15)):
    """Type text like a human with random delays"""
    element.clear()
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(*delay_range))

def human_wait(min_seconds=1, max_seconds=3):
    """Wait for a random human-like duration"""
    time.sleep(random.uniform(min_seconds, max_seconds))

def login_to_octopus(driver):
    """Login to Octopus Energy account using stealth techniques"""
    try:
        logging.info("Starting stealth login process...")
        
        driver.get("https://octopus.energy/login")
        human_wait(2, 4)
        
        # Find email field with multiple selectors
        email_selectors = [
            "input[type='email']",
            "input[name='auth-username']", 
        ]
        
        email_field = None
        for selector in email_selectors:
            try:
                email_field = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                logging.info(f"Found email field with selector: {selector}")
                break
            except:
                continue
        
        if not email_field:
            logging.error("Could not find email field")
            return False
        
        # Human-like interaction with email field
        ActionChains(driver).move_to_element(email_field).click().perform()
        human_wait(0.5, 1)
        human_type(email_field, OCTOPUS_EMAIL)
        
        # Find password field
        password_selectors = [
            "input[type='password']",
            "input[name='auth-password']",
        ]
        
        password_field = None
        for selector in password_selectors:
            try:
                password_field = driver.find_element(By.CSS_SELECTOR, selector)
                logging.info(f"Found password field with selector: {selector}")
                break
            except:
                continue
        
        if not password_field:
            logging.error("Could not find password field")
            return False
        
        # Human-like interaction with password field
        ActionChains(driver).move_to_element(password_field).click().perform()
        human_wait(0.5, 1)
        human_type(password_field, OCTOPUS_PASSWORD)
        
        # Find and click submit button
        submit_selectors = [
            "button[type='submit']",
            "input[type='submit']"
        ]
        
        submit_btn = None
        for selector in submit_selectors:
            try:
                submit_btn = driver.find_element(By.CSS_SELECTOR, selector)
                break
            except:
                continue
        
        if not submit_btn:
            logging.error("Could not find submit button")
            return False
        
        # Human-like click on submit
        ActionChains(driver).move_to_element(submit_btn).pause(random.uniform(0.5, 1.5)).click().perform()
        logging.info("Clicked login button")
        
        # Wait for login to complete
        for i in range(15):
            human_wait(1, 2)
            if "dashboard" in driver.current_url:
                logging.info("✅ Login successful")
                return True
            elif "login" in driver.current_url and i > 5:
                logging.error("Still on login page - login may have failed")
                return False
        
        logging.error("Login timeout")
        return False
        
    except Exception as e:
        logging.error(f"Login failed: {str(e)}")
        return False

def activate_caffe_nero_offer(driver):
    """Navigate to Caffè Nero offer page and activate the offer"""
    try:
        offer_url = f"https://octopus.energy/dashboard/new/accounts/{ACCOUNT_ID}/octoplus/partner/offers/caffe-nero"
        logging.info("Navigating to Caffè Nero offer page...")
        driver.get(offer_url)
        
        human_wait(3, 5)
        
        # Check if already activated
        page_text = driver.page_source.lower()
        if any(phrase in page_text for phrase in ["Sorry, this offer can't be claimed at the moment.", "offer activated", "more codes tomorrow"]):
            logging.info("ℹ️  Offer already activated or no more codes available today")
            return True
        
        # Look for "Activate offer" button with multiple selectors
        activate_selectors = [
            # XPath selectors for text matching
            "//button[contains(text(), 'Activate offer')]",
            "//button[contains(text(), 'Activate')]",
            "//a[contains(text(), 'Activate offer')]",
            "//a[contains(text(), 'Activate')]",
            # CSS selectors for common button patterns
            "button[class*='activate']",
            "a[class*='activate']",
            # Generic button selectors as fallback
            "button[type='submit']",
            "button[class*='primary']",
            "button[class*='cta']"
        ]
        
        activate_button = None
        
        # Try each selector
        for selector in activate_selectors:
            try:
                if selector.startswith("//"):
                    # XPath selector
                    activate_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                else:
                    # CSS selector
                    activate_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                    )
                
                logging.info(f"Found activate button with selector: {selector}")
                break
            except TimeoutException:
                continue
        
        if not activate_button:
            # Last resort - find all buttons and look for relevant text
            try:
                all_buttons = driver.find_elements(By.TAG_NAME, "button")
                all_links = driver.find_elements(By.TAG_NAME, "a")
                
                for element in all_buttons + all_links:
                    element_text = element.text.lower()
                    if any(word in element_text for word in ["activate", "claim", "get"]):
                        activate_button = element
                        logging.info(f"Found button by text content: '{element.text}'")
                        break
            except:
                pass
        
        if not activate_button:
            logging.error("Could not find activate offer button")
            # Log page source for debugging
            logging.debug("Page source snippet for debugging:")
            logging.debug(driver.page_source[:2000])
            return False
        
        # Human-like click on activate button
        ActionChains(driver).move_to_element(activate_button).pause(random.uniform(0.5, 1.5)).click().perform()
        logging.info("🎯 Clicked activate offer button!")
        
        human_wait(3, 5)
        
        # Check for success indicators
        success_indicators = [
            "offer activated",
            "successfully activated",
            "code:",
            "your code",
            "redeem"
        ]
        
        page_text = driver.page_source.lower()
        if any(indicator in page_text for indicator in success_indicators):
            logging.info("✅ Successfully activated Caffè Nero offer!")
        else:
            logging.info("✅ Activate button clicked - offer processing")
        
        return True
        
    except Exception as e:
        logging.error(f"Failed to activate Caffè Nero offer: {str(e)}")
        return False

def main():
    """Main execution"""
    logging.info("🚀 Starting stealth Caffè Nero activation process")
    
    driver = None
    try:
        driver = setup_stealth_driver()
        
        if login_to_octopus(driver) and activate_caffe_nero_offer(driver):
            logging.info("✅ Caffè Nero activation process completed successfully")
        else:
            logging.error("❌ Caffè Nero activation process failed")
            
    except Exception as e:
        logging.error(f"❌ Unexpected error: {str(e)}")
        
    finally:
        if driver:
            driver.quit()

if __name__ == "__main__":
    main()
