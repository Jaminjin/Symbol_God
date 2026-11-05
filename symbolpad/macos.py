"""macOS glue: typing into other apps, the global shortcut and window behaviour.

Everything degrades gracefully: without PyObjC (or off macOS) these become
no-ops and SymbolPad falls back to copying symbols to the clipboard.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import traceback

try:
    import AppKit
    import objc
    import Quartz
    AVAILABLE = sys.platform == "darwin"
except ImportError:          # not on a Mac, or PyObjC isn't installed
    AVAILABLE = False

_activity = None


# --------------------------------------------------------------------------- app & window
def make_accessory_app():
    """No Dock icon or app-switcher entry; SymbolPad lives in its palette and the menu bar."""
    if AVAILABLE:
        AppKit.NSApplication.sharedApplication().setActivationPolicy_(
            AppKit.NSApplicationActivationPolicyAccessory)


def keep_responsive():
    """Stop App Nap from slowing the palette down while another app is in front."""
    global _activity
    if AVAILABLE and _activity is None:
        _activity = AppKit.NSProcessInfo.processInfo().beginActivityWithOptions_reason_(
            AppKit.NSActivityUserInitiatedAllowingIdleSystemSleep, "Floating symbol palette")


def float_above_everything(widget):
    """Show the window on every Space, over full-screen apps, even when SymbolPad isn't active."""
    if not AVAILABLE:
        return
    try:
        window = objc.objc_object(c_void_p=int(widget.winId())).window()
        if window is None:
            return
        window.setCollectionBehavior_(AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
                                      | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary)
        window.setLevel_(AppKit.NSFloatingWindowLevel)
        window.setHidesOnDeactivate_(False)
    except Exception:
        traceback.print_exc()


def bring_self_to_front():
    if not AVAILABLE:
        return
    app = AppKit.NSApplication.sharedApplication()
    try:
        app.activateIgnoringOtherApps_(True)
    except Exception:
        app.activate()


# --------------------------------------------------------------------------- other apps
class FrontAppTracker:
    """Remembers the last app other than SymbolPad that was in front (where symbols go)."""

    def __init__(self):
        self.pid = os.getpid()
        self.last = None
        self._token = None
        if not AVAILABLE:
            return
        workspace = AppKit.NSWorkspace.sharedWorkspace()
        front = workspace.frontmostApplication()
        if front is not None and front.processIdentifier() != self.pid:
            self.last = front
        self._token = workspace.notificationCenter().addObserverForName_object_queue_usingBlock_(
            AppKit.NSWorkspaceDidActivateApplicationNotification, None, None, self._activated)

    def _activated(self, note):
        app = note.userInfo().objectForKey_(AppKit.NSWorkspaceApplicationKey)
        if app is not None and app.processIdentifier() != self.pid:
            self.last = app

    def target(self):
        app = self.last
        if app is None or app.isTerminated():
            return None
        return app


def frontmost_pid():
    if not AVAILABLE:
        return None
    app = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()
    return app.processIdentifier() if app is not None else None


def activate(app):
    """Bring another app to the front (macOS 14+ needs us to hand activation over)."""
    if not AVAILABLE or app is None:
        return False
    try:
        me = AppKit.NSApplication.sharedApplication()
        if hasattr(me, "yieldActivationToApplication_"):
            me.yieldActivationToApplication_(app)
        if hasattr(app, "activateFromApplication_options_"):
            if app.activateFromApplication_options_(AppKit.NSRunningApplication.currentApplication(), 0):
                return True
        return bool(app.activateWithOptions_(AppKit.NSApplicationActivateIgnoringOtherApps))
    except Exception:
        traceback.print_exc()
        return False


def hand_back_focus():
    """Last resort: hide for an instant so macOS re-activates the previous app."""
    if AVAILABLE:
        app = AppKit.NSApplication.sharedApplication()
        app.hide_(None)
        app.unhideWithoutActivation()


# --------------------------------------------------------------------------- typing
def can_type():
    """True once the user has allowed SymbolPad (or PyCharm/Terminal) to send keystrokes."""
    if not AVAILABLE:
        return False
    try:
        return bool(Quartz.CGPreflightPostEventAccess())
    except AttributeError:
        return True


def ask_for_typing_permission():
    """Show macOS's permission prompt and open the right Settings page."""
    if not AVAILABLE:
        return
    try:
        Quartz.CGRequestPostEventAccess()
    except AttributeError:
        pass
    open_accessibility_settings()


