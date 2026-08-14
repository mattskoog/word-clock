"""Runtime settings shared by the render loop and the web UI.

The web server runs in its own thread and must never touch the LEDs directly,
so it only ever writes here; the render loop reads a snapshot on every tick and
applies whatever changed. Settings are persisted to a JSON file so they survive
a restart of the service.
"""

import json
import os
import threading

import themes
import timekeeper

GIF_MODES = ("random", "fixed", "hourly")
BACKGROUND_SOURCES = ("animation", "weather")
HOURS = tuple(str(hour) for hour in range(1, 13))

DEFAULTS = {
    "display_on": True,
    "brightness": 0.5,
    "theme": themes.DEFAULT_THEME,
    "sparkle": False,
    "color": [255, 255, 255],
    "secondary_color": [0, 80, 255],
    # The moving themes and the letter shimmer keep their own pace.
    "animation_speed": 0.05,
    "shimmer_speed": 0.05,
    "timezone": "",
    "gifs_enabled": True,
    "gif_mode": "random",
    "gif_name": "",
    "gif_duration": 6.0,
    # An animation running quietly behind the time, as opposed to the hourly
    # one that takes the whole face. The chosen animation is remembered while
    # the switch is off.
    "background_enabled": False,
    "background": "",
    "background_brightness": 0.25,
    # Where the background comes from: an animation picked by hand, or live
    # weather. The hand-picked one is remembered either way, and is what the
    # clock falls back to when the weather cannot be read.
    "background_source": "animation",
    # Resolved once when the zip is saved, so the running clock only ever has
    # to call the weather service, never the postcode lookup.
    "weather_zip": "",
    "weather_place": "",
    "weather_latitude": None,
    "weather_longitude": None,
    # Which animation plays at each hour, "1" through "12". An empty value
    # means "pick a random one for that hour".
    "hour_gifs": {hour: "" for hour in HOURS},
}


class ValidationError(ValueError):
    pass


def _boolean(value, key):
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in ("true", "false"):
        return value.lower() == "true"
    raise ValidationError(f"{key} must be true or false")


def _number(value, key, minimum, maximum):
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{key} must be a number")
    if number != number:  # NaN
        raise ValidationError(f"{key} must be a number")
    return min(maximum, max(minimum, number))


def _color(value, key):
    if isinstance(value, str):
        text = value.lstrip("#")
        if len(text) != 6:
            raise ValidationError(f"{key} must be a #rrggbb color")
        try:
            value = [int(text[i:i + 2], 16) for i in (0, 2, 4)]
        except ValueError:
            raise ValidationError(f"{key} must be a #rrggbb color")
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValidationError(f"{key} must be three numbers or a #rrggbb color")
    channels = []
    for channel in value:
        try:
            channels.append(min(255, max(0, int(channel))))
        except (TypeError, ValueError):
            raise ValidationError(f"{key} must contain numbers between 0 and 255")
    return channels


def _postcode(value, key):
    """A postcode, kept to what a postcode can contain.

    This is interpolated into a URL, so anything that is not a plain code is
    refused here rather than being escaped and sent on to the lookup service.
    """
    text = str(value or "").strip().upper()
    if not text:
        return ""
    if len(text) > 10 or not all(c.isalnum() or c in " -" for c in text):
        raise ValidationError(f"{key} must be a postcode, e.g. 60601")
    return text


def _choice(value, key, allowed):
    if value not in allowed:
        raise ValidationError(f"{key} must be one of: {', '.join(allowed)}")
    return value


def _copy(value):
    """Shallow copy so callers cannot mutate the stored settings in place."""
    if isinstance(value, list):
        return list(value)
    if isinstance(value, dict):
        return dict(value)
    return value


