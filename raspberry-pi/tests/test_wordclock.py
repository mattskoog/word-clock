"""Tests for the Raspberry Pi word clock.

Runs off-hardware against stubbed LEDs. No test framework needed:

    python3 tests/test_wordclock.py

Only Pillow is required, which the clock needs anyway.
"""

import json
import os
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, ".."))
sys.path[:0] = [os.path.join(HERE, "stubs"), os.path.join(PROJECT, "src", "wordclock")]
GIFS = os.path.join(PROJECT, "gifs")
BACKGROUNDS = os.path.join(PROJECT, "backgrounds")
WEATHER = os.path.join(PROJECT, "weather")

import gif as gif_module
import main as wordclock_main
import themes
import timekeeper
import weather
import webui
from clock_display_hal import ClockDisplayHAL
from gif import GifLibrary
from settings import GIF_MODES, Settings
from word_clock import WordClock

failures = []


def check(name, condition, detail=""):
    if not condition:
        failures.append(name)
    print(f"{'ok  ' if condition else 'FAIL'} {name}{(' -> ' + str(detail)) if detail else ''}")


def fresh_settings(library, **overrides):
    settings = Settings(os.path.join(tempfile.mkdtemp(), "wordclock.json"),
                        gif_names=library.names,
                        background_names=backgrounds.names)
    base = {"theme": "solid", "color": [255, 255, 255], "sparkle": False,
            "brightness": 1.0, "timezone": "", "display_on": True, "background": ""}
    base.update(overrides)
    settings.update(base)
    return settings


library = GifLibrary(GIFS)
backgrounds = GifLibrary(BACKGROUNDS)
weather_library = GifLibrary(WEATHER)
WHEN = datetime(2026, 8, 11, 15, 17)          # "it is fifteen minutes past three"
LATER = datetime(2026, 8, 11, 15, 40)         # "it is twenty minutes to four"


# --- the face itself --------------------------------------------------------

print("\n-- face and word mapping --")
check("grid is 11 rows of 12", len(ClockDisplayHAL.LETTER_ROWS) == ClockDisplayHAL.HEIGHT
      and all(len(row) == ClockDisplayHAL.WIDTH for row in ClockDisplayHAL.LETTER_ROWS))

position_of = {}
for y in range(ClockDisplayHAL.HEIGHT):
    for x in range(ClockDisplayHAL.WIDTH):
        position_of[ClockDisplayHAL.cartesian_to_word_clock_led_strip_index(x, y)] = (y, x)
check("every LED is addressed exactly once", len(position_of) == ClockDisplayHAL.NUM_LEDS,
      len(position_of))

HOUR_WORDS = {1: "ONE", 2: "TWO", 3: "THREE", 4: "FOUR", 5: "FIVE", 6: "SIX",
              7: "SEVEN", 8: "EIGHT", 9: "NINE", 10: "TEN", 11: "ELEVEN", 12: "TWELVE"}
misspelled = []
for word, (start, end) in ClockDisplayHAL.WORDS_TO_LEDS.items():
    spelled = "".join(ClockDisplayHAL.LETTER_ROWS[y][x]
                      for y, x in sorted(position_of[i] for i in range(start, end + 1)))
    expected = HOUR_WORDS[int(word[5:])] if word.startswith("HOUR_") else word
    if spelled != expected:
        misspelled.append((word, spelled, expected))
check("every word spells itself on the face", not misspelled, misspelled)

settings = fresh_settings(library)
hal = ClockDisplayHAL("D12", 1.0)
clock = WordClock(hal, settings, backgrounds)

for moment, expected in [
    (datetime(2026, 8, 11, 15, 0), "it is three o'clock"),
    (datetime(2026, 8, 11, 15, 7), "it is five minutes past three"),
    (datetime(2026, 8, 11, 15, 38), "it is twenty five minutes to four"),
    (datetime(2026, 8, 11, 0, 3), "it is twelve o'clock"),
    (datetime(2026, 8, 11, 23, 58), "it is five minutes to twelve"),
]:
    check(f"phrase at {moment:%H:%M}", clock.phrase(moment) == expected, clock.phrase(moment))

