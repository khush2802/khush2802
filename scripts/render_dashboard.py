#!/usr/bin/env python3
"""Render the SVG images used by this profile README.

Outputs (written to --out, default assets/generated):

  header-{dark,light}.svg               name banner
  dashboard-{dark,light}.svg            isometric contribution landscape + stats
  *-compact-{dark,light}.svg            the same two images laid out for phones
  contributions.json                    the exact numbers behind the dashboard

Data comes from the GitHub GraphQL API (contribution calendar + public repository
count) over an explicit 365-day window that ends on --end (default: today, UTC).
Colour uses GitHub's own contribution level for each day; height uses the raw daily
count on a log scale, so busy days stand out without flattening everything else.

Standard library only, so the workflow needs no dependency install.

Usage:
  GITHUB_TOKEN=... python3 scripts/render_dashboard.py --user khush2802
  python3 scripts/render_dashboard.py --from-json assets/generated/contributions.json --out preview
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import math
import os
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import escape

GRAPHQL_URL = "https://api.github.com/graphql"
WINDOW_DAYS = 365
WEEKDAY_NAMES = ("Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday")
LEVEL_FROM_API = {
    "NONE": 0,
    "FIRST_QUARTILE": 1,
    "SECOND_QUARTILE": 2,
    "THIRD_QUARTILE": 3,
    "FOURTH_QUARTILE": 4,
}

QUERY = """
query ($login: String!, $from: DateTime!, $to: DateTime!) {
  user(login: $login) {
    contributionsCollection(from: $from, to: $to) {
      contributionCalendar {
        weeks { contributionDays { date contributionCount contributionLevel } }
      }
    }
    repositories(privacy: PUBLIC, ownerAffiliations: [OWNER]) { totalCount }
  }
}
"""

MONO = "ui-monospace, SFMono-Regular, 'SF Mono', Menlo, Consolas, 'Liberation Mono', monospace"
SANS = "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'Noto Sans', Helvetica, Arial, sans-serif"

THEMES = {
    "dark": {
        "bg": "#0b0f14",
        "border": "#1f2630",
        "text": "#e6edf3",
        "muted": "#8b949e",
        "faint": "#5b6470",
        "accent": "#3fd364",
        "levels": ("#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"),
    },
    "light": {
        "bg": "#ffffff",
        "border": "#d0d7de",
        "text": "#1f2328",
        "muted": "#59636e",
        "faint": "#8c959f",
        "accent": "#1a7f37",
        "levels": ("#ebedf0", "#9be9a8", "#40c463", "#30a14e", "#216e39"),
    },
}

# Isometric geometry, in SVG user units. The week axis runs right-and-down at a
# shallow angle and the weekday axis runs left-and-down at a steep one, which turns
# the calendar into a wide landscape instead of a thin diagonal ribbon.
PITCH = 15.5            # distance between neighbouring cells
TILE = 13.0             # visible width of a cell (PITCH - TILE is the gap)
WEEK_ANGLE = math.radians(14)
DAY_ANGLE = math.radians(52)
FLOOR_HEIGHT = 2.0      # zero-contribution days are thin slabs, so the grid stays visible
MIN_HEIGHT = 8.0        # one contribution
MAX_HEIGHT = 44.0       # the busiest day in the window
SHADE_LEFT = 0.78
SHADE_RIGHT = 0.6


class DataError(RuntimeError):
    """The data source returned something we refuse to draw."""


@dataclass(frozen=True)
class Day:
    date: dt.date
    count: int
    level: int  # GitHub's bucket: 0 = none, 1-4 = quartiles of that user's activity


@dataclass(frozen=True)
class Snapshot:
    login: str
    days: tuple[Day, ...]
    public_repositories: int | None
    source: str          # short label printed on the image
    source_detail: str   # full provenance, recorded in contributions.json
    fetched_at: str


@dataclass(frozen=True)
class Metrics:
    start: dt.date
    end: dt.date
    total: int
    active_days: int
    weekday_totals: tuple[int, ...]  # Sunday first, matching GitHub's calendar rows
    busiest_weekday: int | None
    busiest_day: Day | None
    longest_streak: int
    public_repositories: int | None


# ---------------------------------------------------------------- data window

def window_for(end: dt.date, days: int = WINDOW_DAYS) -> tuple[dt.date, dt.date]:
    """Inclusive window of `days` days ending on `end`."""
    return end - dt.timedelta(days=days - 1), end


def normalise(raw_days: list[dict], start: dt.date, end: dt.date) -> tuple[Day, ...]:
    """Turn API/JSON day records into one Day per date in [start, end].

    Days outside the window are dropped. A missing day is only tolerated at the very
    end of the window (GitHub may not have rolled over to "today" yet), where it is
    recorded as zero; any other gap means the response is not trustworthy.
    """
    by_date: dict[dt.date, Day] = {}
    for item in raw_days:
        date = dt.date.fromisoformat(str(item["date"]))
        if not start <= date <= end:
            continue
        count = int(item["count"])
        level = int(item["level"])
        if count < 0 or not 0 <= level <= 4:
            raise DataError(f"impossible value for {date}: count={count} level={level}")
        if count == 0 and level != 0 or count > 0 and level == 0:
            raise DataError(f"count and level disagree for {date}: count={count} level={level}")
        by_date[date] = Day(date, count, level)

    days: list[Day] = []
    date = start
    while date <= end:
        if date not in by_date:
            if date != end:
                raise DataError(f"no data for {date}; refusing to draw a partial calendar")
            by_date[date] = Day(date, 0, 0)
        days.append(by_date[date])
        date += dt.timedelta(days=1)
    return tuple(days)


def fetch_snapshot(login: str, token: str, end: dt.date) -> Snapshot:
    start, end = window_for(end)
    variables = {
        "login": login,
        "from": f"{start.isoformat()}T00:00:00Z",
        "to": f"{end.isoformat()}T23:59:59Z",
    }
    request = urllib.request.Request(
        GRAPHQL_URL,
        data=json.dumps({"query": QUERY, "variables": variables}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": f"{login}-profile-dashboard",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise DataError(f"GitHub API returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise DataError(f"could not reach the GitHub API: {exc.reason}") from exc

    if payload.get("errors"):
        raise DataError(f"GitHub API errors: {json.dumps(payload['errors'])[:500]}")
    user = (payload.get("data") or {}).get("user")
    if not user:
        raise DataError(f"user {login!r} not found")

    weeks = user["contributionsCollection"]["contributionCalendar"]["weeks"]
    raw = [
        {
            "date": d["date"],
            "count": d["contributionCount"],
            "level": LEVEL_FROM_API[d["contributionLevel"]],
        }
        for week in weeks
        for d in week["contributionDays"]
    ]
    return Snapshot(
        login=login,
        days=normalise(raw, start, end),
        public_repositories=int(user["repositories"]["totalCount"]),
        source="GitHub GraphQL API",
        source_detail=(f"{GRAPHQL_URL}: user.contributionsCollection(from: {variables['from']}, "
                       f"to: {variables['to']}).contributionCalendar and "
                       "user.repositories(privacy: PUBLIC, ownerAffiliations: OWNER).totalCount"),
        fetched_at=dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat(),
    )


def load_snapshot(path: Path, login: str, end: dt.date | None) -> Snapshot:
    """Read a saved snapshot: either this script's own contributions.json, whose days are
    [date, count, level] triples, or a file whose days are {date, count, level} objects."""
    data = json.loads(path.read_text(encoding="utf-8"))
    raw = [d if isinstance(d, dict) else {"date": d[0], "count": d[1], "level": d[2]} for d in data["days"]]
    if not raw:
        raise DataError(f"{path} contains no days")
    last = max(dt.date.fromisoformat(d["date"]) for d in raw)
    start, end = window_for(end or last)
    public = data.get("public_repositories", (data.get("totals") or {}).get("public_repositories"))
    return Snapshot(
        login=data.get("login", login),
        days=normalise(raw, start, end),
        public_repositories=public,
        source=data.get("source", "saved snapshot"),
        source_detail=data.get("source_detail", str(path)),
        fetched_at=data.get("fetched_at", ""),
    )


# ---------------------------------------------------------------- metrics

def weekday_index(date: dt.date) -> int:
    """0 = Sunday ... 6 = Saturday, the row order of GitHub's calendar."""
    return (date.weekday() + 1) % 7


