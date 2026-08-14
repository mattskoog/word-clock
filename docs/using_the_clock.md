# Using the clock (Raspberry Pi)

Everything below applies to the Raspberry Pi build.

## Web interface

Once the service is running, open `http://<your-pi>:8080` from any device on the
same network — phone included.

At the top of the page is a preview of the clock face showing the current time
in the colors you have chosen. Adjusting any control updates the preview
straight away but does **not** touch the clock: your edits are a draft until you
press **Save to clock** in the bar at the bottom, which applies them and writes
them to `raspberry-pi/wordclock.json` so they survive a reboot. **Revert**
throws the draft away and goes back to what the clock is currently running.

The preview is drawn by the same code that drives the LEDs, using the real
letter layout and word-to-LED map, so what you see is what the clock will show.
The one thing it cannot reproduce faithfully is brightness: a backlit screen
does not behave like an LED, so the preview dims less than the clock does.

From there you can:

| Control | What it does |
| --- | --- |
| Display | A status only, not a control &mdash; see below |
| Brightness | 0–100% |
| Theme | Pick one of the color themes below |
| Color / second color | Used by the solid and gradient themes. For a gradient they read top to bottom: the left swatch is the top of the clock |
| Theme animation speed | How fast a moving theme travels. Shown only for Rainbow and Color cycle |
| Letter shimmer | Twinkle on top of any theme, see below |
| Shimmer speed | How fast the shimmer twinkles, independent of the theme. Shown when the shimmer is on |
| Background animations on/off | Whether an animation plays behind the time |
| Select animation | Which background plays. Shown when backgrounds are on |
| Animation brightness | How bright the background is relative to the time |
| Cuckoo clock on/off | Whether an animation plays at the top of the hour |
| On the hour, play | A random animation, a single animation, or a specific animation each hour |
| Per-hour list | With **A specific animation each hour**, choose one for each of the twelve hours |
| ▶ | Plays that particular animation in the preview |
| Play for | How long the hourly animation runs, 1–60 seconds |
| Preview animation | Plays whichever animation the current settings would use at this hour. Hidden in per-hour mode, where each row has its own ▶ |
| Time zone | Pick from the list, or press **Detect**, see below |
| Save to clock / Revert | Apply the draft to the clock, or discard it |

### Turning the display off

The web interface deliberately cannot switch the display off — it only reports
whether it is on, so the clock cannot be blanked by a stray tap. The setting
still exists for anyone who wants it:

```bash
curl -X POST http://wordclock.local:8080/api/settings -d '{"display_on":false}'
```

or set `"display_on": false` in `raspberry-pi/wordclock.json` and restart the
service. The status in the interface reflects whichever way it was set.

> **Note:** the web interface has no password. It is meant for a home network —
> do not forward the port to the internet. To turn it off entirely, add
> `--no-web` to the `ExecStart` line in `/etc/systemd/system/word_clock.service`.

## Color themes

| Theme | Description |
| --- | --- |
| Phases of the day | A gradient that changes with the time of day, see below |
| Solid color | Every word in the color you choose |
| Gradient | Blends between two colors down the grid; the first swatch is the top of the clock, the second is the bottom |
| Rainbow | A rainbow spread across the grid that drifts over time |
| Color cycle | All words together, slowly cycling through the spectrum |
| Spectrum | An even spread of hues across the lit words, holding steady until the time changes |

Rainbow and color cycle are animated, so the display refreshes about 10 times a
second while they are active. The other themes only redraw when the displayed
time changes.

### Phases of the day

The default theme. It runs a gradient down the face, and which gradient depends
on the time of day, so the clock warms and cools as the day goes on:

| Phase | Hours | Top of the face | Bottom |
| --- | --- | --- | --- |
| Early morning | 5am – 8am | deep blue | warm peach |
| Morning | 8am – 12pm | sky blue | soft yellow |
| Afternoon | 12pm – 5pm | amber `#FBBF24` | yellow `#FDE047` |
| Evening | 5pm – 9pm | purple | sunset orange |
| Night | 9pm – 5am | near-black blue | deep violet |

The change is a clean switch at each boundary rather than a slow fade between
phases. It follows the clock's own time zone, so the phases match your daylight.

## Letter shimmer

Letter shimmer is a switch rather than a theme, so it works with all six. It gently
raises and lowers the brightness of each lit **letter**, every one on its own
timing, while leaving the theme's colors alone — a solid red face still reads
red, it just twinkles. Because neighbouring letters are deliberately out of
step, the shimmer scatters across the face rather than pulsing a word at a time.

