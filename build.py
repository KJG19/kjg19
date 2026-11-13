"""Builds dark_mode.svg and light_mode.svg for the GitHub profile README.

Text fields come from config.json, the face comes from ascii.txt, and the
stats come from the GitHub API. Run with --sample to skip the API and use
placeholder numbers (handy for previewing layout changes locally).

Design inspired by github.com/Andrew6rant/Andrew6rant.
"""
import argparse
import datetime as dt
import json
import os
import time
from pathlib import Path
from xml.sax.saxutils import escape

import requests

import seasons
from dateutil.relativedelta import relativedelta

ROOT = Path(__file__).parent
CACHE_FILE = ROOT / "cache" / "stats.json"

WIDTH_CHARS = 60      # right panel line width, in characters
TEXT_X = 390          # where the right panel starts
ASCII_X = 15
TOP_Y = 30
LINE_H = 20
SVG_W = 985

THEMES = {
    "dark": {
        "bg": "#161b22", "text": "#c9d1d9", "key": "#ffa657", "value": "#a5d6ff",
        "dots": "#616e7f",
    },
    "light": {
        "bg": "#f6f8fa", "text": "#24292f", "key": "#953800", "value": "#0a3069",
        "dots": "#c2cfde",
    },
}

# ---------------------------------------------------------------- GitHub API

API = "https://api.github.com"


