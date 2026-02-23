# Site Change Watcher

A lightweight, dependency-free Python script to monitor web pages for meaningful visible-text changes.

When content changes, it:
- prints **only what changed** (added/removed lines), and
- optionally plays a local sound alert.

Default target is Duo Status history:
- `https://status.duo.com/history`

---

## Features

- ✅ No third-party dependencies (Python standard library only)
- ✅ Watch any URL (not locked to Duo)
- ✅ Clean change output (added/removed lines only)
- ✅ Baseline + persistent state between runs
- ✅ Noise reduction for volatile date/time tokens
- ✅ Audio alert on change (optional)
- ✅ CLI controls for interval, timeout, one-shot mode, max checks, etc.
- ✅ Safe stop behavior (`Ctrl+C`, `SIGTERM`)

---

## Install

### Prerequisites
- Python 3.9+ recommended
- Linux/macOS/WSL supported (should also run on Windows with Python)

### Quick setup
```bash
git clone <your-repo-url>
cd site-change-watcher
chmod +x watch_site_changes.py
```

No pip install required.

---

## Usage

### 1) Default watch (Duo history page)
```bash
python3 watch_site_changes.py
```

### 2) Watch a custom URL
```bash
python3 watch_site_changes.py --url https://status.duo.com/incidents/byd2vdlp1rff
```

### 3) Positional URL syntax
```bash
python3 watch_site_changes.py https://status.duo.com/incidents/byd2vdlp1rff
```

### 4) One-time check (baseline/quick test)
```bash
python3 watch_site_changes.py --once
```

### 5) Auto-exit after N checks
```bash
python3 watch_site_changes.py --interval 30 --max-checks 5
```

### 6) Quiet mode (only changes/errors)
```bash
python3 watch_site_changes.py --quiet
```

### 7) Disable sound alerts
```bash
python3 watch_site_changes.py --no-sound
```

---

## CLI Options

```text
positional URL            optional URL to watch
--url URL                 URL to watch (same as positional)
--interval SECONDS        poll interval (min 10, default: 60)
--timeout SECONDS         request timeout (default: 20)
--state PATH              state file path (default: ~/.cache/site-change-watcher/state.json)
--once                    run one check then exit
--max-checks N            stop after N checks (0 = run forever)
--max-diff-lines N        max changed lines shown per Added/Removed group (default: 40)
--quiet                   only print changes/errors
--no-sound                disable audio alert
```

---

## How It Works

1. Fetch HTML from target URL.
2. Extract visible text (ignoring `script`, `style`, `noscript`).
3. Normalize text (collapse whitespace; remove volatile date/time patterns).
4. Hash normalized content.
5. Compare hash with previous snapshot in state file.
6. If changed, print line-level diff (`Added` / `Removed`) and play alert sound (unless disabled).

---

## Example Output

```text
CHANGE DETECTED: 2026-02-23 10:42:00
Removed:
  - Investigating elevated authentication failures
Added:
  + Monitoring recovery after mitigation
```

---

## Troubleshooting

### “No such file or directory” when running script
Run from repo folder or use full path:
```bash
python3 /full/path/to/watch_site_changes.py
```

### Script doesn’t stop
Use `Ctrl+C`. If running backgrounded, terminate the process:
```bash
pkill -f watch_site_changes.py
```

### No sound is played
- Ensure your system has an available audio player (`paplay`/`aplay`), or
- run with `--no-sound` if silent mode is preferred.

### Too many false positives
- Increase interval (`--interval 120`)
- Use a specific page section URL if possible
- Tune normalization in script for your target page pattern

---

## Roadmap

- [ ] Optional JSON/structured output mode
- [ ] Optional webhook/Slack/Discord notification sink
- [ ] Watch multiple URLs from a config file
- [ ] CSS selector support for targeted page sections
- [ ] Packaged CLI release (`pipx` / PyPI)
- [ ] Windows-friendly sound backends

---

## Security Notes

- This tool performs **read-only HTTP GET** requests.
- It stores page text snapshots in a local state file for diffing.
- Do not use on pages containing sensitive/private data unless you are comfortable with local plaintext state storage.

---

## License

MIT (see `LICENSE`)