The swing is kept modest so the face stays readable: a letter dips up to 10%
below the brightness you have set and lifts up to 30% above it. Above 80%
brightness there is little room left to lift into, so it dips up to 20% instead
to keep the shimmer visible.

How much of that lift you actually see depends on the colour. An LED cannot go
brighter than full, so the lift is capped at whatever headroom the brightest
channel has left, which keeps the hue from shifting as it brightens. Deeper
colours get the whole 30%; a colour already at full, such as pure white, only
dips.

It has its own **Shimmer speed**, separate from a theme's **Theme animation speed**, so
a slowly drifting rainbow can carry a quick twinkle or the other way round.
Turning it on makes the display animated whatever theme is selected.

## Background animations

Separate from the hourly cuckoo: a background animation plays continuously
*behind* the time rather than taking over the face. The lit words are drawn over
it at full strength, so the time stays readable while the animation moves around
it. Switch it on in the interface and pick one.

The two sets are kept apart. Backgrounds live in `raspberry-pi/backgrounds/` and
the hourly animations in `raspberry-pi/gifs/`; neither appears in the other's
picker. Five backgrounds ship with the clock:

| | |
| --- | --- |
| `aurora` | slow bands of green and violet |
| `drift` | a soft field of blues and teals |
| `embers` | warm sparks rising |
| `nebula` | a magenta and indigo cloud, turning slowly |
| `ripple` | overlapping rings, like rain on water |

They are built for the job: even coverage, slow movement and a seamless loop,
since a background has no beginning or end to hide.

A filename beginning with `_` is kept in the folder but left out of the picker,
which is how an animation is retired without deleting it. The same goes for the
hourly ones.

**Background brightness** is measured against the time, not against full scale.
At 25% the animation's brightest pixel is a quarter as bright as the brightest
lit letter, and that ratio holds whichever theme is running - so a dark theme
like the Night phase is not swamped by a vivid animation behind it.

Drop your own files into `raspberry-pi/backgrounds/` and they appear in the
picker too. Setting a background makes the display animated, so it redraws
continuously.

## Animations

Thirteen animations ship with the clock — `sun`, `moon`, `star`, `smiley`,
`rocket`, `snow`, `rain`, `matrix`, `fireworks`, `swirl`, `wave`, `confetti` and
the original `heart_art_small` — one for each hour of the dial, plus a spare to
choose between. One plays at the top of every hour and then the clock goes back
to showing the time.

### Choosing one per hour

Set **On the hour, play** to *A specific animation each hour* and a list of the twelve
hours appears, each with its own picker. Leave an hour on *Random* and it picks
one at random when that hour comes round. The mapping uses the clock's 12-hour
dial, so an animation set against 3 plays at both 3am and 3pm.

### Previewing

Animations play in the preview at the top of the page, so you can see them
without waiting for the hour to turn:

- **▶** beside an animation plays that one.
- **Preview animation** plays whichever one the current settings would choose at
  this hour — the fixed one, this hour's assignment, or a random
  pick, depending on the mode.

They are masked by the letters, exactly as on the real clock, where the light
only escapes through the letter cutouts. So what you see is what the animation
will actually look like, not the raw artwork.

Neither button touches the LEDs. To play one on the clock itself, use the API:

```bash
curl -X POST http://wordclock.local:8080/api/gif/play -d '{"name":"sun.gif"}'
```

Put your own image files in `raspberry-pi/gifs/` and they appear in every picker
straight away.

```bash
scp my-animation.gif pi@wordclock.local:~/word-clock/raspberry-pi/gifs/
```

- Supported: `.gif` (animated or still), `.png`, `.jpg`, `.bmp`, `.webp`
- Frames are scaled to the 12x11 grid; images already close to that size look
  sharpest, since the clock has only 132 pixels to work with
- Animated GIFs play at the frame delays stored in the file and loop until the
  configured play time is up
- Fully transparent pixels are shown as black
- New files are picked up without restarting the service

## Time zone and daylight saving

The Raspberry Pi has no battery-backed clock, so it gets the time from the
network in UTC and converts it locally. Setting a time zone by name means
daylight saving changes are applied automatically from the system tz database.

In the web interface, the time zone is a dropdown listing every zone the Pi
actually has data for (around 420), grouped by region. Choosing one applies
immediately. **System default** follows whatever `timedatectl` is set to.

### The Detect button

**Detect** fills in the time zone of the phone or laptop you are browsing from,
which your device sets from its own location. This is exact and needs no
permission prompt, so it is the recommended way to set the clock.

