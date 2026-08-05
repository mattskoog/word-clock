import time

import themes
import timekeeper
from clock_display_hal import ClockDisplayHAL

# How long the clock takes to dissolve from one time into the next. This is a
# property of the LEDs only; the web preview switches straight over.
CROSSFADE_SECONDS = 0.5
CROSSFADE_INTERVAL = 0.025  # aimed at ~20 steps, fewer on slower hardware

HOUR_NAMES = [
    "twelve", "one", "two", "three", "four", "five",
    "six", "seven", "eight", "nine", "ten", "eleven",
]

WORD_LABELS = {
    "IT": "it",
    "IS": "is",
    "OCLOCK": "o'clock",
    "PAST": "past",
    "TO": "to",
    "MINUTES": "minutes",
    "FIVE": "five",
    "TEN": "ten",
    "FIFTEEN": "fifteen",
    "TWENTY": "twenty",
    "TWENTYFIVE": "twenty five",
    "THIRTY": "thirty",
}


class WordClock:
    def __init__(self, clock_display_hal, settings):
        self.clock_display_hal = clock_display_hal
        self.settings = settings
        self._last_signature = None
        self._last_frame = None  # what the LEDs are showing, for the crossfade
        self._paused_for = 0.0  # animation time skipped while crossfading

    def _elapsed(self):
        """The animation clock, with time spent mid-crossfade taken out.

        Holding this still freezes every moving theme at once - the rainbow
        drift, the color cycle and the sparkle all read from it - and skipping
        the frozen span afterwards means they resume where they left off
        rather than jumping ahead by the length of the fade.
        """
        return time.monotonic() - self._paused_for

    def get_minutes_word(self, minute):
        if minute < 5:
            return "OCLOCK"
        elif minute < 10:
            return "FIVE"
        elif minute < 15:
            return "TEN"
        elif minute < 20:
            return "FIFTEEN"
        elif minute < 25:
            return "TWENTY"
        elif minute < 30:
            return "TWENTYFIVE"
        elif minute < 35:
            return "THIRTY"
        elif minute < 40:
            return "TWENTYFIVE"
        elif minute < 45:
            return "TWENTY"
        elif minute < 50:
            return "FIFTEEN"
        elif minute < 55:
            return "TEN"
        else:
            return "FIVE"

    def words_for(self, moment):
        """The words to light up, in reading order."""
        hour = moment.hour % 12 or 12
        minute = moment.minute
        words = ["IT", "IS"]

        if minute < 5:
            words.append(f"HOUR_{hour}")
            words.append("OCLOCK")
            return words

        words.append(self.get_minutes_word(minute))
        words.append("MINUTES")
        if minute < 35:
            words.append("PAST")
        else:
            words.append("TO")
            hour = (hour + 1) % 12 or 12  # Adjust hour for "to" display
        words.append(f"HOUR_{hour}")
        return words

    def phrase(self, moment):
        """The lit words as readable text, for logs and the web UI."""
        readable = []
        for word in self.words_for(moment):
            if word.startswith("HOUR_"):
                readable.append(HOUR_NAMES[int(word[5:]) % 12])
            else:
                readable.append(WORD_LABELS.get(word, word.lower()))
        return " ".join(readable)

    def now(self):
        return timekeeper.now(self.settings.get("timezone"))

    def invalidate(self, cleared=False):
        """Force the next render to redraw, e.g. after an animation played.

        Pass cleared=True when the LEDs have been blanked, so the next redraw
        fades up from black instead of from a frame that is no longer showing.
        """
        self._last_signature = None
        if cleared:
            self._last_frame = [(0, 0, 0)] * ClockDisplayHAL.NUM_LEDS

    def frame_for(self, current, moment, elapsed=None):
        """One color per LED for the given settings and time."""
        frame = [(0, 0, 0)] * ClockDisplayHAL.NUM_LEDS
        elapsed = self._elapsed() if elapsed is None else elapsed
        sparkle = current["sparkle"]
        shimmer_speed = current["shimmer_speed"]
        brightness = current["brightness"]
        for word, color in self.word_colors(current, moment, elapsed):
            start, end = ClockDisplayHAL.WORDS_TO_LEDS[word]
            for index in range(start, end + 1):
                # Each letter carries its own phase, so the shimmer scatters
                # across the face rather than pulsing a word at a time.
                frame[index] = (
                    themes.apply_sparkle(color, index, elapsed, shimmer_speed, brightness)
                    if sparkle else color
                )
        return frame

    def _crossfade(self, previous, target):
        """Blend one frame into the next over CROSSFADE_SECONDS.

        Driven by the clock rather than by a step count, so a slow Pi drops
        frames instead of stretching the fade out. Returns how long it took.
        """
        start = time.monotonic()
        while True:
            step_started = time.monotonic()
            amount = (step_started - start) / CROSSFADE_SECONDS
            if amount >= 1.0:
                break
            self.clock_display_hal.display_frame(
                [themes.blend(was, now, amount) for was, now in zip(previous, target)]
            )
            self.clock_display_hal.show()
            time.sleep(max(0.0, CROSSFADE_INTERVAL - (time.monotonic() - step_started)))

        # Land exactly on the target rather than wherever the last step got to.
        self.clock_display_hal.display_frame(target)
        self.clock_display_hal.show()
        return time.monotonic() - start

    def word_colors(self, current, moment=None, elapsed=None):
        """[(word, color)] for the given settings, without touching hardware.

        One color per whole word, before sparkle: sparkle varies letter by
        letter, so it is applied in frame_for once words become LEDs. Pass
        `elapsed` to pin the animation clock to a particular instant.
        """
        theme = themes.get(current["theme"])
        moment = moment or timekeeper.now(current["timezone"])
        words = self.words_for(moment)
        elapsed = self._elapsed() if elapsed is None else elapsed

        colored = []
        for position, word in enumerate(words):
            led_range = ClockDisplayHAL.WORDS_TO_LEDS.get(word)
            if led_range is None:
                continue
            context = themes.WordContext(
                word=word,
                start_led=led_range[0],
                end_led=led_range[1],
                position=position,
                word_count=len(words),
                settings=current,
                elapsed=elapsed,
                moment=moment,
            )
            colored.append((word, theme.color_for(context)))
        return colored

    def display_time(self, force=False):
        """Redraw the clock face if anything about it changed."""
        current = self.settings.snapshot()
        moment = timekeeper.now(current["timezone"])
        words = self.words_for(moment)

        signature = (
            tuple(words),
            current["theme"],
            tuple(current["color"]),
            tuple(current["secondary_color"]),
            # Themes may vary with the hour, so a new hour is a new picture even
            # when the words happen to be identical.
            moment.hour,
        )
        changed = signature != self._last_signature
        if not force and not themes.is_animated(current) and not changed:
            return

        if changed and self._last_frame is not None:
            # Pin the animation clock so whatever is moving - a rainbow, a
            # color cycle, the sparkle - holds still while the words dissolve,
            # then carries on from the same point once the fade is done.
            frozen = self._elapsed()
            frame = self.frame_for(current, moment, elapsed=frozen)
            if frame != self._last_frame:
                self._paused_for += self._crossfade(self._last_frame, frame)
            else:
                self.clock_display_hal.display_frame(frame)
                self.clock_display_hal.show()
        else:
            frame = self.frame_for(current, moment)
            self.clock_display_hal.display_frame(frame)
            self.clock_display_hal.show()

        self._last_frame = frame
        self._last_signature = signature
