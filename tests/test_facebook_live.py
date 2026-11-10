import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import top_views as tv

FB_PAGE = "https://www.facebook.com/people/Honest-Wealth-Builders/61574869258101/"
LOGGED_OUT_FIRST_PAGE = 10


class FacebookLoggedOutPagination(unittest.TestCase):
    def test_loads_reels_past_the_first_page_without_login(self):
        r = tv.scrape_facebook(FB_PAGE, [], None, 1, (None, None))
        self.assertGreater(r.scanned, LOGGED_OUT_FIRST_PAGE,
                           f"only {r.scanned} reels loaded; the login dialog blocked scrolling. note={r.note!r}")


if __name__ == "__main__":
    unittest.main()
