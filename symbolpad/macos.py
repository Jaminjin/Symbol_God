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
_dock_click = None
# Qt sometimes lifts the always-on-top palette to the "modal panel" level; this is one above that.
_OVER_PALETTE = 9


# --------------------------------------------------------------------------- app & window
def show_in_dock(on):
    """With a Dock icon SymbolPad is an ordinary app (also in ⌘-Tab); without, it lives in the menu bar."""
    if not AVAILABLE:
        return
    app = AppKit.NSApplication.sharedApplication()
    policy = AppKit.NSApplicationActivationPolicyRegular if on else AppKit.NSApplicationActivationPolicyAccessory
    if app.activationPolicy() != policy:
        app.setActivationPolicy_(policy)


def is_in_dock():
    return AVAILABLE and (AppKit.NSApplication.sharedApplication().activationPolicy()
                          == AppKit.NSApplicationActivationPolicyRegular)


def on_dock_click(callback):
    """Call `callback` when the Dock icon is clicked (or the app is opened again while running).

    Qt owns the application delegate; it passes anything it doesn't handle itself
    on to a "reflection delegate", which is where this listens.
    """
    global _dock_click
    if not AVAILABLE:
        return False
    try:
        if _dock_click is None:
            class SymbolPadDockClick(AppKit.NSObject):
                callback = None

                @objc.typedSelector(b"Z@:@Z")
                def applicationShouldHandleReopen_hasVisibleWindows_(self, _app, _has_visible_windows):
                    try:
                        if self.callback is not None:
                            self.callback()
                    except Exception:
                        traceback.print_exc()
                    return True

            _dock_click = SymbolPadDockClick.alloc().init()
        _dock_click.callback = callback
        delegate = AppKit.NSApplication.sharedApplication().delegate()
        if delegate is None or not delegate.respondsToSelector_(b"setReflectionDelegate:"):
            return False
        delegate.setReflectionDelegate_(_dock_click)
        return True
    except Exception:
        traceback.print_exc()
        return False


def keep_responsive():
    """Stop App Nap from slowing the palette down while another app is in front."""
    global _activity
    if AVAILABLE and _activity is None:
        _activity = AppKit.NSProcessInfo.processInfo().beginActivityWithOptions_reason_(
            AppKit.NSActivityUserInitiatedAllowingIdleSystemSleep, "Floating symbol palette")


def _ns_window(widget):
    """The NSWindow behind a Qt window, or None when Qt isn't drawing real Mac windows (tests)."""
    if not AVAILABLE:
        return None
    from PySide6.QtGui import QGuiApplication
    if QGuiApplication.platformName() != "cocoa":
        return None                    # winId() is only an NSView when Qt uses its Mac ("cocoa") backend
    return objc.objc_object(c_void_p=int(widget.winId())).window()


def float_above_everything(widget, over_palette=False):
    """Show the window on every Space, over full-screen apps, even when SymbolPad isn't active.

    over_palette  for SymbolPad's own little windows, which must never end up underneath the palette.
    """
    try:
        window = _ns_window(widget)
        if window is None:
            return
        window.setCollectionBehavior_(AppKit.NSWindowCollectionBehaviorCanJoinAllSpaces
                                      | AppKit.NSWindowCollectionBehaviorFullScreenAuxiliary)
        window.setLevel_(_OVER_PALETTE if over_palette else AppKit.NSFloatingWindowLevel)
        window.setHidesOnDeactivate_(False)
    except Exception:
        traceback.print_exc()


def raise_color_panel():
    """Keep macOS's colour picker in front of the palette it is colouring."""
    if not AVAILABLE:
        return
    try:
        panel = AppKit.NSColorPanel.sharedColorPanel()
        panel.setLevel_(_OVER_PALETTE)
        panel.orderFront_(None)
    except Exception:
        traceback.print_exc()


_glass_views = {}
_frame_layers = {}      # how each window's frame layer was before the glass rounded it


