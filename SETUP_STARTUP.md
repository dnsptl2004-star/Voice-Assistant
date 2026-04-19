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

### Step 3: Test

1. Restart your computer
2. Both windows-automation server and ngrok should start automatically
3. Check ngrok window for the new tunnel URL
4. Update frontend with the new ngrok URL

### Step 4: Update Frontend

After ngrok starts, check the ngrok window for the new URL and update:
```
REACT_APP_API_URL=<your-new-ngrok-url>
```

## Manual Start

To start manually without restarting:
```
C:\Users\dnspt\OneDrive\Desktop\AI_ML_PROJECT\start_stable.bat
```

## Important Notes

- If you shut down PC → service stops
- If you manually close ngrok → it stops
- Free ngrok plan: URL changes every restart (update frontend after each restart)
- For stable URL, upgrade to ngrok paid plan
