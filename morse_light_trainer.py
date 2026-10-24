#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Morse Light Trainer 1.2

Practice for receiving Morse signals by flashing light, as in the Proficiency
in Communications practical for the Certificate of Competency (Deck Officer)
Class 3. The lamp is timed like CW Player 4.7.5 at the exam settings
(SPEED=10, SPACE=5, SPACEW=1).

CW Player timing, measured from its output:
  dot                     25000 / wpm samples at 22050 Hz (113.4 ms at 10 wpm)
  dash                    3 dots, with 1 dot between the parts of a character
  after every character   3 x SPACE dots
  each space in the text  another (7 x SPACEW - 4) + 3 x SPACE dots
So at the exam settings "T 0" has 3.74 s between the letters and
"G   2" has 7.82 s. Line breaks and letter case change nothing.

Needs Python 3.8 or later with tkinter.
  python morse_light_trainer.py              start it
  python morse_light_trainer.py --selftest   check the timing model
  python morse_light_trainer.py --lamptest   time the lamp on this screen
"""

import bisect
import datetime
import json
import os
import random
import re
import sys
import time

IS_WIN = sys.platform.startswith("win")
IS_MAC = sys.platform == "darwin"
if IS_WIN:
    try:
        import ctypes
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            ctypes.windll.user32.SetProcessDPIAware()
        ctypes.windll.winmm.timeBeginPeriod(1)  # 1 ms timers
    except Exception:
        pass

FROZEN = getattr(sys, "frozen", False)      # built with PyInstaller
APP_DIR = os.path.dirname(os.path.abspath(sys.executable if FROZEN else __file__))
if FROZEN and IS_MAC:
    # Writing inside the .app would break its signature.
    SETTINGS_DIR = os.path.expanduser("~/Library/Application Support/Morse Light Trainer")
    START_DIR = os.path.expanduser("~")
else:
    SETTINGS_DIR = START_DIR = APP_DIR
SETTINGS_PATH = os.path.join(SETTINGS_DIR, "morse_light_trainer_settings.json")
PRACTICE_DIR = os.path.normpath(os.path.join(APP_DIR, "..", "Practice"))

# Morse code
MORSE = {
    "A": ".-", "B": "-...", "C": "-.-.", "D": "-..", "E": ".", "F": "..-.", "G": "--.", "H": "....",
    "I": "..", "J": ".---", "K": "-.-", "L": ".-..", "M": "--", "N": "-.", "O": "---", "P": ".--.",
    "Q": "--.-", "R": ".-.", "S": "...", "T": "-", "U": "..-", "V": "...-", "W": ".--", "X": "-..-",
    "Y": "-.--", "Z": "--..",
    "0": "-----", "1": ".----", "2": "..---", "3": "...--", "4": "....-", "5": ".....",
    "6": "-....", "7": "--...", "8": "---..", "9": "----.",
    ".": ".-.-.-", ",": "--..--", "?": "..--..", "/": "-..-.", "=": "-...-", "+": ".-.-.",
    "-": "-....-", "'": ".----.", ":": "---...", ";": "-.-.-.", "(": "-.--.", ")": "-.--.-",
    '"': ".-..-.", "@": ".--.-.",
}
SHOW = lambda pat: pat.replace(".", "·").replace("-", "−")

# ICS General-section bank
# ICS 2005, General section: the signal meanings of 10 to 20 words with no
# brackets, blanks (". . .") or slashes, checked against the printed page.
# Hyphens and apostrophes are closed up when sent (life-saving -> LIFESAVING)
# and other punctuation is left out.
BANK = [
    ("AD", "I am abandoning my vessel which has suffered a nuclear accident and is a possible source of radiation danger."),
    ("AE 2", "I shall abandon my vessel unless you will remain by me, ready to assist."),
    ("AJ", "I have had a serious nuclear accident and you should approach with caution."),
    ("AW", "Aircraft should endeavour to alight where flag is waved or light is shown."),
    ("A", "I have a diver down; keep well clear at slow speed.", "II"),
    ("BA 1", "You cannot alight on the deck; can you lift crew?"),
    ("BB 1", "You may alight on my deck; I am ready to receive you forward."),
    ("BB 2", "You may alight on my deck; I am ready to receive you amidship."),
    ("BB 3", "You may alight on my deck; I am ready to receive you aft."),
    ("BB 4", "You may alight on my deck but I am not yet ready to receive you."),
    ("BC", "I have established communications with the aircraft in distress on 2182 kHz."),
    ("BC", "I have established visual communications with the aircraft in distress on 2182 kHz."),
    ("BF", "Aircraft is ditched in position indicated and requires immediate assistance."),
    ("BI", "I am flying to likely position of vessel in distress."),
    ("BM", "You should parachute object to windward. Mark it by smoke or light signal."),
    ("BM 1", "I am going to parachute object to windward, marking it by smoke or light signal."),
    ("BP", "Aircraft is coming to participate in search. Expected arrive over the area of accident at time indicated."),
    ("BQ 1", "What is the speed of your aircraft in relation to the surface of the earth?"),
    ("CB 3", "I require immediate assistance; I have a serious disturbance on board."),
    ("CE", "I will attempt to obtain for you the assistance required."),
    ("CM", "One or more vessels are assisting the vessel in distress."),
    ("CX 2", "Boats cannot be used on the starboard side because of list."),
    ("CX 3", "Boats cannot be used on the port side because of list."),
    ("DC", "Boat should endeavour to land where flag is waved or light is shown."),
    ("DH 2", "Have you any boats with radiotelegraph installation or portable radio equipment?"),
    ("DY 4", "What is the depth of water where vessel has sunk?"),
    ("ED 1", "Your distress signals are understood; the nearest life-saving station is being informed."),
    ("EG 1", "Will you listen on 2182 kHz for signals of emergency position-indicating radio beacons?"),
    ("EG 2", "I am listening on 2182 kHz for signals of emergency position-indicating radio beacons."),
    ("EG 3", "Have you received the signal of an emergency position-indicating radio beacon on 2182 kHz?"),
    ("EG 4", "I have received the signal of an emergency position-indicating radio beacon on 2182 kHz."),
    ("EJ", "I have received distress signal transmitted by coast station indicated."),
    ("EJ 1", "Have you received distress signal transmitted by coast station indicated?"),
    ("EK 2", "Have you heard or seen distress signal from survival craft?"),
    ("EZ 1", "Will you give me my position according to bearings taken by radio direction-finder stations which you control?"),
    ("FC", "You should indicate your position by visual or sound signals."),
    ("FE", "I am proceeding to the position of accident at full speed. Expect to arrive at time indicated."),
    ("FE 1", "Are you proceeding to the position of accident? If so, when do you expect to arrive?"),
    ("FP 1", "What is the estimated set and drift of survival craft?"),
    ("FZ", "You should continue search according to instructions and until further notice."),
    ("GB", "You should stop search and return to base or continue your voyage."),
    ("GC 2", "I have searched area of accident but have found no trace of derelict or survivors."),
    ("GC 3", "I have noted patches of oil at likely position of accident."),
    ("GM 1", "I cannot save my vessel; keep as close as possible."),
    ("GN 1", "I wish some persons taken off. Skeleton crew will remain on board."),
    ("GQ", "I cannot proceed to the rescue owing to weather. You should do all you can."),
    ("HM", "Survivors are in bad condition. Medical assistance is urgently required."),
    ("HR", "You should try to obtain from survivors all possible information."),
    ("HT", "You should indicate position of survivors by throwing pyrotechnic signals."),
    ("HY 2", "I do not know what has happened to the vessel with which I collided."),
    ("HY 3", "Has the vessel with which you have been in collision resumed her voyage?"),
    ("IQ", "Diver has been attacked by diver's disease and requires decompression chamber treatment."),
    ("IT 1", "I am on fire and have dangerous cargo on board; keep well clear of me."),
    ("JK", "The tide was high water when the vessel went aground."),
    ("JK 1", "The tide was half water when the vessel went aground."),
    ("JK 2", "The tide was low water when the vessel went aground."),
    ("JL 1", "You are running the risk of going aground; do not approach me from the starboard side."),
    ("JL 2", "You are running the risk of going aground; do not approach me from the port side."),
    ("JL 3", "You are running the risk of going aground; do not approach me from forward."),
    ("JL 4", "You are running the risk of going aground; do not approach me from aft."),
    ("JM", "You are running the risk of going aground at low water."),
    ("JN 1", "You should beach the vessel where flag is waved or light is shown."),
    ("JO 3", "I may be got afloat if prompt assistance is given."),
    ("JT", "I can refloat if an anchor is laid out for me."),
    ("JY", "Leak can be controlled, if it does not get any worse."),
    ("KA 1", "I have placed the collision mat. I can proceed without assistance."),
    ("KE", "The watertight bulkheads are standing up well to the pressure of the water."),
    ("KK 2", "I cannot connect at present but will attempt when conditions improve."),
    ("KP 2", "I must get shelter or anchorage as soon as possible."),
    ("LB", "You should make towing hawser fast to your chain cable."),
    ("LV", "Let me know my bearings from you. I will flash searchlight."),
    ("MP", "I am in shallow water. Please direct me how to navigate."),
    ("MS 1", "My vessel is a dangerous source of radiation; you may approach from my starboard side."),
    ("MS 2", "My vessel is a dangerous source of radiation; you may approach from my port side."),
    ("MS 3", "My vessel is a dangerous source of radiation; you may approach from forward."),
    ("MS 4", "My vessel is a dangerous source of radiation; you may approach from aft."),
    ("MV", "My vessel is releasing radioactive material and presents a hazard."),
    ("MX", "The radioactive material is airborne. Do not approach from leeward."),
    ("MY 7", "It is dangerous to let go an anchor or use bottom trawl."),
    ("MZ 1", "I consider you are carrying out a dangerous navigational practice and I intend to report you."),
    ("NE 1", "You should proceed with great caution; the coast is dangerous."),
    ("NE 2", "You should proceed with great caution; submarines are exercising in this area."),
    ("NE 4", "You should proceed with great caution; keep clear of firing range."),
    ("NF 1", "You are running into danger; there is a radiation hazard."),
    ("NG 1", "You are in a dangerous position; there is a radiation hazard."),
    ("NO", "Negative – “No” or “The significance of the previous group should be read in the negative”."),
    ("OH", "You should switch on your radar and keep radar watch."),
    ("OJ 2", "You should alter your course, if possible, appreciably to starboard to facilitate location by radar."),
    ("OJ 3", "You should alter your course, if possible, appreciably to port to facilitate location by radar."),
    ("OP 2", "Will you send two dashes of ten seconds each, or the carrier of your transmitter, followed by your call sign?"),
    ("OW", "There is a minefield ahead of you. You should stop your vessel and wait for instructions."),
    ("OW 1", "There is a minefield along the coast. You should not approach too close."),
    ("PA", "I will indicate the swept channel. You should follow in my wake."),
    ("PA 3", "I do not see the buoys marking the swept channel."),
    ("PB", "You should keep clear of me; I am engaged in minesweeping operations."),
    ("PB 1", "You should keep clear of me; I am exploding a floating mine."),
    ("PE", "You should extinguish all the lights except the navigation lights."),
    ("PG 2", "I am dazzled by your searchlight. Douse it or lift it."),
    ("QT", "You should not anchor. You are going to foul my anchor."),
    ("RG", "You should send a boat to where I am to anchor or moor."),
    ("RJ 1", "You should have your engines ready as quickly as possible."),
    ("RP 1", "Landing here is highly dangerous. A more favourable location for landing is at position indicated."),
    ("RQ", "Interrogative or “the significance of the previous group should be read as a question”."),
    ("RR 1", "Lights will be shown or flag waved at the best landing place."),
    ("RT", "Stop carrying out your intentions and watch for my signals."),
    ("SC 2", "I shall get under way as soon as the weather permits."),
    ("SP 1", "My vessel is stopped and making no way through the water."),
    ("SQ 1", "You should stop or heave to, otherwise I shall open fire on you."),
    ("SQ 2", "You should stop or heave to; I am going to send a boat."),
    ("SQ 3", "You should stop, or heave to, I am going to board you."),
    ("SV", "I am not seaworthy due to shifting of cargo or ballast."),
    ("SW", "I am taking in, or discharging, or carrying dangerous goods."),
    ("TI", "You should navigate with caution. You are drifting towards my set of nets."),
    ("TJ", "You should navigate with caution. There are nets with a buoy in this area."),
    ("TN", "In what direction, distance and depth does your fishing gear extend?"),
    ("TQ 1", "It is necessary to haul in fishing gear for disentangling."),
    ("TU", "I have to cut the warps. The trawls are entangled."),
    ("TU 1", "Give me your warp. I shall transfer your fishing gear on it."),
    ("TV 1", "Trawling in this area is dangerous because there is an obstruction."),
    ("TW", "Attention. You are in the vicinity of prohibited fishery limits."),
    ("UI", "Sea is too rough; pilot boat cannot get off to you."),
    ("UL", "All vessels should proceed to sea as soon as possible owing to danger in port."),
    ("UP", "Permission to enter harbour is urgently requested. I have an emergency case."),
    ("UV 2", "Your course leads into an area of the territorial sea in which the right of innocent passage is temporarily suspended."),
    ("UV 3", "You should leave the area of the territorial sea in which the right of innocent passage is temporarily suspended."),
    ("UW 1", "Thank you very much for your co-operation. I wish you a pleasant voyage."),
    ("UY", "I am carrying out exercises. Please keep clear of me."),
    ("VC", "Where is the nearest place at which fuel oil is available?"),
    ("VC 1", "Where is the nearest place at which diesel oil is available?"),
    ("VC 2", "Where is the nearest place at which coal is available?"),
    ("VI 1", "What is the estimated height of base of low clouds in hundreds of metres?"),
    ("VP", "What is the character of ice, its development and the effects on navigation?"),
    ("VR 7", "Ice has drifted into the area or has been squeezed together."),
    ("VS 1", "Unobstructed for power-driven vessels built of iron or steel, dangerous for wooden vessels without ice protection."),
    ("VS 2", "Difficult for low-powered vessels without the assistance of an ice-breaker, dangerous for vessels of weak construction."),
    ("VS 3", "Possible without ice-breaker only for high-powered vessels of strong construction."),
    ("VS 7", "Ice-breaker can give assistance only to ships strengthened for navigation in ice."),
    ("WG", "Open channel or open area is in the direction in which aircraft is flying."),
    ("WH", "I can only assist you if you will make all efforts to follow."),
    ("WM", "Ice-breaker support is now commencing. Use special ice-breaker support signals and keep continuous watch for sound, visual or radiotelephony signals."),
    ("YG", "You appear not to be complying with the traffic separation scheme."),
    ("YU", "I am going to communicate with your station by means of the International Code of Signals."),
    ("YV", "The groups which follow are from the International Code of Signals."),
    ("YY", "I wish to communicate by VHF radiotelephony on channel indicated."),
    ("ZD", "Please communicate the following to all shipping in the vicinity."),
    ("ZP", "My last signal was incorrect. I will repeat it correctly."),
    ("ZQ", "Your signal appears incorrectly coded. You should check and repeat the whole."),
    ("ZT", "My Maritime Declaration of Health has negative answers to the six health questions."),
    ("ZV", "I believe I have been in an infected area during the last thirty days."),
]
CHAPTERS = {
    "I": "Distress - emergency", "II": "Casualties - damages",
    "III": "Aids to navigation - navigation - hydrography", "IV": "Manoeuvres",
    "V": "Miscellaneous", "VI": "Meteorology - weather", "VII": "Routeing of ships",
    "VIII": "Communications", "IX": "International Health Regulations",
}
BOUNDS = [("AA", "I"), ("HV", "II"), ("LK", "III"), ("QD", "IV"), ("ST", "V"),
          ("VG", "VI"), ("YG", "VII"), ("YH", "VIII"), ("ZS", "IX")]


def chapter_of(code, override=None):
    if override:
        return override
    ch = "I"
    for start, name in BOUNDS:
        if code[:2] >= start:
            ch = name
    return ch


def words_of(text):
    t = re.sub(r"(\w)[-'’](?=\w)", r"\1", text)     # life-saving -> lifesaving, diver's -> divers
    t = re.sub(r"[^A-Za-z0-9\s]", " ", t)
    return t.upper().split()


MESSAGES = []
for _n, _e in enumerate(BANK):
    MESSAGES.append(dict(id="%s|%d" % (_e[0], _n), code=_e[0], text=_e[1], words=words_of(_e[1]),
                         chapter=chapter_of(_e[0], _e[2] if len(_e) > 2 else None)))
BY_WORDS = dict((tuple(m["words"]), m) for m in MESSAGES)   # finds the ICS source of a loaded message

# The exam light box: dark grey face, darker round recess, grey dot that lights amber.
PRESETS = {
    "Light box": dict(lamp_on="#C88C10", lamp_off="#6C6561", stage_bg="#2F2E32",
                                        housing=True, housing_color="#212022", glow=False),
    "Black screen": dict(lamp_on="#FFD700", lamp_off="#1A1A1A", stage_bg="#000000",
                                           housing=False, housing_color="#0B0C0E", glow=False),
    "Bright yellow": dict(lamp_on="#FFC21A", lamp_off="#3A3836", stage_bg="#111214",
                                    housing=True, housing_color="#08090A", glow=True),
}

# settings
DEFAULTS = {
    "wpm": 10, "space": 5, "spacew": 1,      # cw_player.ini SPEED, SPACE, SPACEW
    "pause_spaces": 30,                       # spaces between parts, about a minute
    "countdown": 5,                           # seconds before the first signal
    "lamp_mm": 9.0,                           # the dot on the exam light box
    "px_per_mm": 0.0,                         # 0 = use the screen's reported size
    "lamp_on": "#C88C10", "lamp_off": "#6C6561", "stage_bg": "#2F2E32",
    "housing": True, "housing_color": "#212022", "glow": False,
    "group_style": "g1",                      # g1 = 4 letters + 1 digit, g2 = 3 letters + 2 digits
    "min_words": 11, "max_words": 16,         # message length range (10 to 20)
    "pass_pct": 90, "show_progress": False,
    "recent": [], "last_dir": "",
    "settings_version": 2,
}
APPEARANCE = ("lamp_mm", "lamp_on", "lamp_off", "glow")
LIMITS = {"wpm": (5, 40), "space": (1, 10), "spacew": (1, 20), "pause_spaces": (0, 120),
          "countdown": (0, 30), "lamp_mm": (1.0, 60.0), "px_per_mm": (0.0, 16.0), "pass_pct": (50, 100),
          "min_words": (10, 20), "max_words": (10, 20)}
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


def load_settings():
    s = dict(DEFAULTS)
    try:
        with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
            got = json.load(f)
        old = got.get("settings_version") != DEFAULTS["settings_version"]
        for k, v in got.items():
            if old and k in APPEARANCE:
                continue            # older file: use the current default look
            if k in DEFAULTS and isinstance(v, type(DEFAULTS[k])) or (k in DEFAULTS and isinstance(DEFAULTS[k], float) and isinstance(v, int)):
                s[k] = v
        s["settings_version"] = DEFAULTS["settings_version"]
    except Exception:
        pass
    for k, (lo, hi) in LIMITS.items():
        try:
            s[k] = type(DEFAULTS[k])(min(hi, max(lo, s[k])))
        except Exception:
            s[k] = DEFAULTS[k]
    for k in ("lamp_on", "lamp_off", "stage_bg", "housing_color"):
        if not HEX.match(str(s[k])):
            s[k] = DEFAULTS[k]
    if s["min_words"] > s["max_words"]:
        s["min_words"], s["max_words"] = s["max_words"], s["min_words"]
    return s


def save_settings(s):
    try:
        if not os.path.isdir(SETTINGS_DIR):
            os.makedirs(SETTINGS_DIR)
        with open(SETTINGS_PATH, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=1)
    except Exception:
        pass


# CW Player timing
def dot_seconds(wpm):
    return 25000.0 / float(wpm) / 22050.0


class Timeline:
    """When the lamp is lit for a text, timed the way CW Player 4.7.5 plays it."""

    def __init__(self, text, wpm, space, spacew):
        u = dot_seconds(wpm)
        self.u = u
        self.char_gap = 3 * space * u                 # silence after every character
        self.space_len = max(0, 7 * spacew - 4) * u   # silence of one space character
        t = 0.0
        ons, syms = [], []
        for i, ch in enumerate(text):
            c = ch.upper()
            if c == " ":
                t += self.space_len + self.char_gap
                continue
            pat = MORSE.get(c)
            if pat is None:          # line breaks and unknown characters are not sent
                continue
            start = t
            for j, e in enumerate(pat):
                if j:
                    t += u
                d = u if e == "." else 3 * u
                ons.append((t, t + d))
                t += d
            syms.append((start, t, i, c))
            t += self.char_gap
        self.ons, self.syms, self.total = ons, syms, t
        self.sym_starts = [s[0] for s in syms]
        self.edges = [x for on in ons for x in on]    # on, off, on, off ...


# exam content
LETTERS, DIGITS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ", "0123456789"
HEAD, TAIL = "AA AA AA", "AR"


def make_groups(n, style):
    """Groups that use every letter and digit, digits at random places."""
    nd = 2 if style == "g2" else 1
    nl = 5 - nd
    letters = list(LETTERS)
    while len(letters) < n * nl:
        letters.append(random.choice(LETTERS))
    random.shuffle(letters)
    digits = list(DIGITS)
    while len(digits) < n * nd:
        digits.append(random.choice(DIGITS))
    random.shuffle(digits)
    out = []
    for i in range(n):
        g = letters[i * nl:(i + 1) * nl]
        for d in digits[i * nd:(i + 1) * nd]:
            g.insert(random.randint(0, len(g)), d)
        out.append("".join(g))
    return out


def block_text(items, lower=False):
    """AA AA AA   T 0 H B G   2 Q F I A   AR  (one space between characters, three between groups)."""
    body = "   ".join(" ".join(w.lower() if lower else w) for w in items)
    return HEAD + "   " + body + "   " + TAIL


# A block runs from AA AA AA to AR, or to the next AA AA AA when the AR is missing.
BLOCK_RE = re.compile(r"\bAA\s+AA\s+AA\b(.*?)(?:\b(?P<ar>AR)\b|(?=\bAA\s+AA\s+AA\b)|\Z)", re.I | re.S)


def is_spaced(body):
    toks = body.split()
    return bool(toks) and sum(len(t) for t in toks) / float(len(toks)) <= 1.3


def parse_blocks(text):
    """Find every AA AA AA ... AR block and the groups or words inside it."""
    blocks = []
    for m in BLOCK_RE.finditer(text):
        b0, b1 = m.span(1)
        body = text[b0:b1]
        pat = re.compile(r"\S(?: \S)*") if is_spaced(body) else re.compile(r"\S+")
        items = [(b0 + im.start(), b0 + im.end(), re.sub(r"\s", "", im.group()).upper()) for im in pat.finditer(body)]
        words = [x[2] for x in items]
        chars = bool(words) and all(len(w) == 5 for w in words) and any(c.isdigit() for w in words for c in w)
        blocks.append(dict(start=m.start(), end=m.end(), items=items, words=words, kind="chars" if chars else "msg",
                           no_ar=m.group("ar") is None))
    return blocks


class Sheet:
    def __init__(self, sid, label):
        self.id, self.label = sid, label
        self.groups = None   # list of 5-character strings
        self.msg = None      # dict(code, text, words, chapter); code is None for loaded files


class Exam:
    """A playable text plus the answer sheets it fills."""

    def __init__(self, text, messages=None, source="generated", mode="sheet"):
        self.text, self.source, self.mode = text, source, mode
        self.blocks = parse_blocks(text)
        self.sheets, self.test = [], None
        msg_meta = list(messages or [])
        cur = None
        for i, b in enumerate(self.blocks):
            if b["kind"] == "chars" and len(b["words"]) <= 6 and i == 0 and len(self.blocks) > 1:
                b["role"], b["label"] = "test", "Test message"
                self.test = b["words"]
                continue
            if b["kind"] == "chars":
                cur = Sheet(len(self.sheets), "")
                cur.groups = b["words"]
                self.sheets.append(cur)
            else:
                meta = msg_meta.pop(0) if msg_meta else BY_WORDS.get(tuple(b["words"]))
                msg = meta or dict(code=None, text=" ".join(b["words"]).capitalize(), words=b["words"], chapter=None)
                if cur is None or cur.msg is not None:
                    cur = Sheet(len(self.sheets), "")
                    self.sheets.append(cur)
                cur.msg = msg
            b["sheet"] = cur.id
        many = len(self.sheets) > 1
        for sh in self.sheets:
            sh.label = ("Member " + "ABCDEFGH"[sh.id]) if many else "Answer sheet"
        for b in self.blocks:
            if b.get("role") != "test":
                part = "characters" if b["kind"] == "chars" else "message"
                b["label"] = (self.sheets[b["sheet"]].label + " · " + part) if many else part.capitalize()
        self.block_starts = [b["start"] for b in self.blocks]
        self.notes = ["%s has no AR at the end." % b["label"] for b in self.blocks if b["no_ar"]]


def read_text_file(path):
    for enc in ("utf-8-sig", "cp1252", "latin-1"):
        try:
            with open(path, "r", encoding=enc) as f:
                return f.read()
        except UnicodeDecodeError:
            continue
    return ""


def load_exam(path):
    """A CW Player text file as an exam. It plays exactly as written, less the leading whitespace."""
    ex = Exam(read_text_file(path), None, path, "file")
    if not ex.blocks:
        raise ValueError("No AA AA AA ... AR blocks found in this file.")
    return ex


def messages_in_range(s):
    lo, hi = sorted((s["min_words"], s["max_words"]))
    return [m for m in MESSAGES if lo <= len(m["words"]) <= hi]


def pick_messages(k, s):
    pool_all = messages_in_range(s) or list(MESSAGES)
    recent = set(c for c in s.get("recent", []) if isinstance(c, str))
    pool = [m for m in pool_all if m["id"] not in recent]
    if len(pool) < k:
        pool = list(pool_all)
    random.shuffle(pool)
    out = pool[:k]
    while len(out) < k:
        out.append(random.choice(pool_all))
    return out


def build_exam(mode, s):
    st, gap = s["group_style"], " " * s["pause_spaces"]
    parts, metas = [], []
    if mode == "full":
        m = pick_messages(2, s)
        parts.append(block_text(make_groups(6, st)))
        for msg in m:
            parts.append(block_text(make_groups(12, st)))
            parts.append(block_text(msg["words"], lower=True))
            metas.append(msg)
    else:
        if mode in ("sheet", "partA"):
            parts.append(block_text(make_groups(12, st)))
        if mode in ("sheet", "partB"):
            msg = pick_messages(1, s)[0]
            parts.append(block_text(msg["words"], lower=True))
            metas.append(msg)
    return Exam(gap.join(parts), metas, "generated", mode)


def cw_file_text(exam, s):
    """Text for the real CW Player: same layout, pause before the first part too."""
    return " " * s["pause_spaces"] + exam.text.strip() + "\r\n"


def answer_key_text(exam):
    out = ["Answer key", "=========="]
    if exam.test:
        out += ["", "Test message (not marked): " + "  ".join(exam.test)]
    for sh in exam.sheets:
        out += ["", sh.label]
        if sh.groups:
            out.append("  Characters:")
            for r in range(0, len(sh.groups), 4):
                out.append("    " + "   ".join(sh.groups[r:r + 4]))
        if sh.msg:
            out.append("  Message (%d words): %s" % (len(sh.msg["words"]), " ".join(sh.msg["words"])))
            if sh.msg.get("code"):
                out.append("  ICS General section, signal %s, chapter %s %s" % (sh.msg["code"], sh.msg["chapter"], CHAPTERS[sh.msg["chapter"]]))
                out.append("  \"%s\"" % sh.msg["text"])
    return "\r\n".join(out) + "\r\n"


def fmt_time(sec):
    sec = max(0, int(round(sec)))
    return "%d:%02d" % (sec // 60, sec % 60)


def need_of(n, pct):
    return -(-pct * n // 100)   # ceiling without floating point


def lcs(a, b):
    dp = [0] * (len(b) + 1)
    for x in a:
        prev = 0
        for j, y in enumerate(b, 1):
            tmp = dp[j]
            dp[j] = prev + 1 if x == y else max(dp[j], dp[j - 1])
            prev = tmp
    return dp[-1]


def mark_sheet(sheet, chars, words, pct):
    """Mark one sheet. chars and words are what was written, box by box; a blank box is wrong."""
    res = {}
    if sheet.groups:
        exp = list("".join(sheet.groups))
        got = [re.sub(r"[^A-Z0-9]", "", c.upper())[:1] for c in chars]
        got = (got + [""] * len(exp))[:len(exp)]
        ok = sum(1 for a, b in zip(got, exp) if a == b)
        res["A"] = dict(exp=exp, got=got, ok=ok, n=len(exp), shift=lcs([g for g in got if g], exp) - ok >= 2)
    if sheet.msg:
        exp = sheet.msg["words"]
        got = [re.sub(r"[^A-Z0-9]", "", w.upper()) for w in words]
        got += [""] * (len(exp) - len(got))
        ok = sum(1 for g, w in zip(got, exp) if g == w)
        res["B"] = dict(exp=exp, got=got, ok=ok, n=len(exp), extra=sum(1 for g in got[len(exp):] if g),
                        shift=lcs([g for g in got if g], exp) - ok >= 2)
    parts = [res[k] for k in ("A", "B") if k in res]
    for r in parts:
        r["need"] = need_of(r["n"], pct)
        r["pass"] = r["ok"] >= r["need"]
        r["pct"] = 100 * r["ok"] // r["n"]     # round down so a fail never shows as 90%
    res["pass"] = all(r["pass"] for r in parts)
    return res


# self test
def selftest():
    """Compare the timing model with CW Player 4.7.5 measurements (10 wpm, SPACE=5, SPACEW=1)."""
    ok = True
    s = dict(DEFAULTS, recent=[])
    random.seed(12345)                 # the same sample text every run

    def check(good, line):
        print("  %-74s %s" % (line, "ok" if good else "FAILED"))
        return bool(good)

    def gap(text):
        tl = Timeline(text, 10, 5, 1)
        return tl.ons[-1][0] - tl.ons[0][1] if len(tl.ons) == 2 else None

    u = dot_seconds(10)
    print("CW Player 4.7.5 timing at SPEED=10, SPACE=5, SPACEW=1")
    print("  dot (u) %.4f s, dash %.3f s, gap inside a character %.3f s" % (u, 3 * u, u))
    print("  after every character 15 u = %.2f s, each space 3 + 15 u = %.2f s" % (15 * u, 18 * u))
    print("  Text        Gap      Model      CW Player")
    measured = [("EE", 1.702), ("E E", 3.743), ("E  E", 5.782), ("E   E", 7.825), ("E    E", 9.866), ("E     E", 11.908)]
    for text, cw in measured:
        g = gap(text)
        good = abs(g - cw) <= 0.05
        ok &= good
        print("  %-10r %4d u   %6.3f s   %6.3f s   %s" % (text, round(g / u), g, cw, "ok" if good else "DIFFERENT"))

    print("Exam content")
    groups = make_groups(12, s["group_style"])
    in_range = messages_in_range(s)
    sheets = [Timeline(block_text(groups) + " " * s["pause_spaces"] + block_text(m["words"], True), 10, 5, 1).total
              for m in in_range]
    mean = sum(sheets) / len(sheets)
    ok &= check(12 * 60 <= mean <= 16 * 60, "One answer sheet (Part A + Part B): %s on average, %s to %s" % (
        fmt_time(mean), fmt_time(min(sheets)), fmt_time(max(sheets))))
    full = build_exam("full", s)
    t_full = Timeline(full.text, 10, 5, 1).total
    ok &= check(25 * 60 <= t_full <= 35 * 60, "Full recording (test + member A + member B): %s" % fmt_time(t_full))
    print("  Sample Part A: " + block_text(groups))
    lengths = {}
    for m in MESSAGES:
        lengths[len(m["words"])] = lengths.get(len(m["words"]), 0) + 1
    ok &= check(len(MESSAGES) == 149 and len(in_range) == 101 and all(10 <= n <= 20 for n in lengths),
                "Messages: %d; %d in the default 11-16 range" % (len(MESSAGES), len(in_range)))
    print("    words: " + ", ".join("%d:%d" % kv for kv in sorted(lengths.items())))

    print("Files and marking")
    p = os.path.join(PRACTICE_DIR, "Morse practice 01.txt")
    if os.path.isfile(p):
        ex = load_exam(p)
        shape = [(sh.label, len(sh.groups or []), len(sh.msg["words"]) if sh.msg else 0) for sh in ex.sheets]
        t = Timeline(ex.text.lstrip(), 10, 5, 1).total
        ok &= check(shape == [("Member A", 12, 20), ("Member B", 12, 20)] and 22 * 60 <= t <= 26 * 60,
                    "Morse practice 01.txt: %s; plays %s" % (", ".join("%s %d groups + %d words" % x for x in shape), fmt_time(t)))
    else:
        print("  Morse practice 01.txt not found in %s, skipped" % PRACTICE_DIR)

    def shape_of(ex):
        out = []
        for b in ex.blocks:
            who = "test" if b.get("role") == "test" else "ABCDEFGH"[b["sheet"]]
            out.append("%s %d" % (who, len(b["words"])) if b["kind"] == "chars" else "%s message" % who)
        return out
    back = Exam(cw_file_text(full, s), None, "saved file", "file")
    same = [(b["kind"], b["words"]) for b in full.blocks] == [(b["kind"], b["words"]) for b in back.blocks]
    same &= [sh.msg["code"] for sh in back.sheets] == [sh.msg["code"] for sh in full.sheets]
    ok &= check(same and shape_of(back) == ["test 6", "A 12", "A message", "B 12", "B message"],
                "Save a full exam and open it again: " + ", ".join(shape_of(back)))

    sh = Sheet(0, "Answer sheet")
    sh.groups = groups
    sh.msg = next(m for m in MESSAGES if len(m["words"]) == 13)
    chars = list("".join(groups))
    for i in (7, 23, 48):
        chars[i] = "1" if chars[i] == "Q" else "Q"
    words = list(sh.msg["words"])
    words[5] = ""
    r1 = mark_sheet(sh, chars, words, 90)
    words[9] = ""
    r2 = mark_sheet(sh, chars, words, 90)
    ok &= check(r1["A"]["ok"] == 57 and r1["A"]["pass"] and r1["A"]["pct"] == 95 and
                r1["B"]["ok"] == 12 and r1["B"]["pass"] and r1["B"]["pct"] == 92 and r1["pass"],
                "Marking 57 / 60 and 12 / 13: %s %d%%, %s %d%% (needs %d and %d)" % (
                    "PASS" if r1["A"]["pass"] else "FAIL", r1["A"]["pct"], "PASS" if r1["B"]["pass"] else "FAIL",
                    r1["B"]["pct"], r1["A"]["need"], r1["B"]["need"]))
    ok &= check(not r2["B"]["pass"] and not r2["pass"], "Marking 11 / 13 words: %s %d%%" % (
        "PASS" if r2["B"]["pass"] else "FAIL", r2["B"]["pct"]))
    print("Lamp edges on screen: run  python morse_light_trainer.py --lamptest")
    print("ALL OK" if ok else "SOME CHECKS FAILED")
    return 0 if ok else 1


# GUI
if __name__ == "__main__" and "--selftest" in sys.argv:
    sys.exit(selftest())

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter import font as tkfont

PAPER, INK, INK2, RULE = "#FFFFFF", "#121A26", "#4A5668", "#18212D"
SHORTCUT = 0x0004 | (0x0008 if IS_MAC else 0)   # Ctrl (and Cmd on a Mac) keys go to the menus
PANEL, FLAG = "#EEF1F5", "#1B4D9B"
OK_BG, OK_FG, BAD_BG, BAD_FG, BLANK_BG, BLANK_FG = "#E1F1E8", "#16724A", "#FBE4E7", "#B5142A", "#FBEED6", "#8A5300"


def _rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def mix(a, b, t):
    """Colour between a and b (t = 0 gives a, t = 1 gives b)."""
    ra, rb = _rgb(a), _rgb(b)
    return "#%02X%02X%02X" % tuple(int(round(x + (y - x) * t)) for x, y in zip(ra, rb))


def is_light(h):
    r, g, b = _rgb(h)
    return (r * 299 + g * 587 + b * 114) / 1000.0 > 140


def look_of(s):
    return dict((k, s[k]) for k in ("lamp_on", "lamp_off", "stage_bg", "housing", "housing_color", "glow"))


def lamp_icon(size):
    """Window icon: the amber lamp in its recess on the box face."""
    img = tk.PhotoImage(width=size, height=size)
    c, rows = (size - 1) / 2.0, []
    for y in range(size):
        row = []
        for x in range(size):
            d = ((x - c) ** 2 + (y - c) ** 2) ** 0.5
            row.append("#C88C10" if d <= size * 0.22 else "#212022" if d <= size * 0.46 else "#2F2E32")
        rows.append("{" + " ".join(row) + "}")
    img.put(" ".join(rows))
    return img


def draw_lamp(c, cx, cy, d, look, on):
    """Draw the light box face: round recess, optional glow and the lamp itself."""
    r = d / 2.0
    items = {"rings": []}
    if look["housing"]:
        hr = r * 4.5          # the recess is about 4.5 times the lamp
        c.create_oval(cx - hr, cy - hr, cx + hr, cy + hr, fill=look["housing_color"],
                      outline=mix(look["housing_color"], "#000000", 0.45), width=max(1, int(round(d * 0.12))))
    items["under"] = look["housing_color"] if look["housing"] else look["stage_bg"]
    if look["glow"]:
        for k, a in ((2.0, 0.10), (1.55, 0.22), (1.22, 0.42)):
            rr = r * k
            items["rings"].append((c.create_oval(cx - rr, cy - rr, cx + rr, cy + rr, fill=items["under"], outline=""), a))
    items["lamp"] = c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=look["lamp_off"], outline="")
    paint_lamp(c, items, look, on)
    return items


def paint_lamp(c, items, look, on):
    if on:
        c.itemconfigure(items["lamp"], fill=look["lamp_on"], outline=mix(look["lamp_on"], "#FFFFFF", 0.2))
    else:
        c.itemconfigure(items["lamp"], fill=look["lamp_off"], outline=mix(look["lamp_off"], "#000000", 0.35))
    for item, a in items["rings"]:
        c.itemconfigure(item, fill=mix(items["under"], look["lamp_on"], a) if on else items["under"])


def show_over(win, parent):
    """Show a withdrawn dialog centred over its parent, and make it modal."""
    win.update_idletasks()
    w, h = win.winfo_reqwidth(), win.winfo_reqheight()
    x = parent.winfo_rootx() + (parent.winfo_width() - w) // 2
    y = parent.winfo_rooty() + (parent.winfo_height() - h) // 3
    x = max(0, min(x, win.winfo_screenwidth() - w))
    y = max(0, min(y, win.winfo_screenheight() - h - 60))
    win.geometry("+%d+%d" % (x, y))
    win.deiconify()
    try:
        win.wait_visibility()
        win.grab_set()
    except Exception:
        pass


class ScrollFrame(ttk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.canvas = tk.Canvas(self, bg=PAPER, highlightthickness=0)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.hbar = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.inner = tk.Frame(self.canvas, bg=PAPER)
        self.win = self.canvas.create_window(0, 0, window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vbar.set, xscrollcommand=self.hbar.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)
        self.inner.bind("<Configure>", lambda e: self._fit())
        self.canvas.bind("<Configure>", lambda e: self._fit())

    def _fit(self):
        """As wide as the pane; a horizontal scroll bar when the sheet does not fit."""
        cw, need = self.canvas.winfo_width(), self.inner.winfo_reqwidth()
        self.canvas.itemconfigure(self.win, width=max(cw, need))
        self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        if need > cw + 1:
            self.hbar.grid(row=1, column=0, sticky="ew")
        else:
            self.hbar.grid_remove()
            self.canvas.xview_moveto(0)

    def hovered(self):
        try:
            w = self.winfo_containing(*self.winfo_pointerxy())
        except Exception:
            return False
        while w is not None:
            if w is self:
                return True
            w = w.master
        return False

    def scroll(self, n):
        self.canvas.yview_scroll(n, "units")


class LampView:
    """The light box on a canvas. Several views can show the same lamp."""

    def __init__(self, app, canvas, hint=""):
        self.app, self.c, self.hint = app, canvas, hint
        self.on, self.note, self.caption, self.sub, self.status = False, "", "", "", ""
        self.items, self.lamp = None, None
        canvas.bind("<Configure>", lambda e: self.redraw())

    def redraw(self):
        c, s = self.c, self.app.s
        c.delete("all")
        c.configure(bg=s["stage_bg"])
        w, h = max(c.winfo_width(), 2), max(c.winfo_height(), 2)
        d = max(3.0, s["lamp_mm"] * self.app.px_per_mm())
        cx, cy, r = w / 2.0, h / 2.0, d / 2.0
        self.items = draw_lamp(c, cx, cy, d, look_of(s), self.on)
        self.lamp = self.items["lamp"]
        light = is_light(s["stage_bg"])
        top = r * 4.5 if s["housing"] else r
        fg, fg2 = ("#1E2530", "#4A5668") if light else ("#D8DDE4", "#9AA3AF")
        self.t_note = c.create_text(cx, cy - top - 30, text=self.note, fill=fg, font=self.app.f_note)
        self.t_cap = c.create_text(cx, cy + top + 40, text=self.caption, fill=("#7A5200" if light else "#F4E7AE"), font=self.app.f_cap)
        self.t_sub = c.create_text(cx, cy + top + 80, text=self.sub, fill=fg2, font=self.app.f_mono)
        self.t_status = c.create_text(12, h - 10, text=self.status, fill=fg2, font=self.app.f_small, anchor="sw")
        if self.hint:
            c.create_text(w - 12, h - 10, text=self.hint, fill=fg2, font=self.app.f_small, anchor="se")

    def paint(self):
        if self.items is not None:
            paint_lamp(self.c, self.items, look_of(self.app.s), self.on)

    def set(self, on):
        if on != self.on:
            self.on = on
            self.paint()

    def text(self, note=None, caption=None, sub=None, status=None):
        for attr, item, val in (("note", "t_note", note), ("caption", "t_cap", caption),
                                ("sub", "t_sub", sub), ("status", "t_status", status)):
            if val is not None and val != getattr(self, attr):
                setattr(self, attr, val)
                if self.lamp is not None:
                    self.c.itemconfigure(getattr(self, item), text=val)


class SheetView(tk.Frame):
    """One answer sheet: 12 x 5 character boxes and numbered word boxes."""

    def __init__(self, master, app, sheet):
        super().__init__(master, bg=PAPER)
        self.app, self.sheet = app, sheet
        self.cells, self.boxes, self.marks = [], [], []
        self.locked = False
        self.res = tk.Frame(self, bg=PAPER)
        self.res.pack(fill="x", padx=16, pady=(12, 0))
        body = self.body = tk.Frame(self, bg=PAPER)
        body.pack(padx=16, pady=12, anchor="n")
        col = 0
        if sheet.groups:
            self._part_a(body).grid(row=0, column=col, sticky="n", padx=(0, int(30 * app.z)))
            col += 1
        if sheet.msg:
            self._part_b(body).grid(row=0, column=col, sticky="n")

    # Part A
    def _part_a(self, parent):
        a, z = self.app, self.app.z
        f = tk.Frame(parent, bg=PAPER)
        tk.Label(f, text="Alpha-numeric Characters", font=a.f_head, bg=PAPER, fg=INK).pack()
        tk.Label(f, text="[write characters received sequentially,\ni.e. character by character, in the following boxes]",
                 font=a.f_instr, bg=PAPER, fg=INK2, justify="center").pack(pady=(0, 6))
        cw, chh, lab, top = int(44 * z), int(40 * z), int(30 * z), int(22 * z)
        rows = max(1, (len(self.sheet.groups) * 5 + 4) // 5)
        cv = tk.Canvas(f, width=lab + 5 * cw + 4, height=top + rows * chh + 4, bg=PAPER, highlightthickness=0)
        cv.pack()
        x0, y0 = lab + 2, top + 2
        for c in range(5):
            cv.create_text(x0 + c * cw + cw / 2, top / 2 + 1, text=str(c + 1), font=a.f_instr, fill=INK2)
        for r in range(rows):
            cv.create_text(lab - 8, y0 + r * chh + chh / 2, text=str(r + 1), font=a.f_small, fill=INK2, anchor="e")
        for c in range(6):
            cv.create_line(x0 + c * cw, y0, x0 + c * cw, y0 + rows * chh, fill=RULE, width=2 if c in (0, 5) else 1)
        for r in range(rows + 1):
            cv.create_line(x0, y0 + r * chh, x0 + 5 * cw, y0 + r * chh, fill=RULE, width=2 if r in (0, rows) else 1)
        for i in range(len(self.sheet.groups) * 5):
            r, c = divmod(i, 5)
            e = tk.Entry(cv, width=2, font=a.f_cell, justify="center", bd=0, relief="flat", bg=PAPER, fg=INK,
                         readonlybackground=PAPER, insertbackground=FLAG, highlightthickness=2,
                         highlightbackground=PAPER, highlightcolor=FLAG)
            cv.create_window(x0 + c * cw + cw / 2, y0 + r * chh + chh / 2, window=e, width=cw - 5, height=chh - 5)
            e.bind("<Key>", lambda ev, i=i: self._key_a(ev, i))
            e.bind("<FocusIn>", lambda ev, i=i: self._focused("a", i))
            self.cells.append(e)
        self.cv_a, self.geo_a = cv, (x0, y0, cw, chh)
        return f

    def _focused(self, part, i):
        self.app.cursor = (self, part, i)
        if part == "a":
            self.cells[i].select_range(0, "end")

    def focus_first(self):
        """Put the cursor on this sheet: back where it was, or in the first box."""
        try:
            f = self.focus_get()
        except Exception:
            f = None
        if f in self.cells or f in self.boxes:
            return
        cur = self.app.cursor
        if cur and cur[0] is self:
            (self._focus_a if cur[1] == "a" else self._focus_b)(cur[2])
        elif self.cells:
            self._focus_a(0)
        else:
            self._focus_b(0)

    def _focus_a(self, i):
        if 0 <= i < len(self.cells):
            self.app.cursor = (self, "a", i)
            if self.app.full_win is None:     # the full-screen window passes keys on
                self.cells[i].focus_set()

    def _key_a(self, ev, i):
        if ev.keysym in ("Tab", "ISO_Left_Tab") or ev.state & SHORTCUT:
            return None
        if self.locked:
            return "break"
        k, ch, e = ev.keysym, ev.char, self.cells[i]
        if k == "BackSpace":
            if e.get():
                e.delete(0, "end")
            elif i > 0:
                self.cells[i - 1].delete(0, "end")
                self._focus_a(i - 1)
            return "break"
        if k == "Delete":
            e.delete(0, "end")
            return "break"
        if k in ("Right", "space", "Return", "KP_Enter"):
            self._focus_a(i + 1)
            return "break"
        if k == "Left":
            self._focus_a(i - 1)
            return "break"
        if k == "Down":
            self._focus_a(i + 5)
            return "break"
        if k == "Up":
            self._focus_a(i - 5)
            return "break"
        if ch and ch.isascii() and ch.isalnum():
            e.delete(0, "end")
            e.insert(0, ch.upper())
            self._focus_a(i + 1)
            return "break"
        if ch and ch.isprintable():
            return "break"
        return None

    # Part B
    def _part_b(self, parent):
        a, z = self.app, self.app.z
        f = tk.Frame(parent, bg=PAPER)
        tk.Label(f, text="Message", font=a.f_head, bg=PAPER, fg=INK).pack()
        tk.Label(f, text="[write words received sequentially,\ni.e. word by word, in the following boxes]",
                 font=a.f_instr, bg=PAPER, fg=INK2, justify="center").pack(pady=(0, 6))
        n = max(20, len(self.sheet.msg["words"]))
        rows = (n + 1) // 2
        bw, bh, top = int(170 * z), int(46 * z), int(22 * z)
        cv = tk.Canvas(f, width=2 * bw + 4, height=top + rows * bh + 4, bg=PAPER, highlightthickness=0)
        cv.pack()
        x0, y0 = 2, top + 2
        cv.create_rectangle(x0, y0, x0 + 2 * bw, y0 + rows * bh, outline=RULE, width=2)
        cv.create_line(x0 + bw, y0, x0 + bw, y0 + rows * bh, fill=RULE)
        for r in range(1, rows):
            cv.create_line(x0, y0 + r * bh, x0 + 2 * bw, y0 + r * bh, fill=RULE)
        self.box_xy = []
        for i in range(n):
            col, row = (0, i) if i < rows else (1, i - rows)
            x, y = x0 + col * bw, y0 + row * bh
            cv.create_text(x + 6, y + 4, text="%d." % (i + 1), anchor="nw", font=a.f_tiny, fill=INK2)
            e = tk.Entry(cv, font=a.f_word, bd=0, relief="flat", bg=PAPER, fg=INK, readonlybackground=PAPER,
                         insertbackground=FLAG, highlightthickness=2, highlightbackground=PAPER, highlightcolor=FLAG)
            cv.create_window(x + 4, y + bh - 3, window=e, anchor="sw", width=bw - 8, height=int(bh * 0.6))
            e.bind("<Key>", lambda ev, i=i: self._key_b(ev, i))
            e.bind("<FocusIn>", lambda ev, i=i: self._focused("b", i))
            self.boxes.append(e)
            self.box_xy.append((x, y, bw, bh))
        self.cv_b = cv
        return f

    def _focus_b(self, i):
        if 0 <= i < len(self.boxes):
            self.app.cursor = (self, "b", i)
            if self.app.full_win is None:
                self.boxes[i].focus_set()
            self.boxes[i].icursor("end")

    def _key_b(self, ev, i):
        if ev.keysym in ("Tab", "ISO_Left_Tab") or ev.state & SHORTCUT:
            return None
        if self.locked:
            return "break"
        k, ch, e = ev.keysym, ev.char, self.boxes[i]
        if k in ("space", "Return", "KP_Enter", "Down"):
            self._focus_b(i + 1)
            return "break"
        if k == "Up":
            self._focus_b(i - 1)
            return "break"
        if k == "BackSpace" and not e.get():
            self._focus_b(i - 1)
            return "break"
        if ch and ch.isascii() and ch.isalnum():
            if e.selection_present():
                e.delete("sel.first", "sel.last")
            e.insert("insert", ch.upper())
            return "break"
        if ch and ch.isprintable():
            return "break"
        return None

    # marking
    def lock(self, flag=True):
        self.locked = flag
        for e in self.cells + self.boxes:
            e.configure(state="readonly" if flag else "normal")

    def mark(self, pct):
        res = mark_sheet(self.sheet, [e.get() for e in self.cells], [e.get() for e in self.boxes], pct)
        self._paint_marks(res)
        self._show_result(res)
        self.lock(True)
        return res

    def _paint_marks(self, res):
        a = self.app
        for w in self.marks:
            w.destroy()
        self.marks = []
        if "A" in res:
            x0, y0, cw, chh = self.geo_a
            for i, (g, e) in enumerate(zip(res["A"]["got"], res["A"]["exp"])):
                bg, fg = (OK_BG, OK_FG) if g == e else ((BAD_BG, BAD_FG) if g else (BLANK_BG, BLANK_FG))
                self.cells[i].configure(readonlybackground=bg, bg=bg, fg=fg)
                if g != e:
                    r, c = divmod(i, 5)
                    lab = tk.Label(self.cv_a, text=e, font=a.f_tiny_b, bg=bg, fg=fg, bd=0, padx=0, pady=0)
                    self.cv_a.create_window(x0 + (c + 1) * cw - 3, y0 + (r + 1) * chh - 2, window=lab, anchor="se")
                    self.marks.append(lab)
        if "B" in res:
            for i, e in enumerate(self.boxes):
                exp = res["B"]["exp"][i] if i < len(res["B"]["exp"]) else None
                g = res["B"]["got"][i]
                if exp is None:
                    bg, fg = (PAPER, INK2)
                else:
                    bg, fg = (OK_BG, OK_FG) if g == exp else ((BAD_BG, BAD_FG) if g else (BLANK_BG, BLANK_FG))
                e.configure(readonlybackground=bg, bg=bg, fg=fg)
                x, y, bw, bh = self.box_xy[i]
                if exp is not None:
                    rect = self.cv_b.create_rectangle(x + 1, y + 1, x + bw - 1, y + bh - 1, fill=bg, outline="")
                    self.cv_b.tag_lower(rect)
                    if g != exp:
                        self.cv_b.create_text(x + bw - 6, y + 4, text=exp, anchor="ne", font=a.f_tiny_b, fill=fg)

    def _show_result(self, res):
        a = self.app
        for w in self.res.winfo_children():
            w.destroy()
        box = tk.Frame(self.res, bg=PANEL, padx=14, pady=10, highlightthickness=1, highlightbackground="#C9D1DC")
        box.pack(fill="x")
        top = tk.Frame(box, bg=PANEL)
        top.pack(fill="x")
        tk.Label(top, text=" PASS " if res["pass"] else " FAIL ", font=a.f_badge, bg=OK_BG if res["pass"] else BAD_BG,
                 fg=OK_FG if res["pass"] else BAD_FG).pack(side="left")
        tk.Label(top, text="  " + ("Your result" if self.sheet.label == "Answer sheet" else self.sheet.label + " result"),
                 font=a.f_bold, bg=PANEL, fg=INK).pack(side="left")
        grid = tk.Frame(box, bg=PANEL)
        grid.pack(fill="x", pady=(8, 2))
        row = 0
        for key, name, unit in (("A", "Characters", "correct"), ("B", "Message", "words")):
            if key not in res:
                continue
            r = res[key]
            tk.Label(grid, text=name, font=a.f_ui, bg=PANEL, fg=INK).grid(row=row, column=0, sticky="w")
            tk.Label(grid, text="%d / %d" % (r["ok"], r["n"]), font=a.f_mono, bg=PANEL, fg=INK).grid(row=row, column=1, padx=12)
            tk.Label(grid, text="%d%%" % r["pct"], font=a.f_mono, bg=PANEL, fg=INK).grid(row=row, column=2)
            tk.Label(grid, text=" PASS " if r["pass"] else " FAIL ", font=a.f_badge_s, bg=OK_BG if r["pass"] else BAD_BG,
                     fg=OK_FG if r["pass"] else BAD_FG).grid(row=row, column=3, padx=(12, 0))
            note = "Pass needs %d of %d %s (%d%%)." % (r["need"], r["n"], unit, self.app.s["pass_pct"])
            if key == "B":
                note += " A wrong, misspelt or blank word counts as wrong."
            tk.Label(grid, text=note, font=a.f_small, bg=PANEL, fg=INK2).grid(row=row + 1, column=0, columnspan=4, sticky="w", pady=(0, 4))
            row += 2
        msg = self.sheet.msg
        if msg:
            self.body.update_idletasks()
            wrap = max(int(300 * a.z), self.body.winfo_reqwidth() - int(40 * a.z))   # never wider than the sheet
            tk.Label(box, text=msg["text"], font=a.f_sent, bg=PANEL, fg=INK, wraplength=wrap, justify="left").pack(anchor="w", pady=(6, 0))
            if msg.get("code"):
                src = "ICS General section, signal %s, chapter %s (%s), %d words" % (
                    msg["code"], msg["chapter"], CHAPTERS[msg["chapter"]], len(msg["words"]))
                tk.Label(box, text=src, font=a.f_small, bg=PANEL, fg=INK2).pack(anchor="w")
        errs = []
        if "A" in res:
            for i, (g, e) in enumerate(zip(res["A"]["got"], res["A"]["exp"])):
                if g == e:
                    continue
                where = "Row %d box %d" % (i // 5 + 1, i % 5 + 1)
                if g:
                    errs.append("%s: sent %s %s, you wrote %s %s" % (where, e, SHOW(MORSE[e]), g, SHOW(MORSE.get(g, ""))))
                else:
                    errs.append("%s: sent %s %s, blank" % (where, e, SHOW(MORSE[e])))
        if "B" in res:
            for i, e in enumerate(res["B"]["exp"]):
                g = res["B"]["got"][i] if i < len(res["B"]["got"]) else ""
                if g != e:
                    errs.append("Word %d: sent %s, %s" % (i + 1, e, ("you wrote " + g) if g else "blank"))
        notes = []
        if any(res[k]["shift"] for k in ("A", "B") if k in res):
            notes.append("Some answers are one box out of place. Leave a box empty when you miss something, so the rest line up.")
        if "B" in res and res["B"]["extra"]:
            notes.append("Boxes filled after the end of the message are not counted.")
        if self.app.exam_note:
            notes.append(self.app.exam_note)
        if self.app.exam and self.sheet.id == 0:
            notes += self.app.exam.notes
        if errs or notes:
            t = tk.Text(box, width=40, height=min(10, len(errs) + len(notes)) or 1, font=a.f_mono_s, bg=PANEL, fg=INK,
                        bd=0, wrap="word", highlightthickness=0)
            t.tag_configure("note", foreground=BLANK_FG, font=a.f_small)
            for line in errs:
                t.insert("end", line + "\n")
            for line in notes:
                t.insert("end", line + "\n", "note")
            t.configure(state="disabled")
            t.pack(fill="x", pady=(8, 0))


class SettingsDialog(tk.Toplevel):
    COLOURS = (("lamp_on", "Lit lamp"), ("lamp_off", "Unlit lamp"), ("stage_bg", "Box face (background)"),
               ("housing_color", "Round recess"))

    def __init__(self, app):
        super().__init__(app.root)
        self.withdraw()
        self.app, s = app, app.s
        self.title("Settings")
        self.transient(app.root)
        self.resizable(False, False)
        nums = ("wpm", "space", "spacew", "pause_spaces", "countdown", "lamp_mm", "pass_pct", "min_words", "max_words")
        self.v = {k: (tk.DoubleVar(value=s[k]) if isinstance(DEFAULTS[k], float) else tk.IntVar(value=s[k])) for k in nums}
        self.col = {k: tk.StringVar(value=s[k]) for k, _ in self.COLOURS}
        self.v_glow = tk.BooleanVar(value=s["glow"])
        self.v_housing = tk.BooleanVar(value=s["housing"])
        self.v_prog = tk.BooleanVar(value=s["show_progress"])
        self.v_style = tk.StringVar(value=s["group_style"])
        self.v_preset = tk.StringVar(value=self._preset_name())
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)
        nb = ttk.Notebook(outer)
        nb.pack(fill="both", expand=True)
        t_time, t_lamp, t_msg = (ttk.Frame(nb, padding=14) for _ in range(3))
        nb.add(t_time, text="  Timing  ")
        nb.add(t_lamp, text="  Lamp  ")
        nb.add(t_msg, text="  Messages and marking  ")

        # timing
        r = self._spin(t_time, 0, "Speed (wpm)", "wpm", 5, 40)
        r = self._spin(t_time, r, "Spaces between characters (one space = 3 dots)", "space", 1, 10)
        r = self._spin(t_time, r, "Spaces between words (one space = 7 dots)", "spacew", 1, 20)
        self.readout = ttk.Label(t_time, text="", foreground=INK2, justify="left")
        self.readout.grid(row=r, column=0, columnspan=3, sticky="w", pady=(4, 10))
        r = self._spin(t_time, r + 1, "Pause between parts (spaces)", "pause_spaces", 0, 120)
        self.pause_note = ttk.Label(t_time, text="", foreground=INK2)
        self.pause_note.grid(row=r - 1, column=2, sticky="w")
        self._spin(t_time, r, "Countdown before the first signal (seconds)", "countdown", 0, 30)

        # lamp
        ttk.Label(t_lamp, text="Look").grid(row=0, column=0, sticky="w")
        cb = ttk.Combobox(t_lamp, textvariable=self.v_preset, values=list(PRESETS) + ["Custom"], state="readonly", width=30)
        cb.grid(row=0, column=1, columnspan=2, sticky="w", padx=8, pady=2)
        cb.bind("<<ComboboxSelected>>", lambda e: self.apply_preset())
        self.preview = tk.Canvas(t_lamp, width=int(330 * app.z), height=int(130 * app.z), highlightthickness=1,
                                 highlightbackground="#C9D1DC")
        self.preview.grid(row=1, column=0, columnspan=3, sticky="w", pady=(8, 10))
        r = 2
        self.swatch = {}
        for key, label in self.COLOURS:
            ttk.Label(t_lamp, text=label).grid(row=r, column=0, sticky="w")
            sw = tk.Label(t_lamp, width=4, relief="solid", bd=1, bg=self.col[key].get())
            sw.grid(row=r, column=1, sticky="w", padx=8, pady=2)
            self.swatch[key] = sw
            row = ttk.Frame(t_lamp)
            row.grid(row=r, column=2, sticky="w")
            ttk.Button(row, text="Change...", command=lambda k=key: self.pick(k)).pack(side="left")
            ttk.Label(row, textvariable=self.col[key], foreground=INK2, font=app.f_mono_s).pack(side="left", padx=6)
            r += 1
        ttk.Checkbutton(t_lamp, text="Round recess around the lamp", variable=self.v_housing,
                        command=self.draw_preview).grid(row=r, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Checkbutton(t_lamp, text="Glow around the lit lamp", variable=self.v_glow,
                        command=self.draw_preview).grid(row=r + 1, column=0, columnspan=3, sticky="w")
        r = self._spin(t_lamp, r + 2, "Lamp diameter (mm)", "lamp_mm", 1, 60, 0.5,
                       "the exam lamp is about 9 mm")
        ttk.Button(t_lamp, text="Calibrate size with a card...", command=lambda: CalibrateDialog(app, self)).grid(
            row=r, column=0, sticky="w", pady=(6, 0))

        # messages and marking
        ttk.Radiobutton(t_msg, text="4 letters and 1 digit in each group", value="g1",
                        variable=self.v_style).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Radiobutton(t_msg, text="3 letters and 2 digits in each group", value="g2",
                        variable=self.v_style).grid(row=1, column=0, columnspan=3, sticky="w", pady=(0, 10))
        r = self._spin(t_msg, 2, "Shortest message (words)", "min_words", 10, 20)
        r = self._spin(t_msg, r, "Longest message (words)", "max_words", 10, 20)
        self.count_note = ttk.Label(t_msg, text="", foreground=INK2)
        self.count_note.grid(row=r, column=0, columnspan=3, sticky="w", pady=(2, 10))
        r = self._spin(t_msg, r + 1, "Pass mark (%)", "pass_pct", 50, 100)
        ttk.Checkbutton(t_msg, text="Show which group or word is being sent", variable=self.v_prog).grid(
            row=r, column=0, columnspan=3, sticky="w")

        b = ttk.Frame(outer)
        b.pack(fill="x", pady=(12, 0))
        ttk.Button(b, text="Reset to exam settings", command=self.reset).pack(side="left")
        ttk.Button(b, text="Save", command=self.save).pack(side="right")
        ttk.Button(b, text="Cancel", command=self.destroy).pack(side="right", padx=6)
        self.refresh()
        self.draw_preview()
        show_over(self, app.root)

    def _spin(self, f, r, label, key, lo, hi, inc=1, note=""):
        ttk.Label(f, text=label).grid(row=r, column=0, sticky="w")
        sp = ttk.Spinbox(f, from_=lo, to=hi, increment=inc, textvariable=self.v[key], width=7, command=self.refresh)
        sp.grid(row=r, column=1, sticky="w", padx=8, pady=2)
        sp.bind("<KeyRelease>", lambda e: self.refresh())
        if note:
            ttk.Label(f, text=note, foreground=INK2).grid(row=r, column=2, sticky="w")
        return r + 1

    def _get(self, key):
        try:
            return self.v[key].get()
        except Exception:
            return self.app.s[key]

    def _look(self):
        look = dict((k, self.col[k].get()) for k, _ in self.COLOURS)
        look["housing"], look["glow"] = self.v_housing.get(), self.v_glow.get()
        return look

    def _preset_name(self):
        for name, p in PRESETS.items():
            if all(self.app.s[k] == v for k, v in p.items()):
                return name
        return "Custom"

    def apply_preset(self):
        p = PRESETS.get(self.v_preset.get())
        if not p:
            return
        for k, _ in self.COLOURS:
            self.col[k].set(p[k])
            self.swatch[k].configure(bg=p[k])
        self.v_housing.set(p["housing"])
        self.v_glow.set(p["glow"])
        self.draw_preview()

    def pick(self, key):
        from tkinter import colorchooser
        got = colorchooser.askcolor(color=self.col[key].get(), parent=self, title="Choose a colour")
        if got and got[1]:
            col = got[1].upper()
            if len(col) == 4:          # #RGB on some systems
                col = "#" + "".join(ch * 2 for ch in col[1:])
            self.col[key].set(col[:7])
            self.swatch[key].configure(bg=col[:7])
            self.v_preset.set("Custom")
            self.draw_preview()

    def draw_preview(self):
        c, look = self.preview, self._look()
        c.delete("all")
        c.configure(bg=look["stage_bg"])
        w, h = int(c.cget("width")), int(c.cget("height"))
        d = min(h / 5.2 if look["housing"] else h / 2.5, 34 * self.app.z)
        fg = "#1E2530" if is_light(look["stage_bg"]) else "#C8CED6"
        for x, on, label in ((w * 0.27, False, "unlit"), (w * 0.73, True, "lit")):
            draw_lamp(c, x, h * 0.45, d, look, on)
            c.create_text(x, h - 10, text=label, fill=fg, font=self.app.f_small)

    def refresh(self):
        try:
            wpm, sp, sw = max(5, self._get("wpm")), max(1, self._get("space")), max(1, self._get("spacew"))
            u = dot_seconds(wpm)
            cg, one = 3 * sp * u, (max(0, 7 * sw - 4) + 3 * sp) * u
            self.readout.configure(text=(
                "Dot %.3f s, after each character %.2f s, each space %.2f s more\n"
                "Between characters %.2f s, between groups %.2f s"
                % (u, cg, one, cg + one, cg + 3 * one)))
            self.pause_note.configure(text="= %s" % fmt_time(cg + self._get("pause_spaces") * one))
        except Exception:
            pass
        try:
            lo, hi = sorted((int(self._get("min_words")), int(self._get("max_words"))))
            n = len(messages_in_range(dict(min_words=lo, max_words=hi)))
            self.count_note.configure(text="%d of the %d ICS messages have %d to %d words." % (n, len(MESSAGES), lo, hi))
        except Exception:
            pass

    def reset(self):
        for k, var in self.v.items():
            var.set(DEFAULTS[k])
        for k, _ in self.COLOURS:
            self.col[k].set(DEFAULTS[k])
            self.swatch[k].configure(bg=DEFAULTS[k])
        self.v_glow.set(DEFAULTS["glow"])
        self.v_housing.set(DEFAULTS["housing"])
        self.v_prog.set(DEFAULTS["show_progress"])
        self.v_style.set(DEFAULTS["group_style"])
        self.v_preset.set(self._name_for(DEFAULTS))
        self.refresh()
        self.draw_preview()

    def _name_for(self, src):
        for name, p in PRESETS.items():
            if all(src[k] == v for k, v in p.items()):
                return name
        return "Custom"

    def save(self):
        s = self.app.s
        old = (s["group_style"], s["min_words"], s["max_words"])
        for k in self.v:
            lo, hi = LIMITS[k]
            try:
                s[k] = type(DEFAULTS[k])(min(hi, max(lo, self.v[k].get())))
            except Exception:
                pass
        if s["min_words"] > s["max_words"]:
            s["min_words"], s["max_words"] = s["max_words"], s["min_words"]
        for k, _ in self.COLOURS:
            if HEX.match(self.col[k].get()):
                s[k] = self.col[k].get()
        s["glow"], s["housing"] = self.v_glow.get(), self.v_housing.get()
        s["show_progress"], s["group_style"] = self.v_prog.get(), self.v_style.get()
        save_settings(s)
        self.destroy()
        self.app.settings_changed(content=old != (s["group_style"], s["min_words"], s["max_words"]))


class CalibrateDialog(tk.Toplevel):
    CARD_MM = 85.6

    def __init__(self, app, parent):
        super().__init__(parent)
        self.withdraw()
        self.app, self.parent = app, parent
        self.title("Calibrate lamp size")
        self.transient(parent)
        self.resizable(False, False)
        f = ttk.Frame(self, padding=14)
        f.pack()
        ttk.Label(f, text="Hold a bank card or ID card against the screen.\n"
                          "Move the slider until the bar is as long as the card.",
                  justify="left").pack(anchor="w")
        width = min(int(16 * self.CARD_MM) + 6, self.winfo_screenwidth() - 80)
        self.cv = tk.Canvas(f, width=width, height=46, bg=PAPER, highlightthickness=0)
        self.cv.pack(pady=10, anchor="w")
        self.var = tk.DoubleVar(value=app.px_per_mm())
        ttk.Scale(f, from_=2.0, to=16.0, variable=self.var, command=lambda e: self.draw(),
                  length=min(int(9 * self.CARD_MM), width)).pack(anchor="w")
        self.lab = ttk.Label(f, text="")
        self.lab.pack(anchor="w", pady=(6, 0))
        b = ttk.Frame(f)
        b.pack(fill="x", pady=(10, 0))
        ttk.Button(b, text="Use screen default", command=self.default).pack(side="left")
        ttk.Button(b, text="OK", command=self.ok).pack(side="right")
        ttk.Button(b, text="Cancel", command=self.close).pack(side="right", padx=6)
        self.protocol("WM_DELETE_WINDOW", self.close)
        self.draw()
        show_over(self, parent)

    def draw(self):
        px = self.var.get()
        self.cv.delete("all")
        w = self.CARD_MM * px
        self.cv.create_rectangle(2, 8, 2 + w, 38, outline=INK, width=2, fill="#DCE2EA")
        mm = self.app.s["lamp_mm"]
        self.lab.configure(text="%.2f pixels per mm, so a %.1f mm lamp is %d px" % (px, mm, round(mm * px)))

    def default(self):
        self.var.set(self.app.root.winfo_fpixels("1m"))
        self.draw()

    def ok(self):
        self.app.s["px_per_mm"] = float(self.var.get())
        save_settings(self.app.s)
        self.app.redraw_lamps()
        self.close()

    def close(self):
        self.destroy()
        if isinstance(self.parent, SettingsDialog):     # it was modal before this one opened
            try:
                self.parent.grab_set()
            except Exception:
                pass


class App:
    MODES = [("sheet", "One answer sheet"), ("full", "Full recording"), ("partA", "Characters only"), ("partB", "Message only")]

    def __init__(self, root):
        self.root, self.s = root, load_settings()
        self.z = max(1.0, root.winfo_fpixels("1i") / 96.0)
        self._fonts()
        root.title("Morse Light Trainer")
        root.configure(bg=PANEL)
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        root.minsize(min(int(980 * self.z), sw - 40), min(int(620 * self.z), sh - 120))
        try:
            self.icons = [lamp_icon(n) for n in (32, 16)]
            root.iconphoto(True, *self.icons)
        except Exception:
            pass
        self.state, self.exam, self.run, self.views = "idle", None, None, []
        self.lamps, self.full_win, self.tidy_end, self.exam_note = [], None, None, ""
        self.loaded_path, self.cursor, self.check_ok = None, None, None
        self._build()
        self.new_exam()
        root.bind("<F11>", lambda e: self.toggle_full())
        root.bind("<Escape>", lambda e: self.on_escape())
        root.protocol("WM_DELETE_WINDOW", self.quit)
        if IS_MAC and tk.TkVersion < 8.6:
            root.after(600, lambda: messagebox.showwarning("Old Tk", (
                "This Python has Tk %s, which is too old to draw the lamp properly.\n\n"
                "Install Python 3 from python.org and start the trainer again.") % tk.TkVersion, parent=root))

    # look
    def _fonts(self):
        fam = set(tkfont.families())
        pick = lambda *names: next((n for n in names if n in fam), names[-1])
        serif = pick("Cambria", "Georgia", "Times New Roman", "DejaVu Serif", "Times")
        sans = pick("Segoe UI", "Helvetica Neue", "Arial", "Helvetica", "DejaVu Sans", "TkDefaultFont")
        mono = pick("Consolas", "Menlo", "SF Mono", "Cascadia Mono", "DejaVu Sans Mono", "Courier New", "Courier")
        self.f_head = (serif, 15, "bold")
        self.f_sent = (serif, 12, "bold")
        self.f_instr = (sans, 9, "italic")
        self.f_ui = (sans, 10)
        self.f_bold = (sans, 10, "bold")
        self.f_small = (sans, 9)
        self.f_tiny = (sans, 7)
        self.f_tiny_b = (mono, 8, "bold")
        self.f_cell = (mono, 17)
        self.f_word = (mono, 13)
        self.f_mono = (mono, 11)
        self.f_mono_s = (mono, 9)
        self.f_cap = (mono, 30, "bold")
        self.f_note = (mono, 13)
        self.f_badge = (mono, 11, "bold")
        self.f_badge_s = (mono, 9, "bold")
        st = ttk.Style()
        try:
            if "vista" in st.theme_names():
                st.theme_use("vista")
            elif IS_MAC and "aqua" in st.theme_names():
                st.theme_use("aqua")
            elif "clam" in st.theme_names():
                st.theme_use("clam")
        except Exception:
            pass
        st.configure("Big.TButton", font=(sans, 10, "bold"), padding=(12, 5))

    def px_per_mm(self):
        return self.s["px_per_mm"] if self.s["px_per_mm"] > 0 else self.root.winfo_fpixels("1m")

    # layout
    def _build(self):
        r = self.root
        menu = tk.Menu(r)
        m_file = tk.Menu(menu, tearoff=0)
        mod, acc = ("Command", "Cmd") if IS_MAC else ("Control", "Ctrl")
        m_file.add_command(label="Open CW Player text file...", command=self.open_file, accelerator=acc + "+O")
        m_file.add_command(label="Save this exam for CW Player...", command=self.save_file, accelerator=acc + "+S")
        m_file.add_separator()
        m_file.add_command(label="Exit", command=self.quit)
        menu.add_cascade(label="File", menu=m_file)
        m_lamp = tk.Menu(menu, tearoff=0)
        m_lamp.add_command(label="Test lamp (V V V)", command=self.test_lamp)
        m_lamp.add_command(label="Full-screen lamp", command=self.toggle_full, accelerator="F11")
        m_lamp.add_command(label="Calibrate size with a card...", command=lambda: CalibrateDialog(self, self.root))
        menu.add_cascade(label="Lamp", menu=m_lamp)
        if IS_MAC:
            # The Mac menu bar ignores plain commands.
            m_set = tk.Menu(menu, tearoff=0)
            m_set.add_command(label="Settings...", command=self.open_settings, accelerator="Cmd+,")
            menu.add_cascade(label="Settings", menu=m_set)
            m_help = tk.Menu(menu, tearoff=0)
            m_help.add_command(label="About Morse Light Trainer", command=self.about)
            menu.add_cascade(label="Help", menu=m_help)
            try:
                r.createcommand("tk::mac::ShowPreferences", self.open_settings)
                r.createcommand("tkAboutDialog", self.about)
            except Exception:
                pass
            r.bind("<Command-comma>", lambda e: self.open_settings())
            r.bind("<Command-Control-f>", lambda e: self.toggle_full())
        else:
            menu.add_command(label="Settings...", command=self.open_settings)
            menu.add_command(label="About", command=self.about)
        r.configure(menu=menu)
        r.bind("<%s-o>" % mod, lambda e: self.open_file())
        r.bind("<%s-s>" % mod, lambda e: self.save_file())

        bar = ttk.Frame(r, padding=(10, 8))
        bar.pack(fill="x")
        ttk.Label(bar, text="Practise:", font=self.f_bold).pack(side="left", padx=(0, 6))
        self.mode = tk.StringVar(value="sheet")
        self.mode_btns = []
        for val, label in self.MODES:
            b = ttk.Radiobutton(bar, text=label, value=val, variable=self.mode, command=self.on_mode)
            b.pack(side="left", padx=4)
            self.mode_btns.append(b)
        self.b_stop = ttk.Button(bar, text="■ Stop", command=self.stop)
        self.b_start = ttk.Button(bar, text="▶ Start", style="Big.TButton", command=self.start)
        self.b_full = ttk.Button(bar, text="Full-screen lamp", command=self.toggle_full)
        self.b_test = ttk.Button(bar, text="Test lamp", command=self.test_lamp)
        for b in (self.b_full, self.b_test, self.b_stop, self.b_start):
            b.pack(side="right", padx=4)

        pane = tk.PanedWindow(r, orient="horizontal", sashwidth=6, bg=PANEL, bd=0)
        pane.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        lamp_canvas = tk.Canvas(pane, bg=self.s["stage_bg"], highlightthickness=0, width=int(420 * self.z))
        self.lamp_main = LampView(self, lamp_canvas)
        self.lamps.append(self.lamp_main)
        pane.add(lamp_canvas, minsize=int(260 * self.z), stretch="always")
        right = ttk.Frame(pane)
        pane.add(right, minsize=int(520 * self.z), stretch="always")
        self.nb = ttk.Notebook(right)
        self.nb.pack(fill="both", expand=True)
        act = ttk.Frame(right, padding=(0, 8, 0, 0))
        act.pack(fill="x")
        self.b_mark = ttk.Button(act, text="Mark my sheet", style="Big.TButton", command=self.mark)
        self.b_replay = ttk.Button(act, text="Replay with captions", command=self.replay)
        self.b_new = ttk.Button(act, text="New exam", command=self.new_exam)
        self.b_mark.pack(side="left")
        self.b_replay.pack(side="left", padx=6)
        self.b_new.pack(side="left")
        self.tidy = ttk.Label(act, text="", font=self.f_mono)
        self.tidy.pack(side="right")
        tip = ("Letters fill the boxes in order. In the message, press Space after each word. "
               "Leave a box empty if you miss something.")
        tip_lab = ttk.Label(right, text=tip, foreground=INK2, wraplength=int(500 * self.z))
        tip_lab.pack(fill="x", pady=(6, 0))
        tip_lab.bind("<Configure>", lambda e: tip_lab.configure(wraplength=max(100, e.width - 4)))

        self.scrolls = []
        r.bind_all("<MouseWheel>", self._wheel, add="+")
        r.bind_all("<Button-4>", lambda e: self._wheel(e, -1), add="+")
        r.bind_all("<Button-5>", lambda e: self._wheel(e, 1), add="+")

        sb = ttk.Frame(r, padding=(10, 2, 10, 6))
        sb.pack(fill="x")
        self.status = ttk.Label(sb, text="")
        self.status.pack(side="left")
        self.timing_lab = ttk.Label(sb, text="", foreground=INK2)
        self.timing_lab.pack(side="right")

    def _wheel(self, e, n=None):
        if n is None:
            d = getattr(e, "delta", 0) or 0
            n = int(-d / 120) if abs(d) >= 120 else (-1 if d > 0 else 1)
        for sf in self.scrolls:
            try:
                if sf.winfo_ismapped() and sf.hovered():
                    sf.scroll(n)
                    break
            except Exception:
                pass

    # state
    def set_state(self, st):
        self.state = st
        busy = st in ("running", "review", "testing")
        show = lambda b, on: b.state(["!disabled"] if on else ["disabled"])
        show(self.b_start, st == "idle")
        show(self.b_stop, busy)
        show(self.b_test, not busy)
        show(self.b_mark, st == "done")
        show(self.b_replay, st == "marked")
        show(self.b_new, not busy)
        for b in self.mode_btns:
            show(b, st in ("idle", "marked"))
        for v in self.views:
            if st == "marked" or st == "review":
                v.lock(True)
        if st != "done":
            self.tidy_end = None
            self.tidy.configure(text="")
        self.update_timing_label()

    def update_timing_label(self):
        s = self.s
        self.timing_lab.configure(text="%d wpm, character spacing %d, word spacing %d, lamp %.1f mm"
                                       % (s["wpm"], s["space"], s["spacew"], s["lamp_mm"]))

    def set_status(self, text):
        self.status.configure(text=text)

    def lamp_text(self, **kw):
        for l in self.lamps:
            l.text(**kw)

    def set_lamp(self, on):
        for l in self.lamps:
            l.set(on)

    def redraw_lamps(self):
        for l in self.lamps:
            l.redraw()
        self.update_timing_label()

    # exam building
    def on_mode(self):
        if self.state in ("idle", "marked"):
            self.loaded_path = None
            self.new_exam()

    def new_exam(self):
        if self.state in ("running", "review", "testing"):
            return
        if self.loaded_path:
            try:
                ex = load_exam(self.loaded_path)
            except Exception:
                self.loaded_path = None
                ex = build_exam(self.mode.get(), self.s)
        else:
            ex = build_exam(self.mode.get(), self.s)
        self.show_exam(ex)

    def show_exam(self, ex):
        self.exam, self.exam_note, self.cursor = ex, "", None
        for tab in self.nb.tabs():
            self.nb.forget(tab)
        for w in self.nb.winfo_children():
            w.destroy()
        self.views, self.scrolls = [], []
        for sh in ex.sheets:
            sf = ScrollFrame(self.nb)
            self.scrolls.append(sf)
            v = SheetView(sf.inner, self, sh)
            v.pack(fill="both", expand=True)
            self.nb.add(sf, text="  %s  " % sh.label)
            self.views.append(v)
        self.b_mark.configure(text="Mark both sheets" if len(ex.sheets) > 1 else "Mark my sheet")
        self.set_state("idle")
        tl = Timeline(ex.text.lstrip(), self.s["wpm"], self.s["space"], self.s["spacew"])
        what = ("File %s" % os.path.basename(ex.source)) if ex.source != "generated" else dict(self.MODES)[ex.mode]
        self.set_status("%s, about %s. Press Start.%s" % (
            what, fmt_time(tl.total + self.s["countdown"]), "".join(" " + n for n in ex.notes)))
        self.lamp_text(note="", caption="", sub="", status="Ready")
        self.set_lamp(False)

    # running the lamp
    def start(self):
        if self.state != "idle" or not self.exam:
            return
        recent = self.s.get("recent", [])
        for sh in self.exam.sheets:
            if sh.msg and sh.msg.get("id") and sh.msg["id"] not in recent:
                recent.append(sh.msg["id"])
        self.s["recent"] = recent[-60:]
        save_settings(self.s)
        self.set_state("running")
        self.set_status("Playing. F11 shows the lamp full screen.")
        self._run(self.exam.text, "exam", self.s["countdown"])

    def replay(self):
        if self.state != "marked":
            return
        self.set_state("review")
        self.set_status("Replay: each character is shown under the lamp as it is sent.")
        self._run(self.exam.text, "review", 2)

    def test_lamp(self):
        if self.run:
            return
        self.back_state = self.state
        self.set_state("testing")
        self._run("V V V", "test", 0.5)

    def lamp_check(self):
        """--lamptest: flash a short text at the exam settings and time every lamp edge."""
        if self.run:
            return
        self.back_state = self.state
        self.set_state("testing")
        self._run(LAMP_CHECK_TEXT, "check", 1.0, (10, 5, 1))

    def _run(self, text, purpose, lead, timing=None):
        wpm, space, spacew = timing or (self.s["wpm"], self.s["space"], self.s["spacew"])
        tl = Timeline(text.lstrip(), wpm, space, spacew)    # a file plays as written, less its leading spaces
        offset = len(text) - len(text.lstrip())
        self.run = dict(tl=tl, purpose=purpose, t0=time.perf_counter() + lead, k=0, after=None, text=text, offset=offset,
                        tab=None, edges=0, late=0.0, late_sum=0.0)
        self.set_lamp(False)
        self.lamp_text(caption="", sub="")
        self._tick()
        self._ui_tick()

    def _tick(self):
        r = self.run
        if not r:
            return
        tl = r["tl"]
        now = time.perf_counter() - r["t0"]
        ons, k = tl.ons, r["k"]
        while k < len(ons) and ons[k][1] <= now:
            k += 1
        r["k"] = k
        on = k < len(ons) and ons[k][0] <= now
        self.set_lamp(on)
        passed = 2 * k + (1 if on else 0)       # lamp edges that are due by now
        for j in range(r["edges"], passed):     # how late each one was switched
            late = now - tl.edges[j]
            r["late"] = max(r["late"], late)
            r["late_sum"] += late
        r["edges"] = passed
        end = tl.total + 0.4
        if now >= end:
            self._end(True)
            return
        nxt = (ons[k][1] if on else ons[k][0]) if k < len(ons) else end
        delay = nxt - (time.perf_counter() - r["t0"])
        r["after"] = self.root.after(max(1, int(delay * 1000)), self._tick)

    def _ui_tick(self):
        r = self.run
        if not r:
            return
        tl = r["tl"]
        now = time.perf_counter() - r["t0"]
        note = "Starting in %d" % (int(-now) + 1) if now < 0 else ""
        i = bisect.bisect_right(tl.sym_starts, now) - 1
        sym = tl.syms[i] if i >= 0 else None
        if r["purpose"] in ("test", "check"):
            self.lamp_text(note=note, status="Test: " + r["text"])
        else:
            status = "%s / %s" % (fmt_time(max(0, now)), fmt_time(tl.total))
            pos = (sym[2] + r["offset"]) if sym else -1
            b = None
            if self.exam and self.exam.blocks and pos >= 0:
                bi = bisect.bisect_right(self.exam.block_starts, pos) - 1
                if bi >= 0:
                    b = self.exam.blocks[bi]
                    if sym and now > sym[1] + 1.0 and pos >= b["end"] - 1 and bi + 1 < len(self.exam.blocks):
                        b = self.exam.blocks[bi + 1]
            if b is not None and (self.s["show_progress"] or r["purpose"] == "review") and now >= 0:
                label = b.get("label", "")
                item = None
                for n, (s0, s1, w) in enumerate(b["items"]):
                    if s0 <= pos < s1:
                        item = (n, w, pos - s0)
                if pos < b["start"] or pos >= b["end"]:
                    status = "Next: %s · %s" % (label, fmt_time(max(0, now)))
                elif item:
                    what = "word" if b["kind"] == "msg" else "group"
                    status = "%s · %s %d of %d · %s" % (label, what, item[0] + 1, len(b["items"]), fmt_time(now))
                else:
                    status = "%s · %s · %s" % (label, "call AA AA AA" if pos < (b["items"][0][0] if b["items"] else b["end"]) else "end AR", fmt_time(now))
            # Switch to each member's sheet 5 s before their part.
            j = bisect.bisect_right(tl.sym_starts, now + 5.0) - 1
            tb = self._block_of(tl.syms[j][2] + r["offset"]) if j >= 0 else None
            if tb is not None and "sheet" in tb and r["tab"] != tb["sheet"]:
                r["tab"] = tb["sheet"]
                try:
                    if len(self.views) > 1:
                        self.nb.select(tb["sheet"])
                    if r["purpose"] == "exam":
                        self.views[tb["sheet"]].focus_first()
                except Exception:
                    pass
            cap = sub = ""
            if r["purpose"] == "review" and sym and now <= sym[1] + tl.char_gap * 0.85:
                cap = sym[3]
            if r["purpose"] == "review" and b is not None and sym:
                for s0, s1, w in b["items"]:
                    if s0 <= pos < s1:
                        sub = w[:len(re.sub(r"\s", "", r["text"][s0:pos + 1]))]
            self.lamp_text(note=note, caption=cap, sub=sub, status=status)
        self.root.after(100, self._ui_tick)

    def _block_of(self, pos):
        if not self.exam or not self.exam.blocks:
            return None
        bi = bisect.bisect_right(self.exam.block_starts, pos) - 1
        return self.exam.blocks[bi] if bi >= 0 else None

    @staticmethod
    def _timing_note(r):
        if not r["edges"]:
            return ""
        return "timing within %.1f ms of CW Player" % (r["late"] * 1000)

    def _end(self, finished):
        r, self.run = self.run, None
        if r and r.get("after"):
            try:
                self.root.after_cancel(r["after"])
            except Exception:
                pass
        self.set_lamp(False)
        self.lamp_text(note="", caption="", sub="")
        if not r:
            return
        now = time.perf_counter() - r["t0"]
        timing = self._timing_note(r)
        if r["purpose"] == "check":
            tl, n = r["tl"], r["edges"]
            self.check_ok = finished and n == len(tl.edges) and r["late"] < 0.005
            print("Lamp edges for %r at 10 wpm, SPACE=5, SPACEW=1 (exam settings):" % r["text"])
            print("  %d of %d edges, latest %.2f ms after the model, average %.2f ms   %s" % (
                n, len(tl.edges), r["late"] * 1000, r["late_sum"] * 1000 / max(1, n),
                "ok (limit 5 ms)" if self.check_ok else "TOO LATE (limit 5 ms)"))
            if sys.stdout:          # None in a windowed .exe
                sys.stdout.flush()
            self.root.after(300, self.quit)
            return
        if r["purpose"] == "test":
            self.set_state(self.back_state)
            self.lamp_text(status="Test done" + (", " + timing if finished and timing else ""))
            return
        if r["purpose"] == "review":
            self.set_state("marked")
            self.lamp_text(status="Replay finished" if finished else "Replay stopped")
            self.set_status("Press New exam for another one.")
            return
        self.exam_note = "" if finished else "The recording was stopped early at %s." % fmt_time(now)
        self.set_state("done")
        self.lamp_text(status=("End of recording" + (", " + timing if timing else ""))
                       if finished else "Stopped at %s" % fmt_time(now))
        self.set_status("Finished. You have 10 minutes to tidy up, then press Mark.")
        self.tidy_end = time.time() + 600
        self._tidy_tick()
        if self.views:
            try:
                self.nb.select(0)
            except Exception:
                pass

    def _tidy_tick(self):
        if self.state != "done" or not self.tidy_end:
            return
        left = self.tidy_end - time.time()
        self.tidy.configure(text=("Tidy-up time %s" % fmt_time(left)) if left > 0 else "Tidy-up time is over")
        if left > 0:
            self.root.after(500, self._tidy_tick)

    def stop(self):
        if not self.run:
            return
        if self.run["purpose"] == "exam" and not messagebox.askyesno("Stop", "Stop the recording now?", parent=self.root):
            return
        self._end(False)

    def on_escape(self):
        if self.full_win is not None:
            self.toggle_full()
        elif self.run:
            self.stop()

    # marking
    def mark(self):
        if self.state != "done":
            return
        results = []
        for n, v in enumerate(self.views):
            res = v.mark(self.s["pass_pct"])
            results.append(res)
            self.nb.tab(n, text="  %s: %s  " % (v.sheet.label, "PASS" if res["pass"] else "FAIL"))
        if self.exam.test and self.views:
            tk.Label(self.views[0].res, text="Test message (not marked): " + "  ".join(self.exam.test), font=self.f_mono_s,
                     bg=PAPER, fg=INK2).pack(anchor="w", pady=(6, 0))
        self.set_state("marked")
        passed = all(x["pass"] for x in results)
        self.set_status(("Pass." if passed else "Fail.") + " Replay with captions shows what was sent.")
        try:
            self.nb.select(0)
        except Exception:
            pass

    # files
    def open_file(self):
        if self.state in ("running", "review", "testing"):
            return
        start = self.s.get("last_dir") or (PRACTICE_DIR if os.path.isdir(PRACTICE_DIR) else START_DIR)
        path = filedialog.askopenfilename(parent=self.root, title="Open a CW Player text file", initialdir=start,
                                          filetypes=[("Text files", "*.txt *.cwp"), ("All files", "*.*")])
        if not path:
            return
        try:
            ex = load_exam(path)
        except Exception as e:
            messagebox.showerror("Can't use this file", str(e), parent=self.root)
            return
        self.s["last_dir"] = os.path.dirname(path)
        save_settings(self.s)
        self.loaded_path = path
        self.mode.set("")
        self.show_exam(ex)

    def save_file(self):
        if not self.exam:
            return
        start = PRACTICE_DIR if os.path.isdir(PRACTICE_DIR) else START_DIR
        name = "ICS exam %s.txt" % datetime.datetime.now().strftime("%Y-%m-%d %H%M")
        path = filedialog.asksaveasfilename(parent=self.root, title="Save this exam for CW Player", initialdir=start,
                                            initialfile=name, defaultextension=".txt", filetypes=[("Text files", "*.txt")])
        if not path:
            return
        key = os.path.splitext(path)[0] + " answers.txt"
        try:
            with open(path, "w", encoding="ascii", errors="replace", newline="") as f:
                f.write(cw_file_text(self.exam, self.s) if self.exam.source == "generated" else self.exam.text)
            with open(key, "w", encoding="utf-8", newline="") as f:
                f.write(answer_key_text(self.exam))
        except Exception as e:
            messagebox.showerror("Save failed", str(e), parent=self.root)
            return
        messagebox.showinfo("Saved", "Saved the exam for CW Player:\n%s\n\nAnswer key:\n%s" % (path, key), parent=self.root)

    # windows
    def toggle_full(self):
        if self.full_win is not None:
            w, self.full_win = self.full_win, None
            self.lamps = [l for l in self.lamps if l.c.winfo_toplevel() is not w]
            w.destroy()
            cur = self.cursor
            if cur and cur[0] in self.views:
                try:
                    self.nb.select(cur[0].sheet.id)
                    (cur[0].cells if cur[1] == "a" else cur[0].boxes)[cur[2]].focus_set()
                except Exception:
                    pass
            return
        w = tk.Toplevel(self.root)
        w.configure(bg=self.s["stage_bg"])
        w.title("Lamp")
        try:
            w.attributes("-fullscreen", True)
        except Exception:
            w.state("zoomed")
        c = tk.Canvas(w, bg=self.s["stage_bg"], highlightthickness=0)
        c.pack(fill="both", expand=True)
        lv = LampView(self, c, hint="Esc to close. Typing still goes into the answer sheet.")
        lv.on = self.lamp_main.on
        lv.note, lv.caption, lv.sub, lv.status = (self.lamp_main.note, self.lamp_main.caption,
                                                   self.lamp_main.sub, self.lamp_main.status)
        self.lamps.append(lv)
        w.bind("<Escape>", lambda e: self.toggle_full())
        w.bind("<F11>", lambda e: self.toggle_full())
        if IS_MAC:
            w.bind("<Command-Control-f>", lambda e: self.toggle_full())
        w.bind("<Key>", self._full_key)
        w.protocol("WM_DELETE_WINDOW", self.toggle_full)
        self.full_win = w
        w.focus_force()

    def _full_key(self, ev):
        """Keys typed in the full-screen window fill the answer sheet."""
        if not self.views or ev.keysym in ("Escape", "F11"):
            return None
        cur = self.cursor
        if not cur or cur[0] not in self.views:
            try:
                v = self.views[self.nb.index("current")]
            except Exception:
                v = self.views[0]
            cur = (v, "a", 0) if v.cells else (v, "b", 0)
            self.cursor = cur
        v, part, i = cur
        return (v._key_a if part == "a" else v._key_b)(ev, i)

    def open_settings(self):
        if self.state in ("running", "review", "testing"):
            return
        SettingsDialog(self)

    def settings_changed(self, content):
        self.redraw_lamps()
        if self.state == "idle" and content and not self.loaded_path:
            self.new_exam()
        elif self.state == "idle" and self.exam:
            tl = Timeline(self.exam.text.lstrip(), self.s["wpm"], self.s["space"], self.s["spacew"])
            self.set_status("About %s. Press Start." % fmt_time(tl.total + self.s["countdown"]))

    def about(self):
        u = dot_seconds(self.s["wpm"])
        messagebox.showinfo("About", (
            "Morse Light Trainer 1.2\n\n"
            "Lamp timing follows CW Player 4.7.5:\n"
            "  dot %.3f s, dash 3 dots, 1 dot inside a character\n"
            "  3 x SPACE dots after every character\n"
            "  (7 x SPACEW - 4) + 3 x SPACE dots for every space\n\n"
            "%d ICS General-section messages of 10 to 20 words.\n"
            "Using %d to %d words (%d messages).\n\n"
            "Settings file:\n%s") % (u, len(MESSAGES), min(self.s["min_words"], self.s["max_words"]),
                                      max(self.s["min_words"], self.s["max_words"]),
                                      len(messages_in_range(self.s)), SETTINGS_PATH), parent=self.root)

    def quit(self):
        self.run = None
        try:
            if IS_WIN:
                import ctypes
                ctypes.windll.winmm.timeEndPeriod(1)
        except Exception:
            pass
        self.root.destroy()


LAMP_CHECK_TEXT = "AA AA AA   T 0 H   AR"


def main():
    root = tk.Tk()
    app = App(root)
    try:
        if IS_WIN:
            root.state("zoomed")
        elif IS_MAC:
            sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
            root.geometry("%dx%d+20+30" % (min(sw - 40, 1440), min(sh - 90, 900)))
        else:
            root.attributes("-zoomed", True)
    except Exception:
        pass
    if "--lamptest" in sys.argv:
        root.after(800, app.lamp_check)
    root.mainloop()
    if "--lamptest" in sys.argv:
        sys.exit(0 if app.check_ok else 1)


if __name__ == "__main__":
    main()
