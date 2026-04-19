# Windows Automation API

A dedicated Express.js service for Windows desktop automation.

## Setup

1. Install dependencies:
```bash
npm install
```

2. Start the server:
```bash
npm start
```

The server will run on `http://localhost:3001` by default.

## Endpoints

- `GET /health` - Health check
- `POST /api/open-app` - Open an application
- `POST /api/close-app` - Close an application
- `POST /api/type-text` - Type text
- `POST /api/media-control` - Media control (play, pause, next, previous)
- `POST /api/volume-control` - Volume control
- `POST /api/screenshot` - Take screenshot
- `POST /api/open-url` - Open URL in browser
- `POST /api/keyboard` - Send keyboard shortcut

## Architecture

1. **Local Windows Machine** → runs this automation API
2. **Vercel** → calls this local/remote Windows API for desktop automation
3. **Render** → main Flask backend for authentication, payments, AI queries

## Environment Variables

- `PORT` - Server port (default: 3001)