def _round_window(widget, frame, radius):
    """Clip everything in the window to a rounded shape (None puts it back as it was).

    A window with glass in it gets its shadow from the window's outline rather
    than from what's drawn, and that outline has tighter corners than the glass:
    without this, a thin line and a faint wedge show outside each corner as soon
    as anything (a colour, the RGB border) is drawn over the glass.
    """
    layer = frame.layer()
    if layer is None and radius is not None:
        frame.setWantsLayer_(True)          # a window that has only just appeared doesn't have its layer yet
        layer = frame.layer()
    if layer is None:
        return
    key = id(widget)
    if radius is None:
        if key in _frame_layers:
            was_radius, was_masking = _frame_layers.pop(key)
            layer.setCornerRadius_(was_radius)
            layer.setMasksToBounds_(was_masking)
        return
    _frame_layers.setdefault(key, (layer.cornerRadius(), layer.masksToBounds()))
    layer.setCornerRadius_(radius)
    layer.setMasksToBounds_(True)


def set_glass(widget, on, radius=20.0, clear=False, dark=True, inset=0.0):
    """Put Apple's Liquid Glass behind a window (the plain blur on macOS older than 26).

    The glass is a real system view underneath Qt's content, so it shows wherever
    SymbolPad paints see-through colours, and macOS does the blur, the bending of
    light at the edges and the bright rim itself.

    clear   Apple's "clear" glass, which you can see straight through, instead of
            the regular glass that blurs what's behind it.
    dark    the dark or the light variety of the material.
    inset   leave this many points free around the glass (the round bubble).

    Returns "glass", "blur" (older macOS) or "" (nothing shown).
    """
    try:
        window = _ns_window(widget)
        content = window.contentView() if window is not None else None
        if content is None or content.superview() is None:
            return ""
        frame = content.superview()
        view = _glass_views.get(id(widget))
        if view is not None and view.superview() is not frame:    # Qt made a new window for the widget
            view = None
            _frame_layers.pop(id(widget), None)
        if not on:
            if view is not None:
                view.setHidden_(True)
            _round_window(widget, frame, None)
            window.invalidateShadow()
            return ""
        glass_class = getattr(AppKit, "NSGlassEffectView", None)
        if view is None:
            if glass_class is not None:                       # macOS 26+: real Liquid Glass
                view = glass_class.alloc().initWithFrame_(content.frame())
            else:                                             # older macOS: frosted blur
                view = AppKit.NSVisualEffectView.alloc().initWithFrame_(content.frame())
                view.setBlendingMode_(AppKit.NSVisualEffectBlendingModeBehindWindow)
                view.setState_(AppKit.NSVisualEffectStateActive)
                view.setWantsLayer_(True)
                view.layer().setMasksToBounds_(True)
            view.setAutoresizingMask_(AppKit.NSViewWidthSizable | AppKit.NSViewHeightSizable)
            frame.addSubview_positioned_relativeTo_(view, AppKit.NSWindowBelow, content)
            _glass_views[id(widget)] = view
        is_glass = glass_class is not None and view.isKindOfClass_(glass_class)
        view.setAppearance_(AppKit.NSAppearance.appearanceNamed_(
            AppKit.NSAppearanceNameDarkAqua if dark else AppKit.NSAppearanceNameAqua))
        if is_glass:
            view.setStyle_(AppKit.NSGlassEffectViewStyleClear if clear else AppKit.NSGlassEffectViewStyleRegular)
            view.setCornerRadius_(radius)
        else:
            view.setMaterial_(AppKit.NSVisualEffectMaterialHUDWindow if dark
                              else AppKit.NSVisualEffectMaterialPopover)
            view.layer().setCornerRadius_(radius)
        view.setFrame_(AppKit.NSInsetRect(content.frame(), inset, inset))
        view.setHidden_(False)
        _round_window(widget, frame, radius + inset)
        window.setOpaque_(False)
        window.setBackgroundColor_(AppKit.NSColor.clearColor())
        window.invalidateShadow()
        return "glass" if is_glass else "blur"
    except Exception:
        traceback.print_exc()
        return ""


