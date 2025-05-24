import configparser
import requests
import sys
import os
import random
from screeninfo import get_monitors
import ctypes # For Windows API calls (SystemParametersInfoW)
import winreg # For modifying Windows registry (wallpaper style)
import math   # For aspect ratio calculations
from urllib.parse import urlparse # To parse URLs and get file extensions
import time   # Added for delays (time.sleep)
import glob   # For finding files during cleanup
import json   # Added for handling wallpaper history

# --- Global Constants & Paths (will be updated during setup if needed) ---
# Default names for files/folders, their exact path depends on user's choice during setup
DEFAULT_CONFIG_FILENAME = 'config.ini'
DEFAULT_HISTORY_FILENAME = 'wallpaper_history.json'
DEFAULT_WALLPAPER_DIR_NAME = 'downloaded_wallpapers'
DEFAULT_LOG_FILENAME = 'wallpaper_changer_log.txt' # For scheduled task output

# Initial paths, will be dynamically updated based on setup
GLOBAL_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GLOBAL_CONFIG_PATH = os.path.join(GLOBAL_SCRIPT_DIR, DEFAULT_CONFIG_FILENAME)
GLOBAL_HISTORY_PATH = os.path.join(GLOBAL_SCRIPT_DIR, DEFAULT_HISTORY_FILENAME)
GLOBAL_DOWNLOAD_PATH = os.path.join(GLOBAL_SCRIPT_DIR, DEFAULT_WALLPAPER_DIR_NAME) # This can be overridden by config

# Windows API constants for setting wallpaper
SPI_SETDESKWALLPAPER = 20
SPIF_UPDATEINIFILE = 0x01
SPIF_SENDCHANGE = 0x02

# --- 1. Load Configuration ---
def load_config():
    config = configparser.ConfigParser()
    if not os.path.exists(GLOBAL_CONFIG_PATH):
        # This shouldn't happen if setup_initial_config is called first
        print(f"Error: {GLOBAL_CONFIG_PATH} not found. Please run setup first.")
        sys.exit(1)
    config.read(GLOBAL_CONFIG_PATH)
    return config['SETTINGS'], config['REDDIT_API']

# --- 2. Check for Internet Connection ---
def check_internet_connection(timeout=10):
    try:
        response = requests.get("https://www.google.com", timeout=timeout)
        response.raise_for_status()
        print("Internet connection active.")
        return True
    except requests.exceptions.RequestException as e:
        print(f"Error: Could not establish network connection. Details: {e}")
        return False
    except Exception as e:
        print(f"An unexpected error occurred while checking internet: {e}")
        return False

# --- 3. Detect and Determine Target Resolution ---
def get_resolutions_and_preference(settings):
    detected_width, detected_height = 0, 0
    try:
        monitors = get_monitors()
        if monitors:
            main_monitor = monitors[0]
            detected_width = main_monitor.width
            detected_height = main_monitor.height
            print(f"Detected current screen resolution: {detected_width}x{detected_height}")
        else:
            print("Warning: Could not detect screen resolution.")
    except Exception as e:
        print(f"Error detecting screen resolution: {e}.")

    target_resolution_str = settings.get('RESOLUTION').strip()
    if target_resolution_str:
        try:
            target_width, target_height = map(int, target_resolution_str.split('x'))
            print(f"Using preferred target resolution from config: {target_width}x{target_height}")
        except ValueError:
            print(f"Warning: Invalid RESOLUTION format in config '{target_resolution_str}'. Using detected resolution as fallback.")
            target_width, target_height = detected_width, detected_height
    else:
        target_width, target_height = detected_width, detected_height
        if target_width == 0: # Fallback if detection also failed
            target_width, target_height = 1920, 1080
            print(f"No preferred resolution set in config and detection failed. Using default 1920x1080.")
        else:
            print(f"No preferred resolution set in config. Using detected resolution ({target_width}x{target_height}) as target.")

    allow_aspect_ratio_variation = settings.getboolean('ALLOW_ASPECT_RATIO_VARIATION', True)
    print(f"Allow aspect ratio variation: {allow_aspect_ratio_variation}")

    return (detected_width, detected_height), (target_width, target_height), allow_aspect_ratio_variation