If your browser cannot report a zone, Detect falls back to asking for your
location and matching the closest zone on the Pi — offline, from the coordinates
in the system `zoneinfo` database, with nothing sent to the internet. Two caveats:

- Browsers only expose location over `https`, and the clock is served over plain
  `http`, so this fallback is refused in normal use. The interface says so rather
  than failing silently.
- Matching is by nearest zone centre, which can pick a neighbouring country's
  zone close to a border. It is offered as a suggestion — check the dropdown
  afterwards.

You can also set the zone system-wide, which is what **System default** uses:

```bash
sudo timedatectl set-timezone America/New_York
```

If the clock is an hour out twice a year, the time zone is the first thing to
check.

## Settings file

`raspberry-pi/wordclock.json` holds everything the web interface changes. You can
edit it directly and restart the service (`sudo systemctl restart
word_clock.service`); invalid values are reported in the log and ignored rather
than crashing the clock.

```json
{
  "display_on": true,
  "brightness": 0.5,
  "theme": "gradient",
  "sparkle": false,
  "color": [255, 255, 255],
  "secondary_color": [0, 80, 255],
  "animation_speed": 0.05,
  "shimmer_speed": 0.05,
  "timezone": "Europe/Warsaw",
  "gifs_enabled": true,
  "gif_mode": "random",
  "gif_name": "",
  "gif_duration": 6.0,
  "background_enabled": false,
  "background": "",
  "background_brightness": 0.25,
  "hour_gifs": {
    "1": "sun.gif",
    "2": "",
    "12": "moon.gif"
  }
}
```

`gif_mode` is one of `random`, `fixed` or `hourly`. `hour_gifs`
only applies to `hourly`; an empty value means that hour picks at random.

## Command line options

```
--pin D12            GPIO pin the LEDs are on (required)
--brightness 0.5     Override the saved brightness at startup
--timezone Zone/Name Override the saved time zone at startup
--gif-dir PATH       Directory of animations (default raspberry-pi/gifs)
--gif FILE           Play one fixed animation (the original single-GIF form)
--config PATH        Settings file (default raspberry-pi/wordclock.json)
--web-host ADDR      Address the web interface binds to (default 0.0.0.0)
--web-port PORT      Port for the web interface (default 8080)
--no-web             Do not start the web interface
```

`--brightness` and `--timezone` write to the settings file, so they override
whatever the web interface last saved. The installed service does not pass them,
which is what keeps your web interface settings in place across restarts.

## HTTP API

Handy for scripting or a home automation system:

```bash
curl http://wordclock.local:8080/api/state
curl http://wordclock.local:8080/api/timezones
curl -X POST http://wordclock.local:8080/api/settings -d '{"theme":"cycle","brightness":0.2}'
curl -X POST http://wordclock.local:8080/api/gif/play -d '{"name":"sun.gif"}'
curl -X POST http://wordclock.local:8080/api/gif/frames -d '{"name":"sun.gif"}'
curl -X POST http://wordclock.local:8080/api/settings -d '{"gif_mode":"hourly","hour_gifs":{"1":"sun.gif"}}'
curl -X POST http://wordclock.local:8080/api/timezone/locate -d '{"latitude":52.23,"longitude":21.01}'
curl -X POST http://wordclock.local:8080/api/preview -d '{"theme":"rainbow"}'
```

`POST /api/settings` accepts any subset of the settings keys, applies them to the
clock, and returns the full state with anything it rejected listed under
`errors`. `GET /api/timezones` lists the selectable zones, and
`POST /api/timezone/locate` returns the zone nearest to a coordinate.

`POST /api/preview` is the read-only one: give it any subset of the settings and
it returns the letter grid plus a `colors` grid of what the face would look like,
without changing anything on the clock. `POST /api/gif/frames` likewise returns
an animation's frames already scaled to the 12x11 grid, each with its delay in
milliseconds, and changes nothing.

`hour_gifs` accepts a partial object — send just the hours you want to change
and the rest are left as they were.

## Troubleshooting

```bash
sudo systemctl status word_clock.service
sudo journalctl -u word_clock.service -f
```

- **Nothing lights up**: check the display is on in the web interface and that
  brightness is not at 0.
- **Web page unreachable**: confirm the service is running and that you are using
  the right port; the installer prints the URL when it finishes.
- **Time is wrong by a whole hour**: the time zone is wrong — see above.
- **Time is wrong by minutes**: the Pi has not reached an NTP server. Check with
  `timedatectl` that "System clock synchronized" is yes.
