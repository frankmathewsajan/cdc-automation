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

# --- CONFIGURATION ---
BASE_DIR = os.getcwd()
PROFILE_PATH = os.path.join(BASE_DIR, "automation_profile")
CONFIG_FILE = os.path.join(BASE_DIR, "course_history.json")
LOG_FILE = "automation_progress.log"
SAFETY_BUFFER = 15  

# --- LOGGING ---
logger = logging.getLogger("CDC_Automate")
logger.setLevel(logging.INFO)
formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s', datefmt='%H:%M:%S')
fh = logging.FileHandler(LOG_FILE, encoding='utf-8')
fh.setFormatter(formatter)
logger.addHandler(fh)
ch = logging.StreamHandler(sys.stdout)
ch.setFormatter(formatter)
logger.addHandler(ch)

exit_requested = False
skip_requested = False
driver = None

def listen_for_input():
    global skip_requested, exit_requested, driver
    while not exit_requested:
        try:
            ui = input().lower().strip()
            if ui == 'q':
                exit_requested = True
                if driver: driver.quit()
                os._exit(0)
            else:
                skip_requested = True
        except: break

def format_seconds(s):
    if s < 0: s = 0
    return f"{int(s//3600):02d}:{int((s%3600)//60):02d}:{int(s%60):02d}"

def get_seconds(time_str):
    try:
        parts = list(map(int, time_str.strip().split(':')))
        if len(parts) == 2: return parts[0] * 60 + parts[1]
        if len(parts) == 3: return parts[0] * 3600 + parts[1] * 60 + parts[2]
        return 0
    except: return 0

def force_play_video(d):
    d.execute_script("var v=document.getElementsByTagName('video'); for(var i=0;i<v.length;i++){v[i].play(); v[i].muted=true;}")
    try:
        iframes = d.find_elements(By.TAG_NAME, "iframe")
        for frame in iframes:
            d.switch_to.frame(frame)
            d.execute_script("""
                window.postMessage('{"event":"command","func":"playVideo","args":""}', '*');
                var b = document.querySelector('button[aria-label="Play"], .ytp-large-play-button');
                if(b) b.click();
                var v = document.querySelector('video');
                if(v) { v.play(); v.muted = true; }
            """)
            d.switch_to.default_content()
    except: d.switch_to.default_content()

