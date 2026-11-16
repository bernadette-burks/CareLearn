@echo off
py -3.14 app.py
if errorlevel 1 (
  echo Python 3.14 or higher was not found. Install Python 3.14.7+ and try again.
  pause
)