def open_accessibility_settings():
    subprocess.Popen(["open", "x-apple.systempreferences:com.apple.preference.security?Privacy_Accessibility"])


def _utf16_chunks(text, limit=20):
    """Split text into pieces of at most `limit` UTF-16 units, never inside a character."""
    chunk, size = "", 0
    for ch in text:
        n = 2 if ord(ch) > 0xFFFF else 1
        if size + n > limit:
            yield chunk
            chunk, size = "", 0
        chunk += ch
        size += n
    if chunk:
        yield chunk


def type_text(text):
    """Type any Unicode text into the front app, as if from the keyboard."""
    if not AVAILABLE:
        return
    source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
    for chunk in _utf16_chunks(text):
        units = len(chunk.encode("utf-16-le")) // 2
        for key_down in (True, False):
            event = Quartz.CGEventCreateKeyboardEvent(source, 0, key_down)
            Quartz.CGEventSetFlags(event, 0)
            Quartz.CGEventKeyboardSetUnicodeString(event, units, chunk)
            Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


def press_paste():
    """Press ⌘V in the front app."""
    if not AVAILABLE:
        return
    source = Quartz.CGEventSourceCreate(Quartz.kCGEventSourceStateHIDSystemState)
    for key_down in (True, False):
        event = Quartz.CGEventCreateKeyboardEvent(source, 9, key_down)   # 9 = V on ANSI keyboards
        Quartz.CGEventSetFlags(event, Quartz.kCGEventFlagMaskCommand)
        Quartz.CGEventPost(Quartz.kCGHIDEventTap, event)


# --------------------------------------------------------------------------- font coverage
class _CFRange(ctypes.Structure):
    _fields_ = [("location", ctypes.c_long), ("length", ctypes.c_long)]


def font_signature():
    """Changes when macOS, Python's Unicode data or the installed fonts change."""
    import platform
    import unicodedata
    count = 0
    for folder in ("/System/Library/Fonts", "/System/Library/Fonts/Supplemental", "/Library/Fonts",
                   os.path.expanduser("~/Library/Fonts")):
        try:
            count += len(os.listdir(folder))
        except OSError:
            pass
    return f"{platform.mac_ver()[0]}|{unicodedata.unidata_version}|{count}"