unmapped = [(h, m, w) for h in range(24) for m in range(60)
            for w in clock.words_for(datetime(2026, 8, 11, h, m))
            if w not in ClockDisplayHAL.WORDS_TO_LEDS]
check("every minute of the day maps to real words", not unmapped, unmapped[:3])


# --- themes -----------------------------------------------------------------

print("\n-- themes --")
check("six themes", len(themes.names()) == 6, themes.names())
check("phases is the default", themes.DEFAULT_THEME == "phases")
for theme in themes.names():
    settings.update({"theme": theme})
    check(f"{theme} lights the face", any(c != (0, 0, 0)
          for c in clock.frame_for(settings.snapshot(), WHEN)))

for hour, phase in [(0, "Night"), (5, "Early morning"), (8, "Morning"),
                    (12, "Afternoon"), (17, "Evening"), (21, "Night")]:
    check(f"{hour:02d}:00 is {phase}", themes.phase_for(hour)[0] == phase,
          themes.phase_for(hour)[0])
check("all five phases are reachable",
      len({themes.phase_for(h)[0] for h in range(24)}) == 5)

gradient = fresh_settings(library, theme="gradient", color=[255, 0, 0],
                          secondary_color=[0, 0, 255])
gradient_clock = WordClock(ClockDisplayHAL("D12", 1.0), gradient, backgrounds)
by_word = dict(gradient_clock.word_colors(gradient.snapshot(),
                                          datetime(2026, 8, 11, 15, 0)))
check("gradient runs top to bottom", by_word["IT"] == (255, 0, 0)
      and by_word["OCLOCK"] == (0, 0, 255), (by_word["IT"], by_word["OCLOCK"]))


# --- letter shimmer ---------------------------------------------------------

print("\n-- letter shimmer --")
sparkly = fresh_settings(library, sparkle=True, shimmer_speed=0.05)
shimmer_clock = WordClock(ClockDisplayHAL("D12", 1.0), sparkly, backgrounds)
frame = shimmer_clock.frame_for(sparkly.snapshot(), WHEN, elapsed=100.0)
minutes = ClockDisplayHAL.WORDS_TO_LEDS["MINUTES"]
levels = [frame[i][0] for i in range(minutes[0], minutes[1] + 1)]
check("shimmer varies letter by letter", len(set(levels)) > 1, levels)
flat = shimmer_clock.frame_for(dict(sparkly.snapshot(), sparkle=False), WHEN, elapsed=100.0)
check("without shimmer a word is one flat color",
      len({flat[i] for i in range(minutes[0], minutes[1] + 1)}) == 1)


def shimmer_band(color, brightness):
    peak = max(color)
    reached = [max(themes.apply_sparkle(color, 7, s * 0.01, 0.5, brightness)) / peak
               for s in range(400)]
    return min(reached), max(reached)


for brightness, floor in ((0.5, 0.90), (0.79, 0.90), (0.8, 0.80), (1.0, 0.80)):
    low, high = shimmer_band((180, 90, 0), brightness)
    check(f"shimmer at brightness {brightness} dips to {floor}", abs(low - floor) < 0.01,
          f"{low:.3f}")
    check(f"shimmer at brightness {brightness} lifts to 1.30", abs(high - 1.30) < 0.01,
          f"{high:.3f}")
_, capped = shimmer_band((255, 255, 255), 0.5)
check("shimmer never clips a full-brightness color", capped <= 1.0, f"{capped:.3f}")
brightest = max((themes.apply_sparkle((200, 100, 0), 7, s * 0.01, 0.5, 0.5)
                 for s in range(400)), key=max)
check("shimmer keeps the hue", abs(200 / 100 - brightest[0] / brightest[1]) < 0.05,
      brightest)


# --- background animations --------------------------------------------------

print("\n-- background animations --")
plain = fresh_settings(library)
bg_clock = WordClock(ClockDisplayHAL("D12", 1.0), plain, backgrounds)
without = bg_clock.frame_for(plain.snapshot(), WHEN)
word_leds = {i for i, color in enumerate(without) if color != (0, 0, 0)}

plain.update({"background_enabled": True, "background": "nebula.gif",
              "background_brightness": 0.25})