def compute_metrics(snapshot: Snapshot) -> Metrics:
    days = snapshot.days
    weekday_totals = [0] * 7
    longest = run = 0
    for day in days:
        weekday_totals[weekday_index(day.date)] += day.count
        run = run + 1 if day.count > 0 else 0
        longest = max(longest, run)
    total = sum(d.count for d in days)
    busiest_weekday = max(range(7), key=lambda i: (weekday_totals[i], -i)) if total else None
    busiest_day = max(days, key=lambda d: (d.count, d.date)) if total else None
    return Metrics(
        start=days[0].date,
        end=days[-1].date,
        total=total,
        active_days=sum(1 for d in days if d.count > 0),
        weekday_totals=tuple(weekday_totals),
        busiest_weekday=busiest_weekday,
        busiest_day=busiest_day,
        longest_streak=longest,
        public_repositories=snapshot.public_repositories,
    )


# ---------------------------------------------------------------- drawing helpers

def fmt_date(date: dt.date) -> str:
    return f"{date.day} {date:%b %Y}"


def shade(hex_colour: str, factor: float) -> str:
    r, g, b = (int(hex_colour[i:i + 2], 16) for i in (1, 3, 5))
    return "#{:02x}{:02x}{:02x}".format(*(max(0, min(255, round(c * factor))) for c in (r, g, b)))