def missing_glyphs(chars):
    """Characters no installed font can draw (they'd show up as placeholder boxes).

    Safe to call from a background thread; takes ~1.5 s for all of Unicode.
    """
    if not AVAILABLE:
        return set()
    try:
        cf = ctypes.CDLL("/System/Library/Frameworks/CoreFoundation.framework/CoreFoundation")
        ct = ctypes.CDLL("/System/Library/Frameworks/CoreText.framework/CoreText")
    except OSError:
        return set()
    cf.CFStringCreateWithCharacters.restype = ctypes.c_void_p
    cf.CFStringCreateWithCharacters.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long]
    cf.CFRelease.argtypes = [ctypes.c_void_p]
    cf.CFStringGetCString.restype = ctypes.c_bool
    cf.CFStringGetCString.argtypes = [ctypes.c_void_p, ctypes.c_char_p, ctypes.c_long, ctypes.c_uint32]
    ct.CTFontCreateWithName.restype = ctypes.c_void_p
    ct.CTFontCreateWithName.argtypes = [ctypes.c_void_p, ctypes.c_double, ctypes.c_void_p]
    ct.CTFontCreateForString.restype = ctypes.c_void_p
    ct.CTFontCreateForString.argtypes = [ctypes.c_void_p, ctypes.c_void_p, _CFRange]
    ct.CTFontCopyPostScriptName.restype = ctypes.c_void_p
    ct.CTFontCopyPostScriptName.argtypes = [ctypes.c_void_p]

    def cf_string(text):
        raw = text.encode("utf-16-le")
        return cf.CFStringCreateWithCharacters(None, raw, len(raw) // 2)

    base_name = cf_string("Helvetica")
    base = ct.CTFontCreateWithName(base_name, 12.0, None)
    missing, buf = set(), ctypes.create_string_buffer(128)
    for ch in chars:
        s = cf_string(ch)
        font = ct.CTFontCreateForString(base, s, _CFRange(0, len(ch.encode("utf-16-le")) // 2))
        name = ct.CTFontCopyPostScriptName(font)
        if cf.CFStringGetCString(name, buf, 128, 0x08000100) and buf.value == b"LastResort":
            missing.add(ch)
        cf.CFRelease(name)
        cf.CFRelease(font)
        cf.CFRelease(s)
    cf.CFRelease(base)
    cf.CFRelease(base_name)
    return missing


# --------------------------------------------------------------------------- global shortcut
class _EventTypeSpec(ctypes.Structure):
    _fields_ = [("eventClass", ctypes.c_uint32), ("eventKind", ctypes.c_uint32)]


class _EventHotKeyID(ctypes.Structure):
    _fields_ = [("signature", ctypes.c_uint32), ("id", ctypes.c_uint32)]


_HANDLER = ctypes.CFUNCTYPE(ctypes.c_int32, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p)
_CMD, _SHIFT, _OPTION, _CONTROL = 1 << 8, 1 << 9, 1 << 11, 1 << 12

# id: (label, virtual key code, Carbon modifiers)
HOTKEYS = {
    "ctrl+alt+s": ("⌃⌥S", 1, _CONTROL | _OPTION),
    "ctrl+shift+s": ("⌃⇧S", 1, _CONTROL | _SHIFT),
    "alt+cmd+s": ("⌥⌘S", 1, _OPTION | _CMD),
    "ctrl+alt+cmd+s": ("⌃⌥⌘S", 1, _CONTROL | _OPTION | _CMD),
    "ctrl+shift+space": ("⌃⇧Space", 49, _CONTROL | _SHIFT),
}

_carbon_lib = None


def _fourcc(code):
    return int.from_bytes(code.encode("ascii"), "big")


def _carbon():
    global _carbon_lib
    if _carbon_lib is None and AVAILABLE:
        try:
            lib = ctypes.CDLL("/System/Library/Frameworks/Carbon.framework/Carbon")
        except OSError:
            return None
        lib.GetApplicationEventTarget.restype = ctypes.c_void_p
        lib.GetApplicationEventTarget.argtypes = []
        lib.InstallEventHandler.restype = ctypes.c_int32
        lib.InstallEventHandler.argtypes = [ctypes.c_void_p, _HANDLER, ctypes.c_ulong,
                                            ctypes.POINTER(_EventTypeSpec), ctypes.c_void_p,
                                            ctypes.POINTER(ctypes.c_void_p)]
        lib.RegisterEventHotKey.restype = ctypes.c_int32
        lib.RegisterEventHotKey.argtypes = [ctypes.c_uint32, ctypes.c_uint32, _EventHotKeyID, ctypes.c_void_p,
                                            ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p)]
        lib.UnregisterEventHotKey.restype = ctypes.c_int32
        lib.UnregisterEventHotKey.argtypes = [ctypes.c_void_p]
        _carbon_lib = lib
    return _carbon_lib


class GlobalHotkey:
    """A system-wide shortcut via Carbon's RegisterEventHotKey (needs no permissions)."""

    def __init__(self, callback):
        self._callback = callback
        self._hotkey_ref = ctypes.c_void_p()
        self._handler_ref = ctypes.c_void_p()
        self._handler = _HANDLER(self._fired)     # must stay alive while registered
        self.label = ""

    def set(self, hotkey_id):
        """Register one of HOTKEYS (or none).  Returns False if it couldn't be registered."""
        self.clear()
        spec = HOTKEYS.get(hotkey_id)
        carbon = _carbon()
        if spec is None or carbon is None:
            return False
        target = carbon.GetApplicationEventTarget()
        if not self._handler_ref:
            types = _EventTypeSpec(_fourcc("keyb"), 5)        # kEventClassKeyboard, kEventHotKeyPressed
            if carbon.InstallEventHandler(target, self._handler, 1, ctypes.byref(types), None,
                                          ctypes.byref(self._handler_ref)) != 0:
                self._handler_ref = ctypes.c_void_p()
                return False
        label, code, mods = spec
        err = carbon.RegisterEventHotKey(code, mods, _EventHotKeyID(_fourcc("SymP"), 1), target, 0,
                                         ctypes.byref(self._hotkey_ref))
        if err != 0:
            self._hotkey_ref = ctypes.c_void_p()
            return False
        self.label = label
        return True

    def clear(self):
        if self._hotkey_ref:
            _carbon().UnregisterEventHotKey(self._hotkey_ref)
            self._hotkey_ref = ctypes.c_void_p()
        self.label = ""

    def _fired(self, _call_ref, _event, _user_data):
        try:
            self._callback()
        except Exception:
            traceback.print_exc()
        return 0