withbg = bg_clock.frame_for(plain.snapshot(), WHEN, elapsed=0.4)
check("background lights letters the time does not",
      len([i for i, c in enumerate(withbg) if c != (0, 0, 0)]) > len(word_leds))
check("the time is untouched by the background",
      all(withbg[i] == without[i] for i in word_leds))

background_only = [i for i, c in enumerate(withbg)
                   if c != (0, 0, 0) and i not in word_leds]
check("the time stays brighter than the background",
      max(max(withbg[i]) for i in word_leds) > max(max(withbg[i]) for i in background_only))

moved = bg_clock.frame_for(plain.snapshot(), WHEN, elapsed=1.2)
check("the background animates", moved != withbg)
check("the words hold still while it does",
      all(moved[i] == withbg[i] for i in word_leds))

# the two brightnesses are independent: one slider must not move the other
def layer_peaks(text_brightness, background_brightness):
    current = dict(plain.snapshot(), theme="solid", color=[255, 255, 255],
                   background_enabled=True, background="nebula.gif",
                   brightness=text_brightness,
                   background_brightness=background_brightness)
    composed = bg_clock.frame_for(current, WHEN, elapsed=0.4)
    words = dict(bg_clock.word_colors(current, WHEN, 0.4))
    lit = {i for w, (a, b) in ClockDisplayHAL.WORDS_TO_LEDS.items() if w in words
           for i in range(a, b + 1)}
    behind = [max(composed[i]) for i in range(ClockDisplayHAL.NUM_LEDS)
              if i not in lit and composed[i] != (0, 0, 0)]
    return max(max(composed[i]) for i in lit), (max(behind) if behind else 0)


text_levels = {layer_peaks(b, 0.25)[0] for b in (0.25, 0.5, 0.75, 1.0)}
background_levels = {layer_peaks(b, 0.25)[1] for b in (0.25, 0.5, 0.75, 1.0)}
check("text brightness dims the text", len(text_levels) == 4, sorted(text_levels))
check("text brightness leaves the background alone", len(background_levels) == 1,
      background_levels)

text_levels = {layer_peaks(0.5, g)[0] for g in (0.1, 0.25, 0.5, 1.0)}
background_levels = {layer_peaks(0.5, g)[1] for g in (0.1, 0.25, 0.5, 1.0)}
check("animation brightness dims the background", len(background_levels) == 4,
      sorted(background_levels))
check("animation brightness leaves the text alone", len(text_levels) == 1, text_levels)

plain.update({"theme": "solid", "background_enabled": False})
check("switching the background off leaves only the time",
      bg_clock.frame_for(plain.snapshot(), WHEN) == without)
check("the animation is remembered while it is off",
      plain.get("background") == "nebula.gif", plain.get("background"))
plain.update({"background_enabled": True, "background": ""})
check("enabled with nothing chosen shows nothing extra",
      bg_clock.frame_for(plain.snapshot(), WHEN) == without)
plain.update({"background": "ripple.gif"})
check("a background makes the display animated", themes.is_animated(plain.snapshot()))
check("and switching it off makes it static again",
      not themes.is_animated(dict(plain.snapshot(), background_enabled=False)))

# only a curated few are offered as backgrounds
offered = backgrounds.names()
check("five backgrounds are offered", len(offered) == 5, offered)

# A leading underscore shelves a file: it stays in the folder but is kept out
# of the picker, so one can be retired and brought back with a rename. Built
# here rather than leaning on a shipped file, so the rule is what is tested.
shelf = tempfile.mkdtemp()
for filename in ("kept.gif", "_shelved.gif"):
    with open(os.path.join(shelf, filename), "wb") as handle:
        handle.write(b"")
shelf_library = GifLibrary(shelf)
check("a shelved animation is still on disk",
      os.path.isfile(os.path.join(shelf, "_shelved.gif")))
check("a shelved animation is left out of the picker",
      shelf_library.names() == ["kept.gif"], shelf_library.names())
check("a shelved animation cannot be resolved to a path",
      shelf_library.path_for("_shelved.gif") is None)
shelf_settings = Settings(os.path.join(tempfile.mkdtemp(), "s.json"),
                          background_names=shelf_library.names)
