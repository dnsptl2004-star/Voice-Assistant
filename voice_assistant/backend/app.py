"""
Voice-Controlled AI Laptop Assistant - Backend
Local-first Flask API for speech command processing and system automation.
"""

import os
from dotenv import load_dotenv
import re
import subprocess
import time
import webbrowser
import logging
import json
import bcrypt
import stripe
from pathlib import Path
from datetime import datetime

# Desktop automation libraries - only import if display is available
HAS_DISPLAY = os.environ.get('DISPLAY') is not None or os.name == 'nt'
pyautogui = None
keyboard = None
sbc = None

if HAS_DISPLAY:
    try:
        import pyautogui
        import keyboard
        import screen_brightness_control as sbc
    except Exception as e:
        logger = logging.getLogger("voice_assistant")
        logger.warning(f"Desktop automation libraries not available: {e}")
        HAS_DISPLAY = False

from volume_control import set_volume, get_volume
from voice_search_service import search_voice
from flask import Flask, request, jsonify
from flask_cors import CORS
from waitress import serve
import auth
import payment

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
load_dotenv(BASE_DIR / ".env.local", override=True)

app = Flask(__name__)
CORS(app)
jwt = auth.init_jwt(app)

# Deduplication tracking for app launches
app_launch_history = {}
DEDUP_WINDOW = 5.0  # seconds

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "assistant.log"

logger = logging.getLogger("voice_assistant")
if not logger.handlers:
    logger.setLevel(logging.INFO)
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    logger.addHandler(file_handler)
    logger.propagate = False

# System Commands Mapping
SYSTEM_COMMANDS = {
    "shutdown": {"action": "shutdown", "requires_confirmation": True},
    "restart": {"action": "restart", "requires_confirmation": True},
    "sleep": {"action": "sleep", "requires_confirmation": False},
    "lock": {"action": "lock", "requires_confirmation": False},
}

# Application Mapping (Windows) with common misinterpretations
APP_MAP = {
    # Browsers
    "chrome": "chrome",
    "google chrome": "chrome",
    "crown": "chrome",
    "chromium": "chrome",
    "firefox": "firefox",
    "fire fox": "firefox",
    "fox": "firefox",
    "edge": "msedge",
    "microsoft edge": "msedge",
    "hedge": "msedge",
    "browser": "chrome",
    
    # Text Editors & IDEs
    "notepad": "notepad",
    "note pad": "notepad",
    "notepad plus plus": "notepad++",
    "notepad++": "notepad++",
    "vscode": "code",
    "vs code": "code",
    "visual studio code": "code",
    "studio": "code",
    "sublime": "sublime_text",
    "atom": "atom",
    
    # Office Applications
    "word": "winword",
    "microsoft word": "winword",
    "ms word": "winword",
    "excel": "excel",
    "microsoft excel": "excel",
    "powerpoint": "powerpnt",
    "power point": "powerpnt",
    "microsoft powerpoint": "powerpnt",
    "outlook": "outlook",
    "teams": "teams",
    "microsoft teams": "teams",
    
    # System Tools
    "calculator": "calc",
    "calc": "calc",
    "paint": "mspaint",
    "ms paint": "mspaint",
    "wordpad": "wordpad",
    "explorer": "explorer",
    "file explorer": "explorer",
    "cmd": "cmd",
    "command prompt": "cmd",
    "terminal": "cmd",
    "powershell": "powershell",
    "power shell": "powershell",
    "settings": "ms-settings:",
    "control panel": "control",
    
    # Media Players
    "spotify": "spotify",
    "spot ify": "spotify",
    "vlc": "vlc",
    "vlc media player": "vlc",
    "media player": "vlc",
    "itunes": "itunes",
    
    # Communication
    "discord": "discord",
    "skype": "skype",
    "zoom": "zoom",
    "slack": "slack",
    "whatsapp": "whatsapp",
    "telegram": "telegram",
    
    # Development Tools
    "git bash": "git-bash",
    "github desktop": "github",
    "docker desktop": "docker",
    "postman": "postman",
    "figma": "figma",
    
    # Other Common Apps
    "steam": "steam",
    "epic games": "epicgameslauncher",
    "obs": "obs64",
    "obs studio": "obs64",
    "photoshop": "photoshop",
    "adobe photoshop": "photoshop",
    "illustrator": "illustrator",
    "adobe illustrator": "illustrator",
    "premiere": "premiere",
    "adobe premiere": "premiere",
    "after effects": "afterfx",
    "adobe after effects": "afterfx",
    "lightroom": "lightroom",
    "adobe lightroom": "lightroom",
    "acrobat": "acrobat",
    "adobe acrobat": "acrobat",
    "reader": "acrord32",
    "adobe reader": "acrord32",

    # Communication Apps
    "telegram": "telegram",
    "signal": "signal",
    "viber": "viber",
    "teamspeak": "teamspeak",
    "discord": "discord",
    "skype": "skype",
    "zoom": "zoom",
    "slack": "slack",
    "whatsapp": "whatsapp",
    "wechat": "wechat",
    "line": "line",

    # Development Tools
    "git bash": "git-bash",
    "github desktop": "github",
    "git": "git",
    "docker": "docker",
    "docker desktop": "docker",
    "postman": "postman",
    "figma": "figma",
    "android studio": "studio",
    "intellij": "idea",
    "intellij idea": "idea",
    "pycharm": "pycharm",
    "visual studio": "devenv",
    "vs": "devenv",
    "xamarin": "xamarin",
    "blender": "blender",
    "unity": "unity",
    "unity hub": "unityhub",
    "unreal": "unreal",
    "unreal engine": "unreal",

    # Media & Entertainment
    "spotify": "spotify",
    "itunes": "itunes",
    "apple music": "itunes",
    "vlc": "vlc",
    "vlc media player": "vlc",
    "media player": "vlc",
    "windows media player": "wmplayer",
    "groove": "groove",
    "netflix": "netflix",
    "amazon prime": "amazon",
    "prime video": "amazon",
    "disney plus": "disneyplus",
    "disney+": "disneyplus",
    "hulu": "hulu",
    "hbo max": "hbomax",
    "twitch": "twitch",

    # Productivity & Notes
    "evernote": "evernote",
    "onenote": "onenote",
    "microsoft onenote": "onenote",
    "notion": "notion",
    "obsidian": "obsidian",
    "bear": "bear",
    "typora": "typora",
    "scratchpad": "scratchpad",

    # Cloud Storage
    "dropbox": "dropbox",
    "google drive": "googledrivesync",
    "onedrive": "onedrive",
    "microsoft onedrive": "onedrive",
    "icloud": "icloud",

    # Security & Utilities
    "norton": "norton",
    "mcafee": "mcafee",
    "avg": "avg",
    "avast": "avast",
    "malwarebytes": "malwarebytes",
    "ccleaner": "ccleaner",
    "defraggler": "defraggler",
    "7-zip": "7z",
    "winzip": "winzip",
    "winrar": "winrar",
    "virtualbox": "virtualbox",
    "vmware": "vmware",
    "putty": "putty",
    "filezilla": "filezilla",
    "winscp": "winscp",

    # Design & Creative
    "gimp": "gimp",
    "inkscape": "inkscape",
    "krita": "krita",
    "paint.net": "paintdotnet",
    "canva": "canva",
    "sketch": "sketch",
    "affinity designer": "affinitydesigner",
    "affinity photo": "affinityphoto",

    # System Tools
    "task manager": "taskmgr",
    "taskmgr": "taskmgr",
    "device manager": "devmgmt",
    "disk management": "diskmgmt",
    "services": "services",
    "event viewer": "eventvwr",
    "performance monitor": "perfmon",
    "registry editor": "regedit",
    "regedit": "regedit",
    "group policy": "gpedit",
    "system information": "msinfo32",
    "system config": "msconfig",

    # Gaming Launchers
    "battle.net": "battle.net",
    "battlenet": "battle.net",
    "origin": "origin",
    "uplay": "uplay",
    "ubisoft connect": "uplay",
    "rockstar launcher": "rockstar",
    "gog galaxy": "goggalaxy",
    "itch.io": "itch",

    # Browsers (more variations)
    "brave": "brave",
    "opera": "opera",
    "vivaldi": "vivaldi",
    "tor browser": "tor",
    "safari": "safari",

    # Email Clients
    "thunderbird": "thunderbird",
    "windows mail": "windowsmail",
    "mail": "windowsmail",

    # Calendar
    "calendar": "outlookcal",
    "windows calendar": "outlookcal",

    # Calculator & Tools
    "calculator": "calc",
    "calc": "calc",
    "scientific calculator": "calc",
    "magnifier": "magnify",
    "snipping tool": "snippingtool",
    "snip": "snippingtool",
    "steps recorder": "psr",

    # Accessibility
    "narrator": "narrator",
    "ease of access": "utilman",

    # Windows Store
    "microsoft store": "winstore",
    "windows store": "winstore",
    "store": "winstore",

    # Windows Security
    "windows security": "windowsdefender",
    "defender": "windowsdefender",
    "windows defender": "windowsdefender",

    # Network Tools
    "network connections": "ncpa.cpl",
    "wifi settings": "wifi",

    # Sound & Audio
    "sound settings": "mmsys.cpl",
    "volume mixer": "sndvol",

    # Display Settings
    "display settings": "desk.cpl",
    "screen resolution": "desk.cpl",

    # Keyboard & Mouse
    "mouse settings": "main.cpl",
    "keyboard settings": "control keyboard",

    # Power Options
    "power options": "powercfg.cpl",
    "battery settings": "powercfg.cpl",

    # Region & Language
    "region settings": "intl.cpl",
    "language settings": "intl.cpl",

    # Date & Time
    "date and time": "timedate.cpl",
    "clock": "timedate.cpl",

    # User Accounts
    "user accounts": "netplwiz",
    "user settings": "netplwiz",

    # Programs & Features
    "programs and features": "appwiz.cpl",
    "add remove programs": "appwiz.cpl",
    "installed programs": "appwiz.cpl",

    # System Properties
    "system properties": "sysdm.cpl",
    "about pc": "sysdm.cpl",
    "computer properties": "sysdm.cpl",

    # Environment Variables
    "environment variables": "sysdm.cpl",

    # Device Manager (duplicate for clarity)
    "device manager": "devmgmt.msc",

    # Windows Update
    "windows update": "wuapp",
    "update settings": "wuapp",

    # Backup & Restore
    "backup and restore": "sdclt",

    # Troubleshooting
    "troubleshoot": "msdt",

    # Remote Desktop
    "remote desktop": "mstsc",
    "rdp": "mstsc",

    # Windows Sandbox
    "windows sandbox": "windowsandbox",

    # Hyper-V Manager
    "hyper-v": "virtmgmt",

    # BitLocker
    "bitlocker": "manage-bde",

    # Windows Firewall
    "firewall": "wf.msc",
    "windows firewall": "wf.msc",

    # Windows To Go
    "windows to go": "imagex",

    # Recovery Environment
    "recovery": "reagentc",

    # System Restore
    "system restore": "rstrui",

    # Disk Cleanup
    "disk cleanup": "cleanmgr",

    # Disk Defragmenter
    "defragment": "dfrgui",
    "defrag": "dfrgui",

    # Check Disk
    "check disk": "chkdsk",

    # System File Checker
    "system file checker": "sfc",

    # Deployment Image Servicing
    "dism": "dism",

    # Windows Package Manager
    "winget": "winget",

    # PowerShell ISE
    "powershell ise": "powershell_ise",

    # Windows Terminal
    "windows terminal": "wt",
    "terminal": "wt",

    # Azure Data Studio
    "azure data studio": "azuredatastudio",

    "sql server": "ssms",
    "sql management studio": "ssms",
}

