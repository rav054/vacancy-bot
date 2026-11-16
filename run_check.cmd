@echo off
REM Double-click this (or point Windows Task Scheduler at it) to check now,
REM pop up desktop alerts and open the dashboard.
cd /d "%~dp0"
python -m bot check
python notify_local.py --open
pause
