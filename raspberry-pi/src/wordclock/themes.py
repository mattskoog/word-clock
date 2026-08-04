"""Color themes.

A theme decides what color every highlighted word gets. Themes marked as
animated are redrawn continuously by the main loop; the others are only redrawn
when the displayed phrase changes.
"""

import colorsys
import math

from clock_display_hal import ClockDisplayHAL


def hsv_color(hue, saturation=1.0, value=1.0):
    red, green, blue = colorsys.hsv_to_rgb(hue % 1.0, saturation, value)
    return (int(red * 255), int(green * 255), int(blue * 255))


def blend(first, second, amount):
    """Linear blend, amount 0.0 gives `first` and 1.0 gives `second`."""
    amount = min(1.0, max(0.0, amount))
    return tuple(int(a + (b - a) * amount) for a, b in zip(first, second))


class WordContext:
    """Everything a theme may need to color a single word."""

    def __init__(self, word, start_led, end_led, position, word_count, settings, elapsed,
                 moment=None):
        self.word = word
        self.start_led = start_led
        self.end_led = end_led
        self.position = position
        self.word_count = word_count
        self.settings = settings
        self.elapsed = elapsed
        self.moment = moment  # the displayed time, for themes that vary by hour

    @property
    def row(self):
        """Grid row of the word, 0 at the bottom of the display."""
        return self.start_led // ClockDisplayHAL.WIDTH

    @property
    def vertical_fraction(self):
        """0.0 on the bottom row of the display, 1.0 on the top row."""
        return self.row / (ClockDisplayHAL.HEIGHT - 1)

    @property
    def depth_from_top(self):
        """0.0 on the top row of the display, 1.0 on the bottom row.

        Themes that read like a list of colors should use this, so the first
        color the user picks is the one they see at the top of the clock.
        """
        return 1.0 - self.vertical_fraction

    @property
    def grid_fraction(self):
        return self.start_led / ClockDisplayHAL.NUM_LEDS

    @property
    def word_fraction(self):
        if self.word_count < 2:
            return 0.0
        return self.position / (self.word_count - 1)


class Theme:
    name = ""
    label = ""
    animated = False

    def color_for(self, context):
        raise NotImplementedError


THEMES = {}


def register(theme_class):
    THEMES[theme_class.name] = theme_class()
    return theme_class


def get(name):
    """Look up a theme, falling back to the default if the name is unknown."""
    return THEMES.get(name) or THEMES[DEFAULT_THEME]


def names():
    return list(THEMES)


def catalog():
    """Theme metadata for the web UI."""
    return [
        {"name": theme.name, "label": theme.label, "animated": theme.animated}
        for theme in THEMES.values()
    ]


# Each phase is (start hour, end hour, label, color at the top of the face,
# color at the bottom), roughly following the sky at that time of day. Night
# wraps past midnight.
DAY_PHASES = (
    (5, 8, "Early morning", (45, 60, 130), (255, 170, 115)),
    (8, 12, "Morning", (70, 160, 255), (255, 225, 150)),
    (12, 17, "Afternoon", (251, 191, 36), (253, 224, 71)),  # amber to yellow
    (17, 21, "Evening", (130, 55, 175), (255, 105, 35)),
    (21, 5, "Night", (15, 25, 85), (85, 45, 135)),
)


def phase_for(hour):
    """The phase of the day covering `hour`."""
    for start, end, label, top, bottom in DAY_PHASES:
        within = start <= hour < end if start < end else (hour >= start or hour < end)
        if within:
            return label, top, bottom
    return DAY_PHASES[-1][2:]


@register
class PhasesTheme(Theme):
    name = "phases"
    label = "Phases of the day"

    def color_for(self, context):
        hour = context.moment.hour if context.moment else 12
        _, top, bottom = phase_for(hour)
        return blend(top, bottom, context.depth_from_top)


@register
class SolidTheme(Theme):
    name = "solid"
    label = "Solid color"

    def color_for(self, context):
        return tuple(context.settings["color"])


@register
class GradientTheme(Theme):
    name = "gradient"
    label = "Gradient"

    def color_for(self, context):
        # Runs top to bottom, matching the order the two colors are shown in.
        return blend(
            tuple(context.settings["color"]),
            tuple(context.settings["secondary_color"]),
            context.depth_from_top,
        )


@register
class RainbowTheme(Theme):
    name = "rainbow"
    label = "Rainbow"
    animated = True

    def color_for(self, context):
        drift = context.elapsed * context.settings["animation_speed"]
        return hsv_color(context.grid_fraction + drift)


@register
class CycleTheme(Theme):
    name = "cycle"
    label = "Color cycle"
    animated = True

    def color_for(self, context):
        return hsv_color(context.elapsed * context.settings["animation_speed"])


@register
class SpectrumTheme(Theme):
    name = "spectrum"
    label = "Spectrum"

    def color_for(self, context):
        # An even spread of hues across the lit words. Unlike Random this is
        # stable, so the face keeps the same colors until the time changes.
        return hsv_color(context.word_fraction * SPECTRUM_SPREAD)


DEFAULT_THEME = PhasesTheme.name

# How much of the color wheel the spectrum theme covers end to end.
SPECTRUM_SPREAD = 0.8

# Sparkle is not a theme but an effect layered over whichever theme is chosen,
# so every theme can shimmer.
SPARKLE_FLOOR = 0.25  # dimmest point of a word's shimmer, as a fraction
SPARKLE_RATE = 8.0  # shimmer cycles per second at animation_speed 1.0


def _sparkle_phase(word):
    """A stable 0-1 offset per word, so words shimmer out of step."""
    total = sum(ord(character) * (index + 1) for index, character in enumerate(word))
    return (total % 997) / 997.0


def apply_sparkle(color, context):
    """Modulate a color's brightness over time, keeping its hue."""
    speed = context.settings["animation_speed"] * SPARKLE_RATE
    wave = 0.5 + 0.5 * math.sin(
        2 * math.pi * (context.elapsed * speed + _sparkle_phase(context.word))
    )
    scale = SPARKLE_FLOOR + (1.0 - SPARKLE_FLOOR) * wave
    return tuple(int(channel * scale) for channel in color)


def is_animated(settings):
    """True when the display has to be redrawn continuously."""
    return get(settings["theme"]).animated or bool(settings.get("sparkle"))
