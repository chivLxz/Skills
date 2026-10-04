#!/usr/bin/env python3
"""Batch-capture web pages as PNG using headless Chrome.

Usage:
    python shoot.py urls.txt -o images/ --width 1440 --height 900 --full-page
    python shoot.py urls.txt -o images/ --wait 8000

urls.txt: one URL per line; blank lines and lines starting with # are ignored.

The script prints one JSON line per URL so callers can record capture results:
    {"url": "...", "file": "images/example-com-01.png", "status": "ok"}
    {"url": "...", "file": null, "status": "failed", "error": "..."}

A non-zero exit code means every URL failed; a partial failure still exits 0 so
callers can inspect the per-URL status lines.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor

CHROME_CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
    "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
    shutil.which("google-chrome") or "",
    shutil.which("chromium") or "",
    shutil.which("chromium-browser") or "",
]


def find_chrome():
    for path in CHROME_CANDIDATES:
        if path and os.path.exists(path):
            return path
    return None


def capture(chrome, url, outdir, width, height, full_page, wait, timeout):
    os.makedirs(outdir, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False, dir=outdir) as tmp:
        out_path = tmp.name
    try:
        os.unlink(out_path)
    except OSError:
        pass

    cmd = [
        chrome,
        "--headless",
        "--disable-gpu",
        "--hide-scrollbars",
        "--no-sandbox",
        "--disable-extensions",
        "--disable-background-networking",
        f"--window-size={width},{height}",
        f"--virtual-time-budget={wait}",
        f"--screenshot={out_path}",
    ]
    if full_page:
        cmd.append("--screenshot-full-page" if _supports_full_page(chrome) else "--screenshot")
    cmd.append(url)

    try:
        proc = subprocess.run(
            cmd, capture_output=True, timeout=timeout, text=True
        )
    except subprocess.TimeoutExpired:
        _safe_unlink(out_path)
        return {"url": url, "file": None, "status": "failed", "error": "timeout"}

    if not os.path.exists(out_path) or os.path.getsize(out_path) == 0:
        _safe_unlink(out_path)
        err = (proc.stderr or "").strip().splitlines()
        return {
            "url": url,
            "file": None,
            "status": "failed",
            "error": err[-1][:200] if err else "no image produced",
        }

    final_name = f"{_host(url)}-{_next_index(outdir, _host(url)):02d}.png"
    final_path = os.path.join(outdir, final_name)
    shutil.move(out_path, final_path)
    return {"url": url, "file": final_path, "status": "ok"}


def _supports_full_page(chrome):
    return True


def _host(url):
    host = re.sub(r"^www\.", "", re.sub(r"^https?://", "", url))
    host = re.sub(r"[^A-Za-z0-9._-]+", "-", host).strip("-") or "page"
    return host[:60]


def _next_index(outdir, host):
    n = 0
    if os.path.isdir(outdir):
        for name in os.listdir(outdir):
            if name.startswith(host + "-") and name.endswith(".png"):
                try:
                    n = max(n, int(name.rsplit("-", 1)[1][:2]))
                except ValueError:
                    continue
    return n + 1


def _safe_unlink(path):
    try:
        os.unlink(path)
    except OSError:
        pass


def read_urls(path):
    urls = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if not re.match(r"^https?://", line):
                line = "https://" + line
            urls.append(line)
    return urls


def main():
    ap = argparse.ArgumentParser(description="Batch screenshot URLs via headless Chrome")
    ap.add_argument("urls", help="file with one URL per line")
    ap.add_argument("-o", "--outdir", default="images", help="output directory")
    ap.add_argument("--width", type=int, default=1440)
    ap.add_argument("--height", type=int, default=900)
    ap.add_argument("--full-page", action="store_true", help="capture entire scrollable page")
    ap.add_argument("--wait", type=int, default=6000, help="virtual time budget in ms")
    ap.add_argument("--timeout", type=int, default=45, help="per-URL timeout in seconds")
    ap.add_argument("--concurrency", type=int, default=4)
    args = ap.parse_args()

    chrome = find_chrome()
    if not chrome:
        print(json.dumps({
            "status": "failed",
            "error": "no Chrome/Chromium/Edge binary found; install Chrome or use a manual screenshot",
        }))
        return 1

    if not os.path.isfile(args.urls):
        print(f"urls file not found: {args.urls}", file=sys.stderr)
        return 1

    urls = read_urls(args.urls)
    if not urls:
        print("no URLs found in input file", file=sys.stderr)
        return 1

    results = [None] * len(urls)

    def work(i):
        results[i] = capture(
            chrome, urls[i], args.outdir, args.width, args.height,
            args.full_page, args.wait, args.timeout,
        )

    workers = max(1, min(args.concurrency, len(urls)))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(work, range(len(urls))))

    for res in results:
        print(json.dumps(res, ensure_ascii=False))

    ok = sum(1 for r in results if r and r.get("status") == "ok")
    if ok == 0:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
