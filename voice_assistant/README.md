# Voice-Controlled AI Laptop Assistant

A professional voice-based AI assistant that understands natural language commands and controls a laptop through speech. Combines speech recognition, AI intent detection (Google Gemini), and system automation for hands-free desktop control.

**Created by Dhruv Patel**

## Features

- **Voice-to-text input** using Web Speech API
- **Natural language understanding** via Google Gemini AI
- **Conversational responses** with text-to-speech
- **Laptop control** including:
  - App launching and closing (Chrome, VS Code, Spotify, etc.)
  - Web search integration
  - Automatic typing into active windows
  - File and folder creation
  - Media controls (play, pause, next, volume)
  - System controls (brightness, sleep, lock)
- **Safety features** with confirmation dialogs for risky actions
- **Professional UI** with real-time status indicators

## Tech Stack

- **Frontend**: React with Web Speech API
- **Backend**: Python Flask
- **AI Model**: Google Gemini API
- **Automation**: pyautogui, keyboard, screen-brightness-control, pycaw
- **TTS**: Browser Speech Synthesis API

## Project Structure

```
voice_assistant/
├── backend/
│   ├── app.py              # Flask API server
│   ├── volume_control.py   # Windows volume control
│   └── requirements.txt    # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── App.js         # Main React component
│   │   ├── App.css        # Styling
│   │   ├── index.js       # Entry point
│   │   └── index.css      # Global styles
│   ├── public/
│   └── package.json       # Node dependencies
├── start.py               # Launcher script
└── README.md
```

## Prerequisites

- Python 3.8+
- Node.js 16+
- Windows 10/11 (for system automation features)
- Chrome/Edge browser (for Web Speech API)
- Google Gemini API key (already configured)

## Installation

### 1. Backend Setup

```bash
cd voice_assistant/backend
pip install -r requirements.txt
```

### 2. Frontend Setup

```bash
cd voice_assistant/frontend
npm install
```

## Running the Application

### Option 1: Using the Launcher Script

```bash
cd voice_assistant
python start.py
```

### Option 2: Manual Start

Terminal 1 - Backend:
```bash
cd voice_assistant/backend
python app.py
```

Terminal 2 - Frontend:
```bash
cd voice_assistant/frontend
npm start
```

Then open http://localhost:3000 in your browser.

## Usage

1. Click the **microphone button** to start listening
2. Speak a command clearly
3. The assistant will:
   - Show your speech as text
   - Process through Gemini AI
   - Speak back the response
   - Execute the action automatically

### Example Commands

| Command | Action |
|---------|--------|
| "Open Chrome" | Launches Google Chrome |
| "Search for Python tutorials" | Opens browser with search |
| "Increase volume to 80 percent" | Sets system volume |
| "Type hello world" | Types text into active window |
| "Create folder Projects" | Creates new folder |
| "Play music" | Sends media play key |
| "Set brightness to 50" | Adjusts screen brightness |

## Safety Features

- **Confirmation dialogs** for shutdown, restart, delete operations
- **60-second delay** on shutdown/restart commands
- **Graceful error handling** with user feedback

## API Configuration

The Gemini API key is already configured in `backend/app.py`. To use a different key:

```python
GEMINI_API_KEY = "your-api-key-here"
```

Or set as environment variable:
```bash
set GEMINI_API_KEY=your-api-key
```

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Speech recognition not supported" | Use Chrome or Edge browser |
| Backend connection failed | Ensure Flask server is running on port 5000 |
| Volume/brightness not working | Run as Administrator |
| Commands not executing | Check Windows permissions for automation |

## License

MIT License
