#!/usr/bin/env python3
"""
Fetch a Kaggle user's public profile page, extract their "earned by exploration"
achievement badges (Community Member, Agent of Discord, course-completion badges,
tenure badges, etc.), and render them as a self-contained SVG strip.

This relies on parsing JSON that Kaggle embeds in the profile page HTML for
client-side hydration. Kaggle has no official public API for this data, so
this script is inherently a scraper: it can break if Kaggle changes their
frontend. If it does, run with --debug to dump the raw JSON blobs found on
the page so the parsing logic can be adjusted.

Kaggle also serves a reCAPTCHA challenge page instead of real profile HTML to
plain unauthenticated requests, which --debug will surface as zero JSON blobs
found. Use --cookie-file to send a real logged-in session's Cookie header,
which is much less likely to get challenged. See SETUP.md for how to capture
one from your browser.

Usage:
    python fetch_and_render.py --username evanka1 --out kaggle-badges.svg
    python fetch_and_render.py --username evanka1 --out kaggle-badges.svg --debug
    python fetch_and_render.py --username evanka1 --out kaggle-badges.svg --cookie-file kaggle_cookie.txt
"""

import argparse
import base64
import json
import re
import sys
import urllib.request
from html.parser import HTMLParser

PROFILE_URL_TMPL = "https://www.kaggle.com/{username}"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)

BADGE_KEY_CANDIDATES = ("badges", "achievements", "userAchievements", "earnedBadges")


def fetch_html(username: str, cookie: str = "") -> str:
    url = PROFILE_URL_TMPL.format(username=username)
    headers = {"User-Agent": USER_AGENT}
    if cookie:
        headers["Cookie"] = cookie
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


class ScriptBlockExtractor(HTMLParser):
    """Pulls out the text content of every <script class="kaggle-component" ...> tag."""

    def __init__(self):
        super().__init__()
        self.in_target = False
        self.current = []
        self.blocks = []

    def handle_starttag(self, tag, attrs):
        if tag != "script":
            return
        attrs_d = dict(attrs)
        cls = attrs_d.get("class", "")
        if "kaggle-component" in cls:
            self.in_target = True
            self.current = []

    def handle_endtag(self, tag):
        if tag == "script" and self.in_target:
            self.in_target = False
            self.blocks.append("".join(self.current))

    def handle_data(self, data):
        if self.in_target:
            self.current.append(data)


def extract_json_blobs(html: str):
    parser = ScriptBlockExtractor()
    parser.feed(html)
    blobs = []
    for raw in parser.blocks:
        raw = raw.strip()
        if not raw:
            continue
        try:
            blobs.append(json.loads(raw))
        except json.JSONDecodeError:
            # Some blocks wrap JSON in extra JS; try to isolate the outermost {...}
            start = raw.find("{")
            end = raw.rfind("}")
            if start != -1 and end != -1 and end > start:
                try:
                    blobs.append(json.loads(raw[start : end + 1]))
                except json.JSONDecodeError:
                    continue
    return blobs


def find_badge_lists(obj, path="root"):
    """Recursively walk parsed JSON looking for lists that look like badge collections."""
    found = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in BADGE_KEY_CANDIDATES and isinstance(value, list):
                found.append((f"{path}.{key}", value))
            found.extend(find_badge_lists(value, f"{path}.{key}"))
    elif isinstance(obj, list):
        for i, item in enumerate(obj):
            found.extend(find_badge_lists(item, f"{path}[{i}]"))
    return found


def looks_like_badge(entry) -> bool:
    if not isinstance(entry, dict):
        return False
    keys = {k.lower() for k in entry.keys()}
    has_name = bool({"name", "title"} & keys)
    has_desc = bool({"description", "desc"} & keys)
    has_earned_signal = bool(
        {"awardedat", "earnedat", "achieveddate", "unlockedat", "date", "awarded"} & keys
    )
    return has_name and (has_desc or has_earned_signal)


def normalize_badge(entry):
    def get(*keys):
        for k in keys:
            for actual_key in entry.keys():
                if actual_key.lower() == k:
                    return entry[actual_key]
        return None

    return {
        "name": get("name", "title") or "Unknown badge",
        "description": get("description", "desc") or "",
        "date": get("awardedat", "earnedat", "achieveddate", "unlockedat", "date"),
        "icon_url": get("iconurl", "imageurl", "icon", "image"),
    }


