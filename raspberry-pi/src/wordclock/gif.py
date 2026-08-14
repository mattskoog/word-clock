"""Animation playback.

Any image dropped into the GIF directory becomes an animation the clock can
play. Frames are scaled down to the 12x11 LED grid and shown for the delay the
file itself asks for, so animations run at the speed they were authored at.
"""

import os
import random
import time

from PIL import Image

from clock_display_hal import ClockDisplayHAL

SUPPORTED_EXTENSIONS = (".gif", ".png", ".jpg", ".jpeg", ".bmp", ".webp")
MINIMUM_FRAME_DELAY = 0.02
DEFAULT_FRAME_DELAY = 0.1
MAX_FRAMES = 120  # bounds memory and the size of a preview response


class GifLibrary:
    """The set of animations available on disk, rescanned on every read."""

    def __init__(self, directory):
        self.directory = directory

    def names(self):
        if not self.directory or not os.path.isdir(self.directory):
            return []
        found = [
            entry
            for entry in os.listdir(self.directory)
            if entry.lower().endswith(SUPPORTED_EXTENSIONS)
            # A leading underscore keeps a file in the folder but out of the
            # pickers, so one can be shelved and brought back with a rename.
            and not entry.startswith("_")
            and os.path.isfile(os.path.join(self.directory, entry))
        ]
        return sorted(found)

    def path_for(self, name):
        """Resolve a name to a path, or None if it is not in the library."""
        if not name or name not in self.names():
            return None
        return os.path.join(self.directory, name)

    def choose(self, mode="random", fixed_name="", hour_gifs=None, hour=None):
        """Pick the next animation to play according to the selection mode."""
        available = self.names()
        if not available:
            return None
        if mode == "hourly":
            # An hour with nothing assigned falls back to a random animation
            # rather than showing nothing at all.
            chosen = (hour_gifs or {}).get(str(hour or ""), "")
            path = self.path_for(chosen)
            if path:
                return path
        elif mode == "fixed":
            return self.path_for(fixed_name) or self.path_for(available[0])
        return self.path_for(random.choice(available))


def _frame_delay(image):
    milliseconds = image.info.get("duration", 0)
    try:
        seconds = float(milliseconds) / 1000.0
    except (TypeError, ValueError):
        seconds = 0.0
    if seconds <= 0:
        seconds = DEFAULT_FRAME_DELAY
    return max(MINIMUM_FRAME_DELAY, seconds)


def _resampling_filter(size):
    # Pixel art authored at (or near) the grid size stays crisp with nearest
    # neighbour; larger sources need averaging or they turn into noise.
    if max(size) <= ClockDisplayHAL.WIDTH * 2:
        return Image.NEAREST
    return Image.LANCZOS


def _grid_from(image, background_color):
    """One frame scaled to the LED grid, as rows of (r, g, b) from the top."""
    target = (ClockDisplayHAL.WIDTH, ClockDisplayHAL.HEIGHT)
    frame = image.convert("RGBA")
    if frame.size != target:
        frame = frame.resize(target, _resampling_filter(frame.size))
    pixels = frame.load()
    rows = []
    for y in range(target[1]):
        row = []
        for x in range(target[0]):
            red, green, blue, alpha = pixels[x, y]
            row.append((red, green, blue) if alpha > 0 else background_color)
        rows.append(row)
    return rows


def load_frames(gif_path, max_frames=MAX_FRAMES, background_color=(0, 0, 0)):
    """[(grid, delay_seconds)] for an animation, decoded once.

    The LED playback and the web preview both read animations through here, so
    what the browser shows is scaled exactly the way the clock scales it.
    """
    frames = []
    try:
        image = Image.open(gif_path)
    except (OSError, ValueError) as error:
        print(f"Could not open animation {gif_path}: {error}")
        return frames

    with image:
        while len(frames) < max_frames:
            try:
                frames.append((_grid_from(image, background_color), _frame_delay(image)))
            except (OSError, ValueError) as error:
                print(f"Could not render {gif_path}: {error}")
                break
            try:
                image.seek(image.tell() + 1)
            except EOFError:
                break  # reached the end of the animation
            except (OSError, ValueError):
                break  # not an animation, the single frame is enough
    return frames


def _show(grid, clock_display_hal, scale=1.0):
    for y, row in enumerate(grid):
        for x, color in enumerate(row):
            if scale != 1.0:
                color = tuple(int(channel * scale) for channel in color)
            clock_display_hal.set_pixel(x, y, color)
    clock_display_hal.show()


def play(gif_path, clock_display_hal, duration=6.0, background_color=(0, 0, 0),
         should_stop=None, scale=1.0):
    """Play an animation for `duration` seconds, looping if it is shorter.

    Returns True if it played, False if the file could not be opened.
    """
    frames = load_frames(gif_path, background_color=background_color)
    if not frames:
        return False

    # Decoded once up front, so looping costs nothing on a slow Pi.
    deadline = time.monotonic() + duration
    index = 0
    while time.monotonic() < deadline:
        if should_stop is not None and should_stop():
            break
        grid, delay = frames[index % len(frames)]
        _show(grid, clock_display_hal, scale)
        time.sleep(min(delay, max(0.0, deadline - time.monotonic())))
        index += 1
    return True


# Kept for backwards compatibility with the original single-GIF entry point.
def display_gif(gif_path, clock_display_hal, display_gif_duration=4, background_color=(0, 0, 0)):
    return play(gif_path, clock_display_hal, display_gif_duration, background_color)
