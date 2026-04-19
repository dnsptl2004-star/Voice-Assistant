@echo off
echo Installing NSSM (Non-Sucking Service Manager)...
powershell -Command "Invoke-WebRequest -Uri 'https://nssm.cc/release/nssm-2.24.zip' -OutFile 'nssm.zip'"
powershell -Command "Expand-Archive -Path 'nssm.zip' -DestinationPath '.'"
echo Installing Voice Assistant Backend as Windows Service...
nssm\nssm.exe install VoiceAssistantBackend python app.py
nssm\nssm.exe set VoiceAssistantBackend AppDirectory %CD%
nssm\nssm.exe set VoiceAssistantBackend DisplayName "Voice Assistant Backend"
nssm\nssm.exe set VoiceAssistantBackend Description "Backend for Voice Assistant with Desktop Automation"
nssm\nssm.exe set VoiceAssistantBackend Start SERVICE_AUTO_START
nssm\nssm.exe start VoiceAssistantBackend
echo Service installed and started!