def download_icon_as_data_uri(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
        mime = "image/png"
        if url.lower().endswith(".svg"):
            mime = "image/svg+xml"
        elif url.lower().endswith(".jpg") or url.lower().endswith(".jpeg"):
            mime = "image/jpeg"
        b64 = base64.b64encode(data).decode("ascii")
        return f"data:{mime};base64,{b64}"
    except Exception:
        return ""


def render_svg(badges, theme="dark"):
    bg = "#0d1117" if theme == "dark" else "#ffffff"
    fg = "#c9d1d9" if theme == "dark" else "#24292f"
    sub = "#8b949e" if theme == "dark" else "#57606a"
    card_bg = "#161b22" if theme == "dark" else "#f6f8fa"
    border = "#30363d" if theme == "dark" else "#d0d7de"

    card_w, card_h, gap, pad = 260, 90, 12, 16
    cols = 2
    n = len(badges)
    rows = (n + cols - 1) // cols if n else 1
    width = pad * 2 + cols * card_w + (cols - 1) * gap
    height = pad * 2 + rows * card_h + (rows - 1) * gap

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" font-family="Segoe UI, Helvetica, Arial, sans-serif">',
        f'<rect x="0" y="0" width="{width}" height="{height}" rx="10" fill="{bg}"/>',
    ]

    for i, b in enumerate(badges):
        col = i % cols
        row = i // cols
        x = pad + col * (card_w + gap)
        y = pad + row * (card_h + gap)

        parts.append(
            f'<rect x="{x}" y="{y}" width="{card_w}" height="{card_h}" rx="8" '
            f'fill="{card_bg}" stroke="{border}" stroke-width="1"/>'
        )

        icon_size = 48
        icon_x = x + 12
        icon_y = y + (card_h - icon_size) // 2
        if b.get("icon_data_uri"):
            parts.append(
                f'<image href="{b["icon_data_uri"]}" x="{icon_x}" y="{icon_y}" '
                f'width="{icon_size}" height="{icon_size}"/>'
            )
        else:
            parts.append(
                f'<circle cx="{icon_x + icon_size/2}" cy="{icon_y + icon_size/2}" '
                f'r="{icon_size/2}" fill="#d4a72c"/>'
            )

        text_x = icon_x + icon_size + 12
        text_w = card_w - (icon_size + 12) - 24
        name = escape_xml(truncate(b["name"], 28))
        date = escape_xml(b.get("date") or "")

        parts.append(
            f'<text x="{text_x}" y="{y + 30}" font-size="13" font-weight="600" fill="{fg}">'
            f"{name}</text>"
        )
        if date:
            parts.append(
                f'<text x="{text_x}" y="{y + 50}" font-size="11" fill="{sub}">{date}</text>'
            )

    parts.append("</svg>")
    return "\n".join(parts)


def truncate(s, n):
    return s if len(s) <= n else s[: n - 1] + "…"


def escape_xml(s):
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--username", required=True)
    ap.add_argument("--out", default="kaggle-badges.svg")
    ap.add_argument("--theme", default="dark", choices=["dark", "light"])
    ap.add_argument("--debug", action="store_true", help="Dump raw JSON blobs and exit")
    ap.add_argument(
        "--cookie-file",
        help=(
            "Path to a file containing a raw Kaggle 'Cookie' header value from a "
            "logged-in browser session. Kaggle's anonymous-request bot detection "
            "(reCAPTCHA challenge page) blocks plain scraping; a real session "
            "cookie is much more likely to get through. See SETUP.md for how to "
            "capture one."
        ),
    )
    args = ap.parse_args()

    cookie = ""
    if args.cookie_file:
        with open(args.cookie_file) as f:
            cookie = f.read().strip()

    html = fetch_html(args.username, cookie=cookie)
    blobs = extract_json_blobs(html)

    if args.debug:
        with open("kaggle_debug_blobs.json", "w") as f:
            json.dump(blobs, f, indent=2)
        print(f"Found {len(blobs)} JSON blob(s) on the page.")
        print("Wrote them to kaggle_debug_blobs.json for inspection.")
        sys.exit(0)

    candidate_lists = []
    for blob in blobs:
        candidate_lists.extend(find_badge_lists(blob))

    badge_entries = []
    for _, lst in candidate_lists:
        for entry in lst:
            if looks_like_badge(entry):
                badge_entries.append(normalize_badge(entry))

    # De-duplicate by name
    seen = set()
    unique_badges = []
    for b in badge_entries:
        if b["name"] not in seen:
            seen.add(b["name"])
            unique_badges.append(b)

    if not unique_badges:
        print(
            "No badges found. Kaggle's page structure may have changed, or the "
            "profile has no achievement badges. Re-run with --debug and share "
            "kaggle_debug_blobs.json so the parser can be adjusted.",
            file=sys.stderr,
        )
        sys.exit(1)

    for b in unique_badges:
        if b.get("icon_url"):
            b["icon_data_uri"] = download_icon_as_data_uri(b["icon_url"])

    svg = render_svg(unique_badges, theme=args.theme)
    with open(args.out, "w") as f:
        f.write(svg)

    print(f"Wrote {len(unique_badges)} badge(s) to {args.out}")


if __name__ == "__main__":
    main()
