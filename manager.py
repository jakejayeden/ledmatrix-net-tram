"""
NET Tram Departures plugin for ChuckBuilds LEDMatrix.

Reads a configured public Traveline stop page. Stop details are supplied
locally through the LEDMatrix WebUI and are not hard-coded in this plugin.
Designed for 32px-high LEDMatrix displays with adaptive display width.
"""
from __future__ import annotations

import re
import urllib.request

from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from src.plugin_system.base_plugin import BasePlugin

BASE_URL = "https://www.traveline.info/stops/{}"
BG = (0, 0, 0)
WHITE = (255, 255, 255)
TRAM = (120, 220, 80)
LIVE = (0, 255, 0)
SCHEDULED = (255, 180, 0)
ERROR = (255, 70, 70)


class NETTramDeparturesPlugin(BasePlugin):
    def __init__(self, plugin_id, config, display_manager, cache_manager, plugin_manager):
        super().__init__(plugin_id, config, display_manager, cache_manager, plugin_manager)
        self.departures = []
        self.error = None
        self.last_updated = ""
        self._load_config()

    def _load_config(self):
        self.stop_id = str(self.config.get("stop_id", "YOUR_STOP_ID")).strip()
        self.stop_name = str(self.config.get("stop_name", "Tram Stop")).strip()
        self.max_departures = max(1, min(2, int(self.config.get("max_departures", 2))))

    def on_config_change(self, new_config):
        super().on_config_change(new_config)
        self._load_config()

    def get_update_interval(self):
        return max(15, int(self.config.get("update_interval", 30)))

    def update(self):
        self._load_config()
        key = f"{self.plugin_id}_{self.stop_id}_tram"
        interval = self.get_update_interval()
        try:
            cached = self.cache_manager.get(key, max_age=interval)
        except Exception:
            cached = None
        if cached:
            self.departures = cached.get("departures", [])
            self.last_updated = cached.get("last_updated", "")
            self.error = None
            return

        try:
            departures, updated = self._parse_page(self._fetch_page())
            self.departures = departures[:self.max_departures]
            self.last_updated = updated
            self.error = None
            try:
                self.cache_manager.set(key, {
                    "departures": self.departures,
                    "last_updated": self.last_updated,
                })
            except Exception:
                pass
        except Exception as exc:
            # Keep the last successful departures on screen if a refresh fails.
            self.logger.error("NET Tram departure fetch failed: %s", exc, exc_info=True)
            self.error = str(exc)[:80]

    def _fetch_page(self):
        if not re.fullmatch(r"[A-Za-z0-9_-]{3,32}", self.stop_id):
            raise ValueError("Invalid stop_id")
        if self.stop_id == "YOUR_STOP_ID":
            raise ValueError("Configure stop_id in the WebUI")
        req = urllib.request.Request(
            BASE_URL.format(self.stop_id),
            headers={
                "User-Agent": "Mozilla/5.0 LEDMatrix-NET-Tram/1.0",
                "Accept": "text/html,application/xhtml+xml",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.read().decode("utf-8", errors="replace")

    @staticmethod
    def _clean(text):
        return re.sub(r"\s+", " ", text or "").strip()

    def _parse_page(self, html):
        soup = BeautifulSoup(html, "html.parser")
        page = self._clean(soup.get_text(" ", strip=True))
        updated = ""
        match = re.search(r"Last updated:\s*([0-2]?\d:[0-5]\d)", page, re.I)
        if match:
            updated = match.group(1)

        if re.search(r"no departures (?:are )?available", page, re.I):
            return [], updated

        results = []
        seen = set()

        # Traveline exposes useful accessible labels such as:
        # Service - TRAM. Destination - .... Departure time - 13 mins. ... Scheduled.
        for node in soup.find_all(True):
            candidates = []
            aria = node.get("aria-label")
            title = node.get("title")
            if aria:
                candidates.append(self._clean(aria))
            if title:
                candidates.append(self._clean(title))
            if node.name in ("a", "li", "article", "tr"):
                candidates.append(self._clean(node.get_text(" ", strip=True)))
            for text in candidates:
                departure = self._departure_from_text(text)
                if departure:
                    key = (departure["destination"], departure["time"], departure["status"])
                    if key not in seen:
                        seen.add(key)
                        results.append(departure)

        if not results:
            results = self._parse_flat_text(page)

        return results[:self.max_departures], updated

    def _departure_from_text(self, text):
        if not re.search(r"(?:Service\s*-\s*)?TRAM\b", text, re.I):
            return None

        structured = re.search(
            r"Service\s*-\s*TRAM\.\s*Destination\s*-\s*(.+?)\.\s*"
            r"Departure time\s*-\s*(Due|\d{1,3}\s*(?:mins?|minutes?)|\d{1,2}:\d{2})\."
            r".*?\b(Live|Scheduled)\b",
            text,
            re.I,
        )
        if structured:
            destination, raw_time, status = structured.groups()
            return self._make_departure(destination, raw_time, status)

        compact = re.search(
            r"\bTRAM\s+(.{1,60}?)\s+(Due|\d{1,3}\s*(?:mins?|minutes?)|\d{1,2}:\d{2})(?:\s+(Live|Scheduled))?(?:\s|$)",
            text,
            re.I,
        )
        if not compact:
            return None
        destination, raw_time, status = compact.groups()
        return self._make_departure(destination, raw_time, status)

    def _make_departure(self, destination, raw_time, status=None):
        destination = self._clean(destination).strip(" .-|–") or "Destination"
        is_minutes = bool(re.search(r"\d{1,3}\s*(?:mins?|minutes?)", raw_time, re.I))
        if raw_time.lower() == "due":
            shown = "DUE"
        elif ":" in raw_time:
            shown = raw_time
        else:
            number = re.search(r"\d{1,3}", raw_time)
            shown = number.group(0) if number else raw_time
        if status:
            resolved_status = status.title()
        else:
            resolved_status = "Live" if raw_time.lower() == "due" else "Scheduled"
        return {
            "route": "TRAM",
            "destination": destination,
            "time": shown,
            "status": resolved_status,
            "is_minutes": is_minutes,
        }

    def _parse_flat_text(self, text):
        results = []
        pattern = re.compile(
            r"Service\s*-\s*TRAM\.\s*Destination\s*-\s*(.+?)\.\s*"
            r"Departure time\s*-\s*(Due|\d{1,3}\s*(?:mins?|minutes?)|\d{1,2}:\d{2})\."
            r".*?\b(Live|Scheduled)\b",
            re.I,
        )
        for match in pattern.finditer(text):
            results.append(self._make_departure(*match.groups()))
        return results

    @staticmethod
    def _font():
        # Match Apple Calendar typography: Pillow's built-in default bitmap font.
        return ImageFont.load_default()

    @staticmethod
    def _fit(draw, text, font, max_width):
        text = str(text)
        if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
            return text
        while text and draw.textbbox((0, 0), text + "..", font=font)[2] > max_width:
            text = text[:-1]
        return text + ".."

    def display(self, force_clear=False):
        # Keep Apple Calendar's Pillow default font, but use the LEDMatrix's
        # configured dimensions so the same plugin adapts to 128x32, 256x32,
        # and other compatible widths without hard-coded cropping.
        width = max(1, int(self.display_manager.width))
        height = max(1, int(self.display_manager.height))
        image = Image.new("RGB", (width, height), BG)
        draw = ImageDraw.Draw(image)
        font = self._font()

        # Pillow's default bitmap font has a fixed size, so it cannot be scaled
        # down like a TTF. Instead, move the divider lower and the header up by
        # one pixel to give the glyph descenders clear breathing room.
        clock = self.last_updated or "--:--"
        clock_width = draw.textbbox((0, 0), clock, font=font)[2]
        clock_x = width - clock_width - 1
        header = self._fit(
            draw,
            self.stop_name or self.stop_id,
            font,
            max(20, clock_x - 4),
        )
        draw.text((1, -2), header, font=font, fill=WHITE)
        draw.text((clock_x, -2), clock, font=font, fill=WHITE)
        draw.line((0, 10, width - 1, 10), fill=TRAM)

        if not self.departures:
            message = "DATA ERROR" if self.error else "NO TRAMS"
            colour = ERROR if self.error else SCHEDULED
            draw.text((2, 12), message, font=font, fill=colour)
        else:
            for index, departure in enumerate(self.departures[:2]):
                y = 10 + index * 10
                time_text = departure["time"][:6]
                status = departure.get("status", "Scheduled")
                time_colour = LIVE if status.lower() == "live" else SCHEDULED

                draw.text((1, y), "TRAM", font=font, fill=TRAM)

                if departure.get("is_minutes"):
                    time_display = f"{time_text} min"
                else:
                    time_display = time_text
                time_width = draw.textbbox((0, 0), time_display, font=font)[2]
                time_x = width - time_width - 1
                draw.text((time_x, y), time_display, font=font, fill=time_colour)

                dest_x = 28
                destination = self._fit(
                    draw,
                    departure["destination"],
                    font,
                    max(1, time_x - dest_x - 3),
                )
                draw.text((dest_x, y), destination, font=font, fill=WHITE)

        self.display_manager.image = image
        self.display_manager.update_display()
        return True
