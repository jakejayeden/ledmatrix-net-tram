# NET Tram Departures — LEDMatrix plugin

A third-party plugin for ChuckBuilds/LEDMatrix that shows upcoming NET tram departures using a configured public Traveline stop page.

The plugin is tuned for a **128×32** LED matrix and follows the same compact display approach as the NCT Bus Departures plugin.

## Privacy-friendly configuration

This repository intentionally contains **no personal tram stop ID or descriptive stop name**. Configure those values locally after installation using the LEDMatrix WebUI.

Default settings:

- **Stop ID:** `YOUR_STOP_ID`
- **Stop name:** `Tram Stop`
- **Maximum departures:** 2
- **Refresh interval:** 30 seconds
- **Display duration:** 15 seconds

The stop ID is the final code in a Traveline stop-page URL. For example, if the URL format is `https://www.traveline.info/stops/YOUR_STOP_ID`, enter only `YOUR_STOP_ID` in the WebUI.

Do not commit your own stop code or stop name to this public repository if you want to keep the location private.

## Display

The screen shows:

- configured stop name and Traveline's last-updated time
- up to two TRAM departures
- destination
- live minute countdowns using a large number plus a smaller `min` label
- scheduled clock times where supplied

If no departures are available the panel shows `NO TRAMS`. If fetching/parsing fails and there is no usable previous data, it shows `DATA ERROR`.

## Install

1. In LEDMatrix open **Plugin Manager → Install from GitHub**.
2. Install this repository.
3. Open the plugin settings in the WebUI.
4. Enter the Traveline/ATCO stop code in **Stop ID**.
5. Enter the heading you want displayed in **Stop name**.
6. Save the configuration and enable the plugin.

## Files

- `manifest.json` — LEDMatrix plugin metadata
- `manager.py` — Traveline fetch, parsing, cache and 128×32 rendering
- `config_schema.json` — WebUI plugin settings
- `requirements.txt` — BeautifulSoup dependency

## Data source and reliability

The plugin reads the public Traveline stop page at runtime. It does not contain a private NET API key or a hard-coded user stop.

Traveline is a third-party dependency and its page structure can change. The parser therefore uses accessible labels, human-readable departure text and a flattened-text fallback rather than relying on one CSS class. If Traveline changes its markup substantially, `manager.py` may need updating.

Network or parsing failures do not immediately erase a previously successful set of departures; the plugin retains the previous display data while reporting the refresh error internally.

## Privacy note

Your configured stop ID and stop name live in your local LEDMatrix configuration. Keep those values out of screenshots, bug reports and public configuration exports as well as out of this repository if they could identify a location you want to keep private.

## License

This starter plugin is provided for modification and use with LEDMatrix.
