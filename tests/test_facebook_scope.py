import base64
import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from datetime import date, timedelta
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import top_views as tv

FB_PAGE = "https://www.facebook.com/people/Honest-Wealth-Builders/61574869258101/"
SINCE = date(2026, 9, 18)
DIALOG_CLOSE = '[role="dialog"] [aria-label="Close"]'


def reel_id(vid: str) -> str:
    return base64.b64encode(f"S:_I61574869258101:{vid}".encode()).decode().rstrip("=")


def reels_body(vids: list[str], has_next: bool, views: dict[str, str] | None = None) -> str:
    edges = [{"profile_reel_node": {"node": {"id": reel_id(v), "video": {"play_count_reduced": (views or {}).get(v, str(int(v) * 10))}}}}
             for v in vids]
    blob = {"data": {"node": {"aggregated_fb_shorts": {"edges": edges, "page_info": {"has_next_page": has_next}}}}}
    return json.dumps(blob) + "\n" + json.dumps({"extensions": {"is_final": True}})


def thirty_reel_pages() -> list[str]:
    # logged out, Facebook serves three pages of 10 then the login wall, with has_next_page still true
    ids = [str(1000 + i) for i in range(30)]
    return [reels_body(ids[0:10], True), reels_body(ids[10:20], True), reels_body(ids[20:30], True)]


def dated(start: date):
    # reel 1000 + i was uploaded i days after start
    return lambda url: (f"caption {url}", start + timedelta(days=int(url.rstrip("/").rsplit("/", 1)[-1]) - 1000))


class FacebookScope(unittest.TestCase):
    def scrape(self, bodies, cookies=(), window=(None, None), top_n=10, meta=None):
        with mock.patch.object(tv, "capture", return_value=(bodies, "")) as cap, \
             mock.patch.object(tv, "ytdlp_meta", side_effect=meta or (lambda u, b: ("", None))):
            r = tv.scrape_facebook(FB_PAGE, list(cookies), "chrome", top_n, window)
        return r, cap

    def run_main(self, argv, capture_side_effect, meta=None):
        out = io.StringIO()
        with tempfile.TemporaryDirectory() as tmp, \
             mock.patch.object(sys, "argv", ["top-views", *argv, "--out-dir", tmp]), \
             mock.patch.object(tv, "browser_cookies", return_value=[]), \
             mock.patch.object(tv, "capture", side_effect=capture_side_effect), \
             mock.patch.object(tv, "ytdlp_meta", side_effect=meta or (lambda u, b: ("", None))), \
             redirect_stdout(out):
            code = tv.main()
            report = next(Path(tmp).glob("*.html")).read_text(encoding="utf-8")
        return code, out.getvalue(), report

    def test_happy_logged_out_loads_all_30_reels_and_dismisses_dialog(self):
        r, cap = self.scrape(thirty_reel_pages())
        self.assertEqual(r.scanned, 30)
        self.assertEqual([v.views for v in r.top], [(1029 - i) * 10 for i in range(10)])
        self.assertEqual(cap.call_args.args[0], FB_PAGE + "?sk=reels_tab")
        self.assertEqual(cap.call_args.kwargs["dismiss"], DIALOG_CLOSE)

    def test_boundary_since_is_inclusive_and_duplicate_reels_count_once(self):
        pages = thirty_reel_pages() + [reels_body(["1029"], True)]
        # reel 1000 uploaded SINCE - 1 day, reel 1001 exactly on SINCE
        r, _ = self.scrape(pages, window=(SINCE, None), top_n=30, meta=lambda u, b: dated(SINCE - timedelta(days=1))(u))
        self.assertEqual(r.scanned, 30)
        urls = {v.url for v in r.top}
        self.assertIn("https://www.facebook.com/reel/1001/", urls)
        self.assertNotIn("https://www.facebook.com/reel/1000/", urls)
        self.assertEqual(len(r.top), 29)

    def test_invalid_login_wall_without_reels_raises_platform_error(self):
        bodies = ["<html><body>You must log in to continue.</body></html>", "{not json", json.dumps({"data": {}})]
        with self.assertRaisesRegex(tv.PlatformError, "login wall"):
            self.scrape(bodies)

    def test_empty_no_reel_in_since_window_gives_empty_top_not_error(self):
        r, _ = self.scrape(thirty_reel_pages(), window=(SINCE, None), meta=lambda u, b: dated(SINCE - timedelta(days=60))(u))
        self.assertEqual(r.scanned, 30)
        self.assertEqual(r.top, [])
        self.assertTrue(r.note.startswith("PARTIAL"))

    def test_permission_logged_out_note_asks_for_facebook_login(self):
        r, _ = self.scrape(thirty_reel_pages())
        self.assertIn("PARTIAL: Facebook only shows the latest 30 reels to logged-out visitors", r.note)
        self.assertIn("Log into Facebook in Chrome", r.note)

    def test_permission_logged_in_does_not_blame_login(self):
        cookie = [{"name": "c_user", "value": "1", "domain": ".facebook.com", "path": "/", "secure": True}]
        r, _ = self.scrape(thirty_reel_pages(), cookies=cookie)
        self.assertIn("scrolling stopped early", r.note)
        self.assertNotIn("logged-out", r.note)
        last = thirty_reel_pages()[:2] + [reels_body([str(1020 + i) for i in range(10)], False)]
        r, _ = self.scrape(last, cookies=cookie)
        self.assertNotIn("PARTIAL", r.note)

    def test_failure_http_error_is_reported_and_exit_code_is_1(self):
        code, out, report = self.run_main([FB_PAGE], tv.PlatformError(f"GET {FB_PAGE}?sk=reels_tab -> HTTP 403"))
        self.assertEqual(code, 1)
        self.assertIn("FAILED: GET", out)
        self.assertIn("HTTP 403", report)

    def test_ui_state_partial_note_and_date_range_shown_in_terminal_and_html(self):
        code, out, report = self.run_main([FB_PAGE, "--cookies-from-browser", "chrome", "--since", str(SINCE)],
                                          lambda *a, **k: (thirty_reel_pages(), ""),
                                          meta=lambda u, b: dated(SINCE - timedelta(days=10))(u))
        self.assertEqual(code, 0)
        self.assertIn("scanned 30 videos (PARTIAL: Facebook only shows the latest 30 reels to logged-out visitors.", out)
        self.assertIn("Date range: 2026-09-18 to any, 10 match", out)
        self.assertIn("<p class=warn>PARTIAL: Facebook only shows the latest 30 reels", report)


if __name__ == "__main__":
    unittest.main()