def bar_height(count: int, peak: int) -> float:
    """Floor slab for 0; MIN_HEIGHT for 1; MAX_HEIGHT for the busiest day; log in between."""
    if count <= 0:
        return FLOOR_HEIGHT
    if peak <= 1:
        return MIN_HEIGHT
    scale = math.log(count) / math.log(peak)
    return MIN_HEIGHT + (MAX_HEIGHT - MIN_HEIGHT) * scale


def project(week: float, row: float, z: float = 0.0) -> tuple[float, float]:
    x = week * PITCH * math.cos(WEEK_ANGLE) - row * PITCH * math.cos(DAY_ANGLE)
    y = week * PITCH * math.sin(WEEK_ANGLE) + row * PITCH * math.sin(DAY_ANGLE) - z
    return x, y


def points(*pts: tuple[float, float]) -> str:
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


def text(x: float, y: float, body: str, *, size: float, fill: str, family: str = MONO,
         weight: int | None = None, anchor: str = "start", spacing: float | None = None) -> str:
    attrs = [f'x="{x:.1f}"', f'y="{y:.1f}"', f'font-family="{family}"', f'font-size="{size}"', f'fill="{fill}"']
    if weight:
        attrs.append(f'font-weight="{weight}"')
    if anchor != "start":
        attrs.append(f'text-anchor="{anchor}"')
    if spacing:
        attrs.append(f'letter-spacing="{spacing}"')
    return f"<text {' '.join(attrs)}>{escape(body)}</text>"


