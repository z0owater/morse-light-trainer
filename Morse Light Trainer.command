#!/bin/bash
# Double-click on a Mac to start the Morse Lamp Exam Trainer.
# Uses Python from python.org when it is installed: Apple's own python3 may have an old Tk.
cd "$(dirname "$0")"
PY=python3
ORG=/Library/Frameworks/Python.framework/Versions/Current/bin/python3
[ -x "$ORG" ] && PY="$ORG"
if command -v "$PY" >/dev/null 2>&1; then
  "$PY" morse_light_trainer.py
else
  echo "Python 3 is not installed. Get it from https://www.python.org/downloads/ and try again."
  read -r -p "Press Enter to close."
fi
