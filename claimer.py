#!/usr/bin/env python3
"""
Octopus Energy Caffè Nero Coffee Claimer

- Claims once per week, retrying daily until successful.
- Uses a state file to track the last successful claim.
- Uses standard Selenium with stealth options.
"""

import fcntl
import glob
import logging
import os
import random
import shutil
import socket
import sys
import time
from datetime import date, datetime, timedelta

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

OCTOPUS_EMAIL    = os.getenv("OCTOPUS_EMAIL")
OCTOPUS_PASSWORD = os.getenv("OCTOPUS_PASSWORD")
ACCOUNT_ID       = os.getenv("OCTOPUS_ACCOUNT_ID")

SCRIPT_DIR      = os.path.dirname(os.path.abspath(__file__))
STATE_FILE      = os.path.join(SCRIPT_DIR, "last_claim.txt")
LOG_FILE        = os.path.join(SCRIPT_DIR, "octopus-coffee.log")
SCREENSHOT_DIR  = os.path.join(SCRIPT_DIR, "screenshots")

PAGE_LOAD_TIMEOUT  = 45   # seconds
MAX_DRIVER_RETRIES = 3
MAX_LOGIN_RETRIES  = 3
MAX_CLAIM_RETRIES  = 2    # retries for the claim step itself

USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

CHROME_BINARIES = [
    "/usr/bin/chromium-browser",
    "/usr/bin/google-chrome",
    "/usr/bin/chromium",
    "/snap/bin/chromium",
    "/usr/bin/google-chrome-stable",
]

CHROME_DRIVERS = [
    "/usr/bin/chromedriver",
    "/usr/local/bin/chromedriver",
    "/snap/bin/chromium.chromedriver",
]

# ---------------------------------------------------------
# Validation
# ---------------------------------------------------------

if not all([OCTOPUS_EMAIL, OCTOPUS_PASSWORD, ACCOUNT_ID]):
    raise ValueError(
        "Missing required environment variables: "
        "OCTOPUS_EMAIL, OCTOPUS_PASSWORD, OCTOPUS_ACCOUNT_ID"
    )

# ---------------------------------------------------------
# Logging
# ---------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------

def human_wait(min_s: float = 1.0, max_s: float = 3.0) -> None:
    time.sleep(random.uniform(min_s, max_s))

def human_type(element, text: str, delay_range=(0.06, 0.14)) -> None:
    """Clear the field and type character-by-character with jitter."""
    element.clear()
    time.sleep(random.uniform(0.15, 0.35))
    for char in text:
        element.send_keys(char)
        time.sleep(random.uniform(*delay_range))

def exponential_backoff(attempt: int, base: float = 5.0, cap: float = 60.0) -> None:
    delay = min(base * (2 ** attempt) + random.uniform(0, 2), cap)
    log.info(f"⏳ Backing off for {delay:.1f}s before retry {attempt + 1}...")
    time.sleep(delay)

def check_network(host: str = "octopus.energy", port: int = 443, timeout: float = 10.0) -> bool:
    """Return True if the target host is reachable."""
    try:
        socket.setdefaulttimeout(timeout)
        socket.create_connection((host, port))
        return True
    except OSError:
        return False

def cleanup_temp_dirs(pid: int = None) -> None:
    """Remove leftover Chrome temp directories for this process (or all)."""
    pattern = f"/tmp/chrome_temp_{pid or os.getpid()}_*"
    for d in glob.glob(pattern):
        try:
            shutil.rmtree(d, ignore_errors=True)
        except Exception:
            pass

def save_screenshot(driver, label: str) -> None:
    """Best-effort screenshot; never raises."""
    try:
        os.makedirs(SCREENSHOT_DIR, exist_ok=True)
        ts   = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(SCREENSHOT_DIR, f"caffe_nero_{ts}_{label}.png")
        try:
            orig = driver.get_window_size()
            w = driver.execute_script("return document.body.scrollWidth")
            h = driver.execute_script("return document.body.scrollHeight")
            driver.set_window_size(w, h)
            time.sleep(0.3)
            driver.save_screenshot(path)
            driver.set_window_size(orig["width"], orig["height"])
        except Exception:
            driver.save_screenshot(path)
        log.info(f"📸 Screenshot saved: {label}")
    except Exception as exc:
        log.warning(f"⚠️  Screenshot failed ({label}): {exc}")