check("a shelved animation is not a valid setting",
      "background" in shelf_settings.update({"background": "_shelved.gif"})[1])
os.rename(os.path.join(shelf, "_shelved.gif"), os.path.join(shelf, "shelved.gif"))
check("renaming brings it back",
      shelf_library.names() == ["kept.gif", "shelved.gif"], shelf_library.names())
check("backgrounds are kept out of the hourly set",
      not (set(offered) & set(library.names())), set(offered) & set(library.names()))
for name in offered:
    frames = gif_module.load_frames(os.path.join(BACKGROUNDS, name))
    shapes = all(len(g) == ClockDisplayHAL.HEIGHT
                 and all(len(r) == ClockDisplayHAL.WIDTH for r in g) for g, _ in frames)
    moves = len({tuple(c for row in g for c in row) for g, _ in frames}) > 1
    check(f"background {name} decodes and animates", bool(frames) and shapes and moves,
          f"{len(frames)} frames")
check("an hourly animation is not a valid background",
      "background" in plain.update({"background": "sun.gif"})[1])


# --- weather ----------------------------------------------------------------

print("\n-- weather --")

# Every WMO code the service can send maps to something, or is deliberately
# unmapped. A code that fell through silently would leave the face dark.
for code, expected in [(0, "clear"), (1, "clear"), (2, "cloud"), (3, "cloud"),
                       (45, "fog"), (48, "fog"), (51, "drizzle"), (55, "drizzle"),
                       (61, "rain"), (65, "rain"), (80, "rain"), (82, "rain"),
                       (71, "snow"), (77, "snow"), (86, "snow"),
                       (95, "storm"), (99, "storm")]:
    check(f"code {code} is {expected}", weather.condition_for(code) == expected,
          weather.condition_for(code))
check("an unknown code maps to nothing", weather.condition_for(7777) is None)
check("a missing code maps to nothing", weather.condition_for(None) is None)

check("clear has a night of its own",
      weather.animation_for("clear", False) == "clear_night.gif")
check("clear by day is the day one",
      weather.animation_for("clear", True) == "clear.gif")
check("rain is rain at any hour",
      weather.animation_for("rain", False) == weather.animation_for("rain", True))
check("drizzle borrows the rain animation",
      weather.animation_for("drizzle") == "rain.gif")
check("no condition means no animation", weather.animation_for(None) == "")
check("a night label says so", weather.label_for("clear", False) == "Clear night")

# Every animation a condition can ask for has to exist on disk, or the clock
# would silently fall back for a weather it claims to support.
wanted = set(weather.ANIMATIONS.values()) | set(weather.NIGHT_ANIMATIONS.values())
on_disk = set(weather_library.names())
check("every condition has its animation", wanted <= on_disk, wanted - on_disk)
check("no weather animation is unreachable", on_disk <= wanted, on_disk - wanted)
for name in sorted(on_disk):
    frames = gif_module.load_frames(os.path.join(WEATHER, name))
    moves = len({tuple(c for row in g for c in row) for g, _ in frames}) > 1
    check(f"weather {name} decodes and animates", len(frames) > 1 and moves,
          f"{len(frames)} frames")

# The watch, driven off a stubbed reading so the tests never touch the network.
weather_settings = fresh_settings(library, background_enabled=True,
                                  background_source="weather")
watch = weather.WeatherWatch(weather_settings)
check("with no reading the watch offers nothing", watch.animation() == "")

def fake_read(condition, is_day=True, temperature=12.0):
    return lambda latitude, longitude: (condition, is_day, temperature)

