"""
CDC Course Automator
"""

import os
import re
import sys
import json
import time
import logging
import threading
import subprocess
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

# --- CONFIGURATION ---
BASE_DIR = os.getcwd()
PROFILE_PATH = os.path.join(BASE_DIR, "automation_profile")
CONFIG_FILE = os.path.join(BASE_DIR, "course_history.json")
LOG_FILE = "automation_progress.log"
SAFETY_BUFFER = 15  
RETRY_PENALTY = 30  # Additional seconds if a video fails to satisfy the server
# ---------------------

# --- LOGGING SETUP ---
logger = logging.getLogger("CDC_Automate")
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', datefmt='%H:%M:%S')
fh = logging.FileHandler(LOG_FILE, encoding='utf-8')
fh.setFormatter(formatter)
logger.addHandler(fh)
ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(formatter)
logger.addHandler(ch)

# --- GLOBAL STATE ---
skip_requested = False
exit_requested = False
course_total_sec = 0
driver = None

def force_kill_chrome():
    if sys.platform.startswith("win"):
        try:
            subprocess.call(['taskkill', '/F', '/IM', 'chromedriver.exe', '/T'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except: pass

def listen_for_input():
    global skip_requested, exit_requested, driver
    while not exit_requested:
        try:
            user_input = input().lower().strip()
            if user_input == 'q':
                exit_requested = True
                logger.info("QUITTING: Closing session...")
                if driver: driver.quit()
                os._exit(0)
            else:
                skip_requested = True
        except EOFError: break

def get_seconds(time_str):
    try:
        parts = list(map(int, time_str.strip().split(':')))
        if len(parts) == 2: return parts[0] * 60 + parts[1]
        if len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
        return 0
    except: return 0

def format_seconds(s):
    if s < 0: s = 0
    h, m, sec = s // 3600, (s % 3600) // 60, s % 60
    return f"{int(h):02d}:{int(m):02d}:{int(sec):02d}"

def force_play_video(d):
    """Aggressive injection for HTML5, Vimeo, and YouTube."""
    d.execute_script("var v=document.getElementsByTagName('video'); for(var i=0;i<v.length;i++){v[i].play(); v[i].muted=true;}")
    iframes = d.find_elements(By.TAG_NAME, "iframe")
    for frame in iframes:
        try:
            d.switch_to.frame(frame)
            # YouTube API command + Vimeo UI click + HTML5 play
            d.execute_script("""
                // YouTube specific postMessage play
                var yt = document.querySelector('.ytp-large-play-button, .ytp-play-button');
                if(yt) yt.click();
                window.postMessage('{"event":"command","func":"playVideo","args":""}', '*');
                
                // Vimeo specific
                var vim = document.querySelector('button[data-play-button="true"]');
                if(vim) vim.click();
                
                // General
                var v=document.getElementsByTagName('video'); 
                if(v.length>0){v[0].play(); v[0].muted=true;}
            """)
            d.switch_to.default_content()
        except: d.switch_to.default_content()

def update_workload(d):
    """Updates the global course_total_sec by scanning sidebar."""
    global course_total_sec
    total = 0
    try:
        sections = d.find_elements(By.XPATH, "//div[@aria-labelledby='sidebar-module']")
        for sec in sections:
            prog = sec.find_element(By.TAG_NAME, "tspan").text
            if "100%" not in prog:
                vids = sec.find_elements(By.CLASS_NAME, "accEach1")
                for v in vids:
                    if "video" in v.text.lower():
                        match = re.search(r'(\d{1,2}:\d{2})', v.text)
                        if match: total += get_seconds(match.group())
    except: pass
    course_total_sec = total

def expand_section(d, idx):
    try:
        sections = d.find_elements(By.XPATH, "//div[@aria-labelledby='sidebar-module']")
        target = sections[idx]
        d.execute_script("arguments[0].scrollIntoView({block: 'center'});", target)
        target.find_element(By.CLASS_NAME, "modpointer").click()
        time.sleep(2)
        for sub in target.find_elements(By.CLASS_NAME, "submod"):
            if any(x in sub.text.lower() for x in ["video", "learning"]):
                sub.find_element(By.CLASS_NAME, "modpointer").click()
                time.sleep(0.5)
    except: pass

def main():
    global skip_requested, exit_requested, driver, course_total_sec
    force_kill_chrome()
    history = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f: history = json.load(f)
        except: pass
    
    print("\n" + "="*70 + "\nCDC AUTOMATOR v11.0 | 'q' to Quit | 'Enter' to Skip\n" + "="*70)
    start_url = "https://cdc.vit.ac.in/mycourses?type=mycourses"
    if history:
        opts = list(history.items())
        for i, (n, u) in enumerate(opts, 1): print(f" [{i}] {n}")
        print(" [0] New Course")
        choice = input("\nSelect course: ")
        if choice.isdigit() and 0 < int(choice) <= len(opts): start_url = opts[int(choice)-1][1]

    options = Options()
    options.add_argument(f"user-data-dir={PROFILE_PATH}")
    options.add_argument("--mute-audio")
    options.add_argument("--autoplay-policy=no-user-gesture-required")
    driver = webdriver.Chrome(options=options)
    
    threading.Thread(target=listen_for_input, daemon=True).start()
    driver.get(start_url)
    logger.info("SYSTEM: Log in, then press ENTER on the course player page.")
    input()
    
    try:
        course_name = driver.find_element(By.ID, "courseNameID").text.strip()
        history[course_name] = driver.current_url
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump(history, f, indent=4)
    except: pass

    s_idx = 0
    while not exit_requested:
        update_workload(driver) # Initial sync
        sections = driver.find_elements(By.XPATH, "//div[@aria-labelledby='sidebar-module']")
        if s_idx >= len(sections): break
        
        sec = sections[s_idx]
        try:
            name = sec.find_element(By.CLASS_NAME, "modpointer").text.strip().splitlines()[0]
            prog = sec.find_element(By.TAG_NAME, "tspan").text
            if "100%" in prog:
                s_idx += 1; continue
            logger.info(f"SECTION: {name} ({prog})")
        except: s_idx += 1; continue

        expand_section(driver, s_idx)
        
        v_idx = 0
        while not exit_requested:
            try:
                curr_sec = driver.find_elements(By.XPATH, "//div[@aria-labelledby='sidebar-module']")[s_idx]
                videos = curr_sec.find_elements(By.CLASS_NAME, "accEach1")
            except: break

            if v_idx >= len(videos): break
            vid = videos[v_idx]
            if "video" not in vid.text.lower(): v_idx += 1; continue

            title = vid.text.splitlines()[0]
            total_sec = get_seconds(re.search(r'(\d{1,2}:\d{2})', vid.text).group())

            logger.info(f"EVALUATING: {title}")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", vid)
            vid.click()
            time.sleep(6)

            try:
                spent_str = driver.find_element(By.ID, "timeSpentCountID").text.split()[0]
                spent_sec = get_seconds(spent_str)
                if spent_sec >= (total_sec - 5):
                    logger.info(f"SATISFIED: {title} ({spent_str}).")
                    v_idx += 1; continue
                
                delta = total_sec - spent_sec
                # Check if this is a second attempt
                wait_time = delta + SAFETY_BUFFER
            except: wait_time = total_sec + SAFETY_BUFFER

            force_play_video(driver)
            logger.info(f"PLAYING: {title} | Watch time: {format_seconds(wait_time)}")
            
            skip_requested = False
            for i in range(wait_time, 0, -1):
                if skip_requested or exit_requested: break
                sys.stdout.write(f"\r    Countdown: {format_seconds(i)} | Course Total: {format_seconds(course_total_sec)} ")
                sys.stdout.flush(); time.sleep(1)
                if i % 10 == 0: # Avoid excessive updates
                     course_total_sec -= 10 if course_total_sec > 10 else 0

            logger.info(f"SYNCING: {title}")
            driver.refresh()
            expand_section(driver, s_idx)
            
            # RE-CHECK: If the server didn't update, add penalty and retry the same v_idx
            try:
                # Re-verify progress
                spent_now = get_seconds(driver.find_element(By.ID, "timeSpentCountID").text.split()[0])
                if spent_now < (total_sec - 5):
                    logger.warning(f"UNSATISFIED: Server still says {spent_now}s. Retrying with penalty...")
                    # Update delta for the loop, but stay on this v_idx
                    continue 
            except: pass

            v_idx += 1 
            update_workload(driver) # Sync workload after each video

        s_idx += 1

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: pass
    finally:
        if driver: driver.quit()