def page_text(driver) -> str:
    """Return lowercased page source; empty string on failure."""
    try:
        return driver.page_source.lower()
    except Exception:
        return ""

# ---------------------------------------------------------
# Driver setup
# ---------------------------------------------------------

def _find_first(paths: list) -> str | None:
    return next((p for p in paths if os.path.exists(p)), None)

def setup_driver(attempt: int = 0) -> webdriver.Chrome:
    """
    Build a stealth Chrome driver using standard Selenium.
    """
    opts = Options()

    # Headless + stability
    opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--disable-software-rasterizer")
    opts.add_argument("--disable-background-timer-throttling")
    opts.add_argument("--disable-backgrounding-occluded-windows")
    opts.add_argument("--disable-renderer-backgrounding")
    opts.add_argument("--disable-ipc-flooding-protection")
    opts.add_argument("--disable-features=TranslateUI")

    # Memory
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-plugins")
    opts.add_argument("--disable-images")
    opts.add_argument("--js-flags=--max-old-space-size=512")

    # Anti-detection
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_experimental_option("useAutomationExtension", False)

    # Locale + UA
    opts.add_argument("--lang=en-GB")
    opts.add_argument("--accept-lang=en-GB,en;q=0.9")
    opts.add_argument(f"--user-agent={random.choice(USER_AGENTS)}")
    opts.add_argument("--window-size=1366,768")

    # Isolated temp profile
    temp_dir = f"/tmp/chrome_temp_{os.getpid()}_{attempt}"
    opts.add_argument(f"--user-data-dir={temp_dir}")
    opts.add_argument(f"--disk-cache-dir={temp_dir}/cache")

    binary = _find_first(CHROME_BINARIES)
    if binary:
        opts.binary_location = binary
        log.info(f"Chrome binary: {binary}")
    else:
        log.warning("No known Chrome binary found — relying on PATH")

    driver_path = _find_first(CHROME_DRIVERS)
    service = Service(driver_path) if driver_path else Service()
    if driver_path:
        log.info(f"Chromedriver: {driver_path}")

    try:
        driver = webdriver.Chrome(service=service, options=opts)
        driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)
        
        # Patch out the webdriver flag
        driver.execute_cdp_cmd(
            "Page.addScriptToEvaluateOnNewDocument",
            {"source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"},
        )
        driver.get("about:blank")
        log.info("✅ Driver initialised successfully")
        return driver
    except Exception as exc:
        shutil.rmtree(temp_dir, ignore_errors=True)
        raise RuntimeError(f"Driver setup failed: {exc}") from exc

# ---------------------------------------------------------
# Login
# ---------------------------------------------------------

def _wait_for_element(driver, selectors: list, timeout: float = 20):
    """Try each (By, selector) pair; return the first match or None."""
    for by, sel in selectors:
        try:
            el = WebDriverWait(driver, timeout).until(
                EC.presence_of_element_located((by, sel))
            )
            if el.is_displayed():
                return el
        except (TimeoutException, NoSuchElementException):
            continue
    return None

