#!/usr/bin/env python3
"""A simple terminal weather app.

Shows current weather for a US zip code. On first run it asks for your zip,
saves it to ~/.config/weather/config.json, and reuses it every time after.
Use --reconfigure to change it (or just edit the config file by hand).

No API keys and no third-party packages required. Uses:
  - api.zippopotam.us   (zip -> latitude/longitude + city/state)
  - api.open-meteo.com  (current weather)
"""

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "weather"
CONFIG_PATH = CONFIG_DIR / "config.json"

# --------------------------------------------------------------------------- #
# ANSI color helpers (with graceful fallback)
# --------------------------------------------------------------------------- #

def _colors_enabled() -> bool:
    if os.environ.get("NO_COLOR") is not None:
        return False
    if os.environ.get("FORCE_COLOR") is not None:
        return True
    return sys.stdout.isatty()


COLOR = _colors_enabled()


def c(text: str, *codes: str) -> str:
    """Wrap text in ANSI SGR codes when colors are enabled."""
    if not COLOR or not codes:
        return text
    return "\033[" + ";".join(codes) + "m" + text + "\033[0m"


# SGR codes
RESET = "0"
BOLD = "1"
DIM = "2"
FG = {
    "red": "38;5;203",
    "orange": "38;5;214",
    "yellow": "38;5;227",
    "green": "38;5;120",
    "cyan": "38;5;123",
    "blue": "38;5;75",
    "white": "38;5;255",
    "gray": "38;5;245",
    "magenta": "38;5;213",
}


def visible_len(s: str) -> int:
    """Length of a string ignoring ANSI escape sequences."""
    return len(re.sub(r"\033\[[0-9;]*m", "", s))


# --------------------------------------------------------------------------- #
# WMO weather code -> (label, ascii art lines, art color)
# --------------------------------------------------------------------------- #

ART = {
    "sun": [
        r"   \ | /   ",
        r"  - (_) -  ",
        r"   / | \   ",
    ],
    "part_cloud": [
        r"   \_.-.   ",
        r"  .-(   ). ",
        r" (___.__)_)",
    ],
    "cloud": [
        r"   .--.    ",
        r" .-(    ). ",
        r"(___.__)__)",
    ],
    "fog": [
        r" _ - _ - _ ",
        r"  - _ - _  ",
        r" _ - _ - _ ",
    ],
    "rain": [
        r"  .-(   ). ",
        r" (___.__)_)",
        r"  ' ' ' '  ",
    ],
    "snow": [
        r"  .-(   ). ",
        r" (___.__)_)",
        r"  *  *  *  ",
    ],
    "storm": [
        r"  .-(   ). ",
        r" (___.__)_)",
        r"   /_  /_  ",
    ],
}


def wmo_info(code: int):
    """Return (label, art_key, color) for a WMO weather code."""
    table = {
        0: ("Clear sky", "sun", "yellow"),
        1: ("Mainly clear", "sun", "yellow"),
        2: ("Partly cloudy", "part_cloud", "cyan"),
        3: ("Overcast", "cloud", "gray"),
        45: ("Fog", "fog", "gray"),
        48: ("Rime fog", "fog", "gray"),
        51: ("Light drizzle", "rain", "blue"),
        53: ("Drizzle", "rain", "blue"),
        55: ("Dense drizzle", "rain", "blue"),
        56: ("Freezing drizzle", "rain", "cyan"),
        57: ("Freezing drizzle", "rain", "cyan"),
        61: ("Light rain", "rain", "blue"),
        63: ("Rain", "rain", "blue"),
        65: ("Heavy rain", "rain", "blue"),
        66: ("Freezing rain", "rain", "cyan"),
        67: ("Freezing rain", "rain", "cyan"),
        71: ("Light snow", "snow", "white"),
        73: ("Snow", "snow", "white"),
        75: ("Heavy snow", "snow", "white"),
        77: ("Snow grains", "snow", "white"),
        80: ("Rain showers", "rain", "blue"),
        81: ("Rain showers", "rain", "blue"),
        82: ("Violent showers", "rain", "blue"),
        85: ("Snow showers", "snow", "white"),
        86: ("Snow showers", "snow", "white"),
        95: ("Thunderstorm", "storm", "magenta"),
        96: ("Thunderstorm + hail", "storm", "magenta"),
        99: ("Thunderstorm + hail", "storm", "magenta"),
    }
    return table.get(code, ("Unknown", "cloud", "gray"))


