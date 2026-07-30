import json
import subprocess
import urllib.request
from datetime import datetime, timezone

KEYCHAIN_SERVICE = "Claude Code-credentials"
USAGE_URL = "https://api.anthropic.com/api/oauth/usage"

CURRENCY_SYMBOLS = {"USD": "$", "EUR": "€", "GBP": "£"}

# limits[].kind values we know how to render, mapped to our normalized slots.
SESSION_KINDS = {"session"}
WEEKLY_KINDS = {"weekly_all"}
SCOPED_KINDS = {"weekly_scoped"}


def _read_keychain_token() -> str:
    raw = subprocess.check_output(
        ["security", "find-generic-password", "-s", KEYCHAIN_SERVICE, "-w"],
        stderr=subprocess.DEVNULL,
    ).decode().strip()
    return json.loads(raw)["claudeAiOauth"]["accessToken"]


def fetch_usage() -> dict:
    token = _read_keychain_token()
    req = urllib.request.Request(
        USAGE_URL,
        headers={
            "Authorization": f"Bearer {token}",
            "anthropic-beta": "oauth-2025-04-20",
        },
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read())


def humanize_reset(iso_ts: str | None) -> str:
    if not iso_ts:
        return "—"
    when = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    delta = when - datetime.now(timezone.utc)
    secs = int(delta.total_seconds())
    if secs <= 0:
        return "now"
    d, rem = divmod(secs, 86400)
    h, rem = divmod(rem, 3600)
    m, _ = divmod(rem, 60)
    if d:
        return f"{d}d {h}h"
    if h:
        return f"{h}h {m}m"
    return f"{m}m"


def _window(percent, resets_at) -> dict | None:
    if percent is None:
        return None
    return {"percent": float(percent), "resets_at": resets_at}


def _scope_label(scope: dict | None) -> str:
    model = (scope or {}).get("model") or {}
    surface = (scope or {}).get("surface") or {}
    return model.get("display_name") or surface.get("display_name") or "scoped"


def _parse_limits(data: dict) -> dict:
    """Prefer the newer limits[] array; it is the only plan-agnostic source."""
    session = weekly = None
    scoped = []
    for entry in data.get("limits") or []:
        kind = entry.get("kind")
        if kind in SESSION_KINDS:
            session = _window(entry.get("percent"), entry.get("resets_at"))
        elif kind in WEEKLY_KINDS:
            weekly = _window(entry.get("percent"), entry.get("resets_at"))
        elif kind in SCOPED_KINDS:
            win = _window(entry.get("percent"), entry.get("resets_at"))
            if win:
                win["label"] = _scope_label(entry.get("scope"))
                scoped.append(win)
    return {"session": session, "weekly": weekly, "scoped": scoped}


def _parse_legacy_windows(data: dict) -> dict:
    """Older shape, still returned alongside limits[] on consumer plans."""
    five = data.get("five_hour") or {}
    seven = data.get("seven_day") or {}
    return {
        "session": _window(five.get("utilization"), five.get("resets_at")),
        "weekly": _window(seven.get("utilization"), seven.get("resets_at")),
        "scoped": [],
    }


def _money(block: dict | None) -> float | None:
    if not block or block.get("amount_minor") is None:
        return None
    return block["amount_minor"] / (10 ** block.get("exponent", 2))


def _parse_spend(data: dict) -> dict | None:
    """Monthly spend cap — only present when usage credits are enabled."""
    spend = data.get("spend") or {}
    used = _money(spend.get("used"))
    cap = _money(spend.get("limit"))
    if used is not None and cap:
        currency = (spend.get("limit") or {}).get("currency") or "USD"
        return {
            "symbol": CURRENCY_SYMBOLS.get(currency, currency + " "),
            "used": used,
            "cap": cap,
            "percent": float(spend.get("percent") or 0),
        }

    extra = data.get("extra_usage") or {}
    if not extra.get("monthly_limit"):
        return None
    currency = extra.get("currency") or "USD"
    places = extra.get("decimal_places", 2)
    return {
        "symbol": CURRENCY_SYMBOLS.get(currency, currency + " "),
        "used": (extra.get("used_credits") or 0) / (10 ** places),
        "cap": extra["monthly_limit"] / (10 ** places),
        "percent": float(extra.get("utilization") or 0),
    }


def normalize(data: dict) -> dict:
    """Flatten the payload into session/weekly/scoped/spend, whatever the plan.

    Falls through limits[] -> five_hour+seven_day -> spend cap, so Pro, Max,
    Team and API-billed accounts each light up whichever fields they have.
    """
    windows = _parse_limits(data)
    if not windows["session"] and not windows["weekly"]:
        windows = _parse_legacy_windows(data)
    windows["spend"] = _parse_spend(data)
    return windows
