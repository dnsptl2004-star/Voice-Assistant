const express = require('express');
const cors = require('cors');
const { exec, spawn } = require('child_process');
const path = require('path');

const app = express();
const PORT = process.env.PORT || 3001;

// Middleware
app.use(cors());
app.use(express.json());

// Health check
app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'windows-automation-api' });
});

// Open application
app.post('/api/open-app', (req, res) => {
  const { app } = req.body;
  if (!app) {
    return res.status(400).json({ success: false, message: 'App name required' });
  }

  exec(`start ${app}`, (error) => {
    if (error) {
      return res.json({ success: false, message: `Failed to open ${app}: ${error.message}` });
    }
    res.json({ success: true, message: `Opened ${app}` });
  });
});

// Close application
app.post('/api/close-app', (req, res) => {
  const { app } = req.body;
  if (!app) {
    return res.status(400).json({ success: false, message: 'App name required' });
  }

  exec(`taskkill /F /IM ${app}.exe`, (error) => {
    if (error) {
      return res.json({ success: false, message: `Failed to close ${app}: ${error.message}` });
    }
    res.json({ success: true, message: `Closed ${app}` });
  });
});

// Type text
app.post('/api/type-text', (req, res) => {
  const { text } = req.body;
  if (!text) {
    return res.status(400).json({ success: false, message: 'Text required' });
  }

  // Using PowerShell to type text
  const psScript = `Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait("${text.replace(/"/g, '""')}")`;
  exec(`powershell -Command "${psScript}"`, (error) => {
    if (error) {
      return res.json({ success: false, message: `Failed to type text: ${error.message}` });
    }
    res.json({ success: true, message: `Typed text: ${text}` });
  });
});

// Media control
app.post('/api/media-control', (req, res) => {
  const { action } = req.body;
  if (!action) {
    return res.status(400).json({ success: false, message: 'Action required' });
  }

  const keyMap = {
    'play': '{MEDIA_PLAY_PAUSE}',
    'pause': '{MEDIA_PLAY_PAUSE}',
    'next': '{MEDIA_NEXT}',
    'previous': '{MEDIA_PREV}',
    'volume_up': '{VOLUME_UP}',
    'volume_down': '{VOLUME_DOWN}',
    'mute': '{VOLUME_MUTE}'
  };

  const key = keyMap[action.toLowerCase()];
  if (!key) {
    return res.status(400).json({ success: false, message: 'Invalid action' });
  }

  const psScript = `Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait("${key}")`;
  exec(`powershell -Command "${psScript}"`, (error) => {
    if (error) {
      return res.json({ success: false, message: `Failed to control media: ${error.message}` });
    }
    res.json({ success: true, message: `Media control: ${action}` });
  });
});

// Volume control
app.post('/api/volume-control', (req, res) => {
  const { action, level } = req.body;
  
  if (action === 'set' && level !== undefined) {
    // Set volume using PowerShell
    const psScript = `$obj = New-Object -ComObject WScript.Shell; $obj.SendKeys([char]173); $obj.SendKeys([char]173); Start-Sleep -m 500; for($i=0; $i -lt ${level}; $i++) { $obj.SendKeys([char]175) }`;
    exec(`powershell -Command "${psScript}"`, (error) => {
      if (error) {
        return res.json({ success: false, message: `Failed to set volume: ${error.message}` });
      }
      res.json({ success: true, message: `Volume set to ${level}` });
    });
  } else if (action === 'mute') {
    exec(`powershell -Command "(New-Object -ComObject WScript.Shell).SendKeys([char]173)"`, (error) => {
      if (error) {
        return res.json({ success: false, message: `Failed to mute: ${error.message}` });
      }
      res.json({ success: true, message: 'Muted' });
    });
  } else {
    res.status(400).json({ success: false, message: 'Invalid action' });
  }
});

// Screenshot
app.post('/api/screenshot', (req, res) => {
  const psScript = `
    Add-Type -AssemblyName System.Windows.Forms;
    Add-Type -AssemblyName System.Drawing;
    $bounds = [System.Windows.Forms.Screen]::PrimaryScreen.Bounds;
    $bmp = New-Object System.Drawing.Bitmap $bounds.width, $bounds.height;
    $graphics = [System.Drawing.Graphics]::FromImage($bmp);
    $graphics.CopyFromScreen($bounds.Location, [System.Drawing.Point]::Empty, $bounds.size);
    $timestamp = (Get-Date).ToString('yyyyMMdd-HHmmss');
    $path = "$env:USERPROFILE\\Desktop\\screenshot-$timestamp.png";
    $bmp.Save($path, [System.Drawing.Imaging.ImageFormat]::Png);
    $graphics.Dispose();
    $bmp.Dispose();
    $path
  `;
  
  exec(`powershell -Command "${psScript}"`, (error, stdout) => {
    if (error) {
      return res.json({ success: false, message: `Failed to take screenshot: ${error.message}` });
    }
    res.json({ success: true, message: `Screenshot saved to ${stdout.trim()}` });
  });
});

// Open URL
app.post('/api/open-url', (req, res) => {
  const { url } = req.body;
  if (!url) {
    return res.status(400).json({ success: false, message: 'URL required' });
  }

  exec(`start ${url}`, (error) => {
    if (error) {
      return res.json({ success: false, message: `Failed to open URL: ${error.message}` });
    }
    res.json({ success: true, message: `Opened ${url}` });
  });
});

// Keyboard shortcut
app.post('/api/keyboard', (req, res) => {
  const { shortcut } = req.body;
  if (!shortcut) {
    return res.status(400).json({ success: false, message: 'Shortcut required' });
  }

  const keyMap = {
    'ctrl+c': '^c',
    'ctrl+v': '^v',
    'ctrl+z': '^z',
    'ctrl+a': '^a',
    'ctrl+x': '^x',
    'alt+tab': '%{TAB}',
    'alt+f4': '%{F4}',
    'win+d': '^{ESC}',
    'win+l': '^l'
  };

  const key = keyMap[shortcut.toLowerCase()] || shortcut;
  const psScript = `Add-Type -AssemblyName System.Windows.Forms; [System.Windows.Forms.SendKeys]::SendWait("${key}")`;
  exec(`powershell -Command "${psScript}"`, (error) => {
    if (error) {
      return res.json({ success: false, message: `Failed to send keyboard shortcut: ${error.message}` });
    }
    res.json({ success: true, message: `Keyboard shortcut: ${shortcut}` });
  });
});

// Start server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Windows Automation API running on port ${PORT}`);
  console.log(`Access at http://localhost:${PORT}`);
});
