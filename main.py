"""
CDC Course Automator 
Automates video watching on the VIT-CDC portal using a delta-based timing logic.
Handles iframe injections (Vimeo/YouTube) and nested course modules.
"""

import os
import re
import sys
import json
import time
import logging
import threading
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- CONSTANTS ---
BASE_DIR = os.getcwd()
PROFILE_PATH = os.path.join(BASE_DIR, "automation_profile")
CONFIG_FILE = os.path.join(BASE_DIR, "course_history.json")
LOG_FILE = os.path.join(BASE_DIR, "automation_progress.log")
SAFETY_BUFFER = 20 


START_URL = "https://cdc.vit.ac.in/mycourses?type=mycourses"
# --- LOGGING SETUP ---
logger = logging.getLogger("CDC_Automate")
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', datefmt='%H:%M:%S')

fh = logging.FileHandler(LOG_FILE)
fh.setFormatter(formatter)
logger.addHandler(fh)

ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(formatter)
logger.addHandler(ch)

# --- GLOBAL STATE ---
skip_requested = False

def listen_for_skip():
    """Background listener for the Enter key to skip the current video."""
    global skip_requested
    while True:
        input()
        skip_requested = True

def load_history():
    """Loads previously automated course URLs from a local JSON file."""
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_history(name, url):
    """Saves a new course URL to the history file."""
    history = load_history()
    history[name] = url
    with open(CONFIG_FILE, 'w') as f:
        json.dump(history, f, indent=4)

def force_play_video(driver):
    """
    Direct JavaScript injection to bypass 'pointer-events: none' and 
    start players inside nested iframes (Vimeo/YouTube).
    """
    # Main page HTML5 check
    driver.execute_script("""
        var vids = document.getElementsByTagName('video');
        for(var i=0; i<vids.length; i++){ vids[i].play(); vids[i].muted = true; }
    """)
    # Iframe drilling
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
        except:
            driver.switch_to.default_content()

def get_seconds(time_str):
    """Parses MM:SS or HH:MM:SS into total integer seconds."""
    try:
        parts = list(map(int, time_str.strip().split(':')))
        if len(parts) == 2: return parts[0] * 60 + parts[1]
        if len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
        return 0
    except: return 0

def format_seconds(s):
    """Converts seconds into MM:SS string."""
    return f"{int(s//60):02d}:{int(s%60):02d}"

def setup_browser():
    """Initializes the Selenium WebDriver with a local profile and autoplay flags."""
    options = Options()
    options.add_argument(f"user-data-dir={PROFILE_PATH}")
    options.add_argument("--mute-audio")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--autoplay-policy=no-user-gesture-required")
    return webdriver.Chrome(options=options)

def main():
    global skip_requested
    history = load_history()
    
    print("\n" + "="*70)
    print("CDC COURSE AUTOMATOR - HISTORY MENU")
    print("="*70)
    
    start_url = START_URL
    
    if history:
        print("Detected previous sessions:")
        options_list = list(history.items())
        for idx, (name, url) in enumerate(options_list, 1):
            print(f" [{idx}] {name}")
        print(f" [0] New Course (Start from My Courses page)")
        
        choice = input("\nSelect an option: ")
        if choice.isdigit() and 0 < int(choice) <= len(options_list):
            start_url = options_list[int(choice)-1][1]
            logger.info(f"Resuming saved session: {options_list[int(choice)-1][0]}")
    
    driver = setup_browser()
    threading.Thread(target=listen_for_skip, daemon=True).start()

    try:
        driver.get(start_url)
        print("\n" + "-"*70)
        logger.info("ACTION REQUIRED: Log in and navigate to the video player.")
        logger.info("Once the first video is loaded, press ENTER in this terminal.")
        print("-" * 70)
        input()
        
        # Capture metadata for history saving
        current_url = driver.current_url
        course_title = "Unknown Course"
        try:
            course_title = driver.find_element(By.ID, "courseNameID").text.strip()
            save_history(course_title, current_url)
        except: pass

        section_idx = 0
        while True:
            # Re-fetch sections to prevent StaleElement errors
            sections = driver.find_elements(By.XPATH, "//div[@aria-labelledby='sidebar-module']")
            if section_idx >= len(sections):
                logger.info("Course mapping finished. All visible items processed.")
                break
            
            section = sections[section_idx]
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", section)
            time.sleep(1)

            try:
                progress = section.find_element(By.TAG_NAME, "tspan").text
                name = section.find_element(By.CLASS_NAME, "modpointer").text.strip().splitlines()[0]
                
                if "100%" in progress:
                    logger.info(f"SKIP SECTION: {name} (Finished)")
                    section_idx += 1; continue
                
                logger.info(f"OPEN SECTION: {name} (Current: {progress})")
                section.find_element(By.CLASS_NAME, "modpointer").click()
                time.sleep(2)
            except: section_idx += 1; continue

            # Sub-module expansion
            try:
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

                logger.info(f"EVALUATING: {title}")
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", vid)
                vid.click()
                time.sleep(6)

                # Time Delta Calculation
                try:
                    spent_el = driver.find_element(By.ID, "timeSpentCountID")
                    spent_str = spent_el.text.split()[0]
                    spent_sec = get_seconds(spent_str)
                    delta = total_sec - spent_sec
                    
                    if delta <= 5:
                        logger.info(f"FINISHED: {title} (Already satisfied)")
                        video_idx += 1; continue
                    wait_time = delta + SAFETY_BUFFER
                except:
                    wait_time = total_sec + SAFETY_BUFFER
                    logger.warning(f"METADATA READ ERROR: Watching full duration of {title}")

                force_play_video(driver)
                logger.info(f"WATCHING: {title} (Remaining: {format_seconds(wait_time)})")
                
                skip_requested = False
                for i in range(wait_time, 0, -1):
                    if skip_requested: 
                        logger.warning(f"MANUAL OVERRIDE: Skipping {title}")
                        break
                    sys.stdout.write(f"\r    Countdown: {format_seconds(i)} | Press ENTER to Skip ")
                    sys.stdout.flush(); time.sleep(1)

                print("\n")
                logger.info("SYNCING: Refreshing to save server-side progress...")
                driver.refresh()
                time.sleep(8)
                
                # RE-LOAD UI STATE after refresh
                try:
                    re_sec = driver.find_elements(By.XPATH, "//div[@aria-labelledby='sidebar-module']")[section_idx]
                    re_sec.find_element(By.CLASS_NAME, "modpointer").click()
                    time.sleep(2)
                    for sub in re_sec.find_elements(By.CLASS_NAME, "submod"):
                        if any(x in sub.text.lower() for x in ["video", "learning"]):
                            sub.find_element(By.CLASS_NAME, "modpointer").click()
                    time.sleep(2)
                except: pass
                
                video_idx += 1

            section_idx += 1

    finally:
        logger.info("TERMINATING: Session closed.")
        driver.quit()

if __name__ == "__main__":
    main()