class Settings:
    def __init__(self, path, gif_names=lambda: [], background_names=lambda: []):
        self._path = path
        self._gif_names = gif_names
        self._background_names = background_names
        self._lock = threading.Lock()
        self._values = dict(DEFAULTS)
        self._pending_gif = None
        self.load()

    # -- persistence -------------------------------------------------------

    def load(self):
        if not self._path or not os.path.exists(self._path):
            return
        try:
            with open(self._path) as config_file:
                contents = config_file.read().strip()
            stored = json.loads(contents) if contents else {}
        except (OSError, ValueError) as error:
            print(f"Ignoring unreadable config {self._path}: {error}")
            return
        if not isinstance(stored, dict):
            print(f"Ignoring config {self._path}: expected a JSON object")
            return
        for key, value in stored.items():
            if key not in DEFAULTS:
                continue
            try:
                self._values[key] = self._clean(key, value)
            except ValidationError as error:
                print(f"Ignoring stored setting {key}: {error}")

    def save(self):
        if not self._path:
            return
        with self._lock:
            values = dict(self._values)
        directory = os.path.dirname(os.path.abspath(self._path))
        temporary = f"{self._path}.tmp"
        try:
            os.makedirs(directory, exist_ok=True)
            with open(temporary, "w") as config_file:
                json.dump(values, config_file, indent=2, sort_keys=True)
                config_file.write("\n")
            os.replace(temporary, self._path)
        except OSError as error:
            print(f"Could not save config to {self._path}: {error}")

    # -- reading -----------------------------------------------------------

    def snapshot(self):
        with self._lock:
            return {key: _copy(value) for key, value in self._values.items()}

    def get(self, key):
        with self._lock:
            return _copy(self._values[key])

    # -- writing -----------------------------------------------------------

    def merged(self, changes):
        """Validate changes on top of the current values without applying them.

        Used by the web preview, which has to show what a setting would look
        like before the user commits it to the clock.
        """
        values = self.snapshot()
        errors = {}
        for key, value in (changes or {}).items():
            if key not in DEFAULTS:
                errors[key] = "unknown setting"
                continue
            try:
                values[key] = self._clean(key, value)
            except ValidationError as error:
                errors[key] = str(error)
        return values, errors

    def update(self, changes, save=True):
        """Apply a partial update. Returns (applied, errors) without raising."""
        applied = {}
        errors = {}
        for key, value in changes.items():
            if key not in DEFAULTS:
                errors[key] = "unknown setting"
                continue
            try:
                applied[key] = self._clean(key, value)
            except ValidationError as error:
                errors[key] = str(error)
        if applied:
            with self._lock:
                self._values.update(applied)
            if save:
                self.save()
        return applied, errors

    def _clean(self, key, value):
        if key in ("display_on", "gifs_enabled", "sparkle", "background_enabled"):
            return _boolean(value, key)
        if key == "brightness":
            return round(_number(value, key, 0.0, 1.0), 3)
        if key in ("animation_speed", "shimmer_speed"):
            return round(_number(value, key, 0.0, 2.0), 3)
        if key == "gif_duration":
            return round(_number(value, key, 1.0, 120.0), 1)
        if key in ("color", "secondary_color"):
            return _color(value, key)
        if key == "theme":
            return _choice(value, key, themes.names())
        if key == "gif_mode":
            return _choice(value, key, GIF_MODES)
        if key == "background_source":
            return _choice(value, key, BACKGROUND_SOURCES)
        if key == "weather_zip":
            return _postcode(value, key)
        if key == "weather_place":
            return str(value or "").strip()[:80]
        if key in ("weather_latitude", "weather_longitude"):
            if value is None or value == "":
                return None
            limit = 90.0 if key == "weather_latitude" else 180.0
            return round(_number(value, key, -limit, limit), 4)
        if key == "background_brightness":
            return round(_number(value, key, 0.0, 1.0), 3)
        if key == "background":
            if not value:
                return ""
            return _choice(value, key, self._background_names() or [""])
        if key == "gif_name":
            if not value:
                return ""
            # Only names the library actually reported are accepted, so a
            # request can never reach outside its directory.
            return _choice(value, key, self._gif_names() or [""])
        if key == "hour_gifs":
            return self._clean_hour_gifs(value)
        if key == "timezone":
            value = str(value).strip()
            if not timekeeper.is_valid_timezone(value):
                raise ValidationError(f"unknown timezone '{value}'")
            return value
        raise ValidationError("unknown setting")

    def _clean_hour_gifs(self, value):
        """Merge an hour -> animation mapping over the current one."""
        if not isinstance(value, dict):
            raise ValidationError("hour_gifs must be an object keyed by hour")
        with self._lock:
            merged = dict(self._values.get("hour_gifs") or {})
        for hour in HOURS:
            merged.setdefault(hour, "")

        known = self._gif_names()
        for hour, name in value.items():
            hour = str(hour)
            if hour not in HOURS:
                raise ValidationError(f"hour_gifs keys must be 1-12, got '{hour}'")
            if not name:
                merged[hour] = ""
                continue
            # Same guard as gif_name: only real library entries are accepted.
            if name not in known:
                raise ValidationError(f"hour {hour}: unknown animation '{name}'")
            merged[hour] = name
        return {hour: merged[hour] for hour in HOURS}

    # -- one-shot requests from the web UI ---------------------------------

    def request_gif(self, name=None):
        with self._lock:
            self._pending_gif = name or ""

    def take_gif_request(self):
        """Return a pending play request ('' means 'whichever is next')."""
        with self._lock:
            pending, self._pending_gif = self._pending_gif, None
            return pending
