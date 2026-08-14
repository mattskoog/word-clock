"""Live weather, used to pick the background animation.

Two services, both free and neither needing a key, so nothing secret ever has
to live on the Pi:

- Open-Meteo for conditions. It serves national weather service output rather
  than a model of its own, which for a US location means NOAA's HRRR at 3km,
  refreshed hourly.
- Zippopotam to turn a zip code into coordinates. This runs once, when the zip
  is saved, and the result is stored in settings; it is never a live dependency
  of the running clock.

Nothing here may raise into the render loop. A failed fetch keeps the last good
reading, and a clock that has never reached the network simply reports no
condition, which the caller treats as "use the chosen background instead".
"""

import json
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
GEOCODE_URL = "https://api.zippopotam.us/{country}/{postcode}"
REQUEST_TIMEOUT = 10

# Open-Meteo publishes a new reading every 900s, so polling faster only spends
# the Pi's network for nothing.
REFRESH_SECONDS = 900
# After a failure, come back sooner than the normal cadence but not so fast
# that a flapping connection turns into a request loop.
RETRY_SECONDS = 120

# The service is identified in the User-Agent as a courtesy to a free API.
USER_AGENT = "word-clock/1.0 (+https://github.com/mattskoog/word-clock)"

# WMO 4677 weather codes, collapsed to the conditions we have artwork for.
# Ranges rather than every code: the distinction between slight and heavy rain
# is not one a 12x11 grid can show.
CONDITIONS = (
    ("clear", (0, 1)),
    ("cloud", (2, 3)),
    ("fog", (45, 48)),
    ("drizzle", (51, 53, 55, 56, 57)),
    ("rain", (61, 63, 65, 66, 67, 80, 81, 82)),
    ("snow", (71, 73, 75, 77, 85, 86)),
    ("storm", (95, 96, 99)),
)

# Drizzle looks like rain at this size, so it shares the animation. Kept as its
# own condition above so the interface can still say which it is.
ANIMATIONS = {
    "clear": "clear.gif",
    "cloud": "cloud.gif",
    "fog": "fog.gif",
    "drizzle": "rain.gif",
    "rain": "rain.gif",
    "snow": "snow.gif",
    "storm": "storm.gif",
}

# Only a clear sky reads differently after dark; rain is rain either way.
NIGHT_ANIMATIONS = {"clear": "clear_night.gif"}

LABELS = {
    "clear": "Clear",
    "cloud": "Cloudy",
    "fog": "Fog",
    "drizzle": "Drizzle",
    "rain": "Rain",
    "snow": "Snow",
    "storm": "Thunderstorm",
}


class WeatherError(Exception):
    """A lookup failed in a way worth showing the user."""


def condition_for(code):
    """The condition name for a WMO code, or None if it is not one we map."""
    try:
        code = int(code)
    except (TypeError, ValueError):
        return None
    for name, codes in CONDITIONS:
        if code in codes:
            return name
    return None


def animation_for(condition, is_day=True):
    """The background filename for a condition, or '' if there is none."""
    if not condition:
        return ""
    if not is_day and condition in NIGHT_ANIMATIONS:
        return NIGHT_ANIMATIONS[condition]
    return ANIMATIONS.get(condition, "")


def label_for(condition, is_day=True):
    """How the condition reads in the interface."""
    if not condition:
        return ""
    label = LABELS.get(condition, condition.title())
    if condition == "clear" and not is_day:
        return "Clear night"
    return label


def _fetch_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=REQUEST_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8"))


def locate(postcode, country="us"):
    """Turn a postcode into (latitude, longitude, place name).

    Raises WeatherError with something worth showing the user, since this runs
    while they are watching, unlike the background refresh.
    """
    postcode = str(postcode or "").strip()
    if not postcode:
        raise WeatherError("Enter a zip code")
    url = GEOCODE_URL.format(country=urllib.parse.quote(country),
                             postcode=urllib.parse.quote(postcode))
    try:
        payload = _fetch_json(url)
    except urllib.error.HTTPError as error:
        # The service answers 404 for a postcode it does not know, which is a
        # user error rather than an outage.
        if error.code == 404:
            raise WeatherError(f"No such zip code: {postcode}")
        raise WeatherError(f"Lookup failed ({error.code})")
    except (urllib.error.URLError, OSError):
        raise WeatherError("Could not reach the lookup service")
    except ValueError:
        raise WeatherError("The lookup service sent something unreadable")

    places = payload.get("places") or []
    if not places:
        raise WeatherError(f"No such zip code: {postcode}")
    place = places[0]
    try:
        latitude = float(place["latitude"])
        longitude = float(place["longitude"])
    except (KeyError, TypeError, ValueError):
        raise WeatherError("The lookup service sent no coordinates")

    name = place.get("place name") or postcode
    state = place.get("state abbreviation") or ""
    return latitude, longitude, f"{name}, {state}".strip(" ,")


