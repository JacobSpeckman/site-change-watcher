#!/usr/bin/env python3
"""
Site Change Watcher
-------------------
Poll a web page, detect meaningful visible-text changes, print only what changed,
and optionally play a local alert sound.

Designed to be simple, dependency-free, and shareable.

Examples:
  python3 watch_site_changes.py
  python3 watch_site_changes.py --url https://status.duo.com/history
  python3 watch_site_changes.py https://status.duo.com/incidents/byd2vdlp1rff
  python3 watch_site_changes.py --interval 60 --max-checks 10
  python3 watch_site_changes.py --once
"""

from __future__ import annotations

import argparse
import difflib
import hashlib
import json
import re
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Optional

DEFAULT_URL = "https://status.duo.com/history"
DEFAULT_INTERVAL = 60
DEFAULT_TIMEOUT = 20
DEFAULT_STATE_PATH = Path.home() / ".cache" / "site-change-watcher" / "state.json"


class VisibleTextExtractor(HTMLParser):
    """Extract visible text from HTML, skipping script/style/noscript."""

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag.lower() in {"script", "style", "noscript"}:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            text = data.strip()
            if text:
                self._parts.append(text)

    def lines(self) -> list[str]:
        return self._parts


@dataclass
class Snapshot:
    url: str
    hash: str
    text: str
    updated: int


def fetch_html(url: str, timeout: int) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "site-change-watcher/1.0",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")


def normalize_visible_text(html: str) -> str:
    extractor = VisibleTextExtractor()
    extractor.feed(html)
    extractor.close()

    normalized: list[str] = []
    for raw in extractor.lines():
        line = raw.strip()
        if not line:
            continue

        # Strip highly volatile tokens to reduce noisy false positives.
        line = re.sub(r"\b\d{1,2}:\d{2}(?::\d{2})?\s?(?:AM|PM|am|pm)?\b", "", line)
        line = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", line)
        line = re.sub(r"\s+", " ", line).strip()

        if line:
            normalized.append(line)

    return "\n".join(normalized)


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_state(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def save_state(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2) + "\n")
    tmp.replace(path)


def parse_snapshot(raw: dict, url: str) -> Optional[Snapshot]:
    snap = raw.get(url)
    if not isinstance(snap, dict):
        return None
    h = snap.get("hash")
    t = snap.get("text", "")
    u = snap.get("updated", 0)
    if not isinstance(h, str):
        return None
    if not isinstance(t, str):
        t = ""
    if not isinstance(u, int):
        u = 0
    return Snapshot(url=url, hash=h, text=t, updated=u)


def print_diff(old: str, new: str, max_lines: int) -> None:
    diff = list(difflib.ndiff(old.splitlines(), new.splitlines()))
    removed = [d[2:] for d in diff if d.startswith("- ")]
    added = [d[2:] for d in diff if d.startswith("+ ")]

    def _print_group(label: str, lines: list[str], prefix: str) -> None:
        if not lines:
            return
        print(f"{label}:")
        shown = lines[:max_lines]
        for line in shown:
            print(f"  {prefix} {line}")
        if len(lines) > max_lines:
            print(f"  ... ({len(lines) - max_lines} more)")

    _print_group("Removed", removed, "-")
    _print_group("Added", added, "+")


def play_sound() -> None:
    candidates = (
        ["paplay", "/usr/share/sounds/freedesktop/stereo/complete.oga"],
        ["paplay", "/usr/share/sounds/freedesktop/stereo/bell.oga"],
        ["aplay", "/usr/share/sounds/alsa/Front_Center.wav"],
    )
    for cmd in candidates:
        if shutil.which(cmd[0]):
            try:
                subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return
            except Exception:
                pass
    # fallback
    print("\a", end="", flush=True)


def run_watcher(
    url: str,
    interval: int,
    timeout: int,
    once: bool,
    quiet: bool,
    state_path: Path,
    max_checks: int,
    max_diff_lines: int,
    no_sound: bool,
) -> int:
    stop = False
    checks = 0

    def _handle_sigterm(signum, frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, _handle_sigterm)

    state = load_state(state_path)
    prev = parse_snapshot(state, url)

    if not quiet:
        print(f"Watching: {url}")
        print(f"Interval: {interval}s")
        print(f"Timeout: {timeout}s")
        print(f"State: {state_path}")

    while not stop:
        try:
            html = fetch_html(url, timeout=timeout)
            text = normalize_visible_text(html)
            h = content_hash(text)
            now = int(time.time())
            checks += 1

            if prev is None:
                if not quiet:
                    print("Initialized baseline.")
            elif h != prev.hash:
                print(f"CHANGE DETECTED: {time.strftime('%Y-%m-%d %H:%M:%S')}")
                print_diff(prev.text, text, max_diff_lines)
                if not no_sound:
                    play_sound()
            elif not quiet:
                print(f"No change: {time.strftime('%Y-%m-%d %H:%M:%S')}")

            state[url] = {"hash": h, "text": text, "updated": now}
            save_state(state_path, state)
            prev = Snapshot(url=url, hash=h, text=text, updated=now)

        except KeyboardInterrupt:
            break
        except urllib.error.URLError as e:
            print(f"Fetch error: {e}", file=sys.stderr)
        except Exception as e:
            print(f"Unexpected error: {e}", file=sys.stderr)

        if once:
            break
        if max_checks > 0 and checks >= max_checks:
            if not quiet:
                print(f"Reached max checks ({max_checks}). Exiting.")
            break

        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            break

    if not quiet:
        print("Watcher stopped.")
    return 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Watch a web page for visible text changes.")
    p.add_argument(
        "url_positional",
        nargs="?",
        help="Optional URL to watch (positional). Overrides default if provided.",
    )
    p.add_argument("--url", help="URL to watch (same as positional).")
    p.add_argument("--interval", type=int, default=DEFAULT_INTERVAL, help="Poll interval in seconds (min 10).")
    p.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="HTTP timeout in seconds.")
    p.add_argument("--state", default=str(DEFAULT_STATE_PATH), help="Path to state JSON file.")
    p.add_argument("--once", action="store_true", help="Run one check then exit.")
    p.add_argument("--max-checks", type=int, default=0, help="Stop after N checks (0 = run forever).")
    p.add_argument("--max-diff-lines", type=int, default=40, help="Max added/removed lines to print per group.")
    p.add_argument("--quiet", action="store_true", help="Only print on changes/errors.")
    p.add_argument("--no-sound", action="store_true", help="Disable audio alert on change.")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    url = args.url or args.url_positional or DEFAULT_URL
    interval = max(10, int(args.interval))
    timeout = max(1, int(args.timeout))
    max_checks = max(0, int(args.max_checks))
    max_diff_lines = max(1, int(args.max_diff_lines))
    state_path = Path(args.state).expanduser()

    return run_watcher(
        url=url,
        interval=interval,
        timeout=timeout,
        once=bool(args.once),
        quiet=bool(args.quiet),
        state_path=state_path,
        max_checks=max_checks,
        max_diff_lines=max_diff_lines,
        no_sound=bool(args.no_sound),
    )


if __name__ == "__main__":
    raise SystemExit(main())
