# Background animations

These play **behind the time**, continuously, dimmed so the words stay readable.
They are deliberately kept apart from `../gifs/`, which holds the animations that
take over the whole face on the hour — nothing here appears in the hourly picker,
and nothing there appears in the background picker.

Five ship with the clock:

| | |
| --- | --- |
| `aurora` | slow bands of green and violet leaning across the face |
| `drift` | a soft field of blues and teals turning slowly |
| `embers` | warm sparks rising over a faint glow at the base |
| `nebula` | a magenta and indigo cloud, turning slowly |
| `ripple` | rings from several points, overlapping as they spread |

## Shelving one

A filename beginning with `_` stays in the folder but is left out of the picker,
so one can be retired without deleting it and brought back with a rename. The
same applies to `../gifs/`.

## What makes a good one

A background is judged by what it does *behind text*, which is a different job
to an hourly animation:

- **Even coverage.** No recognisable subject and no strong centre, or the eye
  locks onto it instead of reading the time.
- **Slow movement.** These run continuously, so anything brisk gets tiring.
- **A seamless loop.** There is no start or end to hide, so a jump at the wrap
  is obvious.

Brightness is levelled for you: whatever an animation was drawn at, the clock
normalises it against its own brightest pixel, so *Animation brightness* means
the same thing whichever one you pick. It is separate from *Text brightness*,
so the two sliders never pull on each other.

## Adding your own

Drop any supported image in here and it appears in the background picker. The
directory is rescanned as it is read, so no restart is needed.

## Regenerating these

They are drawn by a script, straight at 12x11:

```bash
python3 tools/make_backgrounds.py
```

It overwrites only the five it generates, so anything you added by hand under a
different name is left alone.
