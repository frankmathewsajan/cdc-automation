import time
import re
import threading
import sys
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONFIGURATION ---
CHROME_PROFILE_PATH = r"C:\Users\frank\Projects\cdc-automate\automation_profile"
LOG_FILE = "automation_progress.log"
SAFETY_BUFFER = 20  # Extra seconds for heartbeat registration
# ---------------------

# 1. Setup Logging System (File + Terminal)
logger = logging.getLogger("CDC_Automate")
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', datefmt='%H:%M:%S')

# File Handler
fh = logging.FileHandler(LOG_FILE)
fh.setFormatter(formatter)
logger.addHandler(fh)

# Console Handler
ch = logging.StreamHandler()
ch.setFormatter(formatter)
logger.addHandler(ch)

chrome_options = Options()
chrome_options.add_argument(f"user-data-dir={CHROME_PROFILE_PATH}")
chrome_options.add_argument("--mute-audio")
chrome_options.add_argument("--disable-blink-features=AutomationControlled")
chrome_options.add_argument("--autoplay-policy=no-user-gesture-required")

driver = webdriver.Chrome(options=chrome_options)
skip_requested = False

def listen_for_skip():
    global skip_requested
    while True:
        input(); skip_requested = True

threading.Thread(target=listen_for_skip, daemon=True).start()

def force_play_video():
    """Universal play injector for iframe players."""
    # Overlay button
    try: driver.find_element(By.ID, "play0").click()
    except: pass

    # Main page HTML5
    driver.execute_script("var vids = document.getElementsByTagName('video'); for(var i=0; i<vids.length; i++){ vids[i].play(); vids[i].muted = true; }")

    # Iframes (Vimeo/YouTube)
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    for frame in iframes:
        try:
            driver.switch_to.frame(frame)
            driver.execute_script("""
                var yt = document.querySelector('.ytp-large-play-button'); if(yt) yt.click();
                var vim = document.querySelector('button[data-play-button="true"]'); if(vim) vim.click();
                var innerVids = document.getElementsByTagName('video');
                if(innerVids.length > 0) { innerVids[0].play(); innerVids[0].muted = true; }
            """)
            driver.switch_to.default_content()
        except: driver.switch_to.default_content()

def get_seconds(time_str):
    try:
        parts = list(map(int, time_str.strip().split(':')))
        return parts[0] * 60 + parts[1] if len(parts) == 2 else 0
    except: return 0

def format_seconds(s):
    return f"{int(s//60):02d}:{int(s%60):02d}"

try:
    driver.get("https://cdc.vit.ac.in/mycourses/details?id=8a6dcc8d-54d9-45f3-9dd6-0c43e15538d0&type=mycourses")
    print("\n" + "="*70)
    logger.info("SYSTEM READY. Log in and navigate, then press ENTER in terminal.")
    print("="*70)
    input()

    section_idx = 0
    while True:
        sections = driver.find_elements(By.XPATH, "//div[@aria-labelledby='sidebar-module']")
        if section_idx >= len(sections):
            logger.info("🏁 ALL VISIBLE SECTIONS COMPLETE.")
            break
        
        section = sections[section_idx]
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", section)
        
        try:
            progress = section.find_element(By.TAG_NAME, "tspan").text
            name = section.find_element(By.CLASS_NAME, "modpointer").text.strip().splitlines()[0]
            if "100%" in progress:
                logger.info(f"⏭️  SKIPPING {name} - Progress already at 100%.")
                section_idx += 1; continue
            
            logger.info(f"📂 ENTERING SECTION: {name} (Current: {progress})")
        except: section_idx += 1; continue

        # Open Section & Sub-modules
        try:
            section.find_element(By.CLASS_NAME, "modpointer").click()
            time.sleep(2)
            for sub in section.find_elements(By.CLASS_NAME, "submod"):
                if "assessment" not in sub.text.lower():
                    sub.find_element(By.CLASS_NAME, "modpointer").click()
                    time.sleep(1)
        except: pass

        video_idx = 0
        while True:
            try:
                curr_sec = driver.find_elements(By.XPATH, "//div[@aria-labelledby='sidebar-module']")[section_idx]
                videos = curr_sec.find_elements(By.CLASS_NAME, "accEach1")
            except: break

            if video_idx >= len(videos): break

            vid = videos[video_idx]
            if "video" not in vid.text.lower():
                video_idx += 1; continue

            dur_match = re.search(r'(\d{1,2}:\d{2})', vid.text)
            total_sec = get_seconds(dur_match.group()) if dur_match else 300
            title = vid.text.splitlines()[0]

            logger.info(f"🔍 EVALUATING: {title}")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", vid)
            vid.click()
            time.sleep(6)

            # Delta Logic
            try:
                spent_el = driver.find_element(By.ID, "timeSpentCountID")
                spent_str = spent_el.text.split()[0]
                spent_sec = get_seconds(spent_str)
                delta = total_sec - spent_sec
                if delta <= 5:
                    logger.info(f"✅ ALREADY WATCHED: {title} ({spent_str}/{dur_match.group()}).")
                    video_idx += 1; continue
                wait_time = delta + SAFETY_BUFFER
            except:
                wait_time = total_sec + SAFETY_BUFFER
                logger.warning(f"⚠️  METADATA MISSING for {title}. Defaulting to full watch.")

            force_play_video()
            logger.info(f"▶️  WATCHING: {title} for {format_seconds(wait_time)}.")
            
            skip_requested = False
            for i in range(wait_time, 0, -1):
                if skip_requested: 
                    logger.warning(f"⏩ MANUAL SKIP requested for {title}.")
                    break
                # Only Terminal shows the live countdown to keep log file clean
                sys.stdout.write(f"\r    T-minus: {format_seconds(i)} | Press ENTER to Skip... ")
                sys.stdout.flush(); time.sleep(1)

            print("\n")
            logger.info(f"🔄 SYNCING progress for {title} with VIT server...")
            driver.refresh()
            time.sleep(8)
            
            # Recovery
            try:
                re_sec = driver.find_elements(By.XPATH, "//div[@aria-labelledby='sidebar-module']")[section_idx]
                re_sec.find_element(By.CLASS_NAME, "modpointer").click()
                time.sleep(2)
                for sub in re_sec.find_elements(By.CLASS_NAME, "submod"):
                    if "video" in sub.text.lower() or "learning" in sub.text.lower():
                        sub.find_element(By.CLASS_NAME, "modpointer").click()
                time.sleep(2)
            except: pass
            
            video_idx += 1

        section_idx += 1

finally:
    logger.info("⛔ SCRIPT STOPPED. Check automation_progress.log for history.")
    driver.quit()