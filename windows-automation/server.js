const express = require('express');
const cors = require('cors');
const { exec } = require('child_process');
const app = express();
const PORT = 3001;

app.use(cors());
app.use(express.json());

// Desktop automation endpoints
app.post('/api/open-app', (req, res) => {
  const { app } = req.body;
  if (!app) {
    return res.status(400).json({ success: false, message: 'App name required' });
  }
  
  exec(`start ${app}`, (error) => {
    if (error) {
      return res.status(500).json({ success: false, message: `Failed to open ${app}` });
    }
    res.json({ success: true, message: `Opened ${app}` });
  });
});

app.post('/api/type-text', (req, res) => {
  const { text } = req.body;
  if (!text) {
    return res.status(400).json({ success: false, message: 'Text required' });
  }
  
  // This would require additional libraries like robot-js or similar
  res.json({ success: false, message: 'Type text requires additional setup' });
});

app.post('/api/open-url', (req, res) => {
  const { url } = req.body;
  if (!url) {
    return res.status(400).json({ success: false, message: 'URL required' });
  }
  
  exec(`start ${url}`, (error) => {
    if (error) {
      return res.status(500).json({ success: false, message: `Failed to open ${url}` });
    }
    res.json({ success: true, message: `Opened ${url}` });
  });
});

app.get('/health', (req, res) => {
  res.json({ status: 'healthy', service: 'windows-automation' });
});

app.listen(PORT, () => {
  console.log(`Windows Automation API running on port ${PORT}`);
  console.log(`Access at http://localhost:${PORT}`);
});
