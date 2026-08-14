"""Generate the weather animations.

These are backgrounds, so they follow the same rules as the ones in
backgrounds/: even coverage, slow movement, a seamless loop, and quiet enough
to read the time over. What is different is that they are not chosen by hand -
the clock picks one from the current conditions - so each has to be recognisable
as its own weather at a glance, on a 12x11 grid, behind lit words.

    python3 tools/make_weather.py
"""

import math
import os
import random

from PIL import Image

WIDTH = 12
HEIGHT = 11
OUTPUT_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "weather")

# Paced to the weather rather than shared: fog barely moves, rain falls.
FRAME_MS = {"clear": 200, "clear_night": 180, "cloud": 190, "rain": 110,
            "snow": 200, "fog": 220, "storm": 130}


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
    return tuple(min(255, int(channel * max(0.0, amount))) for channel in color)


# --- the animations --------------------------------------------------------

def clear():
    """A warm sky that breathes rather than moves anywhere."""
    low = (120, 70, 0)
    high = (255, 190, 60)
    steps = 30
    frames = []
    for step in range(steps):
        phase = step / float(steps)
        grid = blank()
        for y in range(HEIGHT):
            for x in range(WIDTH):
                # A slow swell across the diagonal, so the warmth pools and
                # drifts instead of pulsing the whole face at once.
                value = math.sin(2 * math.pi * (phase + (x + y) / 26.0))
                value += 0.5 * math.sin(2 * math.pi * (phase * 2 - y / 9.0))
                level = (value + 1.5) / 3.0
                grid[y][x] = scale(mix(low, high, level), 0.45 + 0.55 * level)
        frames.append(grid)
    return frames


def clear_night():
    """A dim field with a scatter of stars, each keeping its own time."""
    random.seed(31)
    steps = 36
    sky = (4, 6, 26)
    star_color = (200, 215, 255)
    # Periods that divide the loop, so every star is back where it started.
    stars = [(random.randrange(WIDTH), random.randrange(HEIGHT),
              random.choice((6, 9, 12, 18)), random.random())
             for _ in range(14)]
    frames = []
    for step in range(steps):
        grid = [[sky] * WIDTH for _ in range(HEIGHT)]
        for x, y, period, offset in stars:
            phase = (step / float(period) + offset) % 1.0
            # Mostly dim with a brief rise, which reads as a twinkle rather
            # than as a row of pulsing dots.
            level = max(0.0, math.sin(2 * math.pi * phase)) ** 3
            put(grid, x, y, mix(sky, star_color, 0.25 + 0.75 * level))
        frames.append(grid)
    return frames


def cloud():
    """Grey mass drifting sideways, thinning and thickening as it goes."""
    thin = (18, 22, 30)
    thick = (120, 130, 145)
    steps = 36
    frames = []
    for step in range(steps):
        phase = step / float(steps)
        grid = blank()
        for y in range(HEIGHT):
            for x in range(WIDTH):
                # Two banks at different speeds, so the cover overlaps itself
                # rather than sliding past as one sheet.
                value = math.sin(2 * math.pi * (x / 11.0 - phase + y / 17.0))
                value += 0.7 * math.sin(2 * math.pi * (x / 6.0 - phase * 2 - y / 9.0))
                level = (value + 1.7) / 3.4
                grid[y][x] = mix(thin, thick, level)
        frames.append(grid)
    return frames


def rain():
    """Falling streaks over a dim sky. Quieter than the hourly rain, which
    has the whole face to itself and can afford to be brighter."""
    random.seed(7)
    steps = 22
    speeds = (0.5, 1.0)  # steps * speed is a whole number of rows
    sky = (6, 10, 20)
    head = (110, 165, 235)
    trail = (30, 60, 120)
    drops = [(column, random.uniform(0, HEIGHT), random.choice(speeds))
             for column in range(WIDTH)]
    drops += [(column, random.uniform(0, HEIGHT), random.choice(speeds))
              for column in random.sample(range(WIDTH), 5)]
    frames = []
    for step in range(steps):
        grid = [[sky] * WIDTH for _ in range(HEIGHT)]
        for column, start, speed in drops:
            position = (start + step * speed) % HEIGHT
            put(grid, column, position - 1, trail)
            put(grid, column, position, head)
        frames.append(grid)
    return frames