WEB_MAP = {
    # Search & AI
    "youtube": "https://www.youtube.com",
    "youtube.com": "https://www.youtube.com",
    "gmail": "https://mail.google.com",
    "google": "https://www.google.com",
    "google.com": "https://www.google.com",
    "google maps": "https://maps.google.com",
    "maps": "https://maps.google.com",
    "chatgpt": "https://chat.openai.com",
    "chat gpt": "https://chat.openai.com",
    "openai": "https://openai.com",
    "claude": "https://claude.ai",
    "anthropic": "https://anthropic.com",
    "bing": "https://www.bing.com",
    "bing.com": "https://www.bing.com",
    "duckduckgo": "https://duckduckgo.com",
    "yahoo": "https://www.yahoo.com",
    "ask": "https://www.ask.com",
    
    # Social Media
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "twitter": "https://www.twitter.com",
    "x": "https://www.x.com",
    "linkedin": "https://www.linkedin.com",
    "tiktok": "https://www.tiktok.com",
    "snapchat": "https://www.snapchat.com",
    "pinterest": "https://www.pinterest.com",
    "reddit": "https://www.reddit.com",
    "tumblr": "https://www.tumblr.com",
    "medium": "https://medium.com",
    "quora": "https://www.quora.com",
    "discord": "https://discord.com",
    
    # Development & Tech
    "github": "https://github.com",
    "gitlab": "https://gitlab.com",
    "bitbucket": "https://bitbucket.org",
    "stackoverflow": "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com",
    "dev.to": "https://dev.to",
    "hashnode": "https://hashnode.com",
    "codepen": "https://codepen.io",
    "jsfiddle": "https://jsfiddle.net",
    "replit": "https://replit.com",
    "glitch": "https://glitch.com",
    "heroku": "https://heroku.com",
    "vercel": "https://vercel.com",
    "netlify": "https://netlify.com",
    "digitalocean": "https://digitalocean.com",
    "aws": "https://aws.amazon.com",
    "azure": "https://azure.microsoft.com",
    "google cloud": "https://cloud.google.com",
    
    # Entertainment
    "netflix": "https://www.netflix.com",
    "amazon prime": "https://www.amazon.com/prime",
    "prime video": "https://www.amazon.com/prime",
    "disney plus": "https://www.disneyplus.com",
    "disney+": "https://www.disneyplus.com",
    "hulu": "https://www.hulu.com",
    "hbo max": "https://www.hbomax.com",
    "hbo": "https://www.hbo.com",
    "paramount plus": "https://www.paramountplus.com",
    "peacock": "https://www.peacocktv.com",
    "apple tv": "https://tv.apple.com",
    "crunchyroll": "https://www.crunchyroll.com",
    "funimation": "https://www.funimation.com",
    "twitch": "https://www.twitch.tv",
    "twitch tv": "https://www.twitch.tv",
    "spotify": "https://www.spotify.com",
    "soundcloud": "https://soundcloud.com",
    "pandora": "https://www.pandora.com",
    "apple music": "https://music.apple.com",
    "deezer": "https://www.deezer.com",
    "audible": "https://www.audible.com",
    
    # Shopping
    "amazon": "https://www.amazon.com",
    "amazon.com": "https://www.amazon.com",
    "ebay": "https://www.ebay.com",
    "etsy": "https://www.etsy.com",
    "walmart": "https://www.walmart.com",
    "target": "https://www.target.com",
    "best buy": "https://www.bestbuy.com",
    "bestbuy": "https://www.bestbuy.com",
    "newegg": "https://www.newegg.com",
    "aliexpress": "https://www.aliexpress.com",
    "alibaba": "https://www.alibaba.com",
    "banggood": "https://www.banggood.com",
    "wish": "https://www.wish.com",
    "shopify": "https://www.shopify.com",
    
    # News & Information
    "wikipedia": "https://www.wikipedia.org",
    "cnn": "https://www.cnn.com",
    "bbc": "https://www.bbc.com",
    "fox news": "https://www.foxnews.com",
    "msnbc": "https://www.msnbc.com",
    "reuters": "https://www.reuters.com",
    "associated press": "https://apnews.com",
    "ap news": "https://apnews.com",
    "nytimes": "https://www.nytimes.com",
    "new york times": "https://www.nytimes.com",
    "washington post": "https://www.washingtonpost.com",
    "wall street journal": "https://www.wsj.com",
    "wsj": "https://www.wsj.com",
    "the guardian": "https://www.theguardian.com",
    "guardian": "https://www.theguardian.com",
    "bbc news": "https://www.bbc.com/news",
    "techcrunch": "https://techcrunch.com",
    "the verge": "https://www.theverge.com",
    "engadget": "https://www.engadget.com",
    "wired": "https://www.wired.com",
    "ars technica": "https://arstechnica.com",
    
    # Education
    "coursera": "https://www.coursera.org",
    "edx": "https://www.edx.org",
    "udemy": "https://www.udemy.com",
    "khan academy": "https://www.khanacademy.org",
    "skillshare": "https://www.skillshare.com",
    "pluralsight": "https://www.pluralsight.com",
    "lynda": "https://www.lynda.com",
    "linkedin learning": "https://www.linkedin.com/learning",
    "mit opencourseware": "https://ocw.mit.edu",
    "crash course": "https://www.crashcourse.com",
    "brilliant": "https://brilliant.org",
    "codecademy": "https://www.codecademy.com",
    "free code camp": "https://www.freecodecamp.org",
    "freecodecamp": "https://www.freecodecamp.org",
    "w3schools": "https://www.w3schools.com",
    "mdn": "https://developer.mozilla.org",
    "mozilla developer": "https://developer.mozilla.org",
    
    # Productivity & Tools
    "notion": "https://www.notion.so",
    "trello": "https://trello.com",
    "asana": "https://asana.com",
    "slack": "https://slack.com",
    "zoom": "https://zoom.us",
    "microsoft teams": "https://teams.microsoft.com",
    "teams": "https://teams.microsoft.com",
    "google drive": "https://drive.google.com",
    "drive": "https://drive.google.com",
    "dropbox": "https://www.dropbox.com",
    "onedrive": "https://onedrive.live.com",
    "icloud": "https://www.icloud.com",
    "google docs": "https://docs.google.com",
    "docs": "https://docs.google.com",
    "google sheets": "https://sheets.google.com",
    "sheets": "https://sheets.google.com",
    "google slides": "https://slides.google.com",
    "slides": "https://slides.google.com",
    "canva": "https://www.canva.com",
    "figma": "https://www.figma.com",
    "sketch": "https://www.sketch.com",
    "adobe creative cloud": "https://www.adobe.com/creativecloud",
    "grammarly": "https://www.grammarly.com",
    "hemingway": "https://hemingwayapp.com",
    "evernote": "https://evernote.com",
    "onenote": "https://www.onenote.com",
    
    # Reference
    "dictionary": "https://www.dictionary.com",
    "thesaurus": "https://www.thesaurus.com",
    "urban dictionary": "https://www.urbandictionary.com",
    "wolfram alpha": "https://www.wolframalpha.com",
    "calculator": "https://www.calculator.net",
    "unit converter": "https://www.unitconverters.net",
    "weather": "https://weather.com",
    "accuweather": "https://www.accuweather.com",
    
    # Finance
    "paypal": "https://www.paypal.com",
    "venmo": "https://venmo.com",
    "cash app": "https://cash.app",
    "square": "https://squareup.com",
    "stripe": "https://stripe.com",
    "robinhood": "https://robinhood.com",
    "coinbase": "https://www.coinbase.com",
    "binance": "https://www.binance.com",
    "yahoo finance": "https://finance.yahoo.com",
    "bloomberg": "https://www.bloomberg.com",
    "morningstar": "https://www.morningstar.com",
    
    # Travel
    "expedia": "https://www.expedia.com",
    "booking.com": "https://www.booking.com",
    "airbnb": "https://www.airbnb.com",
    "tripadvisor": "https://www.tripadvisor.com",
    "kayak": "https://www.kayak.com",
    "google flights": "https://flights.google.com",
    "skyscanner": "https://www.skyscanner.com",
    "priceline": "https://www.priceline.com",
    "hotels.com": "https://www.hotels.com",
    
    # Food & Delivery
    "uber eats": "https://www.ubereats.com",
    "doordash": "https://www.doordash.com",
    "grubhub": "https://www.grubhub.com",
    "instacart": "https://www.instacart.com",
    "hellofresh": "https://www.hellofresh.com",
    "blue apron": "https://www.blueapron.com",
    "yelp": "https://www.yelp.com",
    "tripadvisor": "https://www.tripadvisor.com",
    "opentable": "https://www.opentable.com",
    
    # Health & Fitness
    "myfitnesspal": "https://www.myfitnesspal.com",
    "strava": "https://www.strava.com",
    "fitbit": "https://www.fitbit.com",
    "peloton": "https://www.onepeloton.com",
    "headspace": "https://www.headspace.com",
    "calm": "https://www.calm.com",
    "webmd": "https://www.webmd.com",
    "mayo clinic": "https://www.mayoclinic.org",
    
    # Gaming
    "steam": "https://store.steampowered.com",
    "epic games": "https://www.epicgames.com",
    "itch.io": "https://itch.io",
    "gog": "https://www.gog.com",
    "twitch": "https://www.twitch.tv",
    "discord": "https://discord.com",
    "roblox": "https://www.roblox.com",
    "minecraft": "https://www.minecraft.net",
    
    # Sports
    "espn": "https://www.espn.com",
    "nfl": "https://www.nfl.com",
    "nba": "https://www.nba.com",
    "mlb": "https://www.mlb.com",
    "nhl": "https://www.nhl.com",
    "fifa": "https://www.fifa.com",
    "uefa": "https://www.uefa.com",
    
    # Government & Organizations
    "white house": "https://www.whitehouse.gov",
    "united nations": "https://www.un.org",
    "who": "https://www.who.int",
    "cdc": "https://www.cdc.gov",
    "nasa": "https://www.nasa.gov",
    "noaa": "https://www.noaa.gov",
    
    # Other Popular Sites
    "imgur": "https://imgur.com",
    "flickr": "https://www.flickr.com",
    "vimeo": "https://vimeo.com",
    "dailymotion": "https://www.dailymotion.com",
    "archive.org": "https://archive.org",
    "wayback machine": "https://archive.org/web",
    "craigslist": "https://www.craigslist.org",
    "angellist": "https://angel.co",
    "product hunt": "https://www.producthunt.com",
    "hacker news": "https://news.ycombinator.com",
}

BROWSER_CANDIDATES = ["msedge", "chrome", "firefox"]

# Command synonyms for better natural language understanding
COMMAND_SYNONYMS = {
    "open": ["open", "launch", "start", "run", "begin", "initiate", "fire up", "boot up", "turn on", "activate", "execute"],
    "close": ["close", "exit", "quit", "stop", "end", "shut down", "terminate", "kill", "shutdown", "deactivate"],
    "search": ["search", "find", "look up", "google", "lookup", "query", "browse for", "explore", "hunt for", "seek"],
    "increase": ["increase", "raise", "turn up", "boost", "up", "higher", "more", "louder", "brighter", "enhance", "amplify", "maximize"],
    "decrease": ["decrease", "lower", "turn down", "reduce", "down", "less", "quieter", "dimmer", "decrease", "diminish", "minimize"],
    "set": ["set", "adjust", "change", "make", "put", "configure", "modify", "alter", "update", "establish"],
    "create": ["create", "make", "new", "add", "generate", "build", "construct", "establish", "start", "initiate"],
    "delete": ["delete", "remove", "trash", "erase", "eliminate", "destroy", "wipe", "clear", "discard"],
    "play": ["play", "resume", "start playing", "begin", "unpause", "continue"],
    "pause": ["pause", "stop playing", "freeze", "halt", "suspend"],
    "next": ["next", "skip", "forward", "advance", "proceed"],
    "previous": ["previous", "back", "rewind", "last", "go back", "return"],
    "mute": ["mute", "silent", "silence", "turn off sound", "quiet"],
    "unmute": ["unmute", "unmute", "turn on sound", "restore sound"],
    "show": ["show", "display", "reveal", "present", "exhibit"],
    "hide": ["hide", "conceal", "cover", "mask", "bury"],
    "minimize": ["minimize", "shrink", "reduce", "contract", "dock"],
    "maximize": ["maximize", "enlarge", "expand", "fullscreen", "full screen"],
    "restore": ["restore", "recover", "bring back", "return", "reset"],
    "switch": ["switch", "change", "toggle", "flip", "alternate"],
    "copy": ["copy", "duplicate", "clone", "replicate"],
    "paste": ["paste", "insert", "place", "put"],
    "cut": ["cut", "clip", "snip", "extract"],
    "undo": ["undo", "revert", "go back", "reverse", "cancel"],
    "redo": ["redo", "reapply", "restore", "repeat"],
    "save": ["save", "store", "keep", "preserve", "archive"],
    "print": ["print", "output", "produce", "generate"],
    "refresh": ["refresh", "reload", "renew", "update", "restart"],
    "find": ["find", "search", "locate", "discover", "detect"],
    "select": ["select", "choose", "pick", "highlight", "mark"],
    "zoom": ["zoom", "magnify", "enlarge", "scale"],
    "lock": ["lock", "secure", "protect", "block"],
    "unlock": ["unlock", "unsecure", "unblock", "release"],
    "shutdown": ["shutdown", "shut down", "power off", "turn off", "switch off"],
    "restart": ["restart", "reboot", "reboot", "reset"],
    "sleep": ["sleep", "hibernate", "suspend", "standby"],
    "screenshot": ["screenshot", "capture", "snap", "screen capture", "take picture"],
    "record": ["record", "capture", "film", "tape"],
    "stop": ["stop", "end", "finish", "complete", "halt"],
    "type": ["type", "write", "enter", "input", "insert"],
    "read": ["read", "view", "look at", "examine"],
    "list": ["list", "show", "display", "enumerate"],
    "go": ["go", "navigate", "move", "proceed"],
    "back": ["back", "return", "previous", "go back"],
    "forward": ["forward", "advance", "next", "proceed"],
    "home": ["home", "start", "beginning", "main"],
    "help": ["help", "assist", "support", "aid"],
    "exit": ["exit", "leave", "quit", "close"],
    "cancel": ["cancel", "abort", "stop", "terminate"],
    "confirm": ["confirm", "verify", "approve", "accept"],
    "deny": ["deny", "reject", "refuse", "decline"],
    "enable": ["enable", "activate", "turn on", "start"],
    "disable": ["disable", "deactivate", "turn off", "stop"],
    "install": ["install", "setup", "add", "deploy"],
    "uninstall": ["uninstall", "remove", "delete", "erase"],
    "update": ["update", "upgrade", "refresh", "renew"],
    "download": ["download", "save", "get", "retrieve"],
    "upload": ["upload", "send", "transfer", "submit"],
    "connect": ["connect", "link", "join", "pair"],
    "disconnect": ["disconnect", "unlink", "unjoin", "unpair"],
    "send": ["send", "transmit", "deliver", "dispatch"],
    "receive": ["receive", "get", "accept", "obtain"],
    "call": ["call", "phone", "dial", "ring"],
    "message": ["message", "text", "chat", "sms"],
    "email": ["email", "mail", "send mail"],
    "share": ["share", "send", "distribute", "spread"],
    "like": ["like", "favorite", "love", "enjoy"],
    "follow": ["follow", "subscribe", "track"],
    "block": ["block", "ban", "prevent", "stop"],
    "report": ["report", "flag", "notify"],
    "bookmark": ["bookmark", "save", "favorite", "mark"],
    "archive": ["archive", "store", "backup", "save"],
    "restore": ["restore", "recover", "unarchive", "retrieve"],
    "rename": ["rename", "change name", "retitle"],
    "move": ["move", "transfer", "relocate", "shift"],
    "copy": ["copy", "duplicate", "clone"],
    "paste": ["paste", "insert", "place"],
    "cut": ["cut", "clip", "snip"],
}