def refresh_shadow(widget):
    """Redraw the window's shadow after its shape changed."""
    try:
        window = _ns_window(widget)
        if window is not None:
            window.invalidateShadow()
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
_CMD, _SHIFT, _OPTION, _CONTROL = 1 << 8, 1 << 9, 1 << 11, 1 << 12           # Carbon's modifier bits
_NS_SHIFT, _NS_CONTROL, _NS_OPTION, _NS_COMMAND = 1 << 17, 1 << 18, 1 << 19, 1 << 20   # NSEvent's

# Keys that have a name rather than a character (Mac virtual key codes).
_KEY_NAMES = {
    36: "↩", 48: "⇥", 49: "Space", 51: "⌫", 53: "⎋", 76: "⌤", 117: "⌦",
    123: "←", 124: "→", 125: "↓", 126: "↑", 115: "↖", 119: "↘", 116: "⇞", 121: "⇟",
    122: "F1", 120: "F2", 99: "F3", 118: "F4", 96: "F5", 97: "F6", 98: "F7", 100: "F8", 101: "F9",
    109: "F10", 103: "F11", 111: "F12", 105: "F13", 107: "F14", 113: "F15", 106: "F16", 64: "F17",
    79: "F18", 80: "F19", 90: "F20",
}
_FUNCTION_KEYS = {code for code, name in _KEY_NAMES.items() if name.startswith("F")}
# What each key types on a US keyboard, for when macOS can't tell us.
_US_KEYS = {
    0: "A", 1: "S", 2: "D", 3: "F", 4: "H", 5: "G", 6: "Z", 7: "X", 8: "C", 9: "V", 11: "B", 12: "Q",
    13: "W", 14: "E", 15: "R", 16: "Y", 17: "T", 18: "1", 19: "2", 20: "3", 21: "4", 22: "6", 23: "5",
    24: "=", 25: "9", 26: "7", 27: "-", 28: "8", 29: "0", 30: "]", 31: "O", 32: "U", 33: "[", 34: "I",
    35: "P", 37: "L", 38: "J", 39: "'", 40: "K", 41: ";", 42: "\\", 43: ",", 44: "/", 45: "N", 46: "M",
    47: ".", 50: "`",
}
ESCAPE_KEY, DELETE_KEY = 53, 51


def shortcut_from_key(code, flags, char=""):
    """Describe a key press as a shortcut: {"code", "mods", "label"}.

    `flags` are NSEvent modifier flags and `char` is what the key types on its
    own.  Returns None for a key that can't be a system-wide shortcut by itself
    (anything without ⌘, ⌃ or ⌥, other than the F keys), since that would
    stop the key from typing in every other app.
    """
    mods, label = 0, ""
    for ns_bit, carbon_bit, symbol in ((_NS_CONTROL, _CONTROL, "⌃"), (_NS_OPTION, _OPTION, "⌥"),
                                       (_NS_SHIFT, _SHIFT, "⇧"), (_NS_COMMAND, _CMD, "⌘")):
        if flags & ns_bit:
            mods |= carbon_bit
            label += symbol
    if not mods & (_CMD | _OPTION | _CONTROL) and code not in _FUNCTION_KEYS:
        return None
    name = _KEY_NAMES.get(code)
    if name is None:
        char = (char or "").strip()
        name = char.upper() if len(char) == 1 and char.isprintable() else _US_KEYS.get(code, f"Key {code}")
    return {"code": int(code), "mods": mods, "label": label + name}


def valid_shortcut(spec):
    return (isinstance(spec, dict) and isinstance(spec.get("code"), int) and isinstance(spec.get("mods"), int)
            and 0 <= spec["code"] < 128)


def same_shortcut(a, b):
    return bool(a) and bool(b) and (a.get("code"), a.get("mods")) == (b.get("code"), b.get("mods"))


def shortcut_label(spec):
    return (spec.get("label") or f"Key {spec.get('code')}") if spec else ""