def snow():
    """Flakes drifting down, sideways as much as they fall."""
    random.seed(13)
    # 44 steps, not 40: a flake only lands back where it started if it travels
    # a whole multiple of the 11 rows, so steps * speed has to divide by 11.
    steps = 44
    sky = (10, 14, 24)
    flake = (215, 230, 255)
    flakes = [(random.uniform(0, WIDTH), random.uniform(0, HEIGHT),
               random.choice((0.25, 0.5)), random.uniform(0, 2 * math.pi))
              for _ in range(15)]
    frames = []
    for step in range(steps):
        grid = [[sky] * WIDTH for _ in range(HEIGHT)]
        for x, start, speed, sway in flakes:
            y = (start + step * speed) % HEIGHT
            # A full sway cycle over the loop, so the drift closes too.
            drift = math.sin(2 * math.pi * step / steps + sway) * 1.2
            # The far ones are dimmer, which gives the fall some depth.
            weight = 0.55 + 0.45 * (speed / 0.5)
            put(grid, x + drift, y, mix(sky, flake, weight))
        frames.append(grid)
    return frames


def fog():
    """Barely anything: a flat haze that shifts too slowly to watch."""
    near = (26, 30, 32)
    far = (96, 104, 108)
    steps = 40
    frames = []
    for step in range(steps):
        phase = step / float(steps)
        grid = blank()
        for y in range(HEIGHT):
            for x in range(WIDTH):
                # Long wavelengths and a narrow range: the point is that it
                # has no features, unlike cloud, which has banks.
                value = math.sin(2 * math.pi * (phase + y / 23.0))
                value += 0.4 * math.sin(2 * math.pi * (phase - x / 31.0))
                level = (value + 1.4) / 2.8
                grid[y][x] = mix(near, far, 0.35 + 0.4 * level)
        frames.append(grid)
    return frames


def storm():
    """A dark, heavy sky that lights up now and then.

    The flash is the whole point, so it has to survive the clock's brightness
    scaling: backgrounds are normalised against the animation's brightest
    pixel across every frame, which is the flash itself. That leaves the
    ordinary frames sitting low, which is what a storm should look like.
    """
    random.seed(23)
    steps = 44  # same rule as snow: 44 * 0.5 and 44 * 1.0 are both 11s
    sky = (8, 10, 18)
    cloud_color = (46, 50, 68)
    flash_color = (255, 250, 225)
    speeds = (0.5, 1.0)
    drops = [(column, random.uniform(0, HEIGHT), random.choice(speeds))
             for column in random.sample(range(WIDTH), 8)]
    # Two strikes per loop, each a bright frame and a dimmer afterglow.
    strikes = {11: 1.0, 12: 0.35, 34: 1.0, 35: 0.45, 36: 0.15}

    frames = []
    for step in range(steps):
        phase = step / float(steps)
        grid = blank()
        for y in range(HEIGHT):
            for x in range(WIDTH):
                value = math.sin(2 * math.pi * (x / 9.0 - phase + y / 13.0))
                level = (value + 1.0) / 2.0
                # Heavier along the top, the way a storm cloud sits.
                weight = level * (1.0 - y / float(HEIGHT) * 0.5)
                grid[y][x] = mix(sky, cloud_color, weight)
        for column, start, speed in drops:
            position = (start + step * speed) % HEIGHT
            put(grid, column, position, (70, 90, 150))
        flash = strikes.get(step)
        if flash:
            for y in range(HEIGHT):
                for x in range(WIDTH):
                    # Brightest at the top, falling away down the face, so it
                    # reads as light coming from up in the cloud.
                    reach = flash * (1.0 - y / float(HEIGHT) * 0.7)
                    grid[y][x] = mix(grid[y][x], flash_color, reach)
        frames.append(grid)
    return frames


ANIMATIONS = {
    "clear": clear,
    "clear_night": clear_night,
    "cloud": cloud,
    "rain": rain,
    "snow": snow,
    "fog": fog,
    "storm": storm,
}


def save(name, frames, directory):
    images = []
    for grid in frames:
        image = Image.new("RGB", (WIDTH, HEIGHT))
        image.putdata([pixel for row in grid for pixel in row])
        images.append(image.convert("P", palette=Image.ADAPTIVE, colors=255))
    path = os.path.join(directory, f"{name}.gif")
    images[0].save(path, save_all=True, append_images=images[1:],
                   duration=FRAME_MS.get(name, 160), loop=0, optimize=False)
    return path


def main():
    directory = os.path.abspath(OUTPUT_DIRECTORY)
    os.makedirs(directory, exist_ok=True)
    for name, builder in sorted(ANIMATIONS.items()):
        path = save(name, builder(), directory)
        print(f"wrote {os.path.basename(path)} ({os.path.getsize(path)} bytes)")


if __name__ == "__main__":
    main()
