"""
Windows Input Automation Fallback
Robust keyboard/mouse input using ctypes when keyboard/pyautogui fail.
Handles WinError 2 and non-interactive session issues.
"""

import ctypes
from ctypes import wintypes
import time
import logging

logger = logging.getLogger("voice_assistant")

# ULONG_PTR is not available in all Python versions, define it manually
try:
    ULONG_PTR = wintypes.ULONG_PTR
except AttributeError:
    # Fallback for older Python versions
    if ctypes.sizeof(ctypes.c_void_p) == 4:
        ULONG_PTR = ctypes.c_uint32
    else:
        ULONG_PTR = ctypes.c_uint64

# Windows virtual key codes
VK_CODES = {
    # Media keys
    "media_play_pause": 0xB3,
    "media_stop": 0xB2,
    "media_next": 0xB0,
    "media_prev": 0xB1,
    # Volume keys
    "volume_mute": 0xAD,
    "volume_up": 0xAF,
    "volume_down": 0xAE,
    # Common keys
    "ctrl": 0x11,
    "alt": 0x12,
    "shift": 0x10,
    "tab": 0x09,
    "enter": 0x0D,
    "esc": 0x1B,
    "space": 0x20,
    "backspace": 0x08,
    "delete": 0x2E,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "left": 0x25,
    "up": 0x26,
    "right": 0x27,
    "down": 0x28,
    "f1": 0x70, "f2": 0x71, "f3": 0x72, "f4": 0x73,
    "f5": 0x74, "f6": 0x75, "f7": 0x76, "f8": 0x77,
    "f9": 0x78, "f10": 0x79, "f11": 0x7A, "f12": 0x7B,
    # Letters
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45,
    "f": 0x46, "g": 0x47, "h": 0x48, "i": 0x49, "j": 0x4A,
    "k": 0x4B, "l": 0x4C, "m": 0x4D, "n": 0x4E, "o": 0x4F,
    "p": 0x50, "q": 0x51, "r": 0x52, "s": 0x53, "t": 0x54,
    "u": 0x55, "v": 0x56, "w": 0x57, "x": 0x58, "y": 0x59,
    "z": 0x5A,
    # Numbers
    "0": 0x30, "1": 0x31, "2": 0x32, "3": 0x33, "4": 0x34,
    "5": 0x35, "6": 0x36, "7": 0x37, "8": 0x38, "9": 0x39,
    # Symbols
    "plus": 0xBB, "minus": 0xBD,
}

# Input structures
INPUT_KEYBOARD = 1
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", wintypes.WORD),
        ("wScan", wintypes.WORD),
        ("dwFlags", wintypes.DWORD),
        ("time", wintypes.DWORD),
        ("dwExtraInfo", ULONG_PTR),
    ]


class INPUT_I(ctypes.Union):
    _fields_ = [("ki", KEYBDINPUT)]


class INPUT(ctypes.Structure):
    _fields_ = [("type", wintypes.DWORD), ("ii", INPUT_I)]


def _send_input(inputs):
    """Send raw input events."""
    try:
        nInputs = len(inputs)
        LPINPUT = INPUT * nInputs
        pInputs = LPINPUT(*inputs)
        cbSize = ctypes.c_int(ctypes.sizeof(INPUT))
        ctypes.windll.user32.SendInput(nInputs, pInputs, cbSize)
        return True
    except Exception as e:
        logger.warning(f"SendInput failed: {e}")
        return False


def _key_event(vk, flags=0):
    """Build a single key event."""
    inp = INPUT()
    inp.type = INPUT_KEYBOARD
    inp.ii.ki.wVk = vk
    inp.ii.ki.wScan = 0
    inp.ii.ki.dwFlags = flags
    inp.ii.ki.time = 0
    inp.ii.ki.dwExtraInfo = 0
    return inp


def press_key(vk_name):
    """Press a key by name or VK code."""
    vk = VK_CODES.get(vk_name.lower())
    if vk is None:
        logger.warning(f"Unknown key: {vk_name}")
        return False
    return _send_input([_key_event(vk)])


def release_key(vk_name):
    """Release a key by name or VK code."""
    vk = VK_CODES.get(vk_name.lower())
    if vk is None:
        logger.warning(f"Unknown key: {vk_name}")
        return False
    return _send_input([_key_event(vk, KEYEVENTF_KEYUP)])


def press_and_release(vk_name):
    """Press and release a key."""
    vk = VK_CODES.get(vk_name.lower())
    if vk is None:
        logger.warning(f"Unknown key: {vk_name}")
        return False
    return _send_input([
        _key_event(vk),
        _key_event(vk, KEYEVENTF_KEYUP),
    ])


def hotkey(*keys):
    """Press a combination of keys (e.g., hotkey('ctrl', 's')."""
    vks = []
    for key in keys:
        vk = VK_CODES.get(key.lower())
        if vk is None:
            logger.warning(f"Unknown key in hotkey: {key}")
            return False
        vks.append(vk)

    # Press all down
    down_events = [_key_event(vk) for vk in vks]
    if not _send_input(down_events):
        return False

    time.sleep(0.05)

    # Release all up (reverse order)
    up_events = [_key_event(vk, KEYEVENTF_KEYUP) for vk in reversed(vks)]
    return _send_input(up_events)


def type_text(text, interval=0.01):
    """Type text character by character using SendInput."""
    result = True
    for char in text:
        vk = None
        lower = char.lower()
        if lower in VK_CODES:
            vk = VK_CODES[lower]
        elif char.isupper() and lower in VK_CODES:
            vk = VK_CODES[lower]
        elif char == " ":
            vk = VK_CODES["space"]
        elif char == "\n":
            vk = VK_CODES["enter"]
        elif char == "\t":
            vk = VK_CODES["tab"]
        else:
            logger.debug(f"Skipping unsupported char: {repr(char)}")
            continue

        if char.isupper() or char in '!@#$%^&*()_+{}|":<>?~':
            # Need shift
            _send_input([_key_event(VK_CODES["shift"])])
            _send_input([_key_event(vk)])
            _send_input([_key_event(vk, KEYEVENTF_KEYUP)])
            _send_input([_key_event(VK_CODES["shift"], KEYEVENTF_KEYUP)])
        else:
            _send_input([_key_event(vk)])
            _send_input([_key_event(vk, KEYEVENTF_KEYUP)])

        time.sleep(interval)
    return result


def media_play_pause():
    return press_and_release("media_play_pause")

def media_stop():
    return press_and_release("media_stop")

def media_next():
    return press_and_release("media_next")

def media_prev():
    return press_and_release("media_prev")

def volume_mute():
    return press_and_release("volume_mute")

def volume_up():
    return press_and_release("volume_up")

def volume_down():
    return press_and_release("volume_down")


def is_available():
    """Check if Windows input automation is available."""
    try:
        # Quick test
        press_and_release("volume_mute")
        return True
    except Exception as e:
        logger.warning(f"Windows input fallback not available: {e}")
        return False
