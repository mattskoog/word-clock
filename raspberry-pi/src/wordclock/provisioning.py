"""Showing network setup on the face, for a clock someone else is setting up.

When the clock has never joined a network it broadcasts its own, and whoever
is unboxing it has no way to tell that from a clock that is simply broken.
Worse, with no network there has been no NTP, so the time it would otherwise
display is wrong. Drawing the setup state instead is both more useful and more
honest than showing a confident, incorrect time.

The state comes from comitup, which runs `external_callback` on every change
with one of HOTSPOT, CONNECTING or CONNECTED. That callback cannot draw
anything itself - the clock service already owns the LED strip, and two
processes writing to it would fight - so it writes a word to a file and this
module turns that into a frame.

A missing file means no provisioning is installed, which is the normal case for
a clock already on a network. Everything here is then inert.
"""

import math
import os
import time

from clock_display_hal import ClockDisplayHAL

# On a tmpfs, so a reboot clears it and comitup writes it afresh. Nothing here
# needs to survive a restart; a stale state would be worse than none.
DEFAULT_STATE_PATH = "/run/wordclock/network-state"

HOTSPOT = "HOTSPOT"
CONNECTING = "CONNECTING"
CONNECTED = "CONNECTED"
STATES = (HOTSPOT, CONNECTING, CONNECTED)

# How long the green confirmation holds before the clock goes back to the time.
CONFIRM_SECONDS = 2.5

# The face has to be visible across a room to someone who does not yet know it
# is a clock, so the setup patterns ignore a saved brightness below this. A
# clock handed over at 2% would otherwise appear dead.
MINIMUM_BRIGHTNESS = 0.3

HOTSPOT_COLOR = (255, 150, 20)
CONNECTING_COLOR = (40, 120, 255)
CONNECTED_COLOR = (0, 255, 90)

CENTRE_X = (ClockDisplayHAL.WIDTH - 1) / 2.0
CENTRE_Y = (ClockDisplayHAL.HEIGHT - 1) / 2.0


def read_state(path):
    """The last state comitup reported, or '' if there is nothing to read."""
    try:
        with open(path) as handle:
            word = handle.read().strip().upper()
    except (OSError, ValueError):
        return ""
    return word if word in STATES else ""


def _blank():
    return [(0, 0, 0)] * ClockDisplayHAL.NUM_LEDS


def _paint(grid_value, color, brightness):
    """Build a frame from a function of (x, y) returning 0..1."""
    frame = _blank()
    level = max(MINIMUM_BRIGHTNESS, brightness)
    for y in range(ClockDisplayHAL.HEIGHT):
        for x in range(ClockDisplayHAL.WIDTH):
            value = max(0.0, min(1.0, grid_value(x, y))) * level
            if value <= 0:
                continue
            index = ClockDisplayHAL.cartesian_to_word_clock_led_strip_index(x, y)
            frame[index] = tuple(int(channel * value) for channel in color)
    return frame


def hotspot_frame(elapsed, brightness=1.0):
    """Rings travelling outward: the clock is broadcasting, come and find it."""
    def value(x, y):
        distance = math.hypot(x - CENTRE_X, y - CENTRE_Y)
        # Cubed so the rings are thin bands with dark between them, rather
        # than the whole face breathing as one.
        return max(0.0, math.sin(2 * math.pi * (distance / 5.0 - elapsed * 0.5))) ** 3
    return _paint(value, HOTSPOT_COLOR, brightness)


def connecting_frame(elapsed, brightness=1.0):
    """A bar sweeping across: working on it. Deliberately a different motion
    to the rings, so the two states are not told apart by colour alone."""
    position = (elapsed * 6.0) % ClockDisplayHAL.WIDTH

    def value(x, y):
        gap = abs(x - position)
        gap = min(gap, ClockDisplayHAL.WIDTH - gap)  # wraps at the edge
        return max(0.0, 1.0 - gap / 2.5)
    return _paint(value, CONNECTING_COLOR, brightness)


def connected_frame(elapsed, brightness=1.0):
    """The whole face green, fading out. Returns None once it is spent."""
    if elapsed >= CONFIRM_SECONDS:
        return None
    remaining = 1.0 - (elapsed / CONFIRM_SECONDS)
    return _paint(lambda x, y: remaining, CONNECTED_COLOR, brightness)


class NetworkDisplay:
    """Turns the state file into frames, and knows when to stop.

    Polled by the render loop on every tick. Returns None whenever the clock
    should get on with showing the time, which is the overwhelmingly common
    case and costs one failed open.
    """

    def __init__(self, path=DEFAULT_STATE_PATH, poll_seconds=1.0):
        self.path = path
        self._poll_seconds = poll_seconds
        self._state = ""
        self._since = 0.0
        self._checked_at = None

    def _refresh(self, now):
        # The file changes a handful of times in a clock's life, so it is read
        # at a gentle cadence rather than on every tick of the render loop.
        if self._checked_at is not None and now - self._checked_at < self._poll_seconds:
            return
        self._checked_at = now
        state = read_state(self.path) if self.path else ""
        if state != self._state:
            self._state = state
            self._since = now

    def frame(self, brightness=1.0, now=None):
        """The frame to show instead of the time, or None to show the time."""
        now = time.monotonic() if now is None else now
        self._refresh(now)
        elapsed = now - self._since
        if self._state == HOTSPOT:
            return hotspot_frame(elapsed, brightness)
        if self._state == CONNECTING:
            return connecting_frame(elapsed, brightness)
        if self._state == CONNECTED:
            # Shows briefly, then gets out of the way for good.
            return connected_frame(elapsed, brightness)
        return None

    @property
    def state(self):
        return self._state


def install_hint(path=DEFAULT_STATE_PATH):
    """Whether provisioning looks set up, for the startup banner."""
    return "watching" if os.path.isdir(os.path.dirname(path)) else "not installed"
