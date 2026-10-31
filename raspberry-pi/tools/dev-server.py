"""Run the clock on a laptop, with the LEDs faked.

The web interface is most of this project, and waiting on a Pi to look at a
slider is a bad way to spend an afternoon. This boots the real thing - the
real render loop, the real settings, the real preview - against the stubbed
`board` and `neopixel` modules the tests already use, so everything behaves
as it does on hardware except that nothing lights up.

    python3 tools/dev-server.py
    python3 tools/dev-server.py --port 8099 --config ~/scratch/wordclock.json

Settings go to a throwaway file by default, so running this can never disturb
a clock's real configuration. Pass --config to keep them between runs.

Updates are off unless asked for, and that is deliberate: the Updates panel
operates on the checkout it is running from, and pressing the button on a dev
box would fast-forward your own working copy and try to restart a service
that is not there.
"""

import argparse
import os
import sys
import tempfile
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.abspath(os.path.join(HERE, ".."))
# The stubs come first: they stand in for the Raspberry Pi libraries, which do
# not install on a laptop and would talk to real hardware if they did.
sys.path[:0] = [os.path.join(PROJECT, "tests", "stubs"),
                os.path.join(PROJECT, "src", "wordclock")]

import main as wordclock_main  # noqa: E402
import provisioning  # noqa: E402
import updater  # noqa: E402
import weather  # noqa: E402
import webui  # noqa: E402
from clock_display_hal import ClockDisplayHAL  # noqa: E402
from gif import GifLibrary  # noqa: E402
from settings import Settings  # noqa: E402
from word_clock import WordClock  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--port", type=int, default=8099,
                        help="port to serve on (default 8099, to stay clear "
                             "of a real clock on 8080)")
    parser.add_argument("--host", default="127.0.0.1",
                        help="interface to bind (default localhost only)")
    parser.add_argument("--config", default=None,
                        help="settings file to use; a throwaway one by default")
    parser.add_argument("--network-state", default=None,
                        help="file to read comitup's state from, to exercise "
                             "the setup display")
    parser.add_argument("--updates", action="store_true",
                        help="enable the Updates panel against this checkout. "
                             "Off by default: applying one here would move "
                             "your own working copy.")
    arguments = parser.parse_args()

    config = arguments.config or os.path.join(
        tempfile.mkdtemp(prefix="wordclock-dev-"), "wordclock.json")

    gifs = GifLibrary(os.path.join(PROJECT, "gifs"))
    backgrounds = GifLibrary(os.path.join(PROJECT, "backgrounds"))
    weather_gifs = GifLibrary(os.path.join(PROJECT, "weather"))
    settings = Settings(config, gif_names=gifs.names,
                        background_names=backgrounds.names)

    clock_display_hal = ClockDisplayHAL("D12", 1.0)
    weather_watch = weather.WeatherWatch(settings)
    network = provisioning.NetworkDisplay(arguments.network_state or "")
    update_watch = (updater.UpdateWatch(port=arguments.port)
                    if arguments.updates else None)

    word_clock = WordClock(clock_display_hal, settings, backgrounds,
                           weather_gifs, weather_watch)
    weather_watch.start()
    if update_watch:
        update_watch.start()

    server = webui.start(settings, gifs, backgrounds, word_clock,
                         arguments.host, arguments.port, weather_watch,
                         update_watch)
    if server is None:
        raise SystemExit(f"Could not listen on {arguments.host}:{arguments.port}")

    # The real loop, so hourly animations, crossfades and the setup display
    # behave exactly as they do on a Pi.
    threading.Thread(target=wordclock_main.run,
                     args=(clock_display_hal, word_clock, settings, gifs,
                           network),
                     daemon=True, name="render").start()

    # Flushed, so the banner shows up immediately when this is piped to a log
    # or run in the background, which is how a dev server usually gets run.
    print(f"Clock on http://{arguments.host}:{arguments.port}", flush=True)
    print(f"Settings: {config}", flush=True)
    print(f"Updates:  {'on' if update_watch else 'off (pass --updates)'}",
          flush=True)
    print("The LEDs are stubbed; what the strip would show is in memory only.",
          flush=True)
    try:
        while True:
            time.sleep(3600)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
