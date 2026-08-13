# weather

A beautiful terminal weather app. It shows the current weather for a US zip code
as a colorful ASCII card, right in your terminal.

No API keys and no third-party packages required — just Python 3 and its standard
library.

## Features

- Clean, colorized weather "card" with ASCII art for the current conditions
- Remembers your zip code between runs (stored in a config file)
- Interactive first-run setup that validates your zip code
- Fahrenheit or Celsius (imperial or metric) units
- Graceful color fallback (respects `NO_COLOR` / `FORCE_COLOR`, disables color when not a TTY)

## How it works

The app is a single script, `weather.py`, that uses two free public APIs:

| Service | Purpose |
| --- | --- |
| [`api.zippopotam.us`](https://api.zippopotam.us) | Convert a US zip code → latitude/longitude + city/state |
| [`api.open-meteo.com`](https://open-meteo.com) | Fetch the current weather for those coordinates |

On each run it:

1. Loads your saved configuration (see [Configuration](#configuration)).
2. Geocodes your zip code to coordinates and a city/state via zippopotam.us.
3. Fetches current conditions (temperature, apparent temperature, humidity,
   weather code, wind speed) from Open-Meteo.
4. Renders a bordered card with condition-specific ASCII art and
   temperature-based colors.

The [WMO weather code](https://open-meteo.com/en/docs) returned by Open-Meteo is
mapped to a human-readable label, an ASCII art icon (sun, clouds, rain, snow,
storm, fog), and a color. Temperatures are also colorized on a cold→hot scale.

## Requirements

- Python 3 (uses only the standard library — no `pip install` needed)
- An internet connection

## Usage

Make the script executable (optional) and run it:

```bash
python3 weather.py
# or
chmod +x weather.py
./weather.py
```

On the first run, you'll be prompted for your US zip code. It's validated against
the geocoding service and then saved so future runs go straight to the weather.

### Options

| Flag | Description |
| --- | --- |
| `--reconfigure` | Ask for a new zip code and save it. |
| `--celsius` | Show this run in Celsius (metric). |
| `--fahrenheit` | Show this run in Fahrenheit (imperial). |
| `-h`, `--help` | Show help. |

Examples:

```bash
python3 weather.py                # weather for your saved zip
python3 weather.py --celsius      # this run in metric units
python3 weather.py --reconfigure  # change your saved zip code
```

## Configuration

Your settings are stored as JSON at:

```
${XDG_CONFIG_HOME:-~/.config}/weather/config.json
```

Example:

```json
{
  "zip": "10001",
  "units": "fahrenheit"
}
```

You can edit this file by hand, delete it to start over, or run
`weather.py --reconfigure` to update your zip code interactively. The `units`
value may be `"fahrenheit"` or `"celsius"`; anything else falls back to
Fahrenheit.

## Environment variables

- `NO_COLOR` — if set, disables all ANSI colors.
- `FORCE_COLOR` — if set, forces colors on (even when output isn't a TTY).
- `XDG_CONFIG_HOME` — overrides the base config directory.

## Data sources

- Geocoding: [Zippopotam.us](https://api.zippopotam.us)
- Weather: [Open-Meteo](https://open-meteo.com)
