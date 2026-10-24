@echo off
cd /d "%~dp0"
where pyw >nul 2>nul && (start "" pyw "morse_light_trainer.py" & exit /b)
where pythonw >nul 2>nul && (start "" pythonw "morse_light_trainer.py" & exit /b)
python "morse_light_trainer.py"
if errorlevel 1 pause
