"""Tests for render_dashboard.py. Run with: python3 -m unittest discover -s scripts"""

from __future__ import annotations

import datetime as dt
import io
import json
import tempfile
import unittest
import urllib.error
import xml.etree.ElementTree as ET
from pathlib import Path
from unittest import mock

import render_dashboard as rd

SVG_NS = "{http://www.w3.org/2000/svg}"


def make_days(start: dt.date, counts: list[int]) -> list[dict]:
    def level(c: int) -> int:
        return 0 if c == 0 else min(4, 1 + c // 3)
    return [{"date": (start + dt.timedelta(days=i)).isoformat(), "count": c, "level": level(c)}
            for i, c in enumerate(counts)]


def make_snapshot(end: dt.date = dt.date(2026, 10, 14), pattern: list[int] | None = None) -> rd.Snapshot:
    start, end = rd.window_for(end)
    pattern = pattern or [0, 1, 0, 3, 0, 0, 7]
    counts = [pattern[i % len(pattern)] for i in range(rd.WINDOW_DAYS)]
    return rd.Snapshot("octocat", rd.normalise(make_days(start, counts), start, end), 12,
                       "test data", "unit test", "2026-10-14T00:00:00+00:00")


class WindowTests(unittest.TestCase):
    def test_window_is_365_inclusive_days(self):
        start, end = rd.window_for(dt.date(2026, 10, 11))
        self.assertEqual(start, dt.date(2025, 10, 12))
        self.assertEqual((end - start).days + 1, 365)

    def test_window_across_leap_day(self):
        start, end = rd.window_for(dt.date(2028, 3, 1))
        self.assertEqual((end - start).days + 1, 365)
        self.assertEqual(start, dt.date(2027, 3, 3))


class NormaliseTests(unittest.TestCase):
    start, end = dt.date(2026, 1, 1), dt.date(2026, 1, 10)

    def test_drops_days_outside_window(self):
        raw = make_days(dt.date(2025, 12, 28), [5] * 20)
        days = rd.normalise(raw, self.start, self.end)
        self.assertEqual([d.date for d in days][0], self.start)
        self.assertEqual(len(days), 10)

    def test_missing_final_day_is_zero(self):
        raw = make_days(self.start, [1] * 9)  # stops one day short
        days = rd.normalise(raw, self.start, self.end)
        self.assertEqual(days[-1], rd.Day(self.end, 0, 0))

    def test_gap_inside_window_is_rejected(self):
        raw = [d for d in make_days(self.start, [1] * 10) if d["date"] != "2026-01-05"]
        with self.assertRaisesRegex(rd.DataError, "2026-01-05"):
            rd.normalise(raw, self.start, self.end)

    def test_inconsistent_count_and_level_is_rejected(self):
        raw = make_days(self.start, [1] * 10)
        raw[3]["level"] = 0
        with self.assertRaises(rd.DataError):
            rd.normalise(raw, self.start, self.end)

    def test_negative_count_is_rejected(self):
        raw = make_days(self.start, [1] * 10)
        raw[2]["count"] = -1
        with self.assertRaises(rd.DataError):
            rd.normalise(raw, self.start, self.end)


class GeometryTests(unittest.TestCase):
    def test_weekday_index_matches_github_rows(self):
        self.assertEqual(rd.weekday_index(dt.date(2026, 10, 11)), 0)  # Sunday
        self.assertEqual(rd.weekday_index(dt.date(2026, 10, 17)), 6)  # Saturday

    def test_partial_first_week_keeps_real_weekdays(self):
        # 2026-10-14 is a Wednesday: it must sit in row 3 of the first column,
        # not be shifted up to the Sunday row.
        days = rd.normalise(make_days(dt.date(2026, 10, 14), [1] * 7),
                            dt.date(2026, 10, 14), dt.date(2026, 10, 20))
        cells = rd.cell_geometry(days)
        self.assertEqual(cells[0][:2], (0, 3))
        sunday = next(c for c in cells if c[2].date == dt.date(2026, 10, 18))
        self.assertEqual(sunday[:2], (1, 0))

    def test_heights_are_monotonic_and_bounded(self):
        heights = [rd.bar_height(c, 20) for c in range(0, 21)]
        self.assertEqual(heights[0], rd.FLOOR_HEIGHT)
        self.assertEqual(heights[1], rd.MIN_HEIGHT)
        self.assertAlmostEqual(heights[-1], rd.MAX_HEIGHT)
        self.assertEqual(heights, sorted(heights))

    def test_single_contribution_peak_does_not_divide_by_zero(self):
        self.assertEqual(rd.bar_height(1, 1), rd.MIN_HEIGHT)


class MetricsTests(unittest.TestCase):
    def test_totals_streak_and_weekdays(self):
        start, end = dt.date(2026, 10, 4), dt.date(2026, 10, 17)  # Sunday .. Saturday, two weeks
        counts = [0, 2, 3, 0, 1, 1, 1, 0, 0, 5, 0, 0, 0, 0]
        snap = rd.Snapshot("u", rd.normalise(make_days(start, counts), start, end), None, "t", "t", "")
        m = rd.compute_metrics(snap)
        self.assertEqual(m.total, 13)
        self.assertEqual(m.active_days, 6)
        self.assertEqual(m.longest_streak, 3)
        self.assertEqual(m.weekday_totals, (0, 2, 8, 0, 1, 1, 1))
        self.assertEqual(m.busiest_weekday, 2)
        self.assertEqual(m.busiest_day.date, dt.date(2026, 10, 13))

    def test_empty_year(self):
        start, end = rd.window_for(dt.date(2026, 10, 11))
        snap = rd.Snapshot("u", rd.normalise(make_days(start, [0] * 365), start, end), 0, "t", "t", "")
        m = rd.compute_metrics(snap)
        self.assertEqual((m.total, m.active_days, m.busiest_weekday, m.busiest_day), (0, 0, None, None))
        ET.fromstring(rd.render_dashboard(snap, m, "dark"))  # still renders


class RenderTests(unittest.TestCase):
    def test_dashboard_is_valid_svg_with_one_cell_per_day(self):
        snap = make_snapshot()
        metrics = rd.compute_metrics(snap)
        for theme in rd.THEMES:
            root = ET.fromstring(rd.render_dashboard(snap, metrics, theme))
            self.assertEqual(root.tag, f"{SVG_NS}svg")
            faces = list(root.iter(f"{SVG_NS}polygon"))
            self.assertEqual(len(faces), 3 * rd.WINDOW_DAYS)  # left, right and top face per day
            texts = " ".join(t.text or "" for t in root.iter(f"{SVG_NS}text"))
            self.assertIn("15 Oct 2025", texts)
            self.assertIn("14 Oct 2026", texts)
            self.assertIn(f"{metrics.total:,}", texts)
            self.assertNotIn("nan", rd.render_dashboard(snap, metrics, theme).lower())
            compact = ET.fromstring(rd.render_dashboard_compact(snap, metrics, theme))
            self.assertEqual(len(list(compact.iter(f"{SVG_NS}polygon"))), 3 * rd.WINDOW_DAYS)
            self.assertEqual(compact.get("width"), str(rd.COMPACT_WIDTH))

    def test_text_is_escaped(self):
        snap = make_snapshot()
        snap = rd.Snapshot("a<b&c", snap.days, None, "x<y", "z", "")
        svg = rd.render_dashboard(snap, rd.compute_metrics(snap), "dark")
        ET.fromstring(svg)
        ET.fromstring(rd.render_header("a<b&c", "light"))

    def test_render_all_writes_every_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            metrics, written = rd.render_all(make_snapshot(), Path(tmp))
            names = sorted(p.name for p in written)
            self.assertEqual(names, [
                "contributions.json",
                "dashboard-compact-dark.svg", "dashboard-compact-light.svg",
                "dashboard-dark.svg", "dashboard-light.svg",
                "header-compact-dark.svg", "header-compact-light.svg",
                "header-dark.svg", "header-light.svg",
            ])
            for path in written:
                if path.suffix == ".svg":
                    ET.fromstring(path.read_text())
            data = json.loads((Path(tmp) / "contributions.json").read_text())
            self.assertEqual(data["totals"]["contributions"], metrics.total)
            self.assertEqual(len(data["days"]), rd.WINDOW_DAYS)

    def test_contributions_json_round_trips(self):
        snap = make_snapshot()
        with tempfile.TemporaryDirectory() as tmp:
            metrics, _ = rd.render_all(snap, Path(tmp))
            again = rd.load_snapshot(Path(tmp) / "contributions.json", "ignored", None)
        self.assertEqual(again.days, snap.days)
        self.assertEqual(again.public_repositories, snap.public_repositories)
        self.assertEqual(rd.compute_metrics(again), metrics)

    def test_main_renders_from_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            rd.render_all(make_snapshot(), Path(tmp) / "first")
            with mock.patch("sys.stdout", new=io.StringIO()):
                code = rd.main(["--from-json", str(Path(tmp) / "first" / "contributions.json"),
                                "--out", str(Path(tmp) / "second")])
            self.assertEqual(code, 0)
            self.assertEqual(len(list((Path(tmp) / "second").iterdir())), 9)

    def test_failed_render_leaves_existing_files_untouched(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            (out / "dashboard-dark.svg").write_text("previous")
            with mock.patch.object(rd, "render_header", side_effect=RuntimeError("boom")):
                with self.assertRaises(RuntimeError):
                    rd.render_all(make_snapshot(), out)
            self.assertEqual((out / "dashboard-dark.svg").read_text(), "previous")
            self.assertEqual(sorted(p.name for p in out.iterdir()), ["dashboard-dark.svg"])


class FetchTests(unittest.TestCase):
    end = dt.date(2026, 10, 14)

    def payload(self) -> dict:
        start, end = rd.window_for(self.end)
        names = {0: "NONE", 1: "FIRST_QUARTILE", 2: "SECOND_QUARTILE", 3: "THIRD_QUARTILE", 4: "FOURTH_QUARTILE"}
        days = make_days(start - dt.timedelta(days=2), [1] * (rd.WINDOW_DAYS + 2))  # API padding before start
        weeks, week = [], []
        for d in days:
            week.append({"date": d["date"], "contributionCount": d["count"], "contributionLevel": names[d["level"]]})
            if dt.date.fromisoformat(d["date"]).weekday() == 5:
                weeks.append({"contributionDays": week})
                week = []
        weeks.append({"contributionDays": week})
        return {"data": {"user": {
            "contributionsCollection": {"contributionCalendar": {"weeks": weeks}},
            "repositories": {"totalCount": 35},
        }}}

    def respond(self, body: dict):
        response = mock.MagicMock()
        response.__enter__.return_value = io.BytesIO(json.dumps(body).encode())
        return response

    def test_parses_graphql_response(self):
        with mock.patch.object(rd.urllib.request, "urlopen", return_value=self.respond(self.payload())) as urlopen:
            snap = rd.fetch_snapshot("khush2802", "token", self.end)
        request = urlopen.call_args.args[0]
        sent = json.loads(request.data)
        self.assertEqual(sent["variables"]["from"], "2025-10-15T00:00:00Z")
        self.assertEqual(sent["variables"]["to"], "2026-10-14T23:59:59Z")
        self.assertEqual(request.get_header("Authorization"), "Bearer token")
        self.assertEqual(len(snap.days), rd.WINDOW_DAYS)
        self.assertEqual(snap.days[0].date, dt.date(2025, 10, 15))
        self.assertEqual(snap.public_repositories, 35)

    def test_graphql_errors_raise(self):
        body = {"errors": [{"message": "Something went wrong"}]}
        with mock.patch.object(rd.urllib.request, "urlopen", return_value=self.respond(body)):
            with self.assertRaisesRegex(rd.DataError, "Something went wrong"):
                rd.fetch_snapshot("khush2802", "token", self.end)

    def test_unknown_user_raises(self):
        with mock.patch.object(rd.urllib.request, "urlopen", return_value=self.respond({"data": {"user": None}})):
            with self.assertRaisesRegex(rd.DataError, "not found"):
                rd.fetch_snapshot("nobody", "token", self.end)

    def test_http_error_raises(self):
        error = urllib.error.HTTPError(rd.GRAPHQL_URL, 401, "Unauthorized", {}, io.BytesIO(b"Bad credentials"))
        with mock.patch.object(rd.urllib.request, "urlopen", side_effect=error):
            with self.assertRaisesRegex(rd.DataError, "401"):
                rd.fetch_snapshot("khush2802", "token", self.end)

    def test_main_without_token_exits_cleanly(self):
        with mock.patch.dict(rd.os.environ, {}, clear=True), mock.patch("sys.stderr", new=io.StringIO()):
            self.assertEqual(rd.main(["--user", "khush2802", "--out", "unused"]), 2)


if __name__ == "__main__":
    unittest.main()
