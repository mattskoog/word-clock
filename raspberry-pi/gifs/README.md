# Animations

Twelve animations ship with the clock, one for each hour of the dial:

| | | |
| --- | --- | --- |
| `confetti` | `fireworks` | `heart_art_small` |
| `moon` | `rain` | `rocket` |
| `smiley` | `snow` | `star` |
| `sun` | `swirl` | `wave` |

One plays at the top of every hour, then the clock goes back to showing the
time. Pick which one plays when in the web interface at `http://<your-pi>:8080`,
where **A specific animation each hour** lets you assign one per hour, and
the ▶ button next to each one plays it on the preview.

## Adding your own

Drop image files in here and they appear in the interface straight away — the
directory is rescanned every time an animation is chosen, so there is no need to
restart the service.

- Supported: `.gif` (animated or still), `.png`, `.jpg`, `.bmp`, `.webp`
- Any size works — frames are scaled down to the 12x11 LED grid, but images that
  are already tiny (roughly 12x11 up to 24x22) look sharpest
- Animated GIFs play at the frame delays stored in the file, looping until the
  configured play time is up
- Fully transparent pixels are shown as black (off)

## Regenerating the bundled set

All except `heart_art_small.gif` are drawn by a script, straight at 12x11 so
nothing is lost to scaling. Edit it to change the artwork:

```bash
python3 tools/make_animations.py
```

It overwrites only the files it generates, so anything you added by hand under a
different name is left alone.
