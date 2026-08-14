"""Generate the background animations.

These are a different job to the ones in gifs/. A background plays continuously
behind the time, so it wants even coverage across the whole face, slow movement
and no recognisable subject competing with the words. Every loop is seamless,
because there is no start or end to hide.

    python3 tools/make_backgrounds.py
"""

import math
import os
import random

from PIL import Image

WIDTH = 12
HEIGHT = 11
OUTPUT_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backgrounds")

# Frame rate per animation, chosen with the movement rather than shared.
FRAME_MS = {"aurora": 160, "embers": 150, "ripple": 140,
            "drift": 160, "nebula": 170}

# Written with a leading underscore, which keeps them in the folder but out of
# the picker. Nothing is shelved at the moment; add a name to retire one.
SHELVED = set()


def blank():
    return [[(0, 0, 0)] * WIDTH for _ in range(HEIGHT)]


def put(grid, x, y, color):
    x, y = int(round(x)), int(round(y))
    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
        grid[y][x] = color


def mix(first, second, amount):
    amount = max(0.0, min(1.0, amount))
    return tuple(int(a + (b - a) * amount) for a, b in zip(first, second))


def scale(color, amount):
    return tuple(int(channel * max(0.0, min(1.0, amount))) for channel in color)


# --- the animations --------------------------------------------------------

def aurora():
    """Slow bands of green and violet leaning across the face."""
    low = (0, 90, 70)
    high = (90, 40, 140)
    steps = 36
    frames = []
    for step in range(steps):
        phase = step / float(steps)
        grid = blank()
        for y in range(HEIGHT):
            for x in range(WIDTH):
                # Two waves at different angles, so the bands bend rather than
                # marching straight down.
                wave = math.sin(2 * math.pi * (y / 6.0 - phase + x / 22.0))
                wave += 0.6 * math.sin(2 * math.pi * (y / 3.5 + phase * 2 - x / 14.0))
                level = (wave + 1.6) / 3.2
                grid[y][x] = scale(mix(low, high, level), 0.35 + 0.65 * level)
        frames.append(grid)
    return frames


def embers():
    """Warm sparks drifting upward over a faint glow at the base."""
    random.seed(5)
    steps = 44
    speeds = (0.25, 0.5)
    sparks = [(random.uniform(0, WIDTH), random.uniform(0, HEIGHT), random.choice(speeds),
               random.uniform(0, 2 * math.pi))
              for _ in range(16)]
    frames = []
    for step in range(steps):
        grid = blank()
        # The glow sits at the bottom and fades upward.
        for y in range(HEIGHT):
            warmth = max(0.0, (y - (HEIGHT - 5)) / 5.0)
            if warmth > 0:
                for x in range(WIDTH):
                    grid[y][x] = scale((120, 30, 0), warmth * 0.35)
        for x, start, speed, sway in sparks:
            # Rising, so the position counts down rather than up.
            y = (start - step * speed) % HEIGHT
            drift = math.sin(2 * math.pi * step / steps + sway) * 0.8
            heat = 0.35 + 0.65 * (y / float(HEIGHT))  # cooler as it climbs
            put(grid, x + drift, y, mix((255, 90, 0), (255, 210, 120), 1.0 - heat))
        frames.append(grid)
    return frames


def ripple():
    """Rain on water: rings from several points, overlapping as they spread.

    A single source would sit as a bullseye in the middle of the face, which is
    a shape the eye locks onto. Three off-centre sources interfere instead, so
    the pattern covers the grid without an obvious centre.
    """
    sources = (((2.5, 2.0), 0.0), ((9.0, 7.5), 0.37), ((5.5, 9.5), 0.71))
    near = (0, 70, 120)
    far = (40, 160, 190)
    steps = 36
    frames = []
    for step in range(steps):
        phase = step / float(steps)
        grid = blank()
        for y in range(HEIGHT):
            for x in range(WIDTH):
                total = 0.0
                for (source_x, source_y), offset in sources:
                    distance = math.hypot(x - source_x, y - source_y)
                    total += math.sin(2 * math.pi * (distance / 4.5 - phase - offset))
                level = (total + len(sources)) / (2.0 * len(sources))
                grid[y][x] = scale(mix(near, far, level), 0.28 + 0.72 * level)
        frames.append(grid)
    return frames


def nebula():
    """A slow-turning cloud of magenta and indigo.

    Rotates rather than travelling, which gives it a different feel to the
    others without being any busier.
    """
    centre_x, centre_y = (WIDTH - 1) / 2.0, (HEIGHT - 1) / 2.0
    core = (150, 30, 120)
    edge = (25, 20, 85)
    steps = 36
    frames = []
    for step in range(steps):
        # A whole turn over the loop, so it closes where it started.
        angle = 2 * math.pi * step / steps
        cosine, sine = math.cos(angle), math.sin(angle)
        grid = blank()
        for y in range(HEIGHT):
            for x in range(WIDTH):
                offset_x, offset_y = x - centre_x, y - centre_y
                turned_x = offset_x * cosine - offset_y * sine
                turned_y = offset_x * sine + offset_y * cosine
                value = math.sin(turned_x / 3.0)
                value += math.sin(turned_y / 4.5)
                value += math.sin((turned_x + turned_y) / 5.5)
                level = (value + 3.0) / 6.0
                grid[y][x] = scale(mix(edge, core, level), 0.28 + 0.72 * level)
        frames.append(grid)
    return frames


def drift():
    """A soft field of colour turning slowly through blues and teals."""
    steps = 36
    frames = []
    for step in range(steps):
        phase = step / float(steps)
        grid = blank()
        for y in range(HEIGHT):
            for x in range(WIDTH):
                # Summed sines at unrelated frequencies: no visible repeat, but
                # every term is periodic so the loop still closes.
                value = math.sin(2 * math.pi * (x / 9.0 + phase))
                value += math.sin(2 * math.pi * (y / 7.0 - phase))
                value += math.sin(2 * math.pi * ((x + y) / 11.0 + phase * 2))
                level = (value + 3.0) / 6.0
                hue = mix((20, 60, 150), (0, 150, 130), level)
                grid[y][x] = scale(hue, 0.3 + 0.7 * level)
        frames.append(grid)
    return frames


BACKGROUNDS = {
    "aurora": aurora,
    "embers": embers,
    "ripple": ripple,
    "drift": drift,
    "nebula": nebula,
}


def save(name, frames, directory):
    images = []
    for grid in frames:
        image = Image.new("RGB", (WIDTH, HEIGHT))
        image.putdata([pixel for row in grid for pixel in row])
        images.append(image.convert("P", palette=Image.ADAPTIVE, colors=255))
    prefix = "_" if name in SHELVED else ""
    path = os.path.join(directory, f"{prefix}{name}.gif")
    images[0].save(path, save_all=True, append_images=images[1:],
                   duration=FRAME_MS.get(name, 140), loop=0, optimize=False)
    return path


def main():
    directory = os.path.abspath(OUTPUT_DIRECTORY)
    os.makedirs(directory, exist_ok=True)
    for name, builder in sorted(BACKGROUNDS.items()):
        path = save(name, builder(), directory)
        print(f"wrote {os.path.basename(path)} ({os.path.getsize(path)} bytes)")


if __name__ == "__main__":
    main()
