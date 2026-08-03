"""Generate the clock's animations.

Every animation is drawn straight at the 12x11 size of the LED grid, so nothing
is lost to scaling. Run this to recreate or tweak the set:

    python3 tools/make_animations.py

Existing files are overwritten, so anything you add by hand under a different
name is left alone.
"""

import math
import os
import random

from PIL import Image

WIDTH = 12
HEIGHT = 11
FRAME_MS = 110
OUTPUT_DIRECTORY = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "gifs")

CENTRE_X = (WIDTH - 1) / 2.0
CENTRE_Y = (HEIGHT - 1) / 2.0


def blank():
    return [[(0, 0, 0)] * WIDTH for _ in range(HEIGHT)]


def put(grid, x, y, color):
    x, y = int(round(x)), int(round(y))
    if 0 <= x < WIDTH and 0 <= y < HEIGHT:
        grid[y][x] = color


def disc(grid, cx, cy, radius, color):
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if math.hypot(x - cx, y - cy) <= radius:
                grid[y][x] = color


def ring(grid, cx, cy, radius, thickness, color):
    for y in range(HEIGHT):
        for x in range(WIDTH):
            if abs(math.hypot(x - cx, y - cy) - radius) <= thickness:
                grid[y][x] = color


def fade(color, amount):
    return tuple(int(channel * max(0.0, min(1.0, amount))) for channel in color)


def from_rows(rows, palette):
    """Build a frame from character art, one character per pixel."""
    grid = blank()
    for y, row in enumerate(rows):
        for x, key in enumerate(row):
            if key in palette:
                grid[y][x] = palette[key]
    return grid


# --- the animations --------------------------------------------------------

def sun():
    frames = []
    for step in range(12):
        phase = math.sin(step / 12.0 * 2 * math.pi)
        grid = blank()
        for index in range(8):
            angle = index * math.pi / 4
            length = 3.6 + phase * 0.9
            put(grid, CENTRE_X + math.cos(angle) * length,
                CENTRE_Y + math.sin(angle) * length, (255, 120, 0))
        disc(grid, CENTRE_X, CENTRE_Y, 2.6 + phase * 0.3, (255, 170, 0))
        disc(grid, CENTRE_X, CENTRE_Y, 1.5 + phase * 0.2, (255, 232, 120))
        frames.append(grid)
    return frames


def moon():
    frames = []
    star_positions = [(1, 1), (10, 2), (2, 9), (9, 8)]
    for step in range(12):
        grid = blank()
        disc(grid, CENTRE_X + 0.5, CENTRE_Y, 4.2, (226, 232, 255))
        disc(grid, CENTRE_X + 3.4, CENTRE_Y - 1.0, 4.0, (0, 0, 0))
        for index, (x, y) in enumerate(star_positions):
            twinkle = 0.25 + 0.75 * (0.5 + 0.5 * math.sin((step / 12.0 * 2 * math.pi) + index * 1.7))
            put(grid, x, y, fade((255, 255, 200), twinkle))
        frames.append(grid)
    return frames


STAR_ROWS = [
    ".....##.....",
    "....####....",
    "....####....",
    "############",
    ".##########.",
    "..########..",
    "...######...",
    "..###..###..",
    "..##....##..",
    ".##......##.",
    "............",
]


def star():
    # A drawn five-point star that pulses in brightness; building it from arms
    # at this size just read as a cross.
    frames = []
    for step in range(12):
        pulse = 0.5 + 0.5 * math.sin(step / 12.0 * 2 * math.pi)
        grid = from_rows(STAR_ROWS, {"#": fade((255, 205, 60), 0.45 + 0.55 * pulse)})
        frames.append(grid)
    return frames


def smiley():
    face = (255, 205, 40)
    frames = []
    # Mostly open eyes with a couple of blinks, like the heart's beat pattern.
    blink_at = {7, 8}
    for step in range(14):
        grid = blank()
        disc(grid, CENTRE_X, CENTRE_Y, 5.0, face)
        eye = (40, 30, 0)
        if step in blink_at:
            for x in (3, 4):
                put(grid, x, 4, eye)
            for x in (7, 8):
                put(grid, x, 4, eye)
        else:
            put(grid, 3, 3, eye)
            put(grid, 3, 4, eye)
            put(grid, 8, 3, eye)
            put(grid, 8, 4, eye)
        for x, y in ((3, 7), (4, 8), (5, 8), (6, 8), (7, 8), (8, 7)):
            put(grid, x, y, eye)
        frames.append(grid)
    return frames


def rocket():
    body = """
............
.....##.....
....####....
....####....
....####....
...######...
..##.##.##..
............
............
............
............
""".strip("\n").split("\n")
    frames = []
    for step in range(12):
        grid = from_rows(body, {"#": (230, 236, 255)})
        # Nose cone and window on top of the white body.
        put(grid, 5, 1, (255, 80, 80))
        put(grid, 6, 1, (255, 80, 80))
        put(grid, 5, 3, (90, 170, 255))
        put(grid, 6, 3, (90, 170, 255))
        flame_length = 2 + (step % 3)
        for offset in range(flame_length):
            heat = 1.0 - offset / float(flame_length + 1)
            color = (255, int(120 + 100 * heat), 0)
            put(grid, 5, 7 + offset, color)
            put(grid, 6, 7 + offset, color)
        frames.append(grid)
    return frames


