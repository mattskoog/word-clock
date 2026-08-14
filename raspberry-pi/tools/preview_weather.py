"""Build a standalone page for looking at the weather animations.

Deliberately not part of the clock's web interface: this is a workbench for
choosing brightnesses and judging artwork, not something to leave on the wall
controller. It writes one self-contained HTML file that opens straight from
disk, with no server and nothing running on the Pi.

    python3 tools/preview_weather.py && open weather_preview.html

Frames are built through the clock's own render path - the real word mapping,
the real compositing, the real screen encoding - so what the page shows is what
the clock would draw, not a second implementation that can drift from it.
"""

import argparse
import json
import os
import sys
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, ".."))
sys.path.insert(0, os.path.join(PROJECT, "src", "wordclock"))
# The HAL only talks to the LEDs when it is asked to; importing it needs the
# board modules, which are stubbed for exactly this reason in tests/.
sys.path.insert(0, os.path.join(PROJECT, "tests", "stubs"))

import settings as settings_module  # noqa: E402
import weather  # noqa: E402
import webui  # noqa: E402
from clock_display_hal import ClockDisplayHAL  # noqa: E402
from gif import GifLibrary  # noqa: E402
from word_clock import WordClock  # noqa: E402

WHEN = datetime(2026, 8, 13, 23, 25)  # "it is twenty five minutes past eleven"
MAX_FRAMES = 60


class FixedWeather:
    """Stands in for the live watch, pinned to one condition."""

    def __init__(self, name):
        self._name = name

    def animation(self):
        return self._name


def build(weather_directory, background_directory, text_brightness):
    library = GifLibrary(weather_directory)
    backgrounds = GifLibrary(background_directory)
    names = library.names()
    if not names:
        raise SystemExit(f"No animations in {weather_directory}")

    animations = []
    for name in names:
        values = dict(settings_module.DEFAULTS)
        values.update({
            "theme": "solid",
            "color": [255, 255, 255],
            "brightness": text_brightness,
            "background_enabled": True,
            "background_source": "weather",
            # Drawn at full, so the page can dim it live without rebuilding.
            "background_brightness": 1.0,
        })
        clock = WordClock(ClockDisplayHAL("D12", 1.0), None, backgrounds,
                          library, FixedWeather(name))

        # Sample the animation over exactly one loop, so the page loops as the
        # clock does rather than drifting.
        frames, _ = clock._background_for(name, library)
        total = sum(delay for _, delay in frames) or 1.0
        count = min(MAX_FRAMES, len(frames))
        step = total / count

        rendered = []
        for index in range(count):
            elapsed = index * step
            background = clock.background_frame(values, elapsed)
            words = clock.frame_for(values, WHEN, elapsed=elapsed)
            rendered.append({
                # Two layers, so the page can weigh them against each other
                # without going back to Python for every slider move.
                "background": background,
                "words": [words[i] if words[i] != background[i] else [0, 0, 0]
                          for i in range(ClockDisplayHAL.NUM_LEDS)],
            })

        # Night variants live in their own map, so both have to be searched or
        # clear_night would fall back to showing its filename.
        night = name in weather.NIGHT_ANIMATIONS.values()
        source = weather.NIGHT_ANIMATIONS if night else weather.ANIMATIONS
        matches = [c for c, animation in source.items() if animation == name]
        # Several conditions can share one file - drizzle draws as rain - so
        # prefer the one the file is named after rather than whichever the
        # dictionary happens to yield first.
        stem = name[:-4]
        condition = next((c for c in matches if c == stem),
                         matches[0] if matches else None)
        animations.append({
            "name": name,
            "label": name[:-4].replace("_", " ").capitalize(),
            "condition": weather.label_for(condition, not night) or name[:-4],
            "delay": int(step * 1000),
            "frames": rendered,
        })
    return animations


PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Word clock \u2014 weather animations</title>
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  body { margin: 0; padding: 24px; background: #0b0d12; color: #e8eaf0;
         font: 15px/1.5 -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  h1 { font-size: 20px; margin: 0 0 4px; }
  .lede { color: #8f97ad; margin: 0 0 22px; max-width: 62ch; }
  .controls { position: sticky; top: 0; z-index: 2; background: #0b0d12;
              padding: 12px 0 16px; border-bottom: 1px solid #262a38;
              margin-bottom: 22px; display: flex; gap: 28px; flex-wrap: wrap; }
  .control { min-width: 240px; flex: 1; }
  label { display: block; font-size: 13px; color: #b9c0d0; margin-bottom: 6px; }
  input[type=range] { width: 100%; accent-color: #6c8cff; margin: 2px 0; }
  .value { font-variant-numeric: tabular-nums; color: #8f97ad; font-size: 13px; }
  .grid { display: grid; gap: 22px;
          grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }
  figure { margin: 0; }
  figcaption { margin-top: 10px; font-size: 13px; }
  figcaption b { display: block; font-size: 14px; }
  figcaption span { color: #8f97ad; }
  .face { display: grid; grid-template-columns: repeat(12, minmax(0, 1fr));
          gap: 1px; aspect-ratio: 12 / 11; background: #05070b; padding: 10px;
          border-radius: 10px; border: 1px solid #1d2130; }
  .face span { display: grid; place-items: center; font-size: 10px;
               font-weight: 600; color: #12151d; user-select: none; }
</style>
</head>
<body>
<h1>Weather animations</h1>
<p class="lede">Every face is built by the clock's own render path, encoded for
a screen the same way the web interface encodes it. Slide the brightness to the
setting you run on the wall to judge them where it matters, which is low.</p>
<div class="controls">
  <div class="control">
    <label for="bg">Animation brightness <span class="value" id="bg-value"></span></label>
    <input type="range" id="bg" min="0" max="0.5" step="0.005">
  </div>
  <div class="control">
    <label for="text">Text brightness <span class="value" id="text-value"></span></label>
    <input type="range" id="text" min="0" max="1" step="0.01">
  </div>
</div>
<div class="grid" id="grid"></div>
<script>
var DATA = __DATA__;
var LETTERS = __LETTERS__;
var GAMMA = __GAMMA__;

// The same encoding the web interface applies: LED values are linear light,
// CSS colours are not, so a dim background written straight into a colour
// would all but vanish.
function toScreen(rgb) {
  var out = [];
  for (var i = 0; i < 3; i++) {
    var level = Math.min(1, Math.max(0, rgb[i] / 255));
    out.push(Math.round(255 * Math.pow(level, 1 / GAMMA)));
  }
  return 'rgb(' + out.join(',') + ')';
}

var faces = [];
DATA.forEach(function (animation) {
  var figure = document.createElement('figure');
  var face = document.createElement('div');
  face.className = 'face';
  var cells = [];
  for (var i = 0; i < LETTERS.length; i++) {
    var cell = document.createElement('span');
    cell.textContent = LETTERS[i];
    face.appendChild(cell);
    cells.push(cell);
  }
  var caption = document.createElement('figcaption');
  caption.innerHTML = '<b>' + animation.label + '</b><span>' +
    animation.condition + ' \\u00b7 ' + animation.frames.length + ' frames</span>';
  figure.appendChild(face);
  figure.appendChild(caption);
  document.getElementById('grid').appendChild(figure);
  faces.push({ animation: animation, cells: cells, step: 0 });
});

// Cartesian order for the letters, LED order for the colours: the strip runs
// in a serpentine, so the two are not the same walk.
var TO_LED = __TO_LED__;

function paint() {
  var bg = Number(document.getElementById('bg').value);
  var text = Number(document.getElementById('text').value);
  document.getElementById('bg-value').textContent = Math.round(bg * 100) + '%';
  document.getElementById('text-value').textContent = Math.round(text * 100) + '%';
  faces.forEach(function (entry) {
    var frame = entry.animation.frames[entry.step % entry.animation.frames.length];
    for (var i = 0; i < entry.cells.length; i++) {
      var led = TO_LED[i];
      var word = frame.words[led];
      var colour = (word[0] || word[1] || word[2])
        ? [word[0] * text, word[1] * text, word[2] * text]
        : [frame.background[led][0] * bg, frame.background[led][1] * bg,
           frame.background[led][2] * bg];
      entry.cells[i].style.color = toScreen(colour);
    }
  });
}

document.getElementById('bg').value = 0.02;
document.getElementById('text').value = 0.45;
document.getElementById('bg').oninput = paint;
document.getElementById('text').oninput = paint;
paint();

// Each animation keeps its own authored pace.
faces.forEach(function (entry) {
  setInterval(function () { entry.step++; paint(); }, entry.animation.delay);
});
</script>
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--weather-dir", default=os.path.join(PROJECT, "weather"))
    parser.add_argument("--background-dir", default=os.path.join(PROJECT, "backgrounds"))
    parser.add_argument("--brightness", type=float, default=0.45,
                        help="text brightness the faces are drawn at")
    parser.add_argument("--out", default=os.path.join(PROJECT, "weather_preview.html"))
    arguments = parser.parse_args()

    animations = build(arguments.weather_dir, arguments.background_dir,
                       arguments.brightness)
    letters = [letter for row in ClockDisplayHAL.LETTER_ROWS for letter in row]
    to_led = [ClockDisplayHAL.cartesian_to_word_clock_led_strip_index(x, y)
              for y in range(ClockDisplayHAL.HEIGHT)
              for x in range(ClockDisplayHAL.WIDTH)]

    page = (PAGE
            .replace("__DATA__", json.dumps(animations, separators=(",", ":")))
            .replace("__LETTERS__", json.dumps(letters))
            .replace("__TO_LED__", json.dumps(to_led))
            .replace("__GAMMA__", repr(webui.PREVIEW_GAMMA)))
    with open(arguments.out, "w") as handle:
        handle.write(page)
    print(f"wrote {arguments.out} "
          f"({len(animations)} animations, {os.path.getsize(arguments.out) // 1024} KB)")


if __name__ == "__main__":
    main()
