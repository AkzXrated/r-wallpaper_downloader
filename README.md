🌠 RedditWallpaperChanger 🌠
Your Desktop, Always Fresh.
Tired of staring at the same old desktop wallpaper? RedditWallpaperChanger is a lightweight, automated Python script that effortlessly transforms your Windows desktop with stunning, high-resolution wallpapers directly from your favorite subreddits. Get a dynamic, ever-evolving backdrop without lifting a finger!

✨ Features
🖼️ Dynamic Wallpaper Updates: Automatically changes your desktop background at intervals you define (daily, hourly, minutely, or custom seconds).
🚀 Seamless Reddit Integration: Fetches fresh, trending wallpapers from any public subreddit you specify (e.g., r/wallpapers, r/earthporn, r/Amoledbackgrounds).
📏 Smart Resolution Matching: Prioritizes images that perfectly fit your screen's resolution and aspect ratio, ensuring a crisp, pixel-perfect display.
🚫 NSFW Content Filtering: Keep your workspace safe and professional with an optional filter for Not Safe For Work content.
👍 Minimum Score Filtering: Only download wallpapers that have met a certain upvote threshold, ensuring high-quality selections.
⚙️ Flexible Display Styles: Supports Windows wallpaper styles including Fill, Fit, Stretch, Center, and Tile to perfectly frame your images.
🔄 Intelligent History & Cleanup: Avoids repeating recently used wallpapers and automatically cleans up old downloaded files to save disk space.
🖥️ User-Friendly Interactive Setup: A simple command-line guide makes first-time configuration a breeze.
⏰ Windows Task Scheduler Integration: Generates a ready-to-use PowerShell script to easily automate the app's execution.
🚀 Getting Started
Follow these steps to set up and run the RedditWallpaperChanger on your Windows machine.

Prerequisites
Before you begin, ensure you have:

Python 3.x installed on your system.
Git installed (optional, but recommended for cloning the repository).
An active internet connection.
Installation
Clone the Repository (Recommended):
Open your terminal/PowerShell and clone this repository:

Bash

git clone https://github.com/AkzXrated/RedditWallpaperChanger.git
cd RedditWallpaperChanger
If you're uploading directly, create a folder named RedditWallpaperChanger and place main.py and .gitignore inside it. Then navigate into that folder.

Create a Virtual Environment:
It's good practice to use a virtual environment to manage dependencies.

PowerShell

python -m venv venv
Activate the Virtual Environment:

PowerShell

.\venv\Scripts\activate
You should see (venv) at the beginning of your PowerShell prompt.

Install Dependencies:

PowerShell

pip install requests screeninfo
🛠️ First-Time Setup & Configuration
The app features an interactive setup guide that will help you configure everything on its first run.

Run the Script:
With your virtual environment active, execute the main.py script:

PowerShell

python main.py
Follow the Interactive Prompts:
The script will ask you for:

A directory to store configuration and history files.
Your preferred wallpaper resolution.
How often you want the wallpaper to change.
The subreddit(s) to fetch from.
Filtering preferences (NSFW, minimum score).
Your desired wallpaper style (Fill, Fit, Stretch, etc.).
A custom download path (optional).
Your Reddit username (for API requests – it's crucial for Reddit to identify legitimate requests and won't be shared).
Review and Confirm:
After collecting all inputs, the script will show you a summary of your configuration. Confirm it's correct, or choose to restart the setup.

Run Immediately (Optional):
After configuration is saved, the script will ask if you want to run the wallpaper changer immediately to test it out.

Upon successful setup, a config.ini file will be created in your chosen base directory, storing all your preferences.

⏰ Automated Scheduling with Task Scheduler
To make your wallpaper changes truly automatic, you'll want to schedule the script to run periodically using Windows Task Scheduler. The app will generate a PowerShell script to simplify this for you.

During First-Time Setup:
When prompted, select yes to automatically schedule the task.

Copy PowerShell Script:
The script will display a block of PowerShell code. Copy the entire code block.

Run PowerShell as Administrator:

Search for "PowerShell" in your Start Menu.
Right-click on "Windows PowerShell" and select "Run as administrator."
Confirm the User Account Control prompt.
Paste and Execute:

In the Administrator PowerShell window, paste the copied code.
Press Enter to run the script.
This will create a scheduled task named WallpaperChanger (or similar) that will run your main.py script at the interval you specified during setup. Script output will be logged to wallpaper_changer_log.txt in your base directory.

📂 Project Structure
After running the app, your project directory will look something like this:

RedditWallpaperChanger/
├── main.py                     # The core Python script
├── venv/                       # Python virtual environment (created by you)
├── .gitignore                  # Tells Git which files/folders to ignore
├── config.ini                  # Your saved configuration (created by the script)
├── wallpaper_history.json      # History of applied wallpapers (created by the script)
├── downloaded_wallpapers/      # Where fetched images are stored (created by the script)
│   └── (your downloaded images)
└── wallpaper_changer_log.txt   # Log file if scheduled via Task Scheduler
⚙️ Customization & Advanced Usage
All your settings are stored in config.ini. You can manually edit this file if you wish, after the initial setup.

Ini, TOML

[SETTINGS]
resolution = 1920x1080
allow_aspect_ratio_variation = True
change_interval = daily
subreddit = wallpapers
filter_nsfw = True
min_score = 100
fetch_limit = 50
download_limit = 5
wallpaper_style = fill
download_path = 

[REDDIT_API]
user_agent = Windows:WallpaperChangerScript:v1.0 (by /u/YourRedditUsername)
Remember: If you manually change config.ini, ensure the values are valid (e.g., resolution in WxH format, change_interval as specified in setup, boolean values as True or False).

🤝 Contributing
Contributions are welcome! If you have ideas for improvements, bug fixes, or new features, feel free to:

Fork the repository.
Create a new branch (git checkout -b feature/AmazingFeature). 3. Commit your changes (git commit -m 'Add some AmazingFeature').
Push to the branch (git push origin feature/AmazingFeature).
Open a Pull Request.
📝 License
This project is licensed under the MIT License - see the LICENSE file for details.

Enjoy your ever-changing, personalized desktop! If you have any questions or run into issues, feel free to open an issue on the GitHub repository.
