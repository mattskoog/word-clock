# Weather animations

These play behind the time like the ones in `../backgrounds/`, but they are
never chosen by hand — the clock picks one from the current conditions at your
zip code. That is the whole difference, and it drives the design: a background
only has to be pleasant, whereas one of these has to be recognisable as its own
weather at a glance, on a 12x11 grid, behind lit words.

Seven ship with the clock:

| | |
| --- | --- |
| `clear` | a warm sky that swells and settles |
| `clear_night` | a dim field with a scatter of stars, each twinkling on its own |
| `cloud` | grey banks drifting sideways, thinning and thickening |
| `fog` | a flat haze with no features, barely moving |
| `rain` | falling streaks over a dark sky |
| `snow` | flakes drifting down, sideways as much as they fall |
| `storm` | a heavy sky that lights up twice a loop |

Only `clear` has a night version. Rain looks like rain whatever the hour, and
splitting the rest would have doubled the set for no gain.

## How conditions reach them

The clock reads a WMO weather code and collapses it to one of seven
conditions — the difference between slight and heavy rain is not something this
grid can show:

| condition | WMO codes | animation |
| --- | --- | --- |
| clear | 0, 1 | `clear` / `clear_night` |
| cloud | 2, 3 | `cloud` |
| fog | 45, 48 | `fog` |
| drizzle | 51–57 | `rain` |
| rain | 61–67, 80–82 | `rain` |
| snow | 71–77, 85, 86 | `snow` |
| storm | 95, 96, 99 | `storm` |

Drizzle keeps its own name so the interface can say which it is, but at this
size it draws the same as rain.

## Brightness, and why the storm works

Backgrounds are normalised against the animation's brightest pixel across
**every** frame, not per frame. That matters here: scaling each frame to its own
peak would hold the animation at one level and flatten anything meant to change
over time, so the lightning would come out no brighter than the dark sky around
it. Normalising across the loop instead leaves the ordinary frames sitting low
and lets the flash land, which is what a storm should look like.

If you draw your own, that is the rule to design against — an animation with one
very bright pixel will sit dim everywhere else.

## Looking at them

There is a workbench for this, deliberately kept out of the clock's own web
interface:

```bash
python3 tools/preview_weather.py && open weather_preview.html
```

It writes one self-contained page showing all seven on real clock faces, with
brightness sliders, so they can be judged at the low settings they actually run
at. The frames are built through the clock's own render path, so the page cannot
drift from what the LEDs would draw. The file is gitignored and nothing about it
reaches the Pi.

## Regenerating these

```bash
python3 tools/make_weather.py
```

Loops have to close, and for anything that falls there is a catch: a drop only
lands back where it started if it travels a whole multiple of the 11 rows, so
`steps * speed` has to divide by 11. `44 * 0.25` and `44 * 0.5` do; `40 * 0.25`
does not, and the fall visibly jumps once a loop.
