@echo off
REM Double-click this (or point Windows Task Scheduler at it) to check now,
REM pop up desktop alerts and open the dashboard.
REM
REM Your PC reaches a few Indian government sites that the GitHub runner cannot
REM (NABARD, DRDO RAC), so a local run genuinely adds coverage. We pull first so
REM your copy starts from the latest cloud result. Nothing is pushed back
REM automatically - see the README if you want to publish a local run's findings.
cd /d "%~dp0"
git pull --rebase --autostash
python -m bot check
python notify_local.py --open
pause
