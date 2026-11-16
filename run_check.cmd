@echo off
REM Double-click this (or point Windows Task Scheduler at it) to check now,
REM pop up desktop alerts and open the dashboard.
REM
REM Your PC reaches a few Indian government sites that the GitHub runner cannot
REM (NABARD, DRDO RAC), so a local run genuinely adds coverage.
REM
REM data/ and docs/ are regenerated every run, so we discard the previous local
REM copy before pulling. That keeps the cloud's reminder history authoritative
REM and avoids a merge conflict in generated files. Nothing is pushed back
REM automatically - see the README to publish a local run's findings.
cd /d "%~dp0"
git checkout -- data docs 2>nul
git pull --rebase --autostash
python -m bot check
python notify_local.py --open
pause
