# Morse Light Trainer

Practice for receiving Morse signals by flashing light, as tested in the Proficiency in Communication practical for the Certificate of Competency (Deck Officer) Class 3.

It flashes a signalling lamp on screen with the same timing as the exam recording, gives you an answer sheet laid out like the paper one, and marks each part at the 90% pass mark.

The examination is set out in the Marine Department's [*Certificates of Competency and Licences for Seagoing Deck Officers' Determinations* (2022 Edition)](https://www.mardep.gov.hk/filemanager/en/share/pub-services/pdf/determination_d03.pdf). Section 7.1.1 gives the oral/practical pass mark of 90% for Proficiency in Communication, and section 8.2.2 covers Competence (ii), transmitting and receiving information by visual signalling using the Morse light.

## Disclaimer

This is an unofficial, vibe-coded project. I only made it because I couldn't find anything else like it. It isn't affiliated with or endorsed by the Marine Department or any training institute, and passing here doesn't guarantee a pass in the real exam.

If you're new to Morse code, learn it by sound first at [LCWO.net](https://lcwo.net) (Learn CW Online), then come back here to practise reading it by light.

## Download

Get the latest version from the [Releases page](../../releases/latest).

**Windows:** download `Morse-Light-Trainer-Windows.exe` and double-click it. There's
nothing to install. The first time, Windows may say "Windows protected your PC",
because the program isn't signed. Click **More info**, then **Run anyway**.

**Mac:** download `Morse-Light-Trainer-macOS.dmg`, open it and drag Morse Light
Trainer into Applications. It runs on Intel and Apple Silicon Macs. The app isn't
signed by Apple, so macOS blocks it the first time:

1. Open the app once and close the warning.
2. Go to **System Settings > Privacy & Security**, scroll down and click
   **Open Anyway** next to Morse Light Trainer.

On macOS 14 and older you can instead right-click the app, choose **Open**, then
**Open** again.

**Linux, or if you have Python:** run `python3 morse_light_trainer.py` with Python
3.8 or later and tkinter. On Windows you can double-click `Morse Light Trainer.bat`;
on a Mac, `Morse Light Trainer.command` (use Python from python.org, since the
python3 that comes with macOS has an old Tk).

## Using it

- **One answer sheet**: 60 characters (Part A), then one message (Part B).
- **Full recording**: a test message, then Member A and Member B, about 30 minutes,
  as in the exam.
- Type while you watch the lamp. Letters fill the boxes in order; in the message,
  press Space after each word. Leave a box empty if you miss something.
- When the recording ends you get 10 minutes to tidy up. Then press **Mark**.
- **F11** shows the lamp full screen. Typing still goes into the answer sheet.
- **View** switches between light and dark, or follows your computer's setting.
- **File > Open** plays any CW Player text file. **File > Save** writes the exam as
  a CW Player text file, with an answer key, so you can play it on the real light box.

On a new computer, use **Lamp > Calibrate size with a card** once so the lamp shows
at its real size (about 9 mm), then press **Test lamp**.

## Timing

Measured from CW Player 4.7.5's output at the exam settings (SPEED=10, SPACE=5,
SPACEW=1):

| | |
|---|---|
| dot | 25000 / wpm samples at 22050 Hz, 0.113 s |
| dash | 3 dots |
| gap inside a character | 1 dot |
| after every character | 3 × SPACE dots, 1.70 s |
| each space in the text | (7 × SPACEW − 4) + 3 × SPACE dots, 2.04 s |

So the characters of a group are 3.74 s apart and groups are 7.82 s apart.
`--selftest` checks the model against the recordings, and `--lamptest` times the
lamp on your own screen.

## Messages

Part B uses the 149 signal meanings in the General section of the [International Code of Signals (2005 Edition)](https://bempc.com/images/ics_international_code_of_signals_2005.pdf) that have 10 to 20 words and no brackets or blanks. You can
choose the length range in Settings; it's 11 to 16 words by default.

## Building

GitHub Actions builds the Windows .exe and the Mac .dmg on every push to `main`,
and pushing a tag such as `v1.2.1` attaches them to a release, with that version's
notes from [CHANGELOG.md](CHANGELOG.md). To build the .exe yourself on Windows:

```
py -m pip install pyinstaller
py -m PyInstaller --onefile --windowed --name "Morse Light Trainer" --icon lamp.ico morse_light_trainer.py
```
