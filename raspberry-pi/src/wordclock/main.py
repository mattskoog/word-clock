import argparse
import os
import signal
import sys
import time

import gif
import themes
import timekeeper
import webui
from clock_display_hal import ClockDisplayHAL
import weather
from gif import GifLibrary
from settings import Settings
from word_clock import WordClock

PACKAGE_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIRECTORY = os.path.abspath(os.path.join(PACKAGE_DIRECTORY, "..", ".."))
DEFAULT_CONFIG_PATH = os.path.join(PROJECT_DIRECTORY, "wordclock.json")
DEFAULT_GIF_DIRECTORY = os.path.join(PROJECT_DIRECTORY, "gifs")
DEFAULT_BACKGROUND_DIRECTORY = os.path.join(PROJECT_DIRECTORY, "backgrounds")
DEFAULT_WEATHER_DIRECTORY = os.path.join(PROJECT_DIRECTORY, "weather")

ANIMATED_TICK = 0.1  # redraw interval while an animated theme is running
IDLE_TICK = 0.5


def run(clock_display_hal, word_clock, settings, gif_library):
    last_brightness = None
    display_is_clear = False
    # Disarmed for the rest of minute zero once the hourly animation has run.
    hourly_animation_armed = True

    while True:
        current = settings.snapshot()

        if current["brightness"] != last_brightness:
            # Applied to the words when the frame is built, not by the driver,
            # so it dims the time without touching the background.
            last_brightness = current["brightness"]
            word_clock.invalidate()

        if not current["display_on"]:
            if not display_is_clear:
                clock_display_hal.clear_pixels()
                word_clock.invalidate(cleared=True)
                display_is_clear = True
            time.sleep(IDLE_TICK)
            continue
        display_is_clear = False

        moment = timekeeper.now(current["timezone"])
        top_of_the_hour = moment.minute == 0
        if not top_of_the_hour:
            hourly_animation_armed = True

        clock_hour = moment.hour % 12 or 12
        animation = None
        requested = settings.take_gif_request()
        if requested is not None:
            animation = gif_library.path_for(requested) or gif_library.choose(
                current["gif_mode"], current["gif_name"],
                current["hour_gifs"], clock_hour,
            )
        elif top_of_the_hour and hourly_animation_armed and current["gifs_enabled"]:
            hourly_animation_armed = False
            animation = gif_library.choose(
                current["gif_mode"], current["gif_name"],
                current["hour_gifs"], clock_hour,
            )

        if animation:
            gif.play(
                animation,
                clock_display_hal,
                duration=current["gif_duration"],
                should_stop=lambda: not settings.get("display_on"),
                # The hourly animation takes the whole face, so it follows the
                # display brightness rather than running at full.
                scale=current["brightness"],
            )
            clock_display_hal.clear_pixels(show=False)
            word_clock.invalidate(cleared=True)

        word_clock.display_time()
        time.sleep(ANIMATED_TICK if themes.is_animated(current) else IDLE_TICK)


def main(arguments):
    gif_directory = arguments.gif_dir
    startup_changes = {}

    # Keep the original --gif <file> form working by treating the file's folder
    # as the library and pinning that animation.
    if arguments.gif:
        gif_directory = os.path.dirname(os.path.abspath(arguments.gif)) or gif_directory
        startup_changes["gif_mode"] = "fixed"
        startup_changes["gif_name"] = os.path.basename(arguments.gif)
    if arguments.brightness is not None:
        startup_changes["brightness"] = arguments.brightness
    if arguments.timezone is not None:
        startup_changes["timezone"] = arguments.timezone

    gif_library = GifLibrary(gif_directory)
    # Backgrounds are a separate set: they play behind the time rather than
    # taking the face, so they are kept out of the hourly picker entirely.
    background_library = GifLibrary(arguments.background_dir)
    # The weather set is picked by conditions, never by hand, so it is not
    # offered to Settings for validation the way the other two are.
    weather_library = GifLibrary(arguments.weather_dir)
    settings = Settings(arguments.config, gif_names=gif_library.names,
                        background_names=background_library.names)
    if startup_changes:
        _, errors = settings.update(startup_changes)
        for key, message in errors.items():
            print(f"Ignoring --{key.replace('_', '-')}: {message}")

    # The driver stays at full: brightness is applied per layer in software.
    clock_display_hal = ClockDisplayHAL(arguments.pin, 1.0)
    weather_watch = weather.WeatherWatch(settings)
    word_clock = WordClock(clock_display_hal, settings, background_library,
                           weather_library, weather_watch)
    # Its own thread: a slow link must never hold up the clock face.
    weather_watch.start()

    print(f"Config: {arguments.config}")
    print(f"Animations: {gif_directory} ({len(gif_library.names())} found)")
    print(f"Backgrounds: {arguments.background_dir} ({len(background_library.names())} found)")
    print(f"Weather: {arguments.weather_dir} ({len(weather_library.names())} found)")
    print(f"Time zone: {settings.get('timezone') or 'system default'} "
          f"({timekeeper.describe(word_clock.now())})")

    if not arguments.no_web:
        webui.start(settings, gif_library, background_library, word_clock,
                    arguments.web_host, arguments.web_port, weather_watch)

    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    try:
        run(clock_display_hal, word_clock, settings, gif_library)
    except KeyboardInterrupt:
        pass
    finally:
        clock_display_hal.clear_pixels()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the Word Clock.")
    parser.add_argument("--pin", type=str, required=True,
                        help="The PIN number for the clock display, e.g. D12.")
    parser.add_argument("--brightness", type=float, default=None,
                        help="Display brightness 0-1. Overrides the saved setting.")
    parser.add_argument("--timezone", type=str, default=None,
                        help="IANA time zone, e.g. Europe/Warsaw. Overrides the saved setting.")
    parser.add_argument("--gif-dir", type=str, default=DEFAULT_GIF_DIRECTORY,
                        help="Directory of animations to play on the hour.")
    parser.add_argument("--weather-dir", type=str, default=DEFAULT_WEATHER_DIRECTORY,
                        help="directory of animations chosen by the weather")
    parser.add_argument("--background-dir", type=str, default=DEFAULT_BACKGROUND_DIRECTORY,
                        help="Directory of animations that play behind the time.")
    parser.add_argument("--gif", type=str, default=None,
                        help="Play one specific animation file (legacy single-GIF mode).")
    parser.add_argument("--config", type=str, default=DEFAULT_CONFIG_PATH,
                        help="Where settings changed from the web interface are stored.")
    parser.add_argument("--web-host", type=str, default="0.0.0.0",
                        help="Address the web interface listens on.")
    parser.add_argument("--web-port", type=int, default=8080,
                        help="Port the web interface listens on.")
    parser.add_argument("--no-web", action="store_true",
                        help="Do not start the web interface.")
    main(parser.parse_args())