# --- Reddit Fetching and Filtering Functions ---

def get_reddit_posts(settings, reddit_api_settings):
    subreddit = settings.get('SUBREDDIT')
    sort_order = settings.get('SORT_ORDER')
    fetch_limit = settings.getint('FETCH_LIMIT')
    user_agent = reddit_api_settings.get('USER_AGENT')

    url = f"https://www.reddit.com/r/{subreddit}/{sort_order}/.json?limit={fetch_limit}&t=all"

    print(f"Fetching posts from Reddit: {url}")
    headers = {"User-Agent": user_agent}

    try:
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        posts = data['data']['children']
        print(f"Successfully fetched {len(posts)} posts.")
        return posts
    except requests.exceptions.RequestException as e:
        print(f"Error fetching Reddit posts: {e}")
        return []

def calculate_aspect_ratio(width, height):
    if height == 0:
        return 0
    return width / height

def filter_wallpapers(posts, target_res, allow_variation, settings):
    min_score = settings.getint('MIN_SCORE')
    filter_nsfw = settings.getboolean('FILTER_NSFW')
    download_limit = settings.getint('DOWNLOAD_LIMIT')

    target_width, target_height = target_res
    target_aspect_ratio = calculate_aspect_ratio(target_width, target_height)
    
    ASPECT_RATIO_TOLERANCE = 0.02 
    MIN_DIMENSION_PERCENTAGE = 0.90 

    suitable_wallpapers = []

    print("\nStarting wallpaper filtering...")
    for post in posts:
        post_data = post['data']
        
        if post_data['score'] < min_score:
            continue
        if filter_nsfw and post_data.get('over_18', False):
            continue

        image_url = post_data.get('url_overridden_by_dest') or post_data.get('url')
        if not image_url:
            continue

        parsed_url = urlparse(image_url)
        file_name = parsed_url.path.split('/')[-1] if parsed_url.path else ''
        
        if not (file_name.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')) or
                'i.redd.it' in parsed_url.netloc or 'imgur.com' in parsed_url.netloc):
            continue

        image_width, image_height = 0, 0
        if 'preview' in post_data and 'images' in post_data['preview'] and len(post_data['preview']['images']) > 0:
            source_image = post_data['preview']['images'][0]['source']
            image_width = source_image.get('width', 0)
            image_height = source_image.get('height', 0)
        
        if image_width == 0 or image_height == 0:
            continue

        image_aspect_ratio = calculate_aspect_ratio(image_width, image_height)

        is_suitable_resolution = False
        if not allow_variation:
            if image_width == target_width and image_height == target_height:
                is_suitable_resolution = True
        else:
            if abs(image_aspect_ratio - target_aspect_ratio) < ASPECT_RATIO_TOLERANCE:
                if image_width >= (target_width * MIN_DIMENSION_PERCENTAGE) and \
                   image_height >= (target_height * MIN_DIMENSION_PERCENTAGE):
                    is_suitable_resolution = True
        
        if is_suitable_resolution:
            print(f"  - Found suitable: {post_data['title']} ({image_width}x{image_height}, Score: {post_data['score']})")
            wallpaper_info = {
                'url': image_url,
                'title': post_data['title'],
                'dimensions': (image_width, image_height)
            }
            if 'i.redd.it' in parsed_url.netloc:
                wallpaper_info['is_reddit_host'] = True
            else:
                wallpaper_info['is_reddit_host'] = False
            suitable_wallpapers.append(wallpaper_info)

    if len(suitable_wallpapers) > download_limit:
        suitable_wallpapers = random.sample(suitable_wallpapers, download_limit)
        print(f"Limited suitable wallpapers to {download_limit} for download.")
    
    print(f"Finished filtering. Found {len(suitable_wallpapers)} suitable wallpapers.")
    return suitable_wallpapers