def read(latitude, longitude):
    """One current reading as (condition, is_day, temperature_c).

    Raises WeatherError; callers in the render loop must catch it.
    """
    query = urllib.parse.urlencode({
        "latitude": f"{float(latitude):.4f}",
        "longitude": f"{float(longitude):.4f}",
        # Only the three fields we use, which keeps the response a few hundred
        # bytes rather than a few kilobytes.
        "current": "weather_code,is_day,temperature_2m",
    })
    try:
        payload = _fetch_json(f"{FORECAST_URL}?{query}")
    except (urllib.error.URLError, OSError) as error:
        raise WeatherError(f"Could not reach the weather service: {error}")
    except ValueError:
        raise WeatherError("The weather service sent something unreadable")

    current = payload.get("current") or {}
    condition = condition_for(current.get("weather_code"))
    if not condition:
        raise WeatherError(f"Unknown weather code {current.get('weather_code')!r}")
    return condition, bool(current.get("is_day", 1)), current.get("temperature_2m")


class WeatherWatch:
    """Keeps a current reading, refreshed on its own thread.

    The render loop reads `animation()` on every tick, so the fetch must never
    happen there - a Pi Zero on a slow link would stall the clock face for as
    long as the request took.
    """

    def __init__(self, settings, refresh_seconds=REFRESH_SECONDS):
        self._settings = settings
        self._refresh_seconds = refresh_seconds
        self._lock = threading.Lock()
        self._condition = None
        self._is_day = True
        self._temperature = None
        self._error = ""
        self._checked_at = None
        self._wake = threading.Event()
        self._thread = None

    # -- what the rest of the clock reads ----------------------------------

    def animation(self):
        """The background filename the weather calls for, or '' if unknown."""
        with self._lock:
            condition, is_day = self._condition, self._is_day
        return animation_for(condition, is_day)

    def status(self):
        """What the interface shows about the current reading."""
        with self._lock:
            return {
                "condition": self._condition or "",
                "label": label_for(self._condition, self._is_day),
                "is_day": self._is_day,
                "temperature_c": self._temperature,
                "error": self._error,
                "checked_at": self._checked_at,
            }

    def refresh_now(self):
        """Ask for an immediate refresh, e.g. after the zip code changed."""
        self._wake.set()

    # -- the thread --------------------------------------------------------

    def start(self):
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, name="weather",
                                        daemon=True)
        self._thread.start()

    def _run(self):
        while True:
            waited = self._refresh_seconds if self._check() else RETRY_SECONDS
            # Waiting on the event rather than sleeping means a zip code change
            # takes effect at once instead of at the end of the cycle.
            self._wake.wait(waited)
            self._wake.clear()

    def _check(self):
        """One refresh. Returns True if it produced a reading."""
        values = self._settings.snapshot()
        if values.get("background_source") != "weather":
            return True  # nothing to do, come back at the normal cadence
        latitude = values.get("weather_latitude")
        longitude = values.get("weather_longitude")
        if latitude is None or longitude is None:
            self._record_error("No location set")
            return True

        try:
            condition, is_day, temperature = read(latitude, longitude)
        except WeatherError as error:
            # The last good reading is kept: a dropped connection should not
            # blank the face, it should just stop it changing.
            self._record_error(str(error))
            return False

        with self._lock:
            self._condition = condition
            self._is_day = is_day
            self._temperature = temperature
            self._error = ""
            self._checked_at = time.time()
        return True

    def _record_error(self, message):
        with self._lock:
            self._error = message
            self._checked_at = time.time()
