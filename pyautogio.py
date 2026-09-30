import pyautogui
import time
import subprocess
from datetime import datetime
from pathlib import Path

# -----------------------------
# Configuration
# -----------------------------

URL = (
    "https://www.accuweather.com/en/ch/zurich/316622/"
    "weather-forecast/316622?type=locality"
)

OUTPUT_DIR = Path.home() / "DailyReports"
OUTPUT_DIR.mkdir(exist_ok=True)

today = datetime.now().strftime("%Y-%m-%d")

report_file = OUTPUT_DIR / f"daily_report_{today}.txt"
screenshot_file = OUTPUT_DIR / f"daily_report_{today}.png"

# Safety feature:
# Move mouse to the top-left corner to abort the program.
pyautogui.FAILSAFE = True

# -----------------------------
# Step 1: Open Chrome
# -----------------------------

subprocess.Popen("start chrome", shell=True)

time.sleep(3)

# -----------------------------
# Step 2: Open AccuWeather
# -----------------------------

pyautogui.hotkey("ctrl", "l")
pyautogui.write(URL, interval=0.001)
pyautogui.press("enter")

# Wait for webpage to load
time.sleep(8)

# -----------------------------
# Step 3: Copy information
# -----------------------------

# This approach copies the visible webpage text.
# For a real assignment, you can replace this
# with mouse coordinates that select only the
# required weather information.

pyautogui.hotkey("ctrl", "a")
time.sleep(1)

pyautogui.hotkey("ctrl", "c")
time.sleep(1)

# -----------------------------
# Step 4: Open Notepad
# -----------------------------

subprocess.Popen("notepad.exe")

time.sleep(2)

# -----------------------------
# Step 5: Paste copied data
# -----------------------------

pyautogui.hotkey("ctrl", "v")

# Add a comment
pyautogui.press("enter")
pyautogui.press("enter")

pyautogui.write(
    "Comment: Good for outdoor activities.",
    interval=0.03
)

# -----------------------------
# Step 6: Save report
# -----------------------------

pyautogui.hotkey("ctrl", "shift", "s")

time.sleep(2)

# Type complete filename/path
pyautogui.write(str(report_file), interval=0.02)

pyautogui.press("enter")

time.sleep(2)

# -----------------------------
# Step 7: Screenshot
# -----------------------------

screenshot = pyautogui.screenshot()
screenshot.save(screenshot_file)

print("Report created:")
print(report_file)

print("Screenshot created:")
print(screenshot_file)