def build_general_response(user_input):
    """Provide a quick local conversational response without cloud APIs."""
    text = (user_input or "").strip()
    lowered = sanitize_spoken_text(text)
    compact = re.sub(r"\s+", "", lowered)

    def reply(message):
        return {
            "intent": "general_query",
            "confidence": 78,
            "action": "Respond to query",
            "response": message,
            "requires_confirmation": False,
            "parameters": {},
        }

    if not lowered:
        return reply("Please say or type something and I will help.")

    if lowered in {"hi", "hello", "hey", "hi assistant", "hello assistant"}:
        return reply("Hello. I can chat with you and also control apps, web, media, volume, and brightness.")

    if "how are you" in lowered or compact in {"howareyou", "howru"}:
        return reply("I am working well and ready to help. You can ask me questions or give laptop commands.")

    if "thank you" in lowered or "thanks" in lowered:
        return reply("You're welcome. I am here to help.")

    if "bye" in lowered or "goodbye" in lowered:
        return reply("Goodbye. Call me again when you need help.")

    if "what can you do" in lowered or compact == "whatcanyoudo" or "help" == lowered:
        return reply("I can open apps and websites, search the web, type text, control volume, brightness, media, and answer common questions locally.")

    if "what time is it" in lowered or "current time" in lowered:
        from datetime import datetime
        current_time = datetime.now().strftime("%I:%M %p")
        return reply(f"The current time is {current_time}.")

    if "what day is it" in lowered or "what's today" in lowered:
        from datetime import datetime
        current_date = datetime.now().strftime("%A, %B %d, %Y")
        return reply(f"Today is {current_date}.")

    if "tell me a joke" in lowered or "joke" in lowered:
        jokes = [
            "Why don't scientists trust atoms? Because they make up everything!",
            "Why did the scarecrow win an award? Because he was outstanding in his field!",
        ]
        import random
        return reply(random.choice(jokes))

    if "tell me a fact" in lowered or "random fact" in lowered:
        facts = [
            "Honey never spoils. Archaeologists have found 3,000-year-old honey in Egyptian tombs that was still edible.",
            "Octopuses have three hearts and blue blood.",
        ]
        import random
        return reply(random.choice(facts))

    # Professional and Business Context Responses (essential only)
    if "productivity tips" in lowered or "work tips" in lowered:
        tips = [
            "Use the Pomodoro Technique: Work for 25 minutes, then take a 5-minute break.",
            "Prioritize tasks using the Eisenhower Matrix.",
            "Time-block your calendar to dedicate specific hours to specific tasks.",
        ]
        import random
        return reply(random.choice(tips))

    math_match = re.fullmatch(r"(what is |calculate |solve )?([0-9+\-*/(). ]+)", lowered)
    if math_match:
        expression = math_match.group(2).strip()
        try:
            if re.fullmatch(r"[0-9+\-*/(). ]+", expression):
                result = eval(expression, {"__builtins__": {}}, {})
                return reply(f"The answer is {result}.")
        except Exception:
            pass

    return reply("I am running in local mode. I can handle laptop commands, basic conversation, jokes, date, time, and simple math without any online API.")


def build_api_conversation_response(user_input):
    """Use the configured API-backed search/chat provider for normal conversation."""
    local_response = build_general_response(user_input)
    local_text = (local_response.get("response") or "").strip()

    # Keep tiny conversational turns instant instead of waiting on the API path.
    if user_input and "local mode" not in local_text.lower():
        local_response["source"] = "local-fast"
        local_response["confidence"] = max(local_response.get("confidence", 78), 88)
        return local_response

    result = search_voice(user_input)

    if not isinstance(result, dict):
        fallback = build_general_response(user_input)
        fallback["response"] = "Conversation API did not return a valid response. Commands still work locally."
        fallback["source"] = "api-error"
        return fallback

    if result.get("error"):
        fallback = build_general_response(user_input)
        error_text = str(result.get("error") or "").lower()
        if "rejected the api key" in error_text:
            fallback["response"] = (
                "The Vapi API key is invalid or not accepted. "
                "Update VAPI_API_KEY in backend/.env.local with a valid Vapi private key. "
                "Commands still work locally."
            )
        else:
            fallback["response"] = (
                "Conversation API is not working right now, so I could not answer that with the online assistant. "
                "Commands still work locally."
            )
        fallback["source"] = "api-error"
        fallback["api_error"] = str(result.get("error"))
        return fallback

    answer = str(result.get("answer") or "").strip()
    if answer:
        return {
            "intent": "general_query",
            "confidence": 92,
            "action": "Respond to query",
            "response": answer,
            "requires_confirmation": False,
            "parameters": {},
            "data": result,
            "source": "api",
        }

    provider = str(result.get("provider") or "").strip().lower()
    search_results = result.get("results") or []
    query = (result.get("query") or user_input or "").strip()

    if not isinstance(search_results, list) or not search_results:
        return {
            "intent": "general_query",
            "confidence": 82,
            "action": "Respond to query",
            "response": result.get("message") or f"I could not find a strong answer for {user_input}.",
            "requires_confirmation": False,
            "parameters": {},
            "data": result,
            "source": "api",
        }

    first_item = search_results[0] if search_results else {}
    snippet = str(first_item.get("snippet") or "").strip()
    title = str(first_item.get("title") or "").strip()

    cleaned_snippet = re.sub(r"\s+", " ", snippet).strip(" .")
    cleaned_title = re.sub(r"\s+", " ", title).strip(" .")

    if cleaned_snippet:
        response_text = cleaned_snippet
    elif cleaned_title:
        response_text = cleaned_title
    else:
        response_text = result.get("message") or f"I found information related to {query}."

    if query.lower().startswith("what is ") and cleaned_snippet:
        topic = query[8:].strip(" ?.")
        if topic:
            response_text = f"{topic.capitalize()} is {cleaned_snippet[0].lower() + cleaned_snippet[1:]}" if len(cleaned_snippet) > 1 else f"{topic.capitalize()} is {cleaned_snippet.lower()}"

    return {
        "intent": "general_query",
        "confidence": 90,
        "action": "Respond to query",
        "response": response_text,
        "requires_confirmation": False,
        "parameters": {},
        "data": result,
        "source": "api",
    }


def log_event(event_name, **details):
    """Write structured events to the backend log file."""
    safe_details = {key: str(value) for key, value in details.items()}
    joined = " ".join(f"{key}={value!r}" for key, value in safe_details.items())
    logger.info("%s %s", event_name, joined)


@app.route("/", methods=["GET"])
def index():
    """Root route - returns API information."""
    return jsonify({
        "service": "Voice Assistant Backend API",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "health": "/api/health",
            "process_command": "/api/process-command (POST)",
            "execute": "/api/execute (POST)",
            "voice_search": "/api/voice-search (GET)",
            "client_log": "/api/client-log (POST)"
        }
    })


@app.route("/api/process-command", methods=["POST"])
@auth.jwt_required(optional=True)
def process_command():
    """Process spoken input by keeping commands local and routing conversation to the API."""
    data = request.json or {}

    user_input = (data.get("text") or "").strip()
    if not user_input:
        return jsonify({"error": "No input provided"}), 400

    # Check usage limit for authenticated users
    user_id = auth.get_jwt_identity()
    if user_id and not auth.check_usage_limit(user_id):
        return jsonify({
            "error": "Usage limit exceeded",
            "message": "Free tier limit reached. Please upgrade to premium for unlimited access.",
            "usage_count": auth.get_user_usage(user_id),
            "limit": 100
        }), 429

    result = parse_command_locally(user_input)
    if result["intent"] in {"general_query", "unknown"}:
        result = build_api_conversation_response(user_input)
    
    # Increment usage for authenticated users
    if user_id:
        auth.increment_usage(user_id)
    
    log_event(
        "process_command",
        user_input=user_input,
        intent=result.get("intent", ""),
        response=result.get("response", ""),
        parameters=result.get("parameters", {}),
    )
    return jsonify(result)


@app.route("/api/execute", methods=["POST"])
@auth.jwt_required(optional=True)
def execute_command():
    """Execute system command based on AI intent."""
    data = request.json
    intent = data.get("intent", "")
    parameters = data.get("parameters", {})
    confirmed = data.get("confirmed", False)
    
    # Check usage limit for authenticated users
    user_id = auth.get_jwt_identity()
    if user_id and not auth.check_usage_limit(user_id):
        return jsonify({
            "error": "Usage limit exceeded",
            "message": "Free tier limit reached. Please upgrade to premium for unlimited access.",
            "usage_count": auth.get_user_usage(user_id),
            "limit": 100
        }), 429
    
    result = {"success": False, "message": "Unknown command"}
    
    try:
        if intent == "open_app" or intent == "open_and_search":
            result = handle_open_app(parameters)
        elif intent == "close_app":
            result = handle_close_app(parameters)
        elif intent == "search_web":
            result = handle_search_web(parameters)
        elif intent == "type_text":
            result = handle_type_text(parameters)
        elif intent == "create_file":
            result = handle_create_file(parameters)
        elif intent == "create_folder":
            result = handle_create_folder(parameters)
        elif intent == "delete_file":
            result = handle_delete_file(parameters, confirmed)
        elif intent == "media_control":
            result = handle_media_control(parameters)
        elif intent == "volume_control":
            result = handle_volume_control(parameters)
        elif intent == "brightness_control":
            result = handle_brightness_control(parameters)
        elif intent == "system_control":
            result = handle_system_control(parameters, confirmed)
        elif intent == "screenshot":
            result = handle_screenshot(parameters)
        elif intent == "window_control":
            result = handle_window_control(parameters)
        elif intent == "clipboard":
            result = handle_clipboard(parameters)
        elif intent == "keyboard":
            result = handle_keyboard(parameters)
        elif intent == "open_folder":
            result = handle_open_folder(parameters)
        elif intent == "camera":
            result = handle_camera(parameters)
        elif intent == "screen_record":
            result = handle_screen_record(parameters)
        elif intent == "file_system":
            result = handle_file_system(parameters)
        elif intent == "navigation":
            result = handle_navigation(parameters)
        elif intent == "system_info":
            result = handle_system_info(parameters)
        elif intent == "network_tool":
            result = handle_network_tool(parameters)
        elif intent == "automation":
            result = handle_automation(parameters)
        elif intent == "productivity":
            result = handle_productivity(parameters)
        elif intent == "voice_search":
            result = handle_voice_search(parameters)
        else:
            result = {"success": True, "message": "No action needed for this intent", "action": "none"}
    
    except Exception as e:
        result = {"success": False, "message": f"Error executing command: {str(e)}"}

    log_event(
        "execute_command",
        intent=intent,
        parameters=parameters,
        confirmed=confirmed,
        success=result.get("success", False),
        message=result.get("message", ""),
    )
    
    # Increment usage for authenticated users on successful execution
    if user_id and result.get("success", False):
        auth.increment_usage(user_id)
    
    return jsonify(result)


@app.route("/api/client-log", methods=["POST"])
def client_log():
    """Receive frontend-side debug events."""
    data = request.json or {}
    log_event(
        "client_log",
        level=data.get("level", "info"),
        event=data.get("event", "unknown"),
        message=data.get("message", ""),
        details=data.get("details", {}),
    )
    return jsonify({"success": True})


def find_best_app_match(app_name):
    """Find the best matching app using fuzzy matching and aliases."""
    app_name = sanitize_spoken_text(app_name)
    
    # Direct match
    if app_name in APP_MAP:
        return APP_MAP[app_name]
    
    # Try partial matching
    best_match = None
    best_score = 0
    
    for key, value in APP_MAP.items():
        # Exact word match
        if key in app_name or app_name in key:
            score = len(key) / max(len(app_name), len(key))
            if score > best_score and score > 0.5:
                best_score = score
                best_match = value
    
    return best_match if best_match else app_name


def normalize_browser_name(app_name):
    """Map friendly names to commands we can launch on Windows."""
    system_app = find_best_app_match(app_name)
    if system_app == "msedge":
        return "msedge"
    return system_app


def get_available_browser():
    """Pick the first available browser installed on this machine."""
    for candidate in BROWSER_CANDIDATES:
        if is_windows_target_available(candidate):
            return candidate
    return "msedge"


def sanitize_spoken_text(value):
    """Normalize speech text by removing trailing punctuation and filler words."""
    cleaned = (value or "").strip().lower()
    cleaned = re.sub(r"^(please|can you|could you|would you|hey assistant|assistant|jarvis)\s+", "", cleaned)
    cleaned = re.sub(r"[.!?,:;]+$", "", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def build_physical_access_error(action, detail=""):
    """Build a clearer error for desktop automation failures."""
    message = (
        f"Could not {action}. Make sure the backend is running in your signed-in Windows desktop session "
        "and that Windows allows app launches and input automation."
    )
    if detail:
        message = f"{message} Details: {detail}"
    return message


def quote_for_powershell(value):
    """Safely quote a value for a single-quoted PowerShell string."""
    return str(value).replace("'", "''")


def get_web_target(name):
    """Return a website URL for well-known web destinations."""
    normalized = sanitize_spoken_text(name)
    if normalized in WEB_MAP:
        return WEB_MAP[normalized]
    if "." in normalized and " " not in normalized:
        return f"https://{normalized}"
    return None


def is_windows_target_available(target):
    """Check whether a command or executable is available."""
    normalized = sanitize_spoken_text(target)
    if not normalized:
        return False
    result = subprocess.run(
        ["where.exe", normalized],
        capture_output=True,
        text=True,
        shell=False,
    )
    return result.returncode == 0


def resolve_windows_target_path(target):
    """Resolve an executable command to its concrete path when possible."""
    normalized = sanitize_spoken_text(target)
    if not normalized:
        return ""
    result = subprocess.run(
        ["where.exe", normalized],
        capture_output=True,
        text=True,
        shell=False,
    )
    if result.returncode != 0:
        return ""
    matches = [line.strip() for line in result.stdout.splitlines() if line.strip()]
    return matches[0] if matches else ""


def is_process_running(executable_name):
    """Check whether an executable is already running."""
    process_name = executable_name if executable_name.endswith(".exe") else f"{executable_name}.exe"
    result = subprocess.run(
        ["tasklist", "/FI", f"IMAGENAME eq {process_name}"],
        capture_output=True,
        text=True,
        shell=False,
    )
    return process_name.lower() in result.stdout.lower()


def wait_for_process(executable_name, attempts=8, delay=0.2):
    """Wait briefly for a launched GUI process to become visible to tasklist."""
    for _ in range(attempts):
        if is_process_running(executable_name):
            return True
        time.sleep(delay)
    return False


def start_process_with_powershell(file_path, arguments=None):
    """Use PowerShell Start-Process for a more reliable Windows launch."""
    command = f"Start-Process -FilePath '{quote_for_powershell(file_path)}'"
    if arguments:
        quoted_args = ", ".join(f"'{quote_for_powershell(arg)}'" for arg in arguments)
        command += f" -ArgumentList {quoted_args}"
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-Command", command],
        capture_output=True,
        text=True,
        shell=False,
    )
    log_event(
        "powershell_start_process",
        file_path=file_path,
        arguments=arguments or [],
        returncode=result.returncode,
        stdout=(result.stdout or "").strip(),
        stderr=(result.stderr or "").strip(),
    )
    return result.returncode == 0, (result.stderr or result.stdout).strip()