def temp_color(temp_f: float) -> str:
    if temp_f <= 32:
        return "cyan"
    if temp_f <= 50:
        return "blue"
    if temp_f <= 70:
        return "green"
    if temp_f <= 85:
        return "yellow"
    if temp_f <= 95:
        return "orange"
    return "red"


# --------------------------------------------------------------------------- #
# Networking
# --------------------------------------------------------------------------- #

def http_get_json(url: str, timeout: int = 12):
    req = urllib.request.Request(url, headers={"User-Agent": "weather-cli/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def geocode_zip(zip_code: str):
    """Return dict with city, state, lat, lon. Raises ValueError if not found."""
    try:
        data = http_get_json(f"https://api.zippopotam.us/us/{zip_code}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise ValueError(f"Zip code '{zip_code}' was not found.")
        raise
    place = data["places"][0]
    return {
        "city": place["place name"],
        "state": place["state abbreviation"],
        "lat": float(place["latitude"]),
        "lon": float(place["longitude"]),
    }


def fetch_weather(lat: float, lon: float, units: str):
    unit_param = "celsius" if units == "celsius" else "fahrenheit"
    wind_param = "kmh" if units == "celsius" else "mph"
    url = (
        "https://api.open-meteo.com/v1/forecast"
        f"?latitude={lat}&longitude={lon}"
        "&current=temperature_2m,apparent_temperature,relative_humidity_2m,"
        "weather_code,wind_speed_10m"
        f"&temperature_unit={unit_param}&wind_speed_unit={wind_param}"
        "&timezone=auto"
    )
    data = http_get_json(url)
    cur = data["current"]
    u = data["current_units"]
    wind_unit = u["wind_speed_10m"].replace("mp/h", "mph")
    return {
        "temp": cur["temperature_2m"],
        "feels": cur["apparent_temperature"],
        "humidity": cur["relative_humidity_2m"],
        "code": cur["weather_code"],
        "wind": cur["wind_speed_10m"],
        "temp_unit": u["temperature_2m"],
        "wind_unit": wind_unit,
        "time": cur["time"],
    }


# --------------------------------------------------------------------------- #
# Config
# --------------------------------------------------------------------------- #

def load_config():
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return None
        if not valid_zip(str(data.get("zip", ""))):
            return None
        if data.get("units") not in ("fahrenheit", "celsius"):
            data["units"] = "fahrenheit"
        data["zip"] = str(data["zip"])
        return data
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def save_config(cfg: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)
        f.write("\n")


def valid_zip(z: str) -> bool:
    return bool(re.fullmatch(r"\d{5}", z.strip()))


# --------------------------------------------------------------------------- #
# Interactive prompt
# --------------------------------------------------------------------------- #

def prompt_zip() -> dict:
    if not sys.stdin.isatty():
        die("No zip code configured and no terminal available to ask. "
            f"Please edit {CONFIG_PATH} or pass a valid config.")
    print(c("  Let's set up your weather app.", FG["cyan"], BOLD))
    while True:
        try:
            entry = input(c("  Enter your US zip code: ", FG["yellow"])).strip()
        except (EOFError, KeyboardInterrupt):
            print()
            die("Setup cancelled.")
        if not valid_zip(entry):
            print(c("  ! Please enter a 5-digit US zip code.", FG["red"]))
            continue
        try:
            loc = geocode_zip(entry)
        except ValueError as e:
            print(c(f"  ! {e}", FG["red"]))
            continue
        except (urllib.error.URLError, OSError):
            die("Could not reach the network to verify that zip code.")
        print(c(f"  Found: {loc['city']}, {loc['state']}", FG["green"]))
        return {"zip": entry, "units": "fahrenheit"}


# --------------------------------------------------------------------------- #
# Rendering
# --------------------------------------------------------------------------- #

def die(msg: str) -> None:
    print(c("  ✖ " + msg, FG["red"], BOLD), file=sys.stderr)
    sys.exit(1)


def render_card(loc: dict, wx: dict) -> str:
    label, art_key, art_color = wmo_info(int(wx["code"]))
    art = ART[art_key]
    # temp_color thresholds are in Fahrenheit; convert if we're showing Celsius.
    temp_f = float(wx["temp"]) * 9 / 5 + 32 if wx["temp_unit"].endswith("C") else float(wx["temp"])
    tc = temp_color(temp_f)

    inner_w = 40
    title = f"{loc['city']}, {loc['state']} · {loc['zip']}"

    def pad(line: str) -> str:
        gap = inner_w - visible_len(line)
        return line + " " * max(0, gap)

    # Right-hand info column
    temp_str = f"{round(float(wx['temp']))}{wx['temp_unit']}"
    info = [
        c(label, FG[art_color], BOLD),
        c(temp_str, FG[tc], BOLD),
        c(f"feels like {round(float(wx['feels']))}{wx['temp_unit']}", FG["gray"]),
        c(f"humidity   {wx['humidity']}%", FG["gray"]),
        c(f"wind       {round(float(wx['wind']))} {wx['wind_unit']}", FG["gray"]),
    ]

    art_colored = [c(a, FG[art_color]) for a in art]
    # Vertically center the 3-line art against the 5-line info column.
    left_lines = ["", art_colored[0], art_colored[1], art_colored[2], ""]
    # Blank the art columns to a fixed width so padding stays aligned.
    blank = " " * visible_len(art[0])
    left_lines[0] = blank
    left_lines[4] = blank

    top = "╔" + "═" * inner_w + "╗"
    sep = "╟" + "─" * inner_w + "╢"
    bot = "╚" + "═" * inner_w + "╝"

    lines = [c(top, FG["cyan"])]
    # Title line (centered)
    tvis = visible_len(title)
    left_pad = (inner_w - tvis) // 2
    right_pad = inner_w - tvis - left_pad
    title_line = " " * left_pad + c(title, FG["white"], BOLD) + " " * right_pad
    lines.append(c("║", FG["cyan"]) + title_line + c("║", FG["cyan"]))
    lines.append(c(sep, FG["cyan"]))

    for i in range(5):
        body = "  " + pad_two_col(left_lines[i], info[i], inner_w)
        lines.append(c("║", FG["cyan"]) + body + c("║", FG["cyan"]))

    lines.append(c(bot, FG["cyan"]))
    footer = c(f"  updated {wx['time'].replace('T', ' ')}", FG["gray"], DIM)
    lines.append(footer)
    return "\n".join(lines)


def pad_two_col(left: str, right: str, inner_w: int) -> str:
    """Left column fixed at 12 visible chars, then right column, padded to inner_w-2."""
    left_col_w = 12
    lgap = left_col_w - visible_len(left)
    seg = left + " " * max(0, lgap) + right
    gap = (inner_w - 2) - visible_len(seg)
    return seg + " " * max(0, gap)


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Show the current weather for your saved zip code.")
    parser.add_argument("--reconfigure", action="store_true",
                        help="Ask for a new zip code and save it.")
    parser.add_argument("--celsius", action="store_true",
                        help="Show this run in Celsius (metric).")
    parser.add_argument("--fahrenheit", action="store_true",
                        help="Show this run in Fahrenheit (imperial).")
    args = parser.parse_args()

    cfg = load_config()
    if cfg is None or args.reconfigure:
        cfg = prompt_zip()
        save_config(cfg)
        print(c(f"  Saved to {CONFIG_PATH}", FG["gray"], DIM))
        print()

    units = cfg.get("units", "fahrenheit")
    if args.celsius:
        units = "celsius"
    elif args.fahrenheit:
        units = "fahrenheit"

    try:
        loc = geocode_zip(cfg["zip"])
        wx = fetch_weather(loc["lat"], loc["lon"], units)
    except ValueError as e:
        die(str(e))
    except (urllib.error.URLError, OSError):
        die("Could not reach the weather service. Check your internet connection.")
    except (KeyError, json.JSONDecodeError):
        die("Received an unexpected response from the weather service.")

    loc["zip"] = cfg["zip"]
    print()
    print(render_card(loc, wx))
    print()


if __name__ == "__main__":
    main()
