import time

import themes
import timekeeper
from clock_display_hal import ClockDisplayHAL

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

    def invalidate(self):
        """Force the next render to redraw, e.g. after an animation played."""
        self._last_signature = None

    def word_colors(self, current, moment=None):
        """[(word, color)] for the given settings, without touching hardware.

        The LED render and the web preview both go through here, so what the
        browser shows cannot drift from what the clock actually displays.
        """
        theme = themes.get(current["theme"])
        moment = moment or timekeeper.now(current["timezone"])
        words = self.words_for(moment)
        elapsed = time.monotonic()

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
            color = theme.color_for(context)
            if current["sparkle"]:
                color = themes.apply_sparkle(color, context)
            colored.append((word, color))
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
        if not force and not themes.is_animated(current) and signature == self._last_signature:
            return

        self.clock_display_hal.clear_pixels(show=False)
        for word, color in self.word_colors(current, moment):
            self.clock_display_hal.display_word(word, color)
        self.clock_display_hal.show()
        self._last_signature = signature
