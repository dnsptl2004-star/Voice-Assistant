@echo off
cd /d C:\Users\dnspt\OneDrive\Desktop\AI_ML_PROJECT\windows-automation
echo Starting Windows Automation Server...
start cmd /k node server.js
timeout /t 3 /nobreak > nul
cd /d C:\Users\dnspt\OneDrive\Desktop\AI_ML_PROJECT
echo Starting ngrok tunnel...
ngrok http 3001