def launch_windows_target(target):
    """Use a reliable Windows launch path for apps and URIs."""
    normalized = sanitize_spoken_text(target)
    if not normalized:
        raise ValueError("No target provided")
    log_event("launch_windows_target_begin", target=target, normalized=normalized)

    if normalized.startswith(("http://", "https://")):
        if open_url(normalized):
            log_event("launch_windows_target_success", target=normalized, mode="url")
            return
        raise OSError(f"Could not open URL: {normalized}")

    if normalized.endswith(":"):
        try:
            os.startfile(normalized)
            return
        except OSError:
            launched, _ = start_process_with_powershell(normalized)
            if launched:
                log_event("launch_windows_target_success", target=normalized, mode="uri")
                return
            subprocess.Popen(["cmd", "/c", "start", "", normalized], shell=False)
            log_event("launch_windows_target_success", target=normalized, mode="cmd-uri")
            return

    if is_windows_target_available(normalized):
        resolved_target = resolve_windows_target_path(normalized) or normalized
        launched, detail = start_process_with_powershell(resolved_target)
        if launched:
            if normalized in {"cmd", "powershell"}:
                log_event("launch_windows_target_success", target=normalized, mode="powershell-start")
                return
            log_event("launch_windows_target_success", target=normalized, mode="powershell-start")
            return
        else:
            raise OSError(detail or f"PowerShell could not start {normalized}")

    try:
        os.startfile(normalized)
        if wait_for_process(normalized, attempts=4, delay=0.25):
            log_event("launch_windows_target_success", target=normalized, mode="startfile-process-running")
            return
        log_event("launch_windows_target_failure", target=normalized, mode="startfile-no-process")
    except OSError:
        pass

    try:
        subprocess.Popen([normalized], shell=False)
        if wait_for_process(normalized, attempts=4, delay=0.25):
            log_event("launch_windows_target_success", target=normalized, mode="popen-process-running")
            return
    except OSError:
        pass

    fallback = subprocess.run(
        ["cmd", "/c", "start", "", normalized],
        capture_output=True,
        text=True,
        shell=False,
    )
    if fallback.returncode == 0:
        if wait_for_process(normalized, attempts=4, delay=0.25):
            log_event("launch_windows_target_success", target=normalized, mode="cmd-start-process-running")
            return

    log_event("launch_windows_target_failure", target=normalized, stderr=fallback.stderr, stdout=fallback.stdout)
    raise OSError(fallback.stderr.strip() or fallback.stdout.strip() or f"Could not open {normalized}")


def open_url(url, browser_hint=""):
    """Open a URL in a preferred or available browser."""
    browser_target = normalize_browser_name(browser_hint) if browser_hint else ""
    if browser_target not in BROWSER_CANDIDATES:
        browser_target = get_available_browser()
    try:
        if browser_target in BROWSER_CANDIDATES and is_windows_target_available(browser_target):
            resolved_browser = resolve_windows_target_path(browser_target) or browser_target
            launched, _ = start_process_with_powershell(resolved_browser, [url])
            if launched and wait_for_process(browser_target):
                log_event("open_url_success", url=url, browser=browser_target, mode="powershell-browser-process-running")
                return True
            subprocess.Popen([browser_target, url], shell=False)
            if wait_for_process(browser_target):
                log_event("open_url_success", url=url, browser=browser_target, mode="popen-browser-process-running")
                return True

        try:
            os.startfile(url)
            if wait_for_process(browser_target, attempts=4, delay=0.25):
                log_event("open_url_success", url=url, browser=browser_target or "default", mode="startfile-browser-process-running")
                return True
        except OSError:
            pass

        launched, _ = start_process_with_powershell(url)
        if launched:
            log_event("open_url_success", url=url, browser=browser_target or "default", mode="powershell-url")
            return True

        for command in (
            ["explorer.exe", url],
            ["cmd", "/c", "start", "", url],
        ):
            try:
                subprocess.Popen(command, shell=False)
                if wait_for_process(browser_target, attempts=4, delay=0.25):
                    log_event("open_url_success", url=url, browser=browser_target or "default", mode="fallback-command-process-running")
                    return True
            except OSError:
                continue

        success = webbrowser.open_new_tab(url)
        log_event("open_url_success", url=url, browser=browser_target or "default", mode="webbrowser", success=success)
        return success
    except Exception as error:
        log_event("open_url_failure", url=url, browser=browser_target, error=error)
        return False


def extract_number(text):
    """Extract the first integer number from text."""
    match = re.search(r"(-?\d{1,3})", text or "")
    return int(match.group(1)) if match else None


