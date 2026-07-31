@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0.mvn\wrapper\maven-wrapper.ps1" %*
exit /b %ERRORLEVEL%
