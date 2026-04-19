# Auto-Start Ngrok + Windows Automation Server

## Setup Instructions

### Step 1: Create Startup Shortcut

1. Press `Win + R`
2. Type: `shell:startup`
3. Press Enter (this opens the Startup folder)

### Step 2: Add Script to Startup

Copy `start_stable.bat` from:
```
C:\Users\dnspt\OneDrive\Desktop\AI_ML_PROJECT\start_stable.bat
```

To the Startup folder that opened.

### Step 3: Configure Ngrok Stable Domain

Make sure you have reserved the domain on ngrok dashboard:
- Go to https://dashboard.ngrok.com/domains
- Reserve: `7475-152-59-39-204.ngrok-free.app`

### Step 4: Test

1. Restart your computer
2. Both windows-automation server and ngrok should start automatically
3. Check if ngrok tunnel is active at https://7475-152-59-39-204.ngrok-free.app

### Step 5: Update Frontend

Make sure frontend is configured to use:
```
REACT_APP_API_URL=https://7475-152-59-39-204.ngrok-free.app
```

## Manual Start

To start manually without restarting:
```
C:\Users\dnspt\OneDrive\Desktop\AI_ML_PROJECT\start_stable.bat
```

## Important Notes

- If you shut down PC → service stops
- If you manually close ngrok → it stops
- Stable domain ensures URL doesn't change on restart
- Free ngrok accounts have domain limits