real_read = weather.read
try:
    weather_settings.update({"weather_latitude": 41.9, "weather_longitude": -87.6})
    weather.read = fake_read("snow")
    watch._check()
    check("the watch follows the reading", watch.animation() == "snow.gif",
          watch.animation())
    check("the status reads back", watch.status()["label"] == "Snow",
          watch.status())

    # A dropped connection must not blank the face: the last good reading stands.
    def explode(latitude, longitude):
        raise weather.WeatherError("no route to host")
    weather.read = explode
    watch._check()
    check("a failed fetch keeps the last animation", watch.animation() == "snow.gif",
          watch.animation())
    check("a failed fetch is reported", watch.status()["error"] == "no route to host",
          watch.status())

    # Which animation the clock actually draws.
    weather_clock = WordClock(ClockDisplayHAL("D12", 1.0), weather_settings,
                              backgrounds, weather_library, watch)
    name, chosen = weather_clock._background_choice(weather_settings.snapshot())
    check("the clock draws the weather animation", name == "snow.gif", name)
    check("and takes it from the weather set", chosen is weather_library)

    # With no reading at all it falls back rather than going dark.
    weather_settings.update({"background": "aurora.gif"})
    blank_watch = weather.WeatherWatch(weather_settings)
    fallback_clock = WordClock(ClockDisplayHAL("D12", 1.0), weather_settings,
                               backgrounds, weather_library, blank_watch)
    name, chosen = fallback_clock._background_choice(weather_settings.snapshot())
    check("without a reading it falls back to the chosen animation",
          name == "aurora.gif" and chosen is backgrounds, name)

    check("weather makes the display animated",
          themes.is_animated(dict(weather_settings.snapshot(), background="")))
finally:
    weather.read = real_read

# A postcode is interpolated into a URL, so anything that is not one is refused
# before it gets there.
for bad in ("../../etc/passwd", "60601?x=1", "a" * 11, "60601/../"):
    _, errors = weather_settings.update({"weather_zip": bad})
    check(f"postcode {bad!r} is refused", "weather_zip" in errors, errors)
applied, _ = weather_settings.update({"weather_zip": " 60601 "})
check("a postcode is trimmed", applied.get("weather_zip") == "60601", applied)
_, errors = weather_settings.update({"background_source": "guesswork"})
check("an unknown background source is refused", "background_source" in errors)
applied, _ = weather_settings.update({"weather_latitude": 200})
check("latitude is clamped to the globe", applied["weather_latitude"] == 90.0,
      applied)
applied, _ = weather_settings.update({"weather_latitude": None})
check("latitude can be cleared", applied["weather_latitude"] is None, applied)

# The flash has to survive brightness scaling, which is why the normalisation
# is per animation rather than per frame.
storm_frames = gif_module.load_frames(os.path.join(WEATHER, "storm.gif"))
frame_peaks = [max(max(c) for row in g for c in row) for g, _ in storm_frames]
check("the storm has bright frames and dark ones",
      max(frame_peaks) - min(frame_peaks) > 40,
      f"{min(frame_peaks)}-{max(frame_peaks)}")
flash_settings = fresh_settings(library, background_enabled=True,
                                background_source="weather",
                                background_brightness=1.0)
flash_watch = weather.WeatherWatch(flash_settings)
real_read = weather.read
try:
    flash_settings.update({"weather_latitude": 41.9, "weather_longitude": -87.6})
    weather.read = fake_read("storm")
    flash_watch._check()
    flash_clock = WordClock(ClockDisplayHAL("D12", 1.0), flash_settings,
                            backgrounds, weather_library, flash_watch)
    values = flash_settings.snapshot()
    drawn = [max(max(c) for c in flash_clock.background_frame(values, t * 0.13))
             for t in range(60)]
    check("the flash still reads brighter than the sky",
          max(drawn) - min(drawn) > 40, f"{min(drawn)}-{max(drawn)}")
finally:
    weather.read = real_read


# --- crossfade --------------------------------------------------------------

print("\n-- crossfade --")
real_now = timekeeper.now
fake = {"t": WHEN}
timekeeper.now = lambda tz="": fake["t"]

fade_settings = fresh_settings(library)
fade_hal = ClockDisplayHAL("D12", 1.0)
fade_clock = WordClock(fade_hal, fade_settings, backgrounds)
pushed = []
fade_hal.show = (lambda original: lambda: (pushed.append(list(fade_hal.pixels.buffer)),
                                           original())[1])(fade_hal.show)


def advance_to(moment):
    fake["t"] = moment
    pushed.clear()
    started = time.monotonic()
    fade_clock.display_time()
    return list(pushed), time.monotonic() - started