class KeyCapture:
    """While started, hands every key pressed inside SymbolPad to `callback(code, flags, char)`.

    Used to record a shortcut.  The key presses are swallowed, so pressing ⌘Q
    or ⌘W as the new shortcut doesn't quit SymbolPad or close its window.
    """

    def __init__(self, callback):
        self._callback = callback
        self._monitor = None

    @property
    def active(self):
        return self._monitor is not None

    def start(self):
        if not AVAILABLE:
            return False
        if self._monitor is None:
            self._monitor = AppKit.NSEvent.addLocalMonitorForEventsMatchingMask_handler_(
                AppKit.NSEventMaskKeyDown, self._pressed)
        return self._monitor is not None

    def stop(self):
        if self._monitor is not None:
            AppKit.NSEvent.removeMonitor_(self._monitor)
            self._monitor = None

    def _pressed(self, event):
        try:
            if not event.isARepeat():
                try:
                    char = event.charactersByApplyingModifiers_(0) or ""     # what the key types by itself
                except Exception:
                    char = event.charactersIgnoringModifiers() or ""
                self._callback(int(event.keyCode()), int(event.modifierFlags()), str(char))
        except Exception:
            traceback.print_exc()
        return None                                # swallow the key press


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
        lib.GetEventParameter.restype = ctypes.c_int32
        lib.GetEventParameter.argtypes = [ctypes.c_void_p, ctypes.c_uint32, ctypes.c_uint32, ctypes.c_void_p,
                                          ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p]
        _carbon_lib = lib
    return _carbon_lib


class GlobalHotkeys:
    """System-wide shortcuts via Carbon's RegisterEventHotKey (needs no permissions).

    Each shortcut has a name ("open", "close"); `set` replaces whatever that
    name was bound to before.
    """

    def __init__(self):
        self._handler = _HANDLER(self._fired)     # must stay alive while installed
        self._handler_ref = ctypes.c_void_p()
        self._numbers = {}                        # name -> the number Carbon reports back
        self._refs = {}                           # name -> Carbon's registration
        self._callbacks = {}                      # number -> function
        self._specs = {}                          # name -> the shortcut registered now

    def spec(self, name):
        return self._specs.get(name)

    def set(self, name, spec, callback):
        """Bind `name` to a shortcut (None removes it).  False means macOS refused the shortcut."""
        self.clear(name)
        if not spec:
            return True
        carbon = _carbon()
        if carbon is None or not valid_shortcut(spec):
            return False
        target = carbon.GetApplicationEventTarget()
        if not self._handler_ref:
            types = _EventTypeSpec(_fourcc("keyb"), 5)        # kEventClassKeyboard, kEventHotKeyPressed
            if carbon.InstallEventHandler(target, self._handler, 1, ctypes.byref(types), None,
                                          ctypes.byref(self._handler_ref)) != 0:
                self._handler_ref = ctypes.c_void_p()
                return False
        number = self._numbers.setdefault(name, len(self._numbers) + 1)
        ref = ctypes.c_void_p()
        err = carbon.RegisterEventHotKey(spec["code"], spec["mods"], _EventHotKeyID(_fourcc("SymP"), number),
                                         target, 0, ctypes.byref(ref))
        if err != 0 or not ref:
            return False
        self._refs[name], self._callbacks[number], self._specs[name] = ref, callback, dict(spec)
        return True

    def clear(self, name=None):
        """Remove one shortcut, or all of them."""
        for key in ([name] if name is not None else list(self._refs)):
            ref = self._refs.pop(key, None)
            if ref:
                _carbon().UnregisterEventHotKey(ref)
            self._specs.pop(key, None)
            self._callbacks.pop(self._numbers.get(key), None)

    def _fired(self, _call_ref, event, _user_data):
        try:
            pressed = _EventHotKeyID()
            # kEventParamDirectObject ('----') as a typeEventHotKeyID ('hkid')
            err = _carbon().GetEventParameter(event, _fourcc("----"), _fourcc("hkid"), None,
                                              ctypes.sizeof(pressed), None, ctypes.byref(pressed))
            callback = self._callbacks.get(pressed.id) if err == 0 else None
            if callback is not None:
                callback()
        except Exception:
            traceback.print_exc()
        return 0