def cell_geometry(snapshot_days: tuple[Day, ...]) -> list[tuple[int, int, Day]]:
    """(week column, weekday row, day). Column 0 is the week containing the first day."""
    first = snapshot_days[0].date
    first_sunday = first - dt.timedelta(days=weekday_index(first))
    return [((d.date - first_sunday).days // 7, weekday_index(d.date), d) for d in snapshot_days]


def landscape(days: tuple[Day, ...], palette: dict, origin: tuple[float, float],
              scale: float = 1.0) -> tuple[list[str], dict]:
    """Extruded calendar drawn back-to-front. Returns SVG parts and anchor points."""
    peak = max((d.count for d in days), default=0)
    cells = cell_geometry(days)
    inset = (PITCH - TILE) / 2 / PITCH
    ox, oy = origin
    parts: list[str] = []

    def at(w: float, r: float, z: float = 0.0) -> tuple[float, float]:
        x, y = project(w, r, z)
        return ox + x * scale, oy + y * scale

    # Painter's order: a cell can only be hidden by cells with a larger week and/or
    # weekday index, so sorting by (week + row) draws everything behind first.
    for week, row, day in sorted(cells, key=lambda c: (c[0] + c[1], c[0])):
        h = bar_height(day.count, peak)
        colour = palette["levels"][day.level]
        w0, w1 = week + inset, week + 1 - inset
        r0, r1 = row + inset, row + 1 - inset
        top = points(at(w0, r0, h), at(w1, r0, h), at(w1, r1, h), at(w0, r1, h))
        left = points(at(w0, r1, 0), at(w1, r1, 0), at(w1, r1, h), at(w0, r1, h))
        right = points(at(w1, r0, 0), at(w1, r1, 0), at(w1, r1, h), at(w1, r0, h))
        # No per-cell <title>: GitHub embeds the SVG as an <img>, where tooltips never
        # show, and the image is regenerated daily, so every byte lands in git history.
        parts.append(
            f'<polygon points="{left}" fill="{shade(colour, SHADE_LEFT)}"/>'
            f'<polygon points="{right}" fill="{shade(colour, SHADE_RIGHT)}"/>'
            f'<polygon points="{top}" fill="{colour}"/>'
        )

    anchors = {
        "weeks": max(c[0] for c in cells) + 1,
        "month_starts": [(week, day.date) for week, row, day in cells if day.date.day == 1],
        "at": at,
    }
    return parts, anchors


def landscape_bounds(days: tuple[Day, ...], scale: float = 1.0) -> tuple[float, float, float, float]:
    """min_x, min_y, max_x, max_y of the landscape when drawn at origin (0, 0)."""
    peak = max((d.count for d in days), default=0)
    xs, ys = [], []
    for week, row, day in cell_geometry(days):
        h = bar_height(day.count, peak)
        for w in (week, week + 1):
            for r in (row, row + 1):
                for z in (0, h):
                    x, y = project(w, r, z)
                    xs.append(x * scale)
                    ys.append(y * scale)
    return min(xs), min(ys), max(xs), max(ys)


# ---------------------------------------------------------------- dashboard

WIDTH = 1000
PAD = 36


def render_dashboard(snapshot: Snapshot, metrics: Metrics, theme: str) -> str:
    p = THEMES[theme]
    days = snapshot.days
    min_x, min_y, max_x, max_y = landscape_bounds(days)

    # Centre the landscape horizontally; leave room above it for the title block.
    graph_top = 124
    origin = ((WIDTH - (max_x - min_x)) / 2 - min_x, graph_top - min_y)
    graph_bottom = graph_top + (max_y - min_y)
    height = round(graph_bottom + 104)

    cubes, anchors = landscape(days, p, origin)
    at = anchors["at"]

    period = f"{fmt_date(metrics.start)} – {fmt_date(metrics.end)}"
    out: list[str] = []

    # Title block, top left.
    out.append(text(PAD, 52, "CONTRIBUTION LANDSCAPE", size=13, fill=p["muted"], spacing=2.4))
    out.append(text(PAD, 79, f"{period} · last {WINDOW_DAYS} days", size=14.5, fill=p["faint"]))

    # Stats, top right, in the space the receding landscape leaves free.
    stats = [
        (f"{metrics.total:,}", "contributions", p["accent"]),
        (f"{metrics.active_days}", "active days", p["text"]),
    ]
    if metrics.public_repositories is not None:
        stats.append((f"{metrics.public_repositories}", "public repos", p["text"]))
    x = WIDTH - PAD
    for value, label, colour in reversed(stats):
        out.append(text(x, 62, value, size=36, fill=colour, family=SANS, weight=650, anchor="end"))
        out.append(text(x, 86, label.upper(), size=12, fill=p["muted"], anchor="end", spacing=1.5))
        x -= 158

    out.extend(cubes)

    # Month labels just in front of the landscape, where nothing can cover them.
    last_week = anchors["weeks"] - 1
    for week, date in anchors["month_starts"]:
        if week < 1 or week >= last_week:
            continue
        lx, ly = at(week + 0.5, 8.1)
        out.append(text(lx, ly, f"{date:%b}", size=12, fill=p["faint"], anchor="middle"))

    # Weekday breakdown, bottom left, under the near end of the landscape.
    bx, base = PAD + 2, height - 40
    bar_w, gap, bar_max = 16, 7, 50
    peak_total = max(metrics.weekday_totals) or 1
    out.append(text(bx, base - bar_max - 20, "BY WEEKDAY", size=12, fill=p["muted"], spacing=1.5))
    for i, total in enumerate(metrics.weekday_totals):
        h = max(2.0, bar_max * total / peak_total)
        colour = p["accent"] if i == metrics.busiest_weekday else p["levels"][2]
        x0 = bx + i * (bar_w + gap)
        out.append(f'<rect x="{x0:.1f}" y="{base - h:.1f}" width="{bar_w}" height="{h:.1f}" rx="2" '
                   f'fill="{colour}"/>')
        out.append(text(x0 + bar_w / 2, base + 18, WEEKDAY_NAMES[i][0], size=12, fill=p["faint"], anchor="middle"))
    if metrics.busiest_weekday is not None:
        busiest = WEEKDAY_NAMES[metrics.busiest_weekday]
        tx = bx + 7 * (bar_w + gap) + 10
        out.append(text(tx, base - 20, "most active", size=12, fill=p["faint"]))
        out.append(text(tx, base, busiest, size=15, fill=p["text"], family=SANS, weight=600))

    # Encoding legend and provenance, bottom right.
    lx = WIDTH - PAD
    out.append(text(lx, height - 22, f"updated {metrics.end.isoformat()} · {snapshot.source}",
                    size=12, fill=p["faint"], anchor="end"))
    legend_y = height - 58
    swatch, step = 12, 16
    start_x = lx - 5 * step - 38
    out.append(text(start_x - 8, legend_y + 10.5, "less", size=12, fill=p["faint"], anchor="end"))
    for level in range(5):
        out.append(f'<rect x="{start_x + level * step:.1f}" y="{legend_y:.1f}" width="{swatch}" '
                   f'height="{swatch}" rx="2" fill="{p["levels"][level]}"/>')
    out.append(text(start_x + 5 * step + 4, legend_y + 10.5, "more", size=12, fill=p["faint"]))
    out.append(text(start_x - 52, legend_y + 10.5, "height = log(count) ·", size=12, fill=p["faint"],
                    anchor="end"))

    title = f"{snapshot.login}: {metrics.total} GitHub contributions, {period}"
    busiest_txt = ""
    if metrics.busiest_day is not None and metrics.busiest_weekday is not None:
        busiest_txt = (f" Busiest day {metrics.busiest_day.date.isoformat()} ({metrics.busiest_day.count});"
                       f" most active weekday {WEEKDAY_NAMES[metrics.busiest_weekday]}.")
    desc = (f"Isometric contribution calendar. {metrics.active_days} active days out of {WINDOW_DAYS}."
            f"{busiest_txt} Public repositories: {metrics.public_repositories}. Source: {snapshot.source}.")
    return svg_document(WIDTH, height, title, desc, p, out)


COMPACT_WIDTH = 600
COMPACT_PAD = 26


def render_dashboard_compact(snapshot: Snapshot, metrics: Metrics, theme: str) -> str:
    """Phone-width layout: stats above a smaller landscape, larger type, no side panels."""
    p = THEMES[theme]
    days = snapshot.days
    full = landscape_bounds(days)
    scale = (COMPACT_WIDTH - 2 * COMPACT_PAD) / (full[2] - full[0])
    min_x, min_y, max_x, max_y = landscape_bounds(days, scale)

    out: list[str] = []
    x0, x1 = COMPACT_PAD, COMPACT_WIDTH - COMPACT_PAD
    out.append(text(x0, 48, "CONTRIBUTION LANDSCAPE", size=17, fill=p["muted"], spacing=2.4))
    out.append(text(x0, 78, f"{fmt_date(metrics.start)} \u2013 {fmt_date(metrics.end)}", size=19, fill=p["faint"]))

    stats = [(f"{metrics.total:,}", "contributions", p["accent"]), (f"{metrics.active_days}", "active days", p["text"])]
    if metrics.public_repositories is not None:
        stats.append((f"{metrics.public_repositories}", "public repos", p["text"]))
    column = (x1 - x0) / len(stats)
    for i, (value, label, colour) in enumerate(stats):
        sx = x0 + i * column
        out.append(text(sx, 146, value, size=52, fill=colour, family=SANS, weight=650))
        out.append(text(sx, 176, label.upper(), size=15, fill=p["muted"], spacing=1.2))

    graph_top = 214
    origin = ((COMPACT_WIDTH - (max_x - min_x)) / 2 - min_x, graph_top - min_y)
    cubes, _ = landscape(days, p, origin, scale)
    out.extend(cubes)
    height = round(graph_top + (max_y - min_y) + 92)

    if metrics.busiest_weekday is not None:
        out.append(text(x0, height - 46, f"most active: {WEEKDAY_NAMES[metrics.busiest_weekday]}",
                        size=18, fill=p["muted"]))
    out.append(text(x0, height - 20, f"updated {metrics.end.isoformat()} \u00b7 {snapshot.source}",
                    size=15, fill=p["faint"]))

    title = f"{snapshot.login}: {metrics.total} GitHub contributions, {fmt_date(metrics.start)} \u2013 {fmt_date(metrics.end)}"
    desc = f"Isometric contribution calendar. {metrics.active_days} active days out of {WINDOW_DAYS}."
    return svg_document(COMPACT_WIDTH, height, title, desc, p, out)


# ---------------------------------------------------------------- header

# A fixed miniature landscape: (week, row, level, height). Purely decorative.
HEADER_CUBES = [
    (0, 0, 1, 9), (1, 0, 2, 17), (2, 0, 1, 12), (3, 0, 3, 27),
    (0, 1, 1, 7), (1, 1, 3, 26), (2, 1, 4, 42), (3, 1, 2, 20),
    (0, 2, 2, 13), (1, 2, 1, 10), (2, 2, 3, 24), (3, 2, 1, 9),
]

TAGLINE = "SOFTWARE ENGINEERING \u00b7 APPLIED AI \u00b7 SYSTEMS"
SUBLINE = "Building software to understand how it works underneath."


def cube_cluster(p: dict, origin: tuple[float, float], scale: float) -> list[str]:
    inset = (PITCH - TILE) / 2 / PITCH
    ox, oy = origin

    def at(w: float, r: float, z: float = 0.0) -> tuple[float, float]:
        x, y = project(w, r, z / scale)
        return ox + x * scale, oy + y * scale

    out = []
    for week, row, level, h in sorted(HEADER_CUBES, key=lambda c: (c[0] + c[1], c[0])):
        colour = p["levels"][level]
        w0, w1, r0, r1 = week + inset, week + 1 - inset, row + inset, row + 1 - inset
        out.append(f'<polygon points="{points(at(w0, r1), at(w1, r1), at(w1, r1, h), at(w0, r1, h))}" '
                   f'fill="{shade(colour, SHADE_LEFT)}"/>')
        out.append(f'<polygon points="{points(at(w1, r0), at(w1, r1), at(w1, r1, h), at(w1, r0, h))}" '
                   f'fill="{shade(colour, SHADE_RIGHT)}"/>')
        out.append(f'<polygon points="{points(at(w0, r0, h), at(w1, r0, h), at(w1, r1, h), at(w0, r1, h))}" '
                   f'fill="{colour}"/>')
    return out


def render_header(login: str, theme: str, compact: bool = False) -> str:
    p = THEMES[theme]
    if compact:
        # The tagline and subline are wrapped by hand: SVG text doesn't wrap.
        width, height = COMPACT_WIDTH, 236
        out = [
            text(COMPACT_PAD, 52, "SOFTWARE ENGINEERING", size=17, fill=p["accent"], spacing=2.6),
            text(COMPACT_PAD, 78, "APPLIED AI \u00b7 SYSTEMS", size=17, fill=p["accent"], spacing=2.6),
            text(COMPACT_PAD, 140, "Khush Meena", size=56, fill=p["text"], family=SANS, weight=700, spacing=-0.6),
            text(COMPACT_PAD, 180, "Building software to understand", size=22, fill=p["muted"], family=SANS),
            text(COMPACT_PAD, 206, "how it works underneath.", size=22, fill=p["muted"], family=SANS),
        ]
        out.extend(cube_cluster(p, (500, 52), 1.2))
    else:
        width, height = WIDTH, 176
        out = [
            text(PAD, 58, TAGLINE, size=13.5, fill=p["accent"], spacing=2.6),
            text(PAD, 110, "Khush Meena", size=48, fill=p["text"], family=SANS, weight=700, spacing=-0.6),
            text(PAD, 144, SUBLINE, size=17, fill=p["muted"], family=SANS),
        ]
        out.extend(cube_cluster(p, (842, 64), 1.55))
    desc = "Khush Meena. Software engineering, applied AI, systems. " + SUBLINE
    return svg_document(width, height, f"{login} \u2014 Khush Meena", desc, p, out)


def svg_document(width: int, height: int, title: str, desc: str, p: dict, body: list[str]) -> str:
    return "\n".join([
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-labelledby="t d">',
        f'<title id="t">{escape(title)}</title>',
        f'<desc id="d">{escape(desc)}</desc>',
        f'<rect x="0.5" y="0.5" width="{width - 1}" height="{height - 1}" rx="14" '
        f'fill="{p["bg"]}" stroke="{p["border"]}"/>',
        *body,
        "</svg>",
        "",
    ])


# ---------------------------------------------------------------- output

def atomic_write(path: Path, content: str) -> None:
    """Write via a temp file in the same directory so a crash never leaves half a file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        os.chmod(tmp, 0o644)  # mkstemp creates 0600; published assets should be world-readable
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def summary_json(snapshot: Snapshot, metrics: Metrics) -> str:
    busiest = metrics.busiest_day
    data = {
        "login": snapshot.login,
        "source": snapshot.source,
        "source_detail": snapshot.source_detail,
        "fetched_at": snapshot.fetched_at,
        "window": {"start": metrics.start.isoformat(), "end": metrics.end.isoformat(), "days": WINDOW_DAYS},
        "totals": {
            "contributions": metrics.total,
            "active_days": metrics.active_days,
            "longest_streak_days": metrics.longest_streak,
            "public_repositories": metrics.public_repositories,
        },
        "weekday_totals": dict(zip(WEEKDAY_NAMES, metrics.weekday_totals)),
        "busiest_day": {"date": busiest.date.isoformat(), "count": busiest.count} if busiest else None,
        "days": [[d.date.isoformat(), d.count, d.level] for d in snapshot.days],
    }
    return json.dumps(data, indent=1) + "\n"


def render_all(snapshot: Snapshot, out_dir: Path) -> tuple[Metrics, list[Path]]:
    metrics = compute_metrics(snapshot)
    files = {}
    for t in THEMES:
        files[f"dashboard-{t}.svg"] = render_dashboard(snapshot, metrics, t)
        files[f"dashboard-compact-{t}.svg"] = render_dashboard_compact(snapshot, metrics, t)
        files[f"header-{t}.svg"] = render_header(snapshot.login, t)
        files[f"header-compact-{t}.svg"] = render_header(snapshot.login, t, compact=True)
    files["contributions.json"] = summary_json(snapshot, metrics)
    # Everything is rendered in memory before the first write, so a rendering error
    # leaves the previously published images untouched.
    written = []
    for name, content in files.items():
        atomic_write(out_dir / name, content)
        written.append(out_dir / name)
    return metrics, written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--user", default=os.getenv("GITHUB_REPOSITORY_OWNER", "khush2802"))
    parser.add_argument("--out", type=Path, default=Path("assets/generated"))
    parser.add_argument("--end", type=dt.date.fromisoformat, help="last day of the window (default: today, UTC)")
    parser.add_argument("--from-json", type=Path, help="render from a saved snapshot instead of the API")
    args = parser.parse_args(argv)

    try:
        if args.from_json:
            snapshot = load_snapshot(args.from_json, args.user, args.end)
        else:
            token = os.getenv("GH_TOKEN") or os.getenv("GITHUB_TOKEN")
            if not token:
                print("error: set GITHUB_TOKEN (or GH_TOKEN), or use --from-json", file=sys.stderr)
                return 2
            end = args.end or dt.datetime.now(dt.timezone.utc).date()
            snapshot = fetch_snapshot(args.user, token, end)
        metrics, written = render_all(snapshot, args.out)
    except DataError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    print(f"{snapshot.login}: {metrics.total} contributions, {metrics.active_days} active days, "
          f"{metrics.start} to {metrics.end} ({snapshot.source})")
    for path in written:
        print(f"wrote {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