for theme in ("solid", "phases", "rainbow", "cycle"):
    for shimmer in (False, True):
        fade_settings.update({"theme": theme, "sparkle": shimmer, "animation_speed": 0.5,
                              "shimmer_speed": 0.5})
        fake["t"] = WHEN
        fade_clock._last_signature = None
        fade_clock._last_frame = None
        fade_clock._paused_for = 0.0
        fade_clock.display_time(force=True)
        frames, took = advance_to(LATER)
        label = f"{theme}{' + shimmer' if shimmer else ''}"
        check(f"{label} crossfades on a time change", len(frames) >= 8, len(frames))
        check(f"{label} fade lasts about half a second", 0.4 <= took <= 0.8, f"{took:.2f}s")

# a moving theme resumes where it froze rather than jumping the fade's length
fade_settings.update({"theme": "cycle", "sparkle": False, "animation_speed": 0.5})
current = fade_settings.snapshot()
fake["t"] = WHEN
fade_clock._last_signature = None
fade_clock._last_frame = None
fade_clock._paused_for = 0.0
fade_clock.display_time(force=True)
frozen = fade_clock._elapsed()
lit_word = lambda e=None: dict(fade_clock.word_colors(current, fake["t"], e))["IT"]
before = lit_word(frozen)
advance_to(LATER)
gap = lambda a, b: sum(abs(x - y) for x, y in zip(a, b))
check("a moving theme resumes where it froze", gap(before, lit_word()) < 40,
      f"{before} -> {lit_word()}")
check("and would have jumped without the pause",
      gap(before, lit_word(frozen + fade_clock._paused_for)) > 100)

fade_settings.update({"theme": "solid", "sparkle": True})
fake["t"] = LATER
fade_clock._last_signature = None
fade_clock._last_frame = None
fade_clock.display_time(force=True)
pushed.clear()
started = time.monotonic()
for _ in range(5):
    fade_clock.display_time()
check("no fade while the time is unchanged", time.monotonic() - started < 0.2)

fade_clock.invalidate(cleared=True)
check("a blanked display fades up from black",
      all(color == (0, 0, 0) for color in fade_clock._last_frame))

timekeeper.now = real_now


# --- animations and the cuckoo clock ----------------------------------------

print("\n-- animations --")
names = library.names()
check("thirteen animations ship with the clock", len(names) == 13, len(names))
for name in names:
    frames = gif_module.load_frames(library.path_for(name))
    shapes = all(len(g) == ClockDisplayHAL.HEIGHT
                 and all(len(r) == ClockDisplayHAL.WIDTH for r in g) for g, _ in frames)
    moves = len({tuple(c for row in g for c in row) for g, _ in frames}) > 1
    delays = all(0.02 <= d <= 5 for _, d in frames)
    check(f"{name} decodes and animates", bool(frames) and shapes and moves and delays,
          f"{len(frames)} frames")

check("path traversal is refused", library.path_for("../../../etc/passwd") is None)
hourly = {str(h): "" for h in range(1, 13)}
hourly["3"] = "sun.gif"
check("hourly picks the mapped animation",
      os.path.basename(library.choose("hourly", "", hourly, 3) or "") == "sun.gif")
check("an unmapped hour still gets one", library.choose("hourly", "", hourly, 5) is not None)
check("three selection modes", sorted(GIF_MODES) == ["fixed", "hourly", "random"], GIF_MODES)

loop_now = timekeeper.now
loop_fake = {"t": datetime(2026, 8, 11, 14, 59)}
timekeeper.now = lambda tz="": loop_fake["t"]
played = []
real_play = gif_module.play


def spy_play(path, *args, **kwargs):
    played.append(os.path.basename(path))
    return real_play(path, *args, **kwargs)


gif_module.play = spy_play
wordclock_main.gif.play = spy_play

loop_settings = fresh_settings(library, gifs_enabled=True, gif_mode="hourly",
                               gif_duration=1.0,
                               hour_gifs={"3": "sun.gif", "4": "moon.gif"})
loop_hal = ClockDisplayHAL("D12", 1.0)
loop_clock = WordClock(loop_hal, loop_settings, backgrounds)
threading.Thread(target=wordclock_main.run,
                 args=(loop_hal, loop_clock, loop_settings, library), daemon=True).start()