def parse_command_locally(user_input):
    """Fallback parser for common commands when Gemini is unavailable."""
    text = user_input.strip()
    lowered = sanitize_spoken_text(text)
    compact = re.sub(r"\s+", "", lowered)

    def response(intent, action, reply, params=None, requires_confirmation=False, confidence=85):
        return {
            "intent": intent,
            "confidence": confidence,
            "action": action,
            "response": reply,
            "requires_confirmation": requires_confirmation,
            "parameters": params or {},
        }

    if not lowered:
        return response("unknown", "No input", "Please say a command.", confidence=0)

    if compact in {"howareyou", "howru"}:
        return response(
            "general_query",
            "Respond to greeting",
            "I am working well and ready to help. You can ask me questions or give laptop commands.",
            confidence=90,
        )

    if any(phrase in lowered for phrase in ["shutdown", "shut down"]):
        return response(
            "system_control",
            "Shutdown system",
            "Are you sure you want to shut down the laptop?",
            {"command": "shutdown"},
            requires_confirmation=True,
        )
    if "restart" in lowered or "reboot" in lowered:
        return response(
            "system_control",
            "Restart system",
            "Are you sure you want to restart the laptop?",
            {"command": "restart"},
            requires_confirmation=True,
        )
    if "sleep" in lowered:
        return response("system_control", "Sleep system", "Putting the system to sleep.", {"command": "sleep"})
    if "lock" in lowered:
        return response("system_control", "Lock workstation", "Locking the workstation.", {"command": "lock"})

    volume_match = re.search(r"volume(?:\s+(?:to|at))?\s+(\d{1,3})", lowered)
    if volume_match:
        level = max(0, min(int(volume_match.group(1)), 100))
        return response("volume_control", f"Set volume to {level}%", f"Setting volume to {level} percent.", {"volume_level": level})
    if "mute" in lowered:
        return response("volume_control", "Mute volume", "Muting the volume.", {"action": "mute"})
    if "volume up" in lowered or "increase volume" in lowered or "turn up volume" in lowered:
        return response("volume_control", "Increase volume", "Increasing the volume.", {"action": "up"})
    if "volume down" in lowered or "decrease volume" in lowered or "turn down volume" in lowered:
        return response("volume_control", "Decrease volume", "Decreasing the volume.", {"action": "down"})

    brightness_match = re.search(r"brightness(?:\s+(?:to|at))?\s+(\d{1,3})", lowered)
    if brightness_match:
        level = max(0, min(int(brightness_match.group(1)), 100))
        return response(
            "brightness_control",
            f"Set brightness to {level}%",
            f"Setting brightness to {level} percent.",
            {"brightness_level": level},
        )
    if "increase brightness" in lowered or "brightness up" in lowered:
        return response("brightness_control", "Increase brightness", "Increasing brightness.", {"action": "up"})
    if "decrease brightness" in lowered or "brightness down" in lowered:
        return response("brightness_control", "Decrease brightness", "Decreasing brightness.", {"action": "down"})

    if "play" in lowered:
        return response("media_control", "Play or pause media", "Toggling media playback.", {"action": "play"})
    if "pause" in lowered:
        return response("media_control", "Play or pause media", "Pausing the media.", {"action": "pause"})
    if "next" in lowered:
        return response("media_control", "Next track", "Skipping to the next track.", {"action": "next"})
    if "previous" in lowered or "back track" in lowered:
        return response("media_control", "Previous track", "Going to the previous track.", {"action": "previous"})

    if lowered.startswith("type ") or lowered.startswith("write "):
        content = text.split(" ", 1)[1].strip() if " " in text else ""
        return response("type_text", "Type text", f"Typing {content}.", {"text": content})

    file_match = re.search(r"create file\s+(.+)", lowered)
    if file_match:
        filename = file_match.group(1).strip()
        return response("create_file", f"Create file {filename}", f"Creating file {filename}.", {"filename": filename})

    folder_match = re.search(r"create folder\s+(.+)", lowered)
    if folder_match:
        foldername = folder_match.group(1).strip()
        return response("create_folder", f"Create folder {foldername}", f"Creating folder {foldername}.", {"foldername": foldername})

    open_search_match = re.search(r"(?:open|launch|start)\s+(\w+)\s+(?:and\s+)?search\s+(?:for\s+)?(.+)", lowered)
    if open_search_match:
        app_name = sanitize_spoken_text(open_search_match.group(1))
        search_query = sanitize_spoken_text(open_search_match.group(2))
        return response(
            "open_and_search",
            f"Open {app_name} and search for {search_query}",
            f"Opening {app_name} and searching for {search_query}.",
            {"app": app_name, "search_query": search_query},
            confidence=90,
        )

    search_in_match = re.search(r"search\s+for\s+(.+?)\s+in\s+(.+)", lowered)
    if search_in_match:
        query = sanitize_spoken_text(search_in_match.group(1))
        app_name = sanitize_spoken_text(search_in_match.group(2))
        return response(
            "open_and_search",
            f"Open {app_name} and search for {query}",
            f"Opening {app_name} and searching for {query}.",
            {"app": app_name, "search_query": query},
            confidence=88,
        )

    voice_search_match = re.search(r"(?:voice search(?: for)?|search with voice api(?: for)?|voice api search(?: for)?|test voice search(?: for)?)\s+(.+)", lowered)
    if voice_search_match:
        query = voice_search_match.group(1).strip()
        return response("voice_search", f"Voice search for {query}", f"Testing voice search for {query}.", {"query": query}, confidence=92)

    if lowered in {"test voice search", "voice search test", "check voice search"}:
        return response("voice_search", "Test voice search", "Testing the backend voice search connection.", {"query": "test query"}, confidence=92)

    search_match = re.search(r"(?:search for|search|google)\s+(.+)", lowered)
    if search_match:
        query = search_match.group(1).strip()
        return response("search_web", f"Search web for {query}", f"Searching for {query}.", {"query": query})

    open_match = re.search(r"(?:open|launch|start)\s+(.+)", lowered)
    if open_match:
        app_name = sanitize_spoken_text(open_match.group(1))
        return response("open_app", f"Open {app_name}", f"Opening {app_name}.", {"app": app_name})

    close_match = re.search(r"(?:close|quit|exit)\s+(.+)", lowered)
    if close_match:
        app_name = sanitize_spoken_text(close_match.group(1))
        return response("close_app", f"Close {app_name}", f"Closing {app_name}.", {"app": app_name})

    # Screenshot command
    if "screenshot" in lowered or "take screenshot" in lowered or "capture screen" in lowered:
        return response("screenshot", "Take screenshot", "Taking a screenshot.", {"action": "screenshot"})

    # Window management commands
    if "minimize" in lowered or "minimize window" in lowered:
        return response("window_control", "Minimize window", "Minimizing the current window.", {"action": "minimize"})
    if "maximize" in lowered or "maximize window" in lowered or "fullscreen" in lowered:
        return response("window_control", "Maximize window", "Maximizing the current window.", {"action": "maximize"})
    if "restore" in lowered or "restore window" in lowered:
        return response("window_control", "Restore window", "Restoring the window.", {"action": "restore"})
    if "switch window" in lowered or "next window" in lowered or "alt tab" in lowered:
        return response("window_control", "Switch window", "Switching to the next window.", {"action": "switch"})

    # Copy/Paste commands
    if "copy" in lowered and "file" not in lowered:
        return response("clipboard", "Copy", "Copying selected content.", {"action": "copy"})
    if "paste" in lowered:
        return response("clipboard", "Paste", "Pasting content.", {"action": "paste"})
    if "cut" in lowered:
        return response("clipboard", "Cut", "Cutting selected content.", {"action": "cut"})

    # Undo/Redo commands
    if "undo" in lowered:
        return response("keyboard", "Undo", "Undoing the last action.", {"action": "undo"})
    if "redo" in lowered:
        return response("keyboard", "Redo", "Redoing the last action.", {"action": "redo"})

    # Save command
    if "save" in lowered:
        return response("keyboard", "Save", "Saving the current file.", {"action": "save"})

    # Print command
    if "print" in lowered:
        return response("keyboard", "Print", "Opening print dialog.", {"action": "print"})

    # Refresh command
    if "refresh" in lowered or "reload" in lowered:
        return response("keyboard", "Refresh", "Refreshing the current page.", {"action": "refresh"})

    # Find command
    if "find" in lowered and "file" not in lowered:
        return response("keyboard", "Find", "Opening find dialog.", {"action": "find"})

    # Select all command
    if "select all" in lowered:
        return response("keyboard", "Select all", "Selecting all content.", {"action": "select_all"})

    # New tab/window commands
    if "new tab" in lowered:
        return response("keyboard", "New tab", "Opening a new tab.", {"action": "new_tab"})
    if "new window" in lowered:
        return response("keyboard", "New window", "Opening a new window.", {"action": "new_window"})

    # Close tab/window commands
    if "close tab" in lowered:
        return response("keyboard", "Close tab", "Closing the current tab.", {"action": "close_tab"})
    if "close window" in lowered:
        return response("keyboard", "Close window", "Closing the current window.", {"action": "close_window"})

    # Zoom commands
    if "zoom in" in lowered:
        return response("keyboard", "Zoom in", "Zooming in.", {"action": "zoom_in"})
    if "zoom out" in lowered:
        return response("keyboard", "Zoom out", "Zooming out.", {"action": "zoom_out"})
    if "zoom reset" in lowered or "reset zoom" in lowered:
        return response("keyboard", "Reset zoom", "Resetting zoom.", {"action": "zoom_reset"})

    # Folder navigation commands
    if "open documents" in lowered or "my documents" in lowered:
        return response("open_folder", "Open Documents", "Opening Documents folder.", {"folder": "documents"})
    if "open downloads" in lowered or "my downloads" in lowered:
        return response("open_folder", "Open Downloads", "Opening Downloads folder.", {"folder": "downloads"})
    if "open desktop" in lowered or "go to desktop" in lowered:
        return response("open_folder", "Open Desktop", "Opening Desktop.", {"folder": "desktop"})
    if "open pictures" in lowered or "my pictures" in lowered:
        return response("open_folder", "Open Pictures", "Opening Pictures folder.", {"folder": "pictures"})
    if "open music" in lowered or "my music" in lowered:
        return response("open_folder", "Open Music", "Opening Music folder.", {"folder": "music"})
    if "open videos" in lowered or "my videos" in lowered:
        return response("open_folder", "Open Videos", "Opening Videos folder.", {"folder": "videos"})

    # Delete file/folder command
    delete_match = re.search(r"(?:delete|remove)\s+(?:file\s+)?(.+)", lowered)
    if delete_match:
        path = delete_match.group(1).strip()
        return response("delete_file", f"Delete {path}", f"Are you sure you want to delete {path}?", {"path": path}, requires_confirmation=True)

    # Show desktop command
    if "show desktop" in lowered:
        return response("window_control", "Show desktop", "Showing desktop.", {"action": "show_desktop"})

    # Lock screen command (already handled but adding more variations)
    if "sign out" in lowered or "log out" in lowered:
        return response("system_control", "Sign out", "Signing out from the current session.", {"command": "signout"}, requires_confirmation=True)

    # Hibernate command
    if "hibernate" in lowered:
        return response("system_control", "Hibernate", "Hibernating the system.", {"command": "hibernate"})

    # Empty recycle bin command
    if "empty recycle bin" in lowered or "empty trash" in lowered:
        return response("system_control", "Empty recycle bin", "Emptying the recycle bin.", {"command": "empty_recycle_bin"}, requires_confirmation=True)

    # Open task manager
    if "task manager" in lowered:
        return response("open_app", "Open Task Manager", "Opening Task Manager.", {"app": "task manager"})

    # Open system settings variations
    if "open settings" in lowered or "system settings" in lowered:
        return response("open_app", "Open Settings", "Opening Settings.", {"app": "settings"})

    # Open control panel variations
    if "open control panel" in lowered:
        return response("open_app", "Open Control Panel", "Opening Control Panel.", {"app": "control panel"})

    # Open file explorer variations
    if "open file explorer" in lowered or "open explorer" in lowered or "open folders" in lowered:
        return response("open_app", "Open File Explorer", "Opening File Explorer.", {"app": "file explorer"})

    # Take photo command (if webcam available)
    if "take photo" in lowered or "take picture" in lowered or "capture photo" in lowered:
        return response("camera", "Take photo", "Taking a photo with the webcam.", {"action": "take_photo"})

    # Record screen command
    if "record screen" in lowered or "screen recording" in lowered:
        return response("screen_record", "Record screen", "Starting screen recording.", {"action": "start_record"})

    # Stop recording command
    if "stop recording" in lowered:
        return response("screen_record", "Stop recording", "Stopping screen recording.", {"action": "stop_record"})

    # Open calculator variations
    if "open calculator" in lowered or "calculate" in lowered and "what is" not in lowered:
        return response("open_app", "Open Calculator", "Opening Calculator.", {"app": "calculator"})

    # Open notepad variations
    if "open notepad" in lowered or "new note" in lowered:
        return response("open_app", "Open Notepad", "Opening Notepad.", {"app": "notepad"})

    # Open command prompt variations
    if "open command prompt" in lowered or "open cmd" in lowered:
        return response("open_app", "Open Command Prompt", "Opening Command Prompt.", {"app": "cmd"})

    # Open PowerShell variations
    if "open powershell" in lowered or "open terminal" in lowered:
        return response("open_app", "Open PowerShell", "Opening PowerShell.", {"app": "powershell"})

    # Clear screen command
    if "clear screen" in lowered or "cls" in lowered:
        return response("keyboard", "Clear screen", "Clearing the terminal screen.", {"action": "clear_screen"})

    # List files command
    if "list files" in lowered or "show files" in lowered or "ls" in lowered:
        return response("file_system", "List files", "Listing files in current directory.", {"action": "list_files"})

    # Go back command
    if "go back" in lowered or "back" in lowered:
        return response("navigation", "Go back", "Going back.", {"action": "go_back"})

    # Go forward command
    if "go forward" in lowered or "forward" in lowered:
        return response("navigation", "Go forward", "Going forward.", {"action": "go_forward"})

    # Go home command
    if "go home" in lowered or "home" in lowered:
        return response("navigation", "Go home", "Going to home page.", {"action": "go_home"})

    # Open URL directly
    url_match = re.search(r"(?:open|go to|visit)\s+(https?://[^\s]+)", lowered)
    if url_match:
        url = url_match.group(1).strip()
        return response("open_app", f"Open {url}", f"Opening {url}.", {"app": url})

    # Search YouTube directly
    youtube_search_match = re.search(r"(?:search|play)\s+(?:on\s+)?youtube\s+(?:for\s+)?(.+)", lowered)
    if youtube_search_match:
        query = youtube_search_match.group(1).strip()
        return response("open_and_search", "Search YouTube", f"Searching YouTube for {query}.", {"app": "youtube", "search_query": query}, confidence=90)

    # Play music on Spotify
    spotify_match = re.search(r"(?:play\s+)?(?:on\s+)?spotify\s+(.+)", lowered)
    if spotify_match:
        query = spotify_match.group(1).strip()
        return response("open_and_search", "Play on Spotify", f"Playing {query} on Spotify.", {"app": "spotify", "search_query": query}, confidence=88)

    # Advanced System Commands
    if "disk cleanup" in lowered or "clean disk" in lowered:
        return response("system_control", "Disk cleanup", "Opening disk cleanup utility.", {"command": "disk_cleanup"}, requires_confirmation=True)

    if "system information" in lowered or "system info" in lowered:
        return response("system_info", "System information", "Opening system information.", {"action": "system_info"})

    if "network status" in lowered or "network info" in lowered:
        return response("system_info", "Network status", "Checking network status.", {"action": "network_status"})

    if "running processes" in lowered or "process list" in lowered or "task list" in lowered:
        return response("system_info", "Running processes", "Opening task manager to view processes.", {"action": "process_list"})

    if "check updates" in lowered or "windows update" in lowered:
        return response("system_control", "Check for updates", "Opening Windows Update.", {"command": "check_updates"})

    if "disk space" in lowered or "storage space" in lowered:
        return response("system_info", "Disk space", "Checking disk space.", {"action": "disk_space"})

    if "memory usage" in lowered or "ram usage" in lowered:
        return response("system_info", "Memory usage", "Checking memory usage.", {"action": "memory_usage"})

    if "cpu usage" in lowered or "processor usage" in lowered:
        return response("system_info", "CPU usage", "Checking CPU usage.", {"action": "cpu_usage"})

    if "battery status" in lowered or "battery info" in lowered:
        return response("system_info", "Battery status", "Checking battery status.", {"action": "battery_status"})

    if "network speed" in lowered or "internet speed" in lowered:
        return response("system_info", "Network speed", "Opening speed test in browser.", {"action": "network_speed"})

    if "ping" in lowered:
        ping_match = re.search(r"ping\s+(.+)", lowered)
        if ping_match:
            target = ping_match.group(1).strip()
            return response("network_tool", "Ping", f"Pinging {target}.", {"action": "ping", "target": target})
        return response("network_tool", "Ping", "Pinging default gateway.", {"action": "ping", "target": "google.com"})

    if "trace route" in lowered or "traceroute" in lowered:
        traceroute_match = re.search(r"(?:trace route|traceroute)\s+(.+)", lowered)
        if traceroute_match:
            target = traceroute_match.group(1).strip()
            return response("network_tool", "Trace route", f"Tracing route to {target}.", {"action": "traceroute", "target": target})

    if "flush dns" in lowered or "clear dns" in lowered:
        return response("network_tool", "Flush DNS", "Flushing DNS cache.", {"action": "flush_dns"})

    if "restart network" in lowered or "reset network" in lowered:
        return response("network_tool", "Restart network", "Restarting network adapter.", {"action": "restart_network"}, requires_confirmation=True)

    if "check firewall" in lowered or "firewall status" in lowered:
        return response("system_info", "Firewall status", "Checking firewall status.", {"action": "firewall_status"})

    if "check antivirus" in lowered or "antivirus status" in lowered:
        return response("system_info", "Antivirus status", "Checking antivirus status.", {"action": "antivirus_status"})

    # Automation Commands
    if "create shortcut" in lowered:
        shortcut_match = re.search(r"create shortcut\s+(?:for\s+)?(.+)", lowered)
        if shortcut_match:
            target = shortcut_match.group(1).strip()
            return response("automation", "Create shortcut", f"Creating shortcut for {target}.", {"action": "create_shortcut", "target": target})

    if "schedule task" in lowered or "create task" in lowered:
        return response("automation", "Schedule task", "Opening Task Scheduler.", {"action": "schedule_task"})

    if "run as administrator" in lowered:
        return response("automation", "Run as admin", "Please specify which application to run as administrator.", {"action": "run_as_admin"})

    if "open with admin" in lowered:
        admin_match = re.search(r"open\s+(.+)\s+(?:with\s+)?admin", lowered)
        if admin_match:
            app = admin_match.group(1).strip()
            return response("open_app", f"Open {app} as admin", f"Opening {app} as administrator.", {"app": app, "run_as_admin": True})

    if "system restore" in lowered:
        return response("system_control", "System restore", "Opening System Restore.", {"command": "system_restore"}, requires_confirmation=True)

    if "check system health" in lowered or "health check" in lowered:
        return response("system_info", "System health check", "Running system health check.", {"action": "health_check"})

    if "view event logs" in lowered or "event logs" in lowered:
        return response("system_info", "Event logs", "Opening Event Viewer.", {"action": "event_logs"})

    if "check services" in lowered or "services list" in lowered:
        return response("system_info", "Services", "Opening Services manager.", {"action": "services"})

    if "manage startup" in lowered or "startup programs" in lowered:
        return response("system_info", "Startup programs", "Opening Task Manager to manage startup programs.", {"action": "startup"})

    if "device manager" in lowered:
        return response("system_info", "Device manager", "Opening Device Manager.", {"action": "device_manager"})

    if "performance monitor" in lowered or "performance" in lowered:
        return response("system_info", "Performance monitor", "Opening Performance Monitor.", {"action": "performance_monitor"})

    # Productivity and Workflow Commands
    if "pomodoro" in lowered or "pomodoro timer" in lowered:
        return response("productivity", "Pomodoro timer", "Starting 25-minute Pomodoro timer.", {"action": "pomodoro_start"})

    if "start focus" in lowered or "focus mode" in lowered:
        return response("productivity", "Focus mode", "Enabling focus mode - notifications will be minimized.", {"action": "focus_mode"})

    if "break time" in lowered or "take a break" in lowered:
        return response("productivity", "Break time", "Starting 5-minute break.", {"action": "break_start"})

    if "start timer" in lowered:
        timer_match = re.search(r"start timer\s+(?:for\s+)?(\d+)\s*(?:minute|min|m)?", lowered)
        if timer_match:
            minutes = int(timer_match.group(1))
            return response("productivity", "Timer", f"Starting timer for {minutes} minutes.", {"action": "timer_start", "minutes": minutes})
        return response("productivity", "Timer", "Starting 10-minute timer.", {"action": "timer_start", "minutes": 10})

    if "stop timer" in lowered or "cancel timer" in lowered:
        return response("productivity", "Stop timer", "Stopping timer.", {"action": "timer_stop"})

    if "create todo" in lowered or "add todo" in lowered or "add task" in lowered:
        todo_match = re.search(r"(?:create todo|add todo|add task)\s+(.+)", lowered)
        if todo_match:
            task = todo_match.group(1).strip()
            return response("productivity", "Create todo", f"Added todo: {task}", {"action": "create_todo", "task": task})
        return response("productivity", "Create todo", "Please specify the task.", {"action": "create_todo"})

    if "show todos" in lowered or "list todos" in lowered or "my tasks" in lowered:
        return response("productivity", "Show todos", "Showing your todo list.", {"action": "show_todos"})

    if "complete todo" in lowered or "done todo" in lowered:
        todo_match = re.search(r"(?:complete todo|done todo)\s+(.+)", lowered)
        if todo_match:
            task = todo_match.group(1).strip()
            return response("productivity", "Complete todo", f"Marked todo as done: {task}", {"action": "complete_todo", "task": task})
        return response("productivity", "Complete todo", "Please specify which task to complete.", {"action": "complete_todo"})

    if "delete todo" in lowered or "remove todo" in lowered:
        todo_match = re.search(r"(?:delete todo|remove todo)\s+(.+)", lowered)
        if todo_match:
            task = todo_match.group(1).strip()
            return response("productivity", "Delete todo", f"Deleted todo: {task}", {"action": "delete_todo", "task": task})
        return response("productivity", "Delete todo", "Please specify which task to delete.", {"action": "delete_todo"})

    if "quick note" in lowered or "jot down" in lowered:
        note_match = re.search(r"(?:quick note|jot down)\s+(.+)", lowered)
        if note_match:
            note = note_match.group(1).strip()
            return response("productivity", "Quick note", f"Saved quick note: {note}", {"action": "quick_note", "note": note})
        return response("productivity", "Quick note", "Please specify the note.", {"action": "quick_note"})

    if "show notes" in lowered or "my notes" in lowered:
        return response("productivity", "Show notes", "Showing your quick notes.", {"action": "show_notes"})

    if "daily plan" in lowered or "plan my day" in lowered:
        return response("productivity", "Daily plan", "Opening daily planning template.", {"action": "daily_plan"})

    if "weekly review" in lowered or "review week" in lowered:
        return response("productivity", "Weekly review", "Opening weekly review template.", {"action": "weekly_review"})

    # Keep only useful productivity tools that actually work
    if "translate text" in lowered:
        return response("productivity", "Translate text", "Opening translation tool.", {"action": "translate_text"})

    if "grammar check" in lowered or "check grammar" in lowered:
        return response("productivity", "Grammar check", "Opening grammar checker.", {"action": "grammar_check"})

    if "word count" in lowered:
        return response("productivity", "Word count", "Opening word count tool.", {"action": "word_count"})

    return response(
        "general_query",
        "Respond to query",
        "I can help with app launch, search, typing, volume, brightness, media, window control, screenshots, clipboard, keyboard shortcuts, folder navigation, system commands, network tools, automation, system information, productivity tools, timers, todos, and notes.",
        confidence=55,
    )