def login(driver) -> bool:
    """Log in to Octopus Energy."""
    login_url = "https://octopus.energy/login/"

    for attempt in range(MAX_LOGIN_RETRIES):
        try:
            log.info(f"🔑 Login attempt {attempt + 1}/{MAX_LOGIN_RETRIES}...")
            driver.get(login_url)
            human_wait(3, 5)

            if "octopus.energy" not in driver.current_url:
                raise RuntimeError(f"Unexpected URL after navigation: {driver.current_url}")

            email_field = _wait_for_element(driver, [
                (By.CSS_SELECTOR, "input[type='email']"),
                (By.CSS_SELECTOR, "input[name='auth-username']"),
            ])
            if not email_field:
                raise RuntimeError("Email field not found")
            ActionChains(driver).move_to_element(email_field).click().perform()
            human_wait(0.4, 0.9)
            human_type(email_field, OCTOPUS_EMAIL)

            pwd_field = _wait_for_element(driver, [
                (By.CSS_SELECTOR, "input[type='password']"),
                (By.CSS_SELECTOR, "input[name='auth-password']"),
            ])
            if not pwd_field:
                raise RuntimeError("Password field not found")
            ActionChains(driver).move_to_element(pwd_field).click().perform()
            human_wait(0.4, 0.9)
            human_type(pwd_field, OCTOPUS_PASSWORD)

            submit_btn = _wait_for_element(driver, [
                (By.CSS_SELECTOR, "button[type='submit']"),
                (By.CSS_SELECTOR, "input[type='submit']"),
            ], timeout=15)
            if not submit_btn:
                raise RuntimeError("Submit button not found")
            ActionChains(driver).move_to_element(submit_btn).pause(
                random.uniform(0.5, 1.5)
            ).click().perform()
            log.info("Submitted login form")

            login_success = WebDriverWait(driver, 30).until(
                lambda d: (
                    "dashboard" in d.current_url
                    or "account" in d.current_url
                    or "octoplus" in d.current_url
                ) and "login" not in d.current_url
            )
            if login_success:
                log.info(f"✅ Login successful — URL: {driver.current_url}")
                return True

        except TimeoutException:
            log.warning(f"⏱️  Login timed out on attempt {attempt + 1}")
            save_screenshot(driver, f"login_timeout_{attempt}")
        except Exception as exc:
            log.warning(f"⚠️  Login error on attempt {attempt + 1}: {exc}")
            save_screenshot(driver, f"login_error_{attempt}")

        if attempt < MAX_LOGIN_RETRIES - 1:
            exponential_backoff(attempt)

    log.error(f"❌ Login failed after {MAX_LOGIN_RETRIES} attempts")
    return False

# ---------------------------------------------------------
# Claim
# ---------------------------------------------------------

