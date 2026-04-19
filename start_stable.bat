@echo off
cd /d C:\Users\dnspt\OneDrive\Desktop\AI_ML_PROJECT\windows-automation
echo Starting Windows Automation Server...
start cmd /k node server.js
timeout /t 3 /nobreak > nul
cd /d C:\Users\dnspt\OneDrive\Desktop\AI_ML_PROJECT
echo Starting ngrok tunnel with stable domain...
ngrok http --domain=7475-152-59-39-204.ngrok-free.app 3001