def download_wallpaper(wallpaper_info, download_dir):
    image_url = wallpaper_info['url']
    image_title = wallpaper_info['title']
    
    parsed_url = urlparse(image_url)
    file_extension = os.path.splitext(parsed_url.path)[1].lower()
    if not file_extension:
        file_extension = '.jpg'

    sanitized_title = ''.join(c for c in image_title if c.isalnum() or c in (' ', '.', '_')).strip()
    sanitized_title = sanitized_title.replace(' ', '_')[:50]
    
    original_file_part = os.path.basename(parsed_url.path).split('.')[0][:20]
    
    filename = f"{sanitized_title}_{original_file_part}_{os.urandom(4).hex()}{file_extension}"
    filename = filename[:200]
    file_path = os.path.join(download_dir, filename)

    print(f"Attempting to download: {image_title} from {image_url}")

    max_retries = 3
    for attempt in range(max_retries):
        try:
            time.sleep(5)
            if attempt > 0:
                delay = 2 ** attempt
                print(f"Attempt {attempt + 1}/{max_retries}: Waiting {delay} seconds before retrying download...")
                time.sleep(delay)

            response = requests.get(image_url, stream=True, timeout=10)
            response.raise_for_status()

            with open(file_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
            print("Download complete.")
            return file_path
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 429:
                print(f"Rate limit hit (429 error) for {image_url}. Retrying...")
            else:
                print(f"HTTP Error downloading {image_url}: {e}. Not retrying this particular error.")
                return None
        except requests.exceptions.RequestException as e:
            print(f"Network error downloading {image_url}: {e}. Retrying...")
        except Exception as e:
            print(f"An unexpected error occurred during download for {image_url}: {e}. Not retrying this particular error.")
            return None
    print(f"Max retries reached for {image_url}. Failed to download due to persistent issues.")
    return None

# --- Functions for Setting Wallpaper and Cleanup ---

def set_windows_wallpaper(image_path, style_setting):
    print(f"Setting wallpaper to: {image_path} with style: {style_setting}")
    
    try:
        ctypes.windll.user32.SystemParametersInfoW(SPI_SETDESKWALLPAPER, 0, image_path, SPIF_UPDATEINIFILE | SPIF_SENDCHANGE)

        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Control Panel\Desktop", 0, winreg.KEY_WRITE)

        wallpaper_style_value = "10" # Default to Fill
        tile_wallpaper_value = "0"

        if style_setting.lower() == 'fill':
            wallpaper_style_value = "10"
            tile_wallpaper_value = "0"
        elif style_setting.lower() == 'fit':
            wallpaper_style_value = "6"
            tile_wallpaper_value = "0"
        elif style_setting.lower() == 'stretch':
            wallpaper_style_value = "2"
            tile_wallpaper_value = "0"
        elif style_setting.lower() == 'center':
            wallpaper_style_value = "0"
            tile_wallpaper_value = "0"
        elif style_setting.lower() == 'tile':
            wallpaper_style_value = "0"
            tile_wallpaper_value = "1"
        else:
            print(f"Warning: Unknown wallpaper style '{style_setting}'. Defaulting to 'fill'.")

        winreg.SetValueEx(key, "WallpaperStyle", 0, winreg.REG_SZ, wallpaper_style_value)
        winreg.SetValueEx(key, "TileWallpaper", 0, winreg.REG_SZ, tile_wallpaper_value)
        winreg.CloseKey(key)
        
        print("Wallpaper set successfully.")
        return True
    except Exception as e:
        print(f"Error setting Windows wallpaper: {e}")
        return False

def clean_up_old_wallpapers(download_dir, current_wallpaper_path):
    print(f"\nCleaning up old wallpapers in: {download_dir}")
    
    patterns = ['*.jpg', '*.jpeg', '*.png', '*.gif']
    files_to_check = []
    for pattern in patterns:
        files_to_check.extend(glob.glob(os.path.join(download_dir, pattern)))

    deleted_count = 0
    for file_path in files_to_check:
        if os.path.normcase(file_path) != os.path.normcase(current_wallpaper_path):
            try:
                os.remove(file_path)
                print(f"  - Deleted: {os.path.basename(file_path)}")
                deleted_count += 1
            except Exception as e:
                print(f"  - Error deleting {os.path.basename(file_path)}: {e}")
    
    print(f"Cleanup complete. Deleted {deleted_count} old wallpaper files.")

# --- History functions ---
MAX_HISTORY_SIZE = 10 # Global constant for history size

def load_history():
    if os.path.exists(GLOBAL_HISTORY_PATH):
        with open(GLOBAL_HISTORY_PATH, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                print(f"Warning: Could not decode {GLOBAL_HISTORY_PATH}. Starting with empty history.")
                return []
    return []

def save_history(history):
    history = history[-MAX_HISTORY_SIZE:] 
    with open(GLOBAL_HISTORY_PATH, 'w') as f:
        json.dump(history, f, indent=4)

# --- Interactive Setup Function ---
def setup_initial_config():
    global GLOBAL_CONFIG_PATH, GLOBAL_HISTORY_PATH, GLOBAL_DOWNLOAD_PATH, GLOBAL_SCRIPT_DIR

    print("\n--- Interactive Setup Guide ---")
    print("Welcome to the Wallpaper Changer setup!")
    print("This guide will help you configure the script.")

    # 1. Choose Base Directory
    while True:
        default_base_dir = GLOBAL_SCRIPT_DIR
        base_dir_input = input(f"\n[1/7] Enter a directory to store config files and history (default: '{default_base_dir}'): ").strip()
        base_dir = base_dir_input if base_dir_input else default_base_dir
        
        if not os.path.exists(base_dir):
            try:
                os.makedirs(base_dir)
                print(f"Created directory: {base_dir}")
                break
            except OSError as e:
                print(f"Error creating directory: {e}. Please try again or choose an existing path.")
        else:
            print(f"Using directory: {base_dir}")
            break
    
    # Update global paths based on chosen base directory
    GLOBAL_CONFIG_PATH = os.path.join(base_dir, DEFAULT_CONFIG_FILENAME)
    GLOBAL_HISTORY_PATH = os.path.join(base_dir, DEFAULT_HISTORY_FILENAME)
    # The default download path will be relative to this base_dir unless overridden
    GLOBAL_DOWNLOAD_PATH = os.path.join(base_dir, DEFAULT_WALLPAPER_DIR_NAME)


    # Use a temporary config object to collect inputs before final write
    temp_config = configparser.ConfigParser()
    temp_config['SETTINGS'] = {}
    temp_config['REDDIT_API'] = {}

    # 2. Resolution Settings
    detected_res_str = ""
    detected_width, detected_height = 0, 0
    try:
        monitors = get_monitors()
        if monitors:
            main_monitor = monitors[0]
            detected_width = main_monitor.width
            detected_height = main_monitor.height
            detected_res_str = f"{detected_width}x{detected_height}"
    except Exception:
        pass # Ignore errors if screeninfo fails

    while True:
        res_input = input(f"\n[2/7] Enter your preferred wallpaper resolution (e.g., 1920x1080) [default: {detected_res_str if detected_res_str else '1920x1080'} (auto-detected)]: ").strip()
        if not res_input:
            temp_config['SETTINGS']['RESOLUTION'] = detected_res_str if detected_res_str else "1920x1080"
            break
        try:
            width, height = map(int, res_input.split('x'))
            if width > 0 and height > 0:
                temp_config['SETTINGS']['RESOLUTION'] = f"{width}x{height}"
                break
            else:
                print("Resolution dimensions must be positive integers.")
        except ValueError:
            print("Invalid format. Please use WxH (e.g., 1920x1080).")

    while True:
        aspect_ratio_input = input("[2/7] Allow wallpapers with similar aspect ratios but not exact resolution? (yes/no) [default: yes]: ").strip().lower()
        if aspect_ratio_input in ('yes', 'y', ''):
            temp_config['SETTINGS']['ALLOW_ASPECT_RATIO_VARIATION'] = 'True'
            break
        elif aspect_ratio_input in ('no', 'n'):
            temp_config['SETTINGS']['ALLOW_ASPECT_RATIO_VARIATION'] = 'False'
            break
        else:
            print("Invalid input. Please enter 'yes' or 'no'.")

    # 3. Change Interval
    while True:
        interval_input = input("[3/7] How often should the wallpaper change? (daily/hourly/minutely/seconds) [default: daily]: ").strip().lower()
        if interval_input in ('daily', 'hourly', 'minutely', ''):
            temp_config['SETTINGS']['CHANGE_INTERVAL'] = interval_input if interval_input else 'daily'
            break
        elif interval_input == 'seconds':
            while True:
                try:
                    seconds = int(input("Enter interval in seconds (e.g., 3600 for hourly): ").strip())
                    if seconds > 0:
                        temp_config['SETTINGS']['CHANGE_INTERVAL'] = str(seconds)
                        break
                    else:
                        print("Please enter a positive number of seconds.")
                except ValueError:
                    print("Invalid input. Please enter a number.")
            break
        else:
            print("Invalid input. Please choose from 'daily', 'hourly', 'minutely', or 'seconds'.")

    # 4. Reddit Settings
    subreddit_input = input("[4/7] Enter the subreddit to get wallpapers from (e.g., wallpapers, earthporn) [default: wallpapers]: ").strip()
    temp_config['SETTINGS']['SUBREDDIT'] = subreddit_input if subreddit_input else 'wallpapers'

    while True:
        nsfw_input = input("[4/7] Filter out NSFW (Not Safe For Work) content? (yes/no) [default: yes]: ").strip().lower()
        if nsfw_input in ('yes', 'y', ''):
            temp_config['SETTINGS']['FILTER_NSFW'] = 'True'
            break
        elif nsfw_input in ('no', 'n'):
            temp_config['SETTINGS']['FILTER_NSFW'] = 'False'
            break
        else:
            print("Invalid input. Please enter 'yes' or 'no'.")

    while True:
        min_score_input = input("[4/7] Minimum upvote score for a post (e.g., 100) [default: 100]: ").strip()
        try:
            score = int(min_score_input) if min_score_input else 100
            if score >= 0:
                temp_config['SETTINGS']['MIN_SCORE'] = str(score)
                break
            else:
                print("Score must be a non-negative number.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    while True:
        fetch_limit_input = input("[4/7] Number of posts to fetch from Reddit (more gives more variety) [default: 50]: ").strip()
        try:
            limit = int(fetch_limit_input) if fetch_limit_input else 50
            if limit > 0:
                temp_config['SETTINGS']['FETCH_LIMIT'] = str(limit)
                break
            else:
                print("Limit must be a positive number.")
        except ValueError:
            print("Invalid input. Please enter a number.")
    
    while True:
        download_limit_input = input("[4/7] How many suitable images to try downloading (less than fetch limit) [default: 5]: ").strip()
        try:
            limit = int(download_limit_input) if download_limit_input else 5
            if limit > 0:
                temp_config['SETTINGS']['DOWNLOAD_LIMIT'] = str(limit)
                break
            else:
                print("Limit must be a positive number.")
        except ValueError:
            print("Invalid input. Please enter a number.")

    # 5. Wallpaper Style
    while True:
        style_input = input("[5/7] How should the wallpaper fit the screen? (fill/fit/stretch/center/tile) [default: fill]: ").strip().lower()
        if style_input in ('fill', 'fit', 'stretch', 'center', 'tile', ''):
            temp_config['SETTINGS']['WALLPAPER_STYLE'] = style_input if style_input else 'fill'
            break
        else:
            print("Invalid input. Please choose from 'fill', 'fit', 'stretch', 'center', 'tile'.")

    # 6. Download Path
    default_download_path = os.path.join(base_dir, DEFAULT_WALLPAPER_DIR_NAME)
    download_path_input = input(f"[6/7] Enter directory to save downloaded wallpapers (default: '{default_download_path}'): ").strip()
    if not download_path_input:
        temp_config['SETTINGS']['DOWNLOAD_PATH'] = '' # Store as empty string so script uses its default
    else:
        temp_config['SETTINGS']['DOWNLOAD_PATH'] = download_path_input
        # Ensure the actual download path is created if user specified a custom one
        if not os.path.exists(download_path_input):
            try:
                os.makedirs(download_path_input)
                print(f"Created download directory: {download_path_input}")
            except OSError as e:
                print(f"Warning: Could not create specified download directory '{download_path_input}': {e}. Please ensure it's valid.")

    # 7. Reddit API User-Agent (User's Reddit Username)
    while True:
        reddit_username = input("\n[7/7] Enter your Reddit username (e.g., YourRedditUsername). This is used for API requests and won't be shared: ").strip()
        if reddit_username:
            temp_config['REDDIT_API']['USER_AGENT'] = f"Windows:WallpaperChangerScript:v1.0 (by /u/{reddit_username})"
            break
        else:
            print("Reddit username cannot be empty. Please enter one.")

    # --- Configuration Summary and Confirmation ---
    print("\n--- Configuration Summary ---")
    print(f"Base Directory: {base_dir}")
    for section in temp_config.sections():
        print(f"[{section}]")
        for key, value in temp_config.items(section):
            print(f"  {key} = {value}")
    
    while True:
        confirm = input("\nDoes this configuration look correct? (yes/no) [default: yes]: ").strip().lower()
        if confirm in ('yes', 'y', ''):
            break
        elif confirm in ('no', 'n'):
            print("\nConfiguration not confirmed. Restarting setup...\n")
            # If the user restarts, we call the setup_initial_config again.
            # We return False to prevent the main script from running after this call.
            setup_initial_config() 
            return False 
        else:
            print("Invalid input. Please enter 'yes' or 'no'.")

    # Save Config
    with open(GLOBAL_CONFIG_PATH, 'w') as configfile:
        temp_config.write(configfile)
    print(f"\nConfiguration saved to: {GLOBAL_CONFIG_PATH}")

    # Generate Task Scheduler Script
    run_script_after_setup = True # Default to running after setup
    while True:
        schedule_task = input("\nDo you want to automatically schedule this script to run with Windows Task Scheduler? (yes/no) [default: yes]: ").strip().lower()
        if schedule_task in ('yes', 'y', ''):
            # Generate PowerShell script content
            task_name = "WallpaperChanger"
            python_exe_path = os.path.join(GLOBAL_SCRIPT_DIR, 'venv', 'Scripts', 'python.exe')
            script_path_full = os.path.join(GLOBAL_SCRIPT_DIR, 'main.py')
            log_path_full = os.path.join(base_dir, DEFAULT_LOG_FILENAME)
            
            task_script_content = f"""
# This script will create/update a Windows Scheduled Task for your wallpaper changer.
# Save this content as a .ps1 file (e.g., setup_task.ps1) and run it AS ADMINISTRATOR in PowerShell.

# --- Configuration Variables ---
$TaskName = "{task_name}"
$ScriptPath = "{script_path_full}"
$PythonExePath = "{python_exe_path}"
$WorkingDirectory = "{GLOBAL_SCRIPT_DIR}" # Keep this as the directory where main.py resides
$LogPath = "{log_path_full}"

# --- Task Creation Logic ---

Write-Host "Attempting to create/update scheduled task '$TaskName'."

# Check if the task already exists. If it does, delete it to create a fresh one.
if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {{
    Write-Host "Task '$TaskName' already exists. Deleting existing task..."
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:`$false
}}

# Define the action: Execute your Python script using the venv's python.exe
# We redirect output (stdout and stderr) to a log file for easier debugging.
$Action = New-ScheduledTaskAction -Execute "$PythonExePath" -Argument "`"$ScriptPath`" >> `"$LogPath`" 2>&1" -WorkingDirectory "`"$WorkingDirectory`""

# Determine trigger based on user's selected interval
$Interval = "{temp_config['SETTINGS']['CHANGE_INTERVAL']}"
$Trigger = `$null

if ($Interval -eq "daily") {{
    $Trigger = New-ScheduledTaskTrigger -Daily -At "9:00 AM" # Default daily at 9 AM, user can change later in Task Scheduler GUI
    Write-Host "Configuring daily task."
}} elseif ($Interval -eq "hourly") {{
    $Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration ([TimeSpan]::MaxValue)
    Write-Host "Configuring hourly task."
}} elseif ($Interval -eq "minutely") {{
    $Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 1) -RepetitionDuration ([TimeSpan]::MaxValue)
    Write-Host "Configuring minutely task."
}} else {{ # Seconds interval or fallback
    # For seconds, we'll make it run once immediately and repeat with the specified interval
    $Seconds = [int]$Interval
    $Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Seconds $Seconds) -RepetitionDuration ([TimeSpan]::MaxValue)
    Write-Host "Configuring task to repeat every $($Seconds) seconds."
}}

# Define task settings for reliability and behavior
$Settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable ` # If a scheduled start is missed, run the task as soon as possible
    -RunOnceIfMissed `    # Run the task once if a scheduled start is missed
    -AllowDemandStart `   # Allow the task to be run manually
    -Compatibility V2.1   # Use modern task settings

# Register the scheduled task
Register-ScheduledTask -Action `$Action -Trigger `$Trigger -TaskName `$TaskName -Description "Automatically changes desktop wallpaper from Reddit." -Settings `$Settings

Write-Host ""
Write-Host "Scheduled task '$TaskName' created successfully."
Write-Host "Script output will be saved to: `$LogPath"
Write-Host "To view/modify this task, open Task Scheduler (taskschd.msc) and navigate to 'Task Scheduler Library'."
"""
            print("\n--- Task Scheduler Setup ---")
            print("To schedule the script to run automatically, copy the PowerShell code below.")
            print("Then, open PowerShell AS ADMINISTRATOR (right-click PowerShell -> Run as administrator),")
            print("paste the code, and press Enter.")
            print("----------------------------------------------------------------------------------")
            print(task_script_content)
            print("----------------------------------------------------------------------------------")
            break
        elif schedule_task in ('no', 'n'):
            print("You can manually schedule the script later if needed.")
            break
        else:
            print("Invalid input. Please enter 'yes' or 'no'.")

    # --- Option to Run Immediately After Setup ---
    while True:
        run_now = input("\nWould you like to run the wallpaper changer once now to test it? (yes/no) [default: yes]: ").strip().lower()
        if run_now in ('yes', 'y', ''):
            return True # Proceed to run the script
        elif run_now in ('no', 'n'):
            print("The script will not run immediately. You can run it manually or via Task Scheduler.")
            return False # Exit after setup
        else:
            print("Invalid input. Please enter 'yes' or 'no'.")


# --- Main execution block ---
if __name__ == "__main__":
    print("Starting wallpaper script...")

    # Check if config.ini exists. If not, run interactive setup.
    should_run_main_logic = True # Flag to control if main logic should execute
    if not os.path.exists(GLOBAL_CONFIG_PATH):
        print("\n--- First Run Setup ---")
        print("It looks like this is your first time running the script.")
        should_run_main_logic = setup_initial_config() # setup_initial_config now returns True/False
        print("\n--- Setup Complete ---")
        if should_run_main_logic:
            print("The script will now proceed with the configured settings.")
        else:
            sys.exit("Setup finished. Script terminated as per user's choice.")

    # Proceed with main logic only if should_run_main_logic is True
    if should_run_main_logic:
        # Now, load settings (config.ini should exist after setup_initial_config)
        settings, reddit_api_settings = load_config()

        # Check internet connection
        if not check_internet_connection():
            sys.exit("Script terminated due to no internet connection.")

        # Get resolution details and preference
        detected_res, target_res, allow_variation = get_resolutions_and_preference(settings)

        # Determine and ensure the download directory exists
        configured_download_path = settings.get('DOWNLOAD_PATH').strip()
        if not configured_download_path:
            # If DOWNLOAD_PATH is empty in config, use default subfolder within base_dir (where config is)
            download_path = os.path.join(os.path.dirname(GLOBAL_CONFIG_PATH), DEFAULT_WALLPAPER_DIR_NAME)
        else:
            download_path = configured_download_path

        if not os.path.exists(download_path):
            os.makedirs(download_path)
            print(f"Created download directory: {download_path}")
        else:
            print(f"Using download directory: {download_path}")

        # Fetch posts from Reddit
        reddit_posts = get_reddit_posts(settings, reddit_api_settings)
        if not reddit_posts:
            sys.exit("No posts fetched from Reddit. Script terminated.")

        # Filter suitable wallpapers
        suitable_wallpapers = filter_wallpapers(reddit_posts, target_res, allow_variation, settings)

        if not suitable_wallpapers:
            sys.exit("No suitable wallpapers found after filtering. Script terminated.")
        
        # --- Load History and Filter for Uniqueness ---
        current_history = load_history()
        print(f"Loaded wallpaper history ({len(current_history)} items).")

        available_wallpapers_to_try = [w for w in suitable_wallpapers if w['url'] not in current_history]
        
        if not available_wallpapers_to_try:
            print("No new unique wallpapers found. Re-using from historical list to ensure a wallpaper change attempt.")
            available_wallpapers_to_try = list(suitable_wallpapers)

        downloaded_file_path = None
        chosen_wallpaper = None

        # --- Loop to select and download until successful or options exhausted ---
        while available_wallpapers_to_try:
            reddit_hosted_options = [w for w in available_wallpapers_to_try if w['is_reddit_host']]
            imgur_hosted_options = [w for w in available_wallpapers_to_try if not w['is_reddit_host']]

            if reddit_hosted_options:
                chosen_wallpaper = random.choice(reddit_hosted_options)
                print(f"\nAttempting to download prioritized i.redd.it wallpaper: '{chosen_wallpaper['title']}'")
            elif imgur_hosted_options:
                chosen_wallpaper = random.choice(imgur_hosted_options)
                print(f"\nNo i.redd.it wallpaper available, attempting Imgur wallpaper: '{chosen_wallpaper['title']}'")
            else:
                print("\nNo more unique wallpapers left to try. All options exhausted.")
                break

            downloaded_file_path = download_wallpaper(chosen_wallpaper, download_path)

            if downloaded_file_path:
                break
            else:
                print(f"Failed to download '{chosen_wallpaper['title']}'. Removing from current options and trying another if available.")
                available_wallpapers_to_try.remove(chosen_wallpaper)

                if not available_wallpapers_to_try:
                    print("All suitable wallpapers attempted and failed. Script cannot set a new wallpaper.")
                    break

        if not downloaded_file_path:
            sys.exit("Script terminated: Failed to download any suitable wallpaper after multiple attempts.")

        # --- Set the downloaded image as Windows wallpaper ---
        wallpaper_style = settings.get('WALLPAPER_STYLE', 'fill')
        if not set_windows_wallpaper(downloaded_file_path, wallpaper_style):
            print("Could not set wallpaper. Manual intervention may be needed.")
        else:
            current_history.append(chosen_wallpaper['url'])
            save_history(current_history)

        # --- Clean up old wallpapers ---
        clean_up_old_wallpapers(download_path, downloaded_file_path)

        print("\nScript finished successfully!")