def get_synonym_variations(command_word):
    """Get all variations of a command word."""
    for key, synonyms in COMMAND_SYNONYMS.items():
        if command_word in synonyms:
            return synonyms
    return [command_word]


def handle_open_app(params):
    """Open an application with fuzzy matching support."""
    app_name = sanitize_spoken_text(params.get("app", ""))
    search_query = sanitize_spoken_text(params.get("search_query", ""))

    # Skip if app name is too short (likely a partial recognition)
    if len(app_name) < 3:
        return {"success": False, "message": f"App name too short: {app_name}"}

    # Deduplication check - prevent opening same app within DEDUP_WINDOW seconds
    current_time = time.time()
    if app_name in app_launch_history:
        last_launch_time = app_launch_history[app_name]
        if current_time - last_launch_time < DEDUP_WINDOW:
            logger.info(f"Skipping duplicate launch of {app_name} (last launched {current_time - last_launch_time:.2f}s ago)")
            return {"success": False, "message": f"{app_name} was just opened, skipping duplicate"}

    try:
        # Check web target first before normalizing to system app
        web_target = get_web_target(app_name)
        if web_target:
            if search_query and "youtube" in app_name.lower():
                # Handle youtube search
                url = f"https://www.youtube.com/results?search_query={search_query.replace(' ', '+')}"
                if not open_url(url, get_available_browser()):
                    return {"success": False, "message": build_physical_access_error(f"search for {search_query} in {app_name}")}
                app_launch_history[app_name] = current_time
                return {"success": True, "message": f"Opened {app_name} and searched for {search_query}"}
            if search_query and "chatgpt" in app_name.lower():
                # Handle chatgpt search - open and then type the query
                if not open_url(web_target, get_available_browser()):
                    return {"success": False, "message": build_physical_access_error(f"open {app_name}")}
                # Wait for page to load then type the search query
                if not HAS_DISPLAY or pyautogui is None:
                    return {"success": False, "message": "Desktop automation not available in headless environment"}
                time.sleep(2)
                pyautogui.write(search_query)
                pyautogui.press('enter')
                app_launch_history[app_name] = current_time
                return {"success": True, "message": f"Opened {app_name} and searched for {search_query}"}
            if not open_url(web_target, get_available_browser()):
                return {"success": False, "message": build_physical_access_error(f"open {app_name}")}
            app_launch_history[app_name] = current_time
            return {"success": True, "message": f"Opened {app_name}"}

        # Use fuzzy matching to find best system app
        system_app = normalize_browser_name(app_name)

        if system_app in ["chrome", "firefox", "msedge"] and search_query:
            # Open browser with search
            url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
            if not open_url(url, system_app):
                return {"success": False, "message": build_physical_access_error(f"search for {search_query} in {app_name}")}
            app_launch_history[app_name] = current_time
            return {"success": True, "message": f"Opened {app_name} and searched for {search_query}"}
        if search_query:
            url = f"https://www.google.com/search?q={search_query.replace(' ', '+')}"
            if not open_url(url, get_available_browser()):
                return {"success": False, "message": build_physical_access_error(f"search for {search_query}")}
            app_launch_history[app_name] = current_time
            return {"success": True, "message": f"Searched for {search_query}"}
        else:
            # Open application
            launch_windows_target(system_app)
            app_launch_history[app_name] = current_time
            return {"success": True, "message": f"Opened {app_name}"}
    except Exception as e:
        return {"success": False, "message": build_physical_access_error(f"open {app_name}", str(e))}


