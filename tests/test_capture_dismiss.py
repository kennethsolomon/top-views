import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import top_views as tv

SEL = '[role="dialog"] [aria-label="Close"]'


class FakeLocator:
    def __init__(self, page):
        self.page = page
        self.first = self

    def is_visible(self):
        return self.page.visible

    def click(self, **kw):
        self.page.clicks += 1
        if self.page.click_error:
            raise self.page.click_error


class FakeResp:
    status = 200


class FakePage:
    def __init__(self, visible=False, click_error=None):
        self.visible = visible
        self.click_error = click_error
        self.clicks = 0
        self.locators = []
        self.scrolls = 0

    def on(self, *a):
        pass

    def goto(self, *a, **kw):
        return FakeResp()

    def wait_for_timeout(self, ms):
        pass

    def locator(self, sel):
        self.locators.append(sel)
        return FakeLocator(self)

    def evaluate(self, js):
        self.scrolls += 1

    @property
    def mouse(self):
        return mock.Mock()

    def inner_text(self, sel):
        return "body text"


def run_capture(page, dismiss):
    ctx = mock.Mock()
    ctx.new_page.return_value = page
    browser = mock.Mock()
    browser.new_context.return_value = ctx
    pw = mock.MagicMock()
    pw.__enter__.return_value.chromium.launch.return_value = browser
    with mock.patch.object(tv, "sync_playwright", return_value=pw):
        return tv.capture("https://example.test/", [], max_scrolls=2, dismiss=dismiss)


class CaptureDismiss(unittest.TestCase):
    def test_no_dismiss_never_touches_locator(self):
        page = FakePage(visible=True)
        _, text = run_capture(page, None)
        self.assertEqual(page.locators, [])
        self.assertEqual(text, "body text")

    def test_dialog_absent_does_not_click_or_crash(self):
        page = FakePage(visible=False)
        _, text = run_capture(page, SEL)
        self.assertEqual(page.clicks, 0)
        self.assertEqual(text, "body text")

    def test_dialog_present_is_clicked_once(self):
        page = FakePage(visible=True)
        run_capture(page, SEL)
        self.assertEqual(page.clicks, 1)
        self.assertGreater(page.scrolls, 0)

    def test_click_failure_does_not_abort_capture(self):
        # dialog animates out / is covered between is_visible() and click():
        # Playwright click() then waits 30s for actionability and raises TimeoutError.
        # Before the change, capture() returned the first page of reels; now the whole scrape dies.
        err = tv.PlaywrightTimeout("locator.click: Timeout 30000ms exceeded")
        page = FakePage(visible=True, click_error=err)
        try:
            bodies, text = run_capture(page, SEL)
        except Exception as e:
            self.fail(f"capture() raised {type(e).__name__}: {e} when the dismiss click failed; "
                      "an optional dismiss must not lose the reels already reachable")
        self.assertEqual(text, "body text")
        self.assertGreater(page.scrolls, 0)

    def test_click_uses_bounded_timeout(self):
        # an unbounded click() blocks up to Playwright's 30s default on a covered/detached button
        page = FakePage(visible=True)
        seen = {}

        def click(self, **kw):
            seen.update(kw)
        with mock.patch.object(FakeLocator, "click", click):
            run_capture(page, SEL)
        self.assertIn("timeout", seen, "dismiss click() has no timeout; a stuck overlay stalls capture 30s then crashes")
        self.assertLessEqual(seen["timeout"], 5000)


if __name__ == "__main__":
    unittest.main()