def at(moment, seconds=1.6):
    loop_fake["t"] = moment
    time.sleep(seconds)


at(datetime(2026, 8, 11, 14, 59))
played.clear()
check("cuckoo is silent away from the hour", played == [], played)
at(datetime(2026, 8, 11, 15, 0), 3.0)
check("cuckoo plays at the top of the hour", played == ["sun.gif"], played)
check("the clock face returns afterwards", len(loop_hal.pixels.lit()) > 0)
played.clear()
at(datetime(2026, 8, 11, 15, 5))
check("cuckoo does not fire twice in an hour", played == [], played)
loop_settings.update({"gifs_enabled": False})
played.clear()
at(datetime(2026, 8, 11, 16, 5))
at(datetime(2026, 8, 11, 17, 0), 2.5)
check("cuckoo switched off plays nothing", played == [], played)

gif_module.play = real_play
wordclock_main.gif.play = real_play
timekeeper.now = loop_now


# --- settings and the web API -----------------------------------------------

print("\n-- settings and web API --")
api_settings = fresh_settings(library)
applied, errors = api_settings.update({"brightness": 2.5, "color": "#ff8800"})
check("brightness is clamped", applied["brightness"] == 1.0)
check("hex colors are accepted", applied["color"] == [255, 136, 0])
_, errors = api_settings.update({"theme": "nope", "brightness": "abc",
                                 "timezone": "Mars/Olympus", "gif_name": "../../etc/passwd",
                                 "background": "../../etc/passwd", "bogus": 1})
for key in ("theme", "brightness", "timezone", "gif_name", "background", "bogus"):
    check(f"{key} is rejected when invalid", key in errors)

check("zone list is populated", len(timekeeper.zone_names()) > 300)
for place, lat, lon, expected in [("Warsaw", 52.23, 21.01, "Europe/Warsaw"),
                                  ("Tokyo", 35.68, 139.69, "Asia/Tokyo")]:
    check(f"locate {place}", timekeeper.nearest_timezone(lat, lon) == expected)
for hour, minute, shown in [(0, 5, "12:05 AM"), (12, 0, "12:00 PM"), (15, 34, "3:34 PM")]:
    label = timekeeper.describe(datetime(2026, 8, 11, hour, minute,
                                         tzinfo=timekeeper.resolve_timezone("America/Chicago")))
    check(f"12-hour label {hour:02d}:{minute:02d}", label.startswith(shown), label)

server = webui.start(api_settings, library, backgrounds, clock, "127.0.0.1", 0)
check("web server starts", server is not None)
PORT = server.server_address[1] if server else 0


def request(path, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(f"http://127.0.0.1:{PORT}{path}", data=data,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as response:
        return response.status, response.read()

status, body = request("/")
check("page is served", status == 200 and b"<title>Word Clock" in body)
status, body = request("/api/state")
state = json.loads(body)
check("state carries settings, themes and gifs",
      all(key in state for key in ("settings", "themes", "gifs", "clock", "crossfade")))
status, body = request("/api/preview", dict(api_settings.snapshot(), theme="solid",
                                            color=[255, 0, 0], background=""))
preview = json.loads(body)
check("preview returns the letter grid",
      preview["letters"] == list(ClockDisplayHAL.LETTER_ROWS))
check("preview grid is 11x12", len(preview["colors"]) == 11
      and all(len(row) == 12 for row in preview["colors"]))
before_theme = api_settings.get("theme")
request("/api/preview", dict(api_settings.snapshot(), theme="cycle"))
check("preview does not apply the draft", api_settings.get("theme") == before_theme)
status, body = request("/api/gif/frames", {"name": "sun.gif"})
check("animation frames are served", len(json.loads(body)["frames"]) > 1)
status, body = request("/api/gif/frames", {"name": "../../etc/passwd"})
check("frames endpoint refuses traversal", json.loads(body)["frames"] == [])
try:
    request("/api/nope")
    check("unknown paths 404", False)
except urllib.error.HTTPError as error:
    check("unknown paths 404", error.code == 404)
if server:
    server.shutdown()


print()
print(f"{len(failures)} failure(s)" + (": " + ", ".join(failures) if failures else ""))
sys.exit(1 if failures else 0)