def handle_close_app(params):
    """Close an application."""
    app_name = sanitize_spoken_text(params.get("app", ""))
    system_app = find_best_app_match(app_name)

    # Map common app names to their executable names
    app_executables = {
        "chrome": "chrome.exe",
        "msedge": "msedge.exe",
        "edge": "msedge.exe",
        "firefox": "firefox.exe",
        "notepad": "notepad.exe",
        "calculator": "calc.exe",
        "calc": "calc.exe",
    }

    # Try mapped executable first, then use the system app
    executable = app_executables.get(system_app.lower(), system_app)
    if not executable.endswith(".exe"):
        executable = f"{executable}.exe"

    try:
        result = subprocess.run(f"taskkill /f /im {executable}", shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            # Check if it's a browser and try Alt+F4 as fallback
            if system_app.lower() in ["chrome", "msedge", "edge", "firefox"]:
                if HAS_DISPLAY and pyautogui is not None:
                    try:
                        # Try Alt+F4 to close active window
                        pyautogui.hotkey('alt', 'f4')
                        time.sleep(0.5)
                        return {"success": True, "message": f"Closed {app_name}"}
                    except Exception:
                        pass
            return {"success": False, "message": f"{app_name} is not running or could not be closed"}
        return {"success": True, "message": f"Closed {app_name}"}
    except Exception as e:
        return {"success": False, "message": f"Could not close {app_name}: {str(e)}"}


def handle_search_web(params):
    """Perform web search."""
    query = params.get("query", "")
    if not query:
        return {"success": False, "message": "No search query provided"}
    
    try:
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        if not open_url(url):
            return {"success": False, "message": build_physical_access_error(f"search for {query}")}
        return {"success": True, "message": f"Searching for {query}"}
    except Exception as e:
        return {"success": False, "message": build_physical_access_error(f"search for {query}", str(e))}


def handle_type_text(params):
    """Type text using keyboard automation."""
    if not HAS_DISPLAY or pyautogui is None:
        return {"success": False, "message": "Desktop automation not available in headless environment"}
    
    text = params.get("text", "")
    if not text:
        return {"success": False, "message": "No text provided"}
    
    try:
        pyautogui.typewrite(text, interval=0.01)
        return {"success": True, "message": f"Typed: {text}"}
    except Exception as e:
        return {"success": False, "message": build_physical_access_error("type text", str(e))}


def handle_create_file(params):
    """Create a new file."""
    filename = params.get("filename", "")
    content = params.get("content", "")
    
    if not filename:
        return {"success": False, "message": "No filename provided"}
    
    try:
        with open(filename, 'w') as f:
            f.write(content)
        return {"success": True, "message": f"Created file: {filename}"}
    except Exception as e:
        return {"success": False, "message": f"Could not create file: {str(e)}"}


def handle_create_folder(params):
    """Create a new folder."""
    foldername = params.get("foldername", "")
    
    if not foldername:
        return {"success": False, "message": "No folder name provided"}
    
    try:
        os.makedirs(foldername, exist_ok=True)
        return {"success": True, "message": f"Created folder: {foldername}"}
    except Exception as e:
        return {"success": False, "message": f"Could not create folder: {str(e)}"}


def handle_delete_file(params, confirmed):
    """Delete a file or folder."""
    if not confirmed:
        return {"success": False, "message": "Confirmation required", "needs_confirmation": True}
    
    path = params.get("path", "")
    if not path:
        return {"success": False, "message": "No path provided"}
    
    try:
        if os.path.isfile(path):
            os.remove(path)
        elif os.path.isdir(path):
            os.rmdir(path)
        return {"success": True, "message": f"Deleted: {path}"}
    except Exception as e:
        return {"success": False, "message": f"Could not delete: {str(e)}"}


def handle_media_control(params):
    """Control media playback."""
    if not HAS_DISPLAY or keyboard is None:
        return {"success": False, "message": "Desktop automation not available in headless environment"}
    
    action = params.get("action", "").lower()
    
    try:
        if action in ["play", "pause"]:
            keyboard.press_and_release('play/pause media')
            return {"success": True, "message": "Toggled play/pause"}
        elif action == "next":
            keyboard.press_and_release('next track')
            return {"success": True, "message": "Next track"}
        elif action == "previous":
            keyboard.press_and_release('previous track')
            return {"success": True, "message": "Previous track"}
        elif action == "stop":
            keyboard.press_and_release('stop media')
            return {"success": True, "message": "Stopped media"}
        else:
            return {"success": False, "message": "Unknown media action"}
    except Exception as e:
        return {"success": False, "message": build_physical_access_error("control media", str(e))}


def handle_volume_control(params):
    """Control system volume."""
    action = params.get("action", "")
    level = params.get("volume_level", None)
    
    try:
        if level is not None:
            if not set_volume(level):
                return {"success": False, "message": build_physical_access_error("set volume")}
            return {"success": True, "message": f"Volume set to {level}%"}
        elif action == "mute":
            if not HAS_DISPLAY or keyboard is None:
                return {"success": False, "message": "Desktop automation not available in headless environment"}
            keyboard.press_and_release('volume mute')
            return {"success": True, "message": "Volume muted"}
        elif action == "up":
            if not HAS_DISPLAY or keyboard is None:
                return {"success": False, "message": "Desktop automation not available in headless environment"}
            keyboard.press_and_release('volume up')
            return {"success": True, "message": "Volume increased"}
        elif action == "down":
            if not HAS_DISPLAY or keyboard is None:
                return {"success": False, "message": "Desktop automation not available in headless environment"}
            keyboard.press_and_release('volume down')
            return {"success": True, "message": "Volume decreased"}
        else:
            return {"success": False, "message": "Unknown volume action"}
    except Exception as e:
        return {"success": False, "message": build_physical_access_error("control volume", str(e))}


def handle_brightness_control(params):
    """Control screen brightness."""
    if not HAS_DISPLAY or sbc is None:
        return {"success": False, "message": "Desktop automation not available in headless environment"}
    
    level = params.get("brightness_level", None)
    action = params.get("action", "")
    
    try:
        if level is not None:
            sbc.set_brightness(level)
            return {"success": True, "message": f"Brightness set to {level}%"}
        elif action == "up":
            current = sbc.get_brightness()[0]
            sbc.set_brightness(min(current + 10, 100))
            return {"success": True, "message": "Brightness increased"}
        elif action == "down":
            current = sbc.get_brightness()[0]
            sbc.set_brightness(max(current - 10, 0))
            return {"success": True, "message": "Brightness decreased"}
        else:
            return {"success": False, "message": "Unknown brightness action"}
    except Exception as e:
        return {"success": False, "message": build_physical_access_error("control brightness", str(e))}


def handle_system_control(params, confirmed):
    """Handle system commands."""
    command = params.get("command", "").lower()
    
    if SYSTEM_COMMANDS.get(command, {}).get("requires_confirmation", False) and not confirmed:
        return {"success": False, "message": "Confirmation required for this action", "needs_confirmation": True}
    
    try:
        if command == "shutdown":
            subprocess.Popen("shutdown /s /t 60", shell=True)  # 60 second delay for safety
            return {"success": True, "message": "System will shutdown in 60 seconds"}
        elif command == "restart":
            subprocess.Popen("shutdown /r /t 60", shell=True)
            return {"success": True, "message": "System will restart in 60 seconds"}
        elif command == "sleep":
            subprocess.Popen("rundll32.exe powrprof.dll,SetSuspendState 0,1,0", shell=True)
            return {"success": True, "message": "Putting system to sleep"}
        elif command == "lock":
            subprocess.Popen("rundll32.exe user32.dll,LockWorkStation", shell=True)
            return {"success": True, "message": "Workstation locked"}
        elif command == "hibernate":
            subprocess.Popen("shutdown /h", shell=True)
            return {"success": True, "message": "System will hibernate"}
        elif command == "signout":
            subprocess.Popen("shutdown /l", shell=True)
            return {"success": True, "message": "Signing out from current session"}
        elif command == "empty_recycle_bin":
            subprocess.Popen("powershell.exe -Command \"Clear-RecycleBin -Force\"", shell=True)
            return {"success": True, "message": "Emptying recycle bin"}
        else:
            return {"success": False, "message": "Unknown system command"}
    except Exception as e:
        return {"success": False, "message": build_physical_access_error(f"execute {command}", str(e))}


def handle_screenshot(params):
    """Take a screenshot of the screen."""
    if not HAS_DISPLAY or pyautogui is None:
        return {"success": False, "message": "Desktop automation not available in headless environment"}
    
    try:
        from datetime import datetime
        from pathlib import Path
        
        # Create screenshots directory if it doesn't exist
        screenshots_dir = Path.home() / "Pictures" / "Screenshots"
        screenshots_dir.mkdir(parents=True, exist_ok=True)
        
        # Generate filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"screenshot_{timestamp}.png"
        filepath = screenshots_dir / filename
        
        # Take screenshot using pyautogui
        screenshot = pyautogui.screenshot()
        screenshot.save(str(filepath))
        
        return {"success": True, "message": f"Screenshot saved to {filepath}"}
    except Exception as e:
        return {"success": False, "message": build_physical_access_error("take screenshot", str(e))}


def handle_window_control(params):
    """Control window operations."""
    if not HAS_DISPLAY or pyautogui is None:
        return {"success": False, "message": "Desktop automation not available in headless environment"}
    
    action = params.get("action", "").lower()
    
    try:
        if action == "minimize":
            pyautogui.hotkey('win', 'down')
            time.sleep(0.1)
            pyautogui.hotkey('win', 'down')
            return {"success": True, "message": "Window minimized"}
        elif action == "maximize":
            pyautogui.hotkey('win', 'up')
            return {"success": True, "message": "Window maximized"}
        elif action == "restore":
            pyautogui.hotkey('win', 'down')
            return {"success": True, "message": "Window restored"}
        elif action == "switch":
            pyautogui.hotkey('alt', 'tab')
            return {"success": True, "message": "Switched to next window"}
        elif action == "show_desktop":
            pyautogui.hotkey('win', 'd')
            return {"success": True, "message": "Desktop shown"}
        else:
            return {"success": False, "message": "Unknown window action"}
    except Exception as e:
        return {"success": False, "message": build_physical_access_error("control window", str(e))}


def handle_clipboard(params):
    """Handle clipboard operations."""
    if not HAS_DISPLAY or pyautogui is None:
        return {"success": False, "message": "Desktop automation not available in headless environment"}
    
    action = params.get("action", "").lower()
    
    try:
        if action == "copy":
            pyautogui.hotkey('ctrl', 'c')
            return {"success": True, "message": "Content copied to clipboard"}
        elif action == "paste":
            pyautogui.hotkey('ctrl', 'v')
            return {"success": True, "message": "Content pasted from clipboard"}
        elif action == "cut":
            pyautogui.hotkey('ctrl', 'x')
            return {"success": True, "message": "Content cut to clipboard"}
        else:
            return {"success": False, "message": "Unknown clipboard action"}
    except Exception as e:
        return {"success": False, "message": build_physical_access_error("control clipboard", str(e))}


def handle_keyboard(params):
    """Handle keyboard shortcuts."""
    if not HAS_DISPLAY or pyautogui is None:
        return {"success": False, "message": "Desktop automation not available in headless environment"}
    
    action = params.get("action", "").lower()
    
    try:
        if action == "undo":
            pyautogui.hotkey('ctrl', 'z')
            return {"success": True, "message": "Undo performed"}
        elif action == "redo":
            pyautogui.hotkey('ctrl', 'y')
            return {"success": True, "message": "Redo performed"}
        elif action == "save":
            pyautogui.hotkey('ctrl', 's')
            return {"success": True, "message": "File saved"}
        elif action == "print":
            pyautogui.hotkey('ctrl', 'p')
            return {"success": True, "message": "Print dialog opened"}
        elif action == "refresh":
            pyautogui.hotkey('f5')
            return {"success": True, "message": "Page refreshed"}
        elif action == "find":
            pyautogui.hotkey('ctrl', 'f')
            return {"success": True, "message": "Find dialog opened"}
        elif action == "select_all":
            pyautogui.hotkey('ctrl', 'a')
            return {"success": True, "message": "All content selected"}
        elif action == "new_tab":
            pyautogui.hotkey('ctrl', 't')
            return {"success": True, "message": "New tab opened"}
        elif action == "new_window":
            pyautogui.hotkey('ctrl', 'n')
            return {"success": True, "message": "New window opened"}
        elif action == "close_tab":
            pyautogui.hotkey('ctrl', 'w')
            return {"success": True, "message": "Tab closed"}
        elif action == "close_window":
            pyautogui.hotkey('alt', 'f4')
            return {"success": True, "message": "Window closed"}
        elif action == "zoom_in":
            pyautogui.hotkey('ctrl', '+')
            return {"success": True, "message": "Zoomed in"}
        elif action == "zoom_out":
            pyautogui.hotkey('ctrl', '-')
            return {"success": True, "message": "Zoomed out"}
        elif action == "zoom_reset":
            pyautogui.hotkey('ctrl', '0')
            return {"success": True, "message": "Zoom reset"}
        elif action == "clear_screen":
            # This is for terminal, send cls command
            pyautogui.write('cls')
            pyautogui.press('enter')
            return {"success": True, "message": "Screen cleared"}
        else:
            return {"success": False, "message": "Unknown keyboard action"}
    except Exception as e:
        return {"success": False, "message": build_physical_access_error("execute keyboard shortcut", str(e))}


def handle_open_folder(params):
    """Open system folders."""
    folder = params.get("folder", "").lower()
    
    try:
        folder_paths = {
            "documents": str(Path.home() / "Documents"),
            "downloads": str(Path.home() / "Downloads"),
            "desktop": str(Path.home() / "Desktop"),
            "pictures": str(Path.home() / "Pictures"),
            "music": str(Path.home() / "Music"),
            "videos": str(Path.home() / "Videos"),
        }
        
        if folder in folder_paths:
            os.startfile(folder_paths[folder])
            return {"success": True, "message": f"Opened {folder} folder"}
        else:
            return {"success": False, "message": f"Unknown folder: {folder}"}
    except Exception as e:
        return {"success": False, "message": build_physical_access_error(f"open {folder} folder", str(e))}


def handle_camera(params):
    """Handle camera operations."""
    action = params.get("action", "").lower()
    
    try:
        if action == "take_photo":
            # Open Windows Camera app
            subprocess.Popen(["start", "mswindowscamera:"], shell=True)
            return {"success": True, "message": "Camera opened - press space or click to take photo"}
        else:
            return {"success": False, "message": "Unknown camera action"}
    except Exception as e:
        return {"success": False, "message": build_physical_access_error("access camera", str(e))}


def handle_screen_record(params):
    """Handle screen recording operations."""
    if not HAS_DISPLAY or pyautogui is None:
        return {"success": False, "message": "Desktop automation not available in headless environment"}
    
    action = params.get("action", "").lower()
    
    try:
        if action == "start_record":
            # Open Xbox Game Bar for screen recording
            pyautogui.hotkey('win', 'g')
            return {"success": True, "message": "Game Bar opened - press record button to start recording"}
        elif action == "stop_record":
            pyautogui.hotkey('win', 'g')
            return {"success": True, "message": "Game Bar opened - press stop button to end recording"}
        else:
            return {"success": False, "message": "Unknown screen record action"}
    except Exception as e:
        return {"success": False, "message": build_physical_access_error("control screen recording", str(e))}


def handle_file_system(params):
    """Handle file system operations."""
    action = params.get("action", "").lower()
    
    try:
        if action == "list_files":
            # Open file explorer in current directory
            os.startfile(os.getcwd())
            return {"success": True, "message": "File explorer opened in current directory"}
        else:
            return {"success": False, "message": "Unknown file system action"}
    except Exception as e:
        return {"success": False, "message": build_physical_access_error("access file system", str(e))}


def handle_navigation(params):
    """Handle browser navigation."""
    if not HAS_DISPLAY or pyautogui is None:
        return {"success": False, "message": "Desktop automation not available in headless environment"}
    
    action = params.get("action", "").lower()
    
    try:
        if action == "go_back":
            pyautogui.hotkey('alt', 'left')
            return {"success": True, "message": "Navigated back"}
        elif action == "go_forward":
            pyautogui.hotkey('alt', 'right')
            return {"success": True, "message": "Navigated forward"}
        elif action == "go_home":
            pyautogui.hotkey('alt', 'home')
            return {"success": True, "message": "Navigated to home page"}
        else:
            return {"success": False, "message": "Unknown navigation action"}
    except Exception as e:
        return {"success": False, "message": build_physical_access_error("navigate", str(e))}


def handle_system_info(params):
    """Handle system information requests."""
    action = params.get("action", "").lower()
    
    try:
        if action == "system_info":
            subprocess.Popen(["msinfo32.exe"], shell=False)
            return {"success": True, "message": "System Information opened"}
        elif action == "network_status":
            subprocess.Popen(["ncpa.cpl"], shell=True)
            return {"success": True, "message": "Network connections opened"}
        elif action == "process_list":
            subprocess.Popen(["taskmgr"], shell=True)
            return {"success": True, "message": "Task Manager opened"}
        elif action == "disk_space":
            result = subprocess.run(["wmic", "logicaldisk", "get", "size,freespace,caption"], capture_output=True, text=True, shell=False)
            return {"success": True, "message": f"Disk space info:\n{result.stdout}"}
        elif action == "memory_usage":
            result = subprocess.run(["wmic", "OS", "get", "TotalVisibleMemorySize,FreePhysicalMemory"], capture_output=True, text=True, shell=False)
            return {"success": True, "message": f"Memory usage info:\n{result.stdout}"}
        elif action == "cpu_usage":
            # Open Performance Monitor for CPU
            subprocess.Popen(["perfmon"], shell=False)
            return {"success": True, "message": "Performance Monitor opened - check CPU usage"}
        elif action == "battery_status":
            result = subprocess.run(["wmic", "path", "Win32_Battery", "get", "EstimatedChargeRemaining,BatteryStatus"], capture_output=True, text=True, shell=False)
            return {"success": True, "message": f"Battery status:\n{result.stdout}"}
        elif action == "network_speed":
            open_url("https://www.speedtest.net")
            return {"success": True, "message": "Speed test opened in browser"}
        elif action == "firewall_status":
            subprocess.Popen(["wf.msc"], shell=False)
            return {"success": True, "message": "Windows Firewall opened"}
        elif action == "antivirus_status":
            subprocess.Popen(["windowsdefender://"], shell=True)
            return {"success": True, "message": "Windows Defender opened"}
        elif action == "event_logs":
            subprocess.Popen(["eventvwr.msc"], shell=False)
            return {"success": True, "message": "Event Viewer opened"}
        elif action == "services":
            subprocess.Popen(["services.msc"], shell=False)
            return {"success": True, "message": "Services opened"}
        elif action == "startup":
            subprocess.Popen(["taskmgr", "/0", "/startup"], shell=False)
            return {"success": True, "message": "Task Manager opened to startup tab"}
        elif action == "device_manager":
            subprocess.Popen(["devmgmt.msc"], shell=False)
            return {"success": True, "message": "Device Manager opened"}
        elif action == "system_properties":
            subprocess.Popen(["sysdm.cpl"], shell=False)
            return {"success": True, "message": "System Properties opened"}
        elif action == "advanced_settings":
            subprocess.Popen(["sysdm.cpl", ",,3"], shell=False)
            return {"success": True, "message": "Advanced system settings opened"}
        elif action == "env_variables":
            if not HAS_DISPLAY or pyautogui is None:
                return {"success": False, "message": "Desktop automation not available in headless environment"}
            subprocess.Popen(["sysdm.cpl", ",,3"], shell=False)
            time.sleep(1)
            pyautogui.hotkey('alt', 'e')
            return {"success": True, "message": "Environment variables opened"}
        elif action == "performance_monitor":
            subprocess.Popen(["perfmon"], shell=False)
            return {"success": True, "message": "Performance Monitor opened"}
        elif action == "resource_monitor":
            subprocess.Popen(["resmon"], shell=False)
            return {"success": True, "message": "Resource Monitor opened"}
        elif action == "reliability_monitor":
            subprocess.Popen(["perfmon", "/rel"], shell=False)
            return {"success": True, "message": "Reliability Monitor opened"}
        elif action == "health_check":
            # Run basic health check
            checks = []
            try:
                result = subprocess.run(["wmic", "OS", "get", "FreePhysicalMemory"], capture_output=True, text=True, shell=False)
                checks.append("Memory check completed")
            except:
                checks.append("Memory check failed")
            
            try:
                result = subprocess.run(["ping", "-n", "1", "8.8.8.8"], capture_output=True, text=True, shell=False)
                checks.append("Network connectivity check completed")
            except:
                checks.append("Network check failed")
            
            return {"success": True, "message": f"Health check completed:\n" + "\n".join(checks)}
        else:
            return {"success": False, "message": "Unknown system info action"}
    except Exception as e:
        return {"success": False, "message": build_physical_access_error(f"get system info for {action}", str(e))}


def handle_network_tool(params):
    """Handle network tools."""
    action = params.get("action", "").lower()
    target = params.get("target", "google.com")
    
    try:
        if action == "ping":
            result = subprocess.run(["ping", "-n", "4", target], capture_output=True, text=True, shell=False)
            return {"success": True, "message": f"Ping results for {target}:\n{result.stdout}"}
        elif action == "traceroute":
            result = subprocess.run(["tracert", target], capture_output=True, text=True, shell=False)
            return {"success": True, "message": f"Traceroute results for {target}:\n{result.stdout}"}
        elif action == "flush_dns":
            result = subprocess.run(["ipconfig", "/flushdns"], capture_output=True, text=True, shell=True)
            return {"success": True, "message": f"DNS cache flushed:\n{result.stdout}"}
        elif action == "restart_network":
            # Restart network adapter
            result = subprocess.run(["ipconfig", "/release"], capture_output=True, text=True, shell=True)
            time.sleep(2)
            result2 = subprocess.run(["ipconfig", "/renew"], capture_output=True, text=True, shell=True)
            return {"success": True, "message": f"Network restarted:\n{result.stdout}\n{result2.stdout}"}
        else:
            return {"success": False, "message": "Unknown network tool action"}
    except Exception as e:
        return {"success": False, "message": build_physical_access_error(f"execute network tool {action}", str(e))}


def handle_automation(params):
    """Handle automation commands."""
    action = params.get("action", "").lower()
    target = params.get("target", "")
    
    try:
        if action == "create_shortcut":
            if not target:
                return {"success": False, "message": "Target not specified for shortcut"}
            # Create shortcut on desktop
            desktop = Path.home() / "Desktop"
            shortcut_path = desktop / f"{target}.lnk"
            # Use PowerShell to create shortcut
            command = f"$ws = New-Object -ComObject WScript.Shell; $s = $ws.CreateShortcut('{shortcut_path}'); $s.TargetPath = '{target}'; $s.Save()"
            result = subprocess.run(["powershell.exe", "-Command", command], capture_output=True, text=True, shell=False)
            if result.returncode == 0:
                return {"success": True, "message": f"Shortcut created for {target} on desktop"}
            else:
                return {"success": False, "message": f"Failed to create shortcut: {result.stderr}"}
        elif action == "schedule_task":
            subprocess.Popen(["taskschd.msc"], shell=False)
            return {"success": True, "message": "Task Scheduler opened"}
        elif action == "run_as_admin":
            if not target:
                return {"success": False, "message": "Application not specified"}
            # Run as administrator using PowerShell
            command = f"Start-Process '{target}' -Verb RunAs"
            result = subprocess.run(["powershell.exe", "-Command", command], capture_output=True, text=True, shell=False)
            return {"success": True, "message": f"Attempting to run {target} as administrator"}
        else:
            return {"success": False, "message": "Unknown automation action"}
    except Exception as e:
        return {"success": False, "message": build_physical_access_error(f"execute automation {action}", str(e))}


def handle_productivity(params):
    """Handle productivity and workflow commands."""
    action = params.get("action", "").lower()
    
    # Simple in-memory storage for todos and notes
    if not hasattr(handle_productivity, 'todos'):
        handle_productivity.todos = []
    if not hasattr(handle_productivity, 'notes'):
        handle_productivity.notes = []
    
    try:
        if action == "pomodoro_start":
            # Start 25-minute timer using PowerShell
            command = f"Start-Sleep -Seconds 1500; [System.Media.SystemSounds]::Beep.Play()"
            subprocess.Popen(["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", command], shell=False)
            return {"success": True, "message": "25-minute Pomodoro timer started. You'll hear a beep when done."}
        
        elif action == "focus_mode":
            # Enable focus mode - turn on Do Not Disturb
            subprocess.Popen(["powershell.exe", "-Command", "Set-Content -Path '$env:TEMP\\focus_mode.txt' -Value 'active'"], shell=False)
            return {"success": True, "message": "Focus mode enabled. Minimize distractions and focus on your work."}
        
        elif action == "break_start":
            # Start 5-minute break timer
            command = f"Start-Sleep -Seconds 300; [System.Media.SystemSounds]::Beep.Play()"
            subprocess.Popen(["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", command], shell=False)
            return {"success": True, "message": "5-minute break timer started. You'll hear a beep when done."}
        
        elif action == "timer_start":
            minutes = params.get("minutes", 10)
            seconds = minutes * 60
            command = f"Start-Sleep -Seconds {seconds}; [System.Media.SystemSounds]::Beep.Play()"
            subprocess.Popen(["powershell.exe", "-NoProfile", "-WindowStyle", "Hidden", "-Command", command], shell=False)
            return {"success": True, "message": f"Timer started for {minutes} minutes. You'll hear a beep when done."}
        
        elif action == "timer_stop":
            # Stop timer by killing PowerShell processes
            subprocess.Popen(["taskkill", "/F", "/IM", "powershell.exe"], shell=True)
            return {"success": True, "message": "Timer stopped."}
        
        elif action == "create_todo":
            task = params.get("task", "")
            if task:
                handle_productivity.todos.append({"task": task, "completed": False})
                return {"success": True, "message": f"Added todo: {task}"}
            return {"success": False, "message": "No task specified"}
        
        elif action == "show_todos":
            if handle_productivity.todos:
                todo_list = "\n".join([f"- {todo['task']} {'(done)' if todo['completed'] else ''}" for todo in handle_productivity.todos])
                return {"success": True, "message": f"Your todos:\n{todo_list}"}
            return {"success": True, "message": "No todos yet. Say 'create todo [task]' to add one."}
        
        elif action == "complete_todo":
            task = params.get("task", "")
            if task:
                for todo in handle_productivity.todos:
                    if task.lower() in todo["task"].lower():
                        todo["completed"] = True
                        return {"success": True, "message": f"Marked as done: {task}"}
                return {"success": False, "message": f"Todo not found: {task}"}
            return {"success": False, "message": "No task specified"}
        
        elif action == "delete_todo":
            task = params.get("task", "")
            if task:
                handle_productivity.todos = [todo for todo in handle_productivity.todos if task.lower() not in todo["task"].lower()]
                return {"success": True, "message": f"Deleted todo: {task}"}
            return {"success": False, "message": "No task specified"}
        
        elif action == "quick_note":
            note = params.get("note", "")
            if note:
                from datetime import datetime
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                handle_productivity.notes.append({"note": note, "timestamp": timestamp})
                return {"success": True, "message": f"Saved note: {note}"}
            return {"success": False, "message": "No note specified"}
        
        elif action == "show_notes":
            if handle_productivity.notes:
                notes_list = "\n".join([f"[{note['timestamp']}] {note['note']}" for note in handle_productivity.notes])
                return {"success": True, "message": f"Your notes:\n{notes_list}"}
            return {"success": True, "message": "No notes yet. Say 'quick note [note]' to add one."}
        
        elif action in ["daily_plan", "weekly_review", "translate_text", "grammar_check", "word_count"]:
            # For productivity tools, open relevant web tools
            tool_urls = {
                "translate_text": "https://translate.google.com",
                "grammar_check": "https://www.grammarly.com",
                "word_count": "https://www.wordcounttools.com",
            }
            
            if action in tool_urls:
                open_url(tool_urls[action])
                return {"success": True, "message": f"Opened {action} tool in browser"}
            
            # For template and planning, open Notepad
            if action in ["daily_plan", "weekly_review"]:
                subprocess.Popen(["notepad.exe"], shell=False)
                return {"success": True, "message": f"Opened Notepad for {action}"}
        
        else:
            return {"success": False, "message": "Unknown productivity action"}
    
    except Exception as e:
        return {"success": False, "message": build_physical_access_error(f"execute productivity action {action}", str(e))}


def handle_voice_search(params):
    """Test the configured voice search provider from the backend."""
    query = (params.get("query") or "test query").strip()

    try:
        result = search_voice(query)
        if result.get("error"):
            message = f"Voice search test failed: {result['error']}"
            if result.get("hint"):
                message = f"{message}. {result['hint']}"
            return {"success": False, "message": message, "data": result}

        return {
            "success": True,
            "message": f"Voice search request completed for '{query}'.",
            "data": result,
        }
    except Exception as e:
        return {"success": False, "message": build_physical_access_error(f"test voice search for {query}", str(e))}


@app.route("/api/voice-search", methods=["GET"])
def mock_voice_search():
    """Local mock voice-search provider used for quick testing."""
    query = (request.args.get("query") or "").strip()
    if not query:
        return jsonify({"error": "Query is required"}), 400

    sample_results = [
        {
            "title": f"Top result for {query}",
            "snippet": f"This is a local mock voice-search response for '{query}'.",
            "url": f"https://www.google.com/search?q={query.replace(' ', '+')}",
        },
        {
            "title": f"{query.title()} buying guide",
            "snippet": f"A second mock result to help test voice-search rendering for '{query}'.",
            "url": f"https://www.youtube.com/results?search_query={query.replace(' ', '+')}",
        },
    ]

    return jsonify(
        {
            "query": query,
            "provider": "local-mock",
            "count": len(sample_results),
            "results": sample_results,
        }
    )


# Authentication Routes
@app.route("/api/auth/register", methods=["POST"])
def register():
    """Register a new user."""
    data = request.json
    email = data.get("email", "").lower().strip()
    password = data.get("password", "")
    
    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400
    
    if auth.get_user_by_email(email):
        return jsonify({"error": "Email already registered"}), 400
    
    import uuid
    user_id = str(uuid.uuid4())
    password_hash = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
    
    users_data = auth.load_users()
    users_data["users"].append({
        "id": user_id,
        "email": email,
        "password_hash": password_hash,
        "is_admin": False,
        "is_premium": False,
        "usage_count": 0,
        "created_at": datetime.now().isoformat()
    })
    auth.save_users(users_data)
    
    return jsonify({
        "success": True,
        "message": "User registered successfully",
        "user_id": user_id
    })


@app.route("/api/auth/login", methods=["POST"])
def login():
    """Login user and return JWT tokens."""
    data = request.json
    email = data.get("email", "").lower().strip()
    password = data.get("password", "")
    
    if not email or not password:
        return jsonify({"error": "Email and password required"}), 400
    
    user = auth.get_user_by_email(email)
    if not user:
        return jsonify({"error": "Invalid credentials"}), 401
    
    if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
        return jsonify({"error": "Invalid credentials"}), 401
    
    access_token = auth.create_access_token(identity=user["id"])
    refresh_token = auth.create_refresh_token(identity=user["id"])
    
    return jsonify({
        "success": True,
        "access_token": access_token,
        "refresh_token": refresh_token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "is_admin": user.get("is_admin", False),
            "is_premium": user.get("is_premium", False),
            "usage_count": user.get("usage_count", 0)
        }
    })