ACTIVATE_SELECTORS = [
    (By.XPATH, "//button[.//span[contains(translate(text(),'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'activate offer')]]"),
    (By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ','abcdefghijklmnopqrstuvwxyz'), 'activate offer')]"),
    (By.XPATH, "//button[contains(@class,'activate')]"),
]

SUCCESS_INDICATORS = [
    "your code",
    "voucher code",
    "redemption code",
    "redeem your",
    "already claimed",
]

HARD_STOP_INDICATORS = [
    "sorry, this offer can't be claimed at the moment",
    "more codes tomorrow",
]

def _click_element(driver, element) -> bool:
    strategies = [
        ("ActionChains", lambda: ActionChains(driver).move_to_element(element).pause(random.uniform(0.5, 1.0)).click().perform()),
        ("Direct",       lambda: element.click()),
        ("JavaScript",   lambda: driver.execute_script("arguments[0].click();", element)),
    ]
    for name, fn in strategies:
        try:
            fn()
            log.info(f"🎯 Clicked via {name}")
            return True
        except Exception as exc:
            log.warning(f"Click strategy '{name}' failed: {exc}")
    return False

def claim_offer(driver) -> bool:
    offer_url = (
        f"https://octopus.energy/dashboard/new/accounts/"
        f"{ACCOUNT_ID}/octoplus/partner/offers/caffe-nero"
    )

    for attempt in range(MAX_CLAIM_RETRIES):
        log.info(f"☕ Claim attempt {attempt + 1}/{MAX_CLAIM_RETRIES}...")
        try:
            driver.get(offer_url)
            human_wait(4, 6)

            content_ready = False
            for load_try in range(3):
                try:
                    WebDriverWait(driver, 35).until(
                        lambda d: (
                            "activate" in page_text(d)
                            or "sorry, this offer" in page_text(d)
                            or "already claimed" in page_text(d)
                        )
                    )
                    content_ready = True
                    break
                except TimeoutException:
                    log.warning(f"Content load timeout (try {load_try + 1}); refreshing...")
                    driver.refresh()
                    human_wait(5, 8)

            if not content_ready:
                log.error("❌ Page never showed expected content")
                if attempt < MAX_CLAIM_RETRIES - 1:
                    exponential_backoff(attempt)
                    continue
                return False

            txt = page_text(driver)

            if "already claimed" in txt:
                log.info("✅ Offer already claimed this week (detected on page load)")
                return True

            if any(msg in txt for msg in HARD_STOP_INDICATORS):
                log.info("ℹ️  Offer unavailable (no codes / ended)")
                return False

            activate_btn = None
            for by, sel in ACTIVATE_SELECTORS:
                try:
                    elements = WebDriverWait(driver, 15).until(
                        EC.presence_of_all_elements_located((by, sel))
                    )
                    for el in elements:
                        if el.is_displayed() and el.is_enabled():
                            activate_btn = el
                            log.info("✓ Activate Button found")
                            break
                    if activate_btn:
                        break
                except (TimeoutException, Exception):
                    continue

            if not activate_btn:
                log.error("❌ 'Activate offer' button not found")
                if attempt < MAX_CLAIM_RETRIES - 1:
                    exponential_backoff(attempt)
                    continue
                return False

            driver.execute_script("arguments[0].scrollIntoView({behavior:'smooth',block:'center'});", activate_btn)
            human_wait(1, 2)

            if not _click_element(driver, activate_btn):
                log.error("❌ All click strategies failed")
                return False

            human_wait(8, 12)
            
            # Verify
            txt = page_text(driver)
            if any(ind in txt for ind in SUCCESS_INDICATORS):
                log.info("✅ Success indicators found immediately after click!")
                return True

            log.info("Reloading to verify claim...")
            driver.refresh()
            human_wait(4, 6)
            
            if any(ind in page_text(driver) for ind in SUCCESS_INDICATORS):
                log.info("✅ Claim VERIFIED after page reload!")
                return True

            log.warning(f"⚠️  Could not verify claim on attempt {attempt + 1}")
            if attempt < MAX_CLAIM_RETRIES - 1:
                exponential_backoff(attempt)

        except Exception as exc:
            log.error(f"❌ Unexpected error on claim attempt {attempt + 1}: {exc}")
            if attempt < MAX_CLAIM_RETRIES - 1:
                exponential_backoff(attempt)

    log.error("❌ Claim failed — all attempts exhausted")
    return False

# ---------------------------------------------------------
# State management 
# ---------------------------------------------------------

def has_claimed_this_week() -> bool:
    if not os.path.exists(STATE_FILE):
        return False
    try:
        with open(STATE_FILE, "r") as f:
            raw = f.read().strip()
            if not raw:
                return False
            last = datetime.fromisoformat(raw).date()
            today = date.today()
            week_start = today - timedelta(days=today.weekday())
            if last >= week_start:
                log.info(f"✅ Already claimed this week (recorded: {last})")
                return True
            return False
    except (ValueError, OSError) as exc:
        log.warning(f"⚠️  Could not read state file: {exc}")
        return False

def record_claim() -> None:
    try:
        with open(STATE_FILE, "w") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                f.write(datetime.now().isoformat())
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)
        log.info("📝 Successful claim recorded")
    except OSError as exc:
        log.error(f"❌ Failed to write state file: {exc}")

# ---------------------------------------------------------
# Main
# ---------------------------------------------------------

def main() -> None:
    if has_claimed_this_week():
        return

    if not check_network():
        log.error("❌ Network unavailable — octopus.energy unreachable. Aborting.")
        sys.exit(1)

    log.info("🚀 Starting Caffè Nero claim...")
    driver = None

    for driver_attempt in range(MAX_DRIVER_RETRIES):
        try:
            driver = setup_driver(driver_attempt)

            if not login(driver):
                log.error("❌ Could not log in — aborting this driver attempt")
                raise RuntimeError("Login failed")

            if claim_offer(driver):
                record_claim()
                log.info("✅ All done — coffee is on Octopus today ☕")
                return
            else:
                log.info("ℹ️  Claim not successful — will retry later")
                return 

        except Exception as exc:
            log.error(f"❌ Driver attempt {driver_attempt + 1} failed: {exc}")
            if driver_attempt < MAX_DRIVER_RETRIES - 1:
                exponential_backoff(driver_attempt, base=10)
        finally:
            if driver:
                try:
                    driver.quit()
                except Exception:
                    pass
                driver = None
            cleanup_temp_dirs()

    log.error(f"❌ Gave up after {MAX_DRIVER_RETRIES} driver attempts")

if __name__ == "__main__":
    try:
        main()
    finally:
        cleanup_temp_dirs()