def snow():
    random.seed(7)
    flakes = [(random.randrange(WIDTH), random.uniform(0, HEIGHT), random.uniform(0.35, 0.8))
              for _ in range(14)]
    frames = []
    for step in range(16):
        grid = blank()
        for x, y, speed in flakes:
            position = (y + step * speed) % (HEIGHT + 1)
            put(grid, x, position, fade((220, 240, 255), 0.45 + speed * 0.7))
        frames.append(grid)
    return frames


def rain():
    random.seed(11)
    drops = [(random.randrange(WIDTH), random.uniform(0, HEIGHT), random.uniform(0.8, 1.4))
             for _ in range(12)]
    frames = []
    for step in range(14):
        grid = blank()
        for y in range(2):
            for x in range(1, WIDTH - 1):
                grid[y][x] = (95, 105, 130)
        for x in range(2, WIDTH - 2):
            grid[2][x] = (75, 85, 110)
        for x, y, speed in drops:
            position = 3 + (y + step * speed) % (HEIGHT - 3)
            put(grid, x, position, (90, 160, 255))
        frames.append(grid)
    return frames


def fireworks():
    # Individual sparks flying outwards read far better at this size than a
    # drawn ring, which turned into a dim smudge.
    directions = [(math.cos(index * math.pi / 6), math.sin(index * math.pi / 6))
                  for index in range(12)]
    frames = []
    for color in ((255, 90, 90), (255, 220, 90), (130, 200, 255)):
        for launch_y in (HEIGHT - 1, HEIGHT - 3, CENTRE_Y + 1):
            grid = blank()
            put(grid, CENTRE_X, launch_y, (255, 245, 190))
            put(grid, CENTRE_X, launch_y + 1, (255, 150, 50))
            frames.append(grid)
        for stage in range(5):
            grid = blank()
            radius = 1.0 + stage * 1.15
            brightness = 1.0 - stage * 0.12  # stays visible once the LEDs dim it
            for dx, dy in directions:
                put(grid, CENTRE_X + dx * radius, CENTRE_Y + dy * radius,
                    fade(color, brightness))
            if stage < 2:
                disc(grid, CENTRE_X, CENTRE_Y, 1.0 - stage * 0.6, (255, 255, 225))
            frames.append(grid)
    return frames


def swirl():
    frames = []
    for step in range(16):
        grid = blank()
        spin = step / 16.0 * 2 * math.pi
        for index in range(3):
            angle = spin + index * 2 * math.pi / 3
            for distance in range(1, 5):
                trail = 1.0 - (distance - 1) / 5.0
                hue = (index / 3.0 + step / 16.0) % 1.0
                color = (
                    int(255 * abs(math.sin(hue * math.pi))),
                    int(255 * abs(math.sin((hue + 0.33) * math.pi))),
                    int(255 * abs(math.sin((hue + 0.66) * math.pi))),
                )
                put(grid, CENTRE_X + math.cos(angle + distance * 0.4) * distance,
                    CENTRE_Y + math.sin(angle + distance * 0.4) * distance,
                    fade(color, trail))
        frames.append(grid)
    return frames


def wave():
    frames = []
    for step in range(16):
        grid = blank()
        for x in range(WIDTH):
            height = CENTRE_Y + math.sin((x / float(WIDTH) * 2 * math.pi) - step / 16.0 * 2 * math.pi) * 2.6
            for y in range(HEIGHT):
                if y >= height:
                    depth = (y - height) / float(HEIGHT)
                    grid[y][x] = (int(20 + 40 * depth), int(120 - 60 * depth), 255 - int(60 * depth))
            put(grid, x, height, (180, 240, 255))
        frames.append(grid)
    return frames


def confetti():
    random.seed(3)
    palette = [(255, 90, 90), (255, 210, 90), (120, 255, 150), (120, 200, 255), (220, 140, 255)]
    pieces = [(random.randrange(WIDTH), random.uniform(0, HEIGHT),
               random.uniform(0.4, 0.9), random.choice(palette)) for _ in range(18)]
    frames = []
    for step in range(16):
        grid = blank()
        for x, y, speed, color in pieces:
            position = (y + step * speed) % (HEIGHT + 1)
            drift = int(math.sin((position + x) * 0.7) * 1.2)
            put(grid, x + drift, position, color)
        frames.append(grid)
    return frames


ANIMATIONS = {
    "sun": sun,
    "moon": moon,
    "star": star,
    "smiley": smiley,
    "rocket": rocket,
    "snow": snow,
    "rain": rain,
    "fireworks": fireworks,
    "swirl": swirl,
    "wave": wave,
    "confetti": confetti,
}


def save(name, frames, directory):
    images = []
    for grid in frames:
        image = Image.new("RGB", (WIDTH, HEIGHT))
        image.putdata([pixel for row in grid for pixel in row])
        # A per-frame adaptive palette keeps the colors these were drawn with.
        images.append(image.convert("P", palette=Image.ADAPTIVE, colors=255))
    path = os.path.join(directory, f"{name}.gif")
    images[0].save(path, save_all=True, append_images=images[1:],
                   duration=FRAME_MS, loop=0, optimize=False)
    return path


def main():
    directory = os.path.abspath(OUTPUT_DIRECTORY)
    os.makedirs(directory, exist_ok=True)
    for name, builder in sorted(ANIMATIONS.items()):
        path = save(name, builder(), directory)
        print(f"wrote {os.path.basename(path)} ({os.path.getsize(path)} bytes)")


if __name__ == "__main__":
    main()