def main():
    global skip_requested, exit_requested, driver
    
    # 1. Clean History Loader (Removes blank entries)
    history = {}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f: 
                raw_history = json.load(f)
                history = {k: v for k, v in raw_history.items() if k.strip()} # Filter blanks
        except: pass
    
    print("\n" + "="*60 + "\nCDC AUTOMATOR v16.1 | 'q' to Quit\n" + "="*60)
    start_url = "https://cdc.vit.ac.in/mycourses?type=mycourses"
    auto_start = False
    
    if history:
        opts = list(history.items())
        for i, (n, u) in enumerate(opts, 1): print(f" [{i}] {n}")
        print(" [0] New Course")
        choice = input("\nSelect course: ")
        if choice.isdigit() and 0 < int(choice) <= len(opts):
            start_url = opts[int(choice)-1][1]
            auto_start = True

    logger.info("BOOT: Launching Chrome...")
    options = Options()
    options.add_argument(f"user-data-dir={PROFILE_PATH}")
    options.add_argument("--mute-audio")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    try:
        driver = webdriver.Chrome(options=options)
    except:
        logger.error("FATAL: Profile locked. Close other Chrome windows.")
        return

    threading.Thread(target=listen_for_input, daemon=True).start()
    driver.get(start_url)
    
    if not auto_start:
        logger.info("ACTION: Navigate and press ENTER.")
        input()
    else:
        logger.info("BOOT: Waiting for Player UI...")
        try:
            WebDriverWait(driver, 30).until(EC.presence_of_element_located((By.ID, "teamsID")))
            time.sleep(5) # CRITICAL: Wait for Angular to populate items
        except:
            logger.warning("BOOT: UI didn't load. Press ENTER once ready.")
            input()

    # Save proper history
    try:
        course_name = driver.find_element(By.ID, "courseNameID").text.strip()
        if course_name:
            history[course_name] = driver.current_url
            with open(CONFIG_FILE, 'w') as f: json.dump(history, f, indent=4)
    except: pass

    # Main Loop
    s_idx = 0
    while not exit_requested:
        sections = driver.find_elements(By.XPATH, "//div[@aria-labelledby='sidebar-module']")
        
        # Guard against zero-length detection during page load
        if not sections and s_idx == 0:
            time.sleep(3)
            continue

        if s_idx >= len(sections):
            logger.info("FINISH: No more modules found.")
            break
        
        sec = sections[s_idx]
        try:
            name = sec.find_element(By.CLASS_NAME, "modpointer").text.strip().splitlines()[0]
            prog = sec.find_element(By.TAG_NAME, "tspan").text
            if "100%" in prog:
                s_idx += 1; continue
            logger.info(f"MODULE: {name} ({prog})")
        except: s_idx += 1; continue

        # Expand Section
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", sec)
            sec.find_element(By.CLASS_NAME, "modpointer").click()
            time.sleep(2)
            for sub in sec.find_elements(By.CLASS_NAME, "submod"):
                if "video" in sub.text.lower() or "learning" in sub.text.lower():
                    sub.find_element(By.CLASS_NAME, "modpointer").click()
        except: pass

        v_idx = 0
        while not exit_requested:
            try:
                curr_module = driver.find_elements(By.XPATH, "//div[@aria-labelledby='sidebar-module']")[s_idx]
                videos = curr_module.find_elements(By.CLASS_NAME, "accEach1")
            except: break

            if v_idx >= len(videos): break
            vid = videos[v_idx]
            if "video" not in vid.text.lower(): v_idx += 1; continue

            title = vid.text.splitlines()[0]
            total_sec = get_seconds(re.search(r'(\d{1,2}:\d{2})', vid.text).group())

            logger.info(f"CHECKING: {title}")
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", vid)
            vid.click()
            
            time.sleep(5) # Let metadata load
            try:
                spent_el = driver.find_element(By.ID, "timeSpentCountID")
                spent_sec = get_seconds(spent_el.text.split()[0])
                if spent_sec >= (total_sec - 5):
                    logger.info(f"SKIP: Already finished.")
                    v_idx += 1; continue
                wait_time = (total_sec - spent_sec) + SAFETY_BUFFER
            except:
                wait_time = total_sec + SAFETY_BUFFER

            force_play_video(driver)
            logger.info(f"WATCH: {title} | {format_seconds(wait_time)} remaining.")
            
            skip_requested = False
            for i in range(wait_time, 0, -1):
                if skip_requested or exit_requested: break
                sys.stdout.write(f"\r    T-minus: {format_seconds(i)} (Enter=Skip | q=Quit) ")
                sys.stdout.flush(); time.sleep(1)

            logger.info(f"SYNC: Refreshing for {title}...")
            driver.refresh()
            time.sleep(8)
            
            # Re-expand logic
            try:
                re_sec = driver.find_elements(By.XPATH, "//div[@aria-labelledby='sidebar-module']")[s_idx]
                re_sec.find_element(By.CLASS_NAME, "modpointer").click()
                time.sleep(2)
                for sub in re_sec.find_elements(By.CLASS_NAME, "submod"):
                    if any(x in sub.text.lower() for x in ["video", "learning"]):
                        sub.find_element(By.CLASS_NAME, "modpointer").click()
            except: pass
            
            v_idx += 1 
        s_idx += 1

if __name__ == "__main__":
    try: main()
    except KeyboardInterrupt: pass
    finally:
        if driver:
            try: driver.quit()
            except: pass