@app.route("/api/auth/refresh", methods=["POST"])
@auth.jwt_required(refresh=True)
def refresh():
    """Refresh access token."""
    user_id = auth.get_jwt_identity()
    access_token = auth.create_access_token(identity=user_id)
    return jsonify({"access_token": access_token})


@app.route("/api/auth/me", methods=["GET"])
@auth.jwt_required()
def get_current_user():
    """Get current user info."""
    user_id = auth.get_jwt_identity()
    user = auth.get_user_by_id(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    
    return jsonify({
        "id": user["id"],
        "email": user["email"],
        "is_admin": user.get("is_admin", False),
        "is_premium": user.get("is_premium", False),
        "usage_count": user.get("usage_count", 0),
        "subscription_id": user.get("subscription_id"),
        "premium_since": user.get("premium_since")
    })


# Payment Routes
@app.route("/api/payment/plans", methods=["GET"])
def get_plans():
    """Get available subscription plans."""
    return jsonify(payment.get_plans())


@app.route("/api/payment/create-checkout", methods=["POST"])
@auth.jwt_required()
def create_checkout():
    """Create Stripe checkout session."""
    user_id = auth.get_jwt_identity()
    data = request.json
    plan_id = data.get("plan_id")
    
    if not plan_id:
        return jsonify({"error": "Plan ID required"}), 400
    
    session, error = payment.create_checkout_session(plan_id)
    if error:
        return jsonify({"error": error}), 400
    
    return jsonify({"url": session.url, "session_id": session.id})


@app.route("/api/payment/success", methods=["GET"])
def payment_success():
    """Handle successful payment."""
    session_id = request.args.get("session_id")
    if not session_id:
        return jsonify({"error": "Session ID required"}), 400
    
    success, result = payment.verify_payment_session(session_id)
    if not success:
        return jsonify({"error": result}), 400
    
    return jsonify({
        "success": True,
        "message": "Payment successful! You now have premium access."
    })


@app.route("/api/payment/cancel", methods=["GET"])
def payment_cancel():
    """Handle cancelled payment."""
    return jsonify({
        "success": False,
        "message": "Payment cancelled. You can try again anytime."
    })


@app.route("/api/payment/cancel-subscription", methods=["POST"])
@auth.jwt_required()
def cancel_subscription():
    """Cancel user's subscription."""
    user_id = auth.get_jwt_identity()
    success, message = payment.cancel_subscription(user_id)
    
    if not success:
        return jsonify({"error": message}), 400
    
    return jsonify({"success": True, "message": message})


@app.route("/api/payment/webhook", methods=["POST"])
def stripe_webhook():
    """Handle Stripe webhook events."""
    payload = request.get_data()
    sig_header = request.headers.get('Stripe-Signature')
    
    if not sig_header:
        return jsonify({"error": "No signature header"}), 400
    
    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, os.environ.get('STRIPE_WEBHOOK_SECRET', '')
        )
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    
    return jsonify(payment.handle_webhook(event))


@app.route("/api/health", methods=["GET"])
def health_check():
    """Health check endpoint."""
    return jsonify(
        {
            "status": "healthy",
            "service": "voice-assistant-backend",
            "voice_search_configured": bool(os.getenv("VOICE_SEARCH_API_KEY")),
        }
    )


if __name__ == "__main__":
    print("Voice Assistant Backend starting...")
    print("Running in local assistant mode")
    port = int(os.environ.get("PORT", 5000))
    serve(app, host="0.0.0.0", port=port)
