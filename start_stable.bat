@echo off
cd /d C:\Users\dnspt\OneDrive\Desktop\AI_ML_PROJECT\voice_assistant\backend
echo Starting Python Backend with Desktop Automation...
start cmd /k python app.py
timeout /t 5 /nobreak > nul
cd /d C:\Users\dnspt\OneDrive\Desktop\AI_ML_PROJECT
echo Starting ngrok tunnel to Python backend...
ngrok http 5000