def session():
    token = os.environ.get("ACCESS_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if not token:
        raise SystemExit("Set ACCESS_TOKEN (or GITHUB_TOKEN) to fetch stats, or run with --sample.")
    s = requests.Session()
    s.headers.update({"Authorization": f"bearer {token}", "Accept": "application/vnd.github+json"})
    return s


REPO_QUERY = """
query($login: String!, $cursor: String, $privacy: RepositoryPrivacy, $affil: [RepositoryAffiliation]) {
  user(login: $login) {
    followers { totalCount }
    repositories(first: 100, after: $cursor, privacy: $privacy, ownerAffiliations: $affil) {
      totalCount
      pageInfo { hasNextPage endCursor }
      nodes { nameWithOwner stargazerCount pushedAt isFork }
    }
  }
}
"""


def list_repos(s, login, privacy, affil):
    repos, cursor, followers = [], None, 0
    while True:
        r = s.post(f"{API}/graphql", json={"query": REPO_QUERY, "variables": {
            "login": login, "cursor": cursor, "privacy": privacy, "affil": affil}})
        r.raise_for_status()
        body = r.json()
        if "errors" in body:
            raise SystemExit(f"GraphQL error: {body['errors']}")
        user = body["data"]["user"]
        followers = user["followers"]["totalCount"]
        page = user["repositories"]
        repos += page["nodes"]
        if not page["pageInfo"]["hasNextPage"]:
            return repos, followers
        cursor = page["pageInfo"]["endCursor"]


def contributor_stats(s, repo, login):
    """Returns the number of commits by `login` in `repo`, or None if GitHub is still computing."""
    for _ in range(6):
        r = s.get(f"{API}/repos/{repo}/stats/contributors")
        if r.status_code == 202:      # GitHub is building the stats; try again shortly
            time.sleep(4)
            continue
        if r.status_code == 204:      # empty repo
            return 0
        r.raise_for_status()
        for c in r.json() or []:
            if c.get("author") and c["author"]["login"].lower() == login.lower():
                return c["total"]
        return 0
    return None


def fetch_stats(cfg):
    s = session()
    login = cfg["username"]
    privacy = None if cfg.get("include_private") else "PUBLIC"

    owned, followers = list_repos(s, login, privacy, ["OWNER"])
    everything, _ = list_repos(s, login, privacy, ["OWNER", "COLLABORATOR", "ORGANIZATION_MEMBER"])

    cache = json.loads(CACHE_FILE.read_text()) if CACHE_FILE.exists() else {}
    new_cache = {}
    commits = 0
    for repo in everything:
        name = repo["nameWithOwner"]
        old = cache.get(name)
        pushed = repo["pushedAt"]
        if old and old["pushedAt"] == pushed:
            count = old["commits"]                      # nothing new pushed; reuse
        else:
            count = contributor_stats(s, name, login)
            if count is None:                           # still computing; keep last known value, retry next run
                count = old["commits"] if old else 0
                pushed = old["pushedAt"] if old else None
        new_cache[name] = {"pushedAt": pushed, "commits": count}
        commits += count

    CACHE_FILE.parent.mkdir(exist_ok=True)
    CACHE_FILE.write_text(json.dumps(new_cache, indent=2, sort_keys=True))

    return {
        "repos": len([r for r in owned if not r["isFork"]]),
        "stars": sum(r["stargazerCount"] for r in owned),
        "followers": followers,
        "commits": commits,
    }


SAMPLE_STATS = {"repos": 14, "stars": 6, "followers": 9, "commits": 812}

# ---------------------------------------------------------------- text fields


def uptime(start, today):
    d = relativedelta(today, start)
    parts = [(d.years, "year"), (d.months, "month"), (d.days, "day")]
    return ", ".join(f"{n} {unit}{'' if n == 1 else 's'}" for n, unit in parts)


def degree_bar(start_pct, done, needed, cells=10):
    """Progress = the % you started with, plus your share of the remaining courses."""
    pct = min((start_pct + (100 - start_pct) * done / needed) / 100, 1)
    filled = round(pct * cells)
    return f"[{'█' * filled}{'░' * (cells - filled)}] {int(round(pct * 100, 6) + 0.5)}%"


def fill(value, ctx):
    for k, v in ctx.items():
        value = value.replace("{" + k + "}", v)
    return value

# ---------------------------------------------------------------- SVG pieces
# Each line is built as a list of (text, css_class) segments so we can count
# characters for alignment and still colour each piece.


def seg(text, cls=None):
    return (text, cls)


def kv_line(key, value, width=WIDTH_CHARS, extra=0):
    """'. Key: ........ value' with the value right-aligned to `width`.
    `extra` reserves room for characters drawn after the value (e.g. animated dots)."""
    prefix = 2 + len(key) + 1          # ". " + key + ":"
    dots = max(width - prefix - len(value) - extra - 2, 1)
    return [seg(". ", "cc"), seg(key, "key"), seg(":"),
            seg(" " + "." * dots + " ", "cc"), seg(value, "value")]


def rule_line(label):
    head = f"- {label} " if label else ""
    return [seg(head), seg("─" * (WIDTH_CHARS - len(head)))]


def render_segments(segments):
    out = []
    for text, cls in segments:
        t = escape(text)
        out.append(f'<tspan class="{cls}">{t}</tspan>' if cls else t)
    return "".join(out)


def render_cells(cells, x0, y0):
    """Turns a {(row, col): (char, class)} dict into <tspan> rows, one colour run at a time."""
    out = []
    for r in sorted({r for r, _ in cells}):
        row = {c: v for (rr, c), v in cells.items() if rr == r and v[1]}
        if not row:
            continue
        parts, run_key, run = [], None, ""

        def flush():
            if run:
                parts.append(f'<tspan class="s-{run_key}">{escape(run)}</tspan>' if run_key else run)

        for c in range(max(row) + 1):
            ch, cls = row.get(c, (" ", None))
            key = cls if ch != " " else None      # spaces are uncoloured
            if key != run_key:
                flush()
                run_key, run = key, ""
            run += ch
        flush()
        out.append(f'<tspan x="{x0}" y="{y0 + r * LINE_H}">{"".join(parts)}</tspan>')
    return "\n".join(out)


def season_svg(scene, theme_name, top_y):
    """SVG pieces for the seasonal strip: CSS, the static layer, and every animation frame."""
    static, frames, duration = scene
    x0 = round((SVG_W - seasons.COLS * 9.6) / 2)
    pal = seasons.COLOURS[theme_name]
    n = len(frames)
    css = [f".s-{k} {{fill: {v};}}" for k, v in pal.items()]
    css += [
        f".sf {{visibility: hidden; animation: sshow {duration}s steps(1) infinite;}}",
        f"@keyframes sshow {{ 0% {{visibility: visible}} {100 / n - 0.02:.4f}% {{visibility: hidden}} 100% {{visibility: hidden}} }}",
    ]
    body = [f"<text>{render_cells(static, x0, top_y)}</text>"]
    for i, fr in enumerate(frames):
        delay = i * duration / n - duration
        body.append(f'<text class="sf" style="animation-delay:{delay:.3f}s">{render_cells(fr, x0, top_y)}</text>')
    return css, body


def build_svg(cfg, ascii_lines, stats, theme_name, today, scene=None):
    a_size = cfg.get("ascii_font_size", 16)
    a_line = round(a_size * 1.25, 2)
    th = THEMES[theme_name]
    ctx = {
        "uptime": uptime(dt.date.fromisoformat(cfg["uptime_start"]), today),
        "degree_bar": degree_bar(cfg["degree_start_percent"], cfg["degree_courses_done"],
                                 cfg["degree_courses_needed"]),
    }

    lines = []      # list of (segments, extras) where extras is raw SVG appended after the line
    for row in cfg["rows"]:
        kind = row["type"]
        if kind == "header":
            h = cfg["header"]
            lines.append(([seg(h, "head"), seg(" " + "─" * (WIDTH_CHARS - len(h) - 1))], ""))
        elif kind == "blank":
            lines.append(([seg("")], ""))
        elif kind == "section":
            lines.append((rule_line(row["title"]), ""))
        elif kind == "kv":
            value = fill(row["value"], ctx)
            if row.get("animate") == "dots":
                segs = kv_line(row["key"], value, extra=3)
                anim = ('<tspan class="value d1">.</tspan>'
                        '<tspan class="value d2">.</tspan>'
                        '<tspan class="value d3">.</tspan>')
                lines.append((segs, anim))
            else:
                lines.append((kv_line(row["key"], value), ""))
        elif kind == "stats":
            half = 29
            left = kv_line("Repos", f"{stats['repos']:,}", width=half)
            right = kv_line("Stars", f"{stats['stars']:,}", width=WIDTH_CHARS - half - 1)[1:]
            lines.append((left + [seg(" | ", "cc")] + right, ""))
            left = kv_line("Commits", f"{stats['commits']:,}", width=half)
            right = kv_line("Followers", f"{stats['followers']:,}", width=WIDTH_CHARS - half - 1)[1:]
            lines.append((left + [seg(" | ", "cc")] + right, ""))

        elif kind == "prompt":
            lines.append(([seg(f"{cfg['username'].lower()}@github", "head"), seg(":~$ ")],
                          '<tspan class="cursor">█</tspan>'))

    ascii_h = len(ascii_lines) * a_line
    height = max(TOP_Y + len(lines) * LINE_H, round(TOP_Y - LINE_H + a_size + ascii_h))
    season_css, season_body = [], []
    if scene:
        strip_top = height + 22
        season_css, season_body = season_svg(scene, theme_name, strip_top)
        height = strip_top + seasons.ROWS * LINE_H

    out = [
        "<?xml version='1.0' encoding='UTF-8'?>",
        f'<svg xmlns="http://www.w3.org/2000/svg" xml:space="preserve" font-family="ConsolasFallback,Consolas,Menlo,\'DejaVu Sans Mono\',monospace" '
        f'width="{SVG_W}px" height="{height}px" font-size="16px">',
        "<style>",
        "@font-face { src: local('Consolas'), local('Consolas Bold'); font-family: 'ConsolasFallback';"
        " font-display: swap; -webkit-size-adjust: 109%; size-adjust: 109%; }",
        f".key {{fill: {th['key']};}}",
        f".value {{fill: {th['value']};}}",
        f".cc {{fill: {th['dots']};}}",
        f".head {{fill: {th['key']}; font-weight: bold;}}",
        "text, tspan {white-space: pre;}",
        # buffering dots: each dot fades in one after another, then all reset
        "@keyframes dot1 { 0%, 20% {opacity: 0} 25%, 100% {opacity: 1} }",
        "@keyframes dot2 { 0%, 45% {opacity: 0} 50%, 100% {opacity: 1} }",
        "@keyframes dot3 { 0%, 70% {opacity: 0} 75%, 100% {opacity: 1} }",
        ".d1 {animation: dot1 2s steps(1) infinite;}",
        ".d2 {animation: dot2 2s steps(1) infinite;}",
        ".d3 {animation: dot3 2s steps(1) infinite;}",
        "@keyframes blink { 0%, 50% {opacity: 1} 51%, 100% {opacity: 0} }",
        f".cursor {{fill: {th['text']}; animation: blink 1.1s steps(1) infinite;}}",
        *season_css,
        "</style>",
        f'<rect width="{SVG_W}px" height="{height}px" fill="{th["bg"]}" rx="15"/>',
        f'<text x="{ASCII_X}" y="{TOP_Y}" fill="{th["text"]}" class="ascii" font-size="{a_size}px">',
    ]
    a_top = TOP_Y - LINE_H + a_size
    for i, line in enumerate(ascii_lines):
        out.append(f'<tspan x="{ASCII_X}" y="{a_top + i * a_line:.2f}">{escape(line)}</tspan>')
    out.append("</text>")

    out.append(f'<text x="{TEXT_X}" y="{TOP_Y}" fill="{th["text"]}">')
    for i, (segs, extra) in enumerate(lines):
        out.append(f'<tspan x="{TEXT_X}" y="{TOP_Y + i * LINE_H}">{render_segments(segs)}{extra}</tspan>')
    out.append("</text>")
    out.extend(season_body)
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", action="store_true", help="use placeholder stats instead of the GitHub API")
    ap.add_argument("--season", choices=list(seasons.SCENES), help="force a season (default: pick by month)")
    args = ap.parse_args()

    cfg = json.loads((ROOT / "config.json").read_text(encoding="utf-8"))
    def load_ascii(theme):
        # ascii_dark.txt / ascii_light.txt if present (shading suited to each background), else ascii.txt
        f = ROOT / f"ascii_{theme}.txt"
        f = f if f.exists() else ROOT / "ascii.txt"
        return f.read_text(encoding="utf-8").rstrip("\n").split("\n")
    stats = SAMPLE_STATS if args.sample else fetch_stats(cfg)
    today = dt.date.today()
    season = args.season or cfg.get("season", "auto")
    scene = seasons.SCENES[season]() if season != "auto" else seasons.scene_for(today.month)

    for theme in THEMES:
        (ROOT / f"{theme}_mode.svg").write_text(build_svg(cfg, load_ascii(theme), stats, theme, today, scene), encoding="utf-8")
    print("Built SVGs with stats:", stats)


if __name__ == "__main__":
    main()
