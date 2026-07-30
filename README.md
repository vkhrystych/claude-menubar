# Claude Menubar

Your Claude Code usage, in the macOS menu bar.

```
7% / resets in 1h 47m
```

No dock icon, no window, no telemetry. It reads the OAuth token Claude Code already stored in your keychain, asks Anthropic how much of your limit you've burned, and puts the number next to the clock. Refreshes every 2 minutes.

Works on **any plan** — Pro, Max, Team, and API-billed accounts each show whichever limits they actually have.

---

## What you see

The menu bar shows your session window by default:

```
7% / resets in 1h 47m
```

Turn on weekly and it appends after a separator:

```
7% / resets in 1h 47m | weekly 11%
```

On an API-billed account with no session window, it falls back to your monthly spend cap:

```
€34.39 / €120 · 29% · resets in 2d
```

Click the icon for the full breakdown:

```
Session · 7% · resets in 1h 47m
Weekly · 11% · resets in 3d 14h
Weekly (Fable) · 0%
─────────────────────────────────
Spend · €34.39 of €120.00 · 29%
Resets Aug 1 (in 2 days)
─────────────────────────────────
✓ Show weekly in menu bar
  Refresh now
```

The weekly toggle persists across restarts.

---

## Install

**Requires:** macOS on Apple Silicon, and [Claude Code](https://docs.anthropic.com/en/docs/claude-code) installed and logged in. Intel Macs need to [build from source](#build-from-source).

```sh
git clone git@github.com:vkhrystych/claude-menubar.git
cd claude-menubar
cp -R "dist/Claude Menubar.app" /Applications/
xattr -dr com.apple.quarantine "/Applications/Claude Menubar.app"
open "/Applications/Claude Menubar.app"
```

That's it — a prebuilt `.app` ships in `dist/`, with its own Python runtime inside. Nothing to install, no venv, no dependencies.

> **Use `git clone`, not GitHub's "Download ZIP".** The bundle contains symlinks that the ZIP export mangles, and the app won't launch.

### Two prompts on first launch

1. **"Claude Menubar can't be opened because Apple cannot check it for malicious software."** The app is ad-hoc signed, not notarized — I'm not paying Apple $99/year for a menu bar widget. The `xattr` line above clears the quarantine flag. If you skipped it, run it now, or right-click the app → **Open**.
2. **A keychain prompt.** Click **Always Allow**. The app needs to read the `Claude Code-credentials` entry. Click "Allow Once" and you'll be asked again every 2 minutes.

### Start at login

**System Settings → General → Login Items → Open at Login → `+`** and pick `Claude Menubar.app`.

---

## Build from source

Needed on Intel Macs, or if you'd rather not trust a binary from a stranger on the internet.

```sh
python3 -m venv .venv                     # Python 3.10+
.venv/bin/pip install -r requirements.txt

.venv/bin/python app.py                   # run it directly
```

To produce the `.app` bundle:

```sh
.venv/bin/pip install py2app
.venv/bin/python setup.py py2app          # -> dist/Claude Menubar.app
```

---

## How it works

Three moving parts, ~300 lines total.

1. **`usage.py`** shells out to `security find-generic-password -s "Claude Code-credentials"` and pulls the OAuth access token out of the JSON blob Claude Code keeps there.
2. It calls `GET https://api.anthropic.com/api/oauth/usage` with that bearer token and the `oauth-2025-04-20` beta header.
3. **`app.py`** ([rumps](https://github.com/jaredks/rumps)) renders the result.

The interesting bit is `normalize()`, which is what makes this work across plan types. The endpoint returns a different shape depending on your account, so it falls through three sources:

| Source | Provides | Present on |
|---|---|---|
| `limits[]` | session, weekly, per-model weekly | newest shape, all consumer plans |
| `five_hour` / `seven_day` | session, weekly | older shape, still returned |
| `spend` / `extra_usage` | monthly cap in your currency | only when usage credits are enabled |

Anything that resolves gets rendered; anything that doesn't is skipped. That's the whole trick — the original version of this app only read `extra_usage` and therefore appeared to work only on API-billed accounts.

Nothing is written to disk except a two-line preferences file:

```
~/Library/Application Support/Claude Menubar/prefs.json
```

No network calls other than the one to `api.anthropic.com`. No analytics. Your token never leaves the machine.

---

## Troubleshooting

| Menu bar shows | Meaning | Fix |
|---|---|---|
| `Claude !` | Can't read the keychain, or the API rejected the token | Open **Keychain Access**, find `Claude Code-credentials`, allow the app. Or run `claude login` again. |
| `Claude …` + "Rate-limited" | HTTP 429 | Nothing to do, it retries every 2 minutes |
| `Claude idle` | The API returned no limits it recognizes | Likely an account type this hasn't been tested against — [open an issue](https://github.com/vkhrystych/claude-menubar/issues) with your (redacted) payload |
| Stale number + `⚠ offline` | Network is down | It keeps showing the last known value |

Verify the raw payload yourself:

```sh
TOKEN=$(security find-generic-password -s "Claude Code-credentials" -w \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['claudeAiOauth']['accessToken'])")
curl -s https://api.anthropic.com/api/oauth/usage \
  -H "Authorization: Bearer $TOKEN" \
  -H "anthropic-beta: oauth-2025-04-20" | python3 -m json.tool
```

---

## Caveats

- **`/api/oauth/usage` is undocumented.** It's what Claude Code itself calls. Anthropic can change or remove it without notice, and one day this will simply stop working. Treat it as a hack, not infrastructure.
- **The `limits[]` shape drifts.** Unknown `kind` values are ignored rather than guessed at, so a new limit type shows up as nothing rather than as nonsense.
- **Session and weekly are percentages only.** The API returns `null` for `limit_dollars` / `used_dollars` on consumer plans.
- **The payload contains unreleased-feature placeholders** with names like `tangelo` and `nimbus_quill`. They're skipped. Enjoy the glimpse.
- **The prebuilt binary is arm64 and ad-hoc signed.** Build from source if that bothers you — it should.

---

## Contributing

Issues and PRs welcome. Useful things to report:

- A plan type where the menu bar says `Claude idle` — include the redacted JSON payload
- A `limits[].kind` value not handled in `usage.py`
- An Intel build, if you can produce a universal2 bundle

Keep it dependency-free beyond `rumps`. The appeal is that the whole thing fits in your head.

## License

MIT — see [LICENSE](LICENSE).
