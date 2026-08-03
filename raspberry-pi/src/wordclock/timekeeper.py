"""Timezone handling.

The Raspberry Pi has no real time clock, so the time comes from NTP in UTC and
has to be converted locally. Using an explicit IANA zone (e.g. "Europe/Warsaw")
means daylight saving transitions are applied from the tz database, whether or
not the system timezone was ever configured.
"""

import math
import os
from datetime import datetime

try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError, available_timezones
except ImportError:  # Python < 3.9
    ZoneInfo = None
    available_timezones = None

    class ZoneInfoNotFoundError(Exception):
        pass


# Shipped with the system tzdata. Every geographic zone is listed here with its
# coordinates, which is what makes an offline location lookup possible.
ZONE_TABLE_PATHS = (
    "/usr/share/zoneinfo/zone1970.tab",
    "/usr/share/zoneinfo/zone.tab",
)

_zone_cache = {}
_zone_table = None


def is_valid_timezone(name):
    """True if `name` is an empty string (system local time) or a known zone."""
    if not name:
        return True
    try:
        resolve_timezone(name)
        return True
    except (ZoneInfoNotFoundError, ValueError):
        return False


def resolve_timezone(name):
    """Return a tzinfo for an IANA name, or None to mean system local time."""
    if not name:
        return None
    if ZoneInfo is None:
        raise ZoneInfoNotFoundError("zoneinfo requires Python 3.9 or newer")
    if name not in _zone_cache:
        _zone_cache[name] = ZoneInfo(name)
    return _zone_cache[name]


def now(timezone_name=""):
    """Current wall clock time, DST included, in the configured timezone."""
    try:
        zone = resolve_timezone(timezone_name)
    except (ZoneInfoNotFoundError, ValueError):
        zone = None
    if zone is None:
        return datetime.now().astimezone()
    return datetime.now(zone)


def _parse_iso6709(text):
    """Decode zone.tab coordinates, e.g. '+5215+02100' or '-720041+0023206'."""
    for index, character in enumerate(text[1:], start=1):
        if character in "+-":
            latitude, longitude = text[:index], text[index:]
            break
    else:
        return None

    def to_degrees(value, degree_digits):
        sign = -1 if value[0] == "-" else 1
        digits = value[1:]
        degrees = int(digits[:degree_digits])
        minutes = int(digits[degree_digits:degree_digits + 2] or 0)
        seconds = int(digits[degree_digits + 2:degree_digits + 4] or 0)
        return sign * (degrees + minutes / 60.0 + seconds / 3600.0)

    try:
        return to_degrees(latitude, 2), to_degrees(longitude, 3)
    except ValueError:
        return None


def zone_table():
    """[(name, latitude, longitude)] for every zone the system knows about."""
    global _zone_table
    if _zone_table is not None:
        return _zone_table

    known = set(available_timezones()) if available_timezones else None
    entries = {}
    for path in ZONE_TABLE_PATHS:
        if not os.path.exists(path):
            continue
        try:
            with open(path, encoding="utf-8") as table:
                for line in table:
                    if line.startswith("#"):
                        continue
                    fields = line.rstrip("\n").split("\t")
                    if len(fields) < 3:
                        continue
                    coordinates = _parse_iso6709(fields[1])
                    name = fields[2].strip()
                    if not coordinates or not name or name in entries:
                        continue
                    if known is not None and name not in known:
                        continue
                    entries[name] = (name, coordinates[0], coordinates[1])
        except OSError as error:
            print(f"Could not read {path}: {error}")
        if entries:
            break  # zone1970.tab is preferred; only fall back if it was missing

    _zone_table = sorted(entries.values())
    return _zone_table


def zone_names():
    """Zone names to offer in the picker, most specific list available."""
    names = [entry[0] for entry in zone_table()]
    if not names and available_timezones:
        # No zone.tab: fall back to every zone, minus the legacy aliases.
        names = sorted(
            name for name in available_timezones()
            if "/" in name and not name.startswith(("Etc/", "SystemV/"))
        )
    if "UTC" not in names:
        names.append("UTC")
    return names


def nearest_timezone(latitude, longitude):
    """Closest zone to a coordinate, or None if no zone table is available."""
    table = zone_table()
    if not table:
        return None

    latitude_radians = math.radians(latitude)
    longitude_radians = math.radians(longitude)
    closest = None
    shortest = None
    for name, zone_latitude, zone_longitude in table:
        # Great-circle distance; plain lat/lon differences would badly misjudge
        # longitude gaps at high latitudes.
        other_latitude = math.radians(zone_latitude)
        other_longitude = math.radians(zone_longitude)
        delta_latitude = other_latitude - latitude_radians
        delta_longitude = other_longitude - longitude_radians
        haversine = (
            math.sin(delta_latitude / 2) ** 2
            + math.cos(latitude_radians) * math.cos(other_latitude)
            * math.sin(delta_longitude / 2) ** 2
        )
        distance = 2 * math.asin(min(1.0, math.sqrt(haversine)))
        if shortest is None or distance < shortest:
            shortest, closest = distance, name
    return closest


def describe(moment):
    """Short label for the web UI, e.g. '2:05 PM CEST (UTC+02:00)'."""
    offset = moment.strftime("%z")
    if offset:
        offset = f"UTC{offset[:3]}:{offset[3:]}"
    abbreviation = moment.tzname() or ""
    # 12-hour, without the leading zero that %I pads single-digit hours with.
    parts = [moment.strftime("%I:%M %p").lstrip("0")]
    if abbreviation and abbreviation != offset:
        parts.append(abbreviation)
    if offset:
        parts.append(f"({offset})")
    return " ".join(parts)
