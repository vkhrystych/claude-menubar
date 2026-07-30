import json
import os
from datetime import date, datetime

import rumps

from usage import fetch_usage, humanize_reset, normalize

ICON_PATH = os.path.join(os.path.dirname(__file__), "claude icon.png")
APP_NAME = "Claude Menubar"
PREFS_FILE = "prefs.json"


def _next_month_first(today: date) -> date:
    year, month = (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
    return date(year, month, 1)


def _days_until(target: date, today: date) -> int:
    return (target - today).days


class ClaudeUsageApp(rumps.App):
    def __init__(self):
        super().__init__(APP_NAME, title="Claude …", icon=ICON_PATH, template=False)
        self.menu = [rumps.MenuItem("Loading…")]
        self._prefs_path = os.path.join(rumps.application_support(APP_NAME), PREFS_FILE)
        self._show_weekly = self._load_pref("show_weekly", False)
        self._last_usage = None
        self._last_fetched_at = None
        self.refresh()

    # ---------- preferences ----------

    def _load_pref(self, key, default):
        try:
            with open(self._prefs_path) as fh:
                return json.load(fh).get(key, default)
        except (OSError, ValueError):
            return default

    def _save_pref(self, key, value):
        try:
            data = {}
            if os.path.exists(self._prefs_path):
                with open(self._prefs_path) as fh:
                    data = json.load(fh)
            data[key] = value
            with open(self._prefs_path, "w") as fh:
                json.dump(data, fh)
        except (OSError, ValueError):
            pass

    # ---------- lifecycle ----------

    @rumps.timer(120)
    def tick(self, _):
        self.refresh()

    def on_refresh(self, _):
        self.refresh()

    def on_toggle_weekly(self, sender):
        self._show_weekly = not self._show_weekly
        sender.state = 1 if self._show_weekly else 0
        self._save_pref("show_weekly", self._show_weekly)
        if self._last_usage is not None:
            self.title = self._format_title(self._last_usage)

    def refresh(self):
        try:
            data = fetch_usage()
        except Exception as e:
            self._handle_error(e)
            return

        usage = normalize(data)
        self._last_usage = usage
        self._last_fetched_at = datetime.now()
        self.title = self._format_title(usage)
        self._render_menu(usage, stale=None)

    def _handle_error(self, exc):
        is_rate_limited = "429" in str(exc)
        kind = "rate-limited" if is_rate_limited else "offline"
        if self._last_usage is not None:
            self.title = self._format_title(self._last_usage)
            self._render_menu(self._last_usage, stale=kind)
        elif is_rate_limited:
            self.title = "Claude …"
            self._set_menu([rumps.MenuItem("Rate-limited · retrying every 120s")])
        else:
            self.title = "Claude !"
            self._set_menu([rumps.MenuItem(f"Error: {str(exc)[:80]}")])

    # ---------- rendering ----------

    def _format_title(self, usage):
        session = usage.get("session")
        weekly = usage.get("weekly")
        spend = usage.get("spend")

        if session:
            parts = [f"{session['percent']:.0f}% / resets in {humanize_reset(session['resets_at'])}"]
            if self._show_weekly and weekly:
                parts.append(f"weekly {weekly['percent']:.0f}%")
            return " | ".join(parts)

        if weekly:
            return f"weekly {weekly['percent']:.0f}% / resets in {humanize_reset(weekly['resets_at'])}"

        if spend:
            days = _days_until(_next_month_first(date.today()), date.today())
            sym = spend["symbol"]
            return (
                f"{sym}{spend['used']:,.2f} / {sym}{spend['cap']:,.0f} · "
                f"{spend['percent']:.0f}% · resets in {days}d"
            )

        return "Claude idle"

    def _render_menu(self, usage, stale):
        items: list = []

        session = usage.get("session")
        if session:
            items.append(rumps.MenuItem(
                f"Session · {session['percent']:.0f}% · resets in {humanize_reset(session['resets_at'])}"
            ))

        weekly = usage.get("weekly")
        if weekly:
            items.append(rumps.MenuItem(
                f"Weekly · {weekly['percent']:.0f}% · resets in {humanize_reset(weekly['resets_at'])}"
            ))

        for scope in usage.get("scoped") or []:
            suffix = f" · resets in {humanize_reset(scope['resets_at'])}" if scope["resets_at"] else ""
            items.append(rumps.MenuItem(
                f"Weekly ({scope['label']}) · {scope['percent']:.0f}%{suffix}"
            ))

        spend = usage.get("spend")
        if spend:
            if items:
                items.append(None)
            sym = spend["symbol"]
            reset = _next_month_first(date.today())
            days = _days_until(reset, date.today())
            day_word = "day" if days == 1 else "days"
            items.append(rumps.MenuItem(
                f"Spend · {sym}{spend['used']:,.2f} of {sym}{spend['cap']:,.2f} · {spend['percent']:.0f}%"
            ))
            items.append(rumps.MenuItem(
                f"Resets {reset.strftime('%b %-d')} (in {days} {day_word})"
            ))

        if not items:
            items.append(rumps.MenuItem("No usage data available"))

        if stale and self._last_fetched_at:
            items.append(None)
            items.append(rumps.MenuItem(
                f"⚠ {stale} · last update {self._last_fetched_at.strftime('%H:%M')}"
            ))

        self._set_menu(items, show_weekly_toggle=weekly is not None)

    def _set_menu(self, items, show_weekly_toggle=False):
        items = list(items)
        items.append(None)
        if show_weekly_toggle:
            toggle = rumps.MenuItem("Show weekly in menu bar", callback=self.on_toggle_weekly)
            toggle.state = 1 if self._show_weekly else 0
            items.append(toggle)
        items.append(rumps.MenuItem("Refresh now", callback=self.on_refresh))

        self.menu.clear()
        self.menu.update(items)


if __name__ == "__main__":
    ClaudeUsageApp().run()
