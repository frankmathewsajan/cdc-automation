# CDC Course Automator

Automates repetitive browser interactions for course video progress tracking on the CDC portal using Selenium.

## Important Responsible-Use Notice

This project is provided for educational and automation-learning purposes only.

- Do not use this tool to violate platform rules, academic integrity policies, or institutional guidelines.
- Do not use it to skip coursework you are required to complete personally.
- You are fully responsible for how you use this code.

If your institution or course policy disallows this kind of automation, do not run it.

## What This Script Does

- Opens CDC in Chrome via Selenium.
- Uses a local browser profile stored in `automation_profile`.
- Lets you log in manually, then continues automated navigation.
- Iterates sections and videos, estimates remaining time, and waits with a countdown.
- Tries to force-play embedded video players (including iframe-based players).
- Refreshes and re-syncs page state so progress can be recorded server-side.
- Supports manual skip for the current wait cycle by pressing Enter in terminal.

## Project Structure

- `main.py`: Primary automation script.
- `course_history.json`: Saved sessions/history for resume.
- `automation_profile/`: Local Chrome profile data used by Selenium.
- `requirements.txt`: Pip-compatible dependency list.
- `pyproject.toml`: Project metadata and uv-managed dependencies.

## Prerequisites

- Python 3.14+ (as declared in `pyproject.toml`)
- Google Chrome installed
- A compatible ChromeDriver available to Selenium (Selenium Manager usually handles this automatically)

## Setup Option 1: Using uv (recommended)

`uv` is fast and lockfile-friendly.

### 1) Install uv

Windows PowerShell:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

### 2) Clone and enter project

```powershell
git clone https://github.com/frankmathewsajan/cdc-automation
cd cdc-automate
```

### 3) Install dependencies

If a lockfile exists and is up to date:

```powershell
uv sync
```

If you need to generate/update lockfile first:

```powershell
uv lock
uv sync
```

### 4) Run

```powershell
uv run main.py
```

## Setup Option 2: Using pip

### 1) Clone and enter project

```powershell
git clone https://github.com/frankmathewsajan/cdc-automation
cd cdc-automate
```

### 2) Create and activate virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3) Install dependencies

```powershell
pip install -r requirements.txt
```

### 4) Run

```powershell
python main.py
```

## uv vs pip (quick comparison)

- `uv`: Very fast dependency resolution and install, built-in lockfile workflow (`uv lock`, `uv sync`), convenient `uv run`.
- `pip`: Standard and widely known, works everywhere, simple `requirements.txt` workflow.

Use either one. If your team already uses lockfiles and reproducible environments, `uv` is usually the cleaner path.

## Typical Runtime Flow

1. Launch script.
2. Browser opens at CDC page.
3. Log in and navigate to first playable video.
4. Press Enter in terminal when ready.
5. Script processes sections/videos and waits for remaining duration.
6. Press Enter any time during countdown to skip current wait.

## Notes and Caveats

- UI changes on the CDC site may break selectors and require script updates.
- Network failures, modal popups, or anti-automation controls can interrupt execution.
- The script uses broad exception handling in places; review logs (`automation_progress.log`) for troubleshooting.

## Troubleshooting

- Driver/session issues: close all Chrome instances and rerun.
- Profile lock issues: delete stale files under `automation_profile` only if you understand the impact.
- Dependency issues (uv): run `uv lock` then `uv sync`.
- Dependency issues (pip): recreate venv and reinstall from `requirements.txt`.

## Legal and Policy Reminder

This repository is not intended to facilitate cheating, policy circumvention, or assignment skipping. Keep usage compliant with all applicable academic rules, terms of service, and local laws.
