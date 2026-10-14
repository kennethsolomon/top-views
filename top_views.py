import argparse
import base64
import csv
import html
import json
import re
import shutil
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeout, sync_playwright

REPORT_DIR = Path(__file__).resolve().parent / "reports"
LM_URL = "http://localhost:1234"
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
COOKIE_DOMAINS = ("tiktok.com", "instagram.com", "facebook.com")
YTDLP = str(Path(sys.executable).with_name("yt-dlp"))


class PlatformError(Exception):
    pass


@dataclass
class Video:
    url: str
    views: int
    caption: str = ""
    uploaded: date | None = None
    approx: bool = False

    @property
    def per_day(self) -> float | None:
        if not self.uploaded:
            return None
        return self.views / max((date.today() - self.uploaded).days, 1)


@dataclass
class Result:
    platform: str
    url: str
    scanned: int = 0
    top: list[Video] | None = None
    note: str = ""
    error: str = ""
    topics: list[str] | None = None
    summary: str = ""


def platform_of(url: str) -> str:
    for name in ("tiktok", "instagram", "facebook"):
        if f"{name}.com" in url:
            return name
    raise SystemExit(f"Unsupported URL (need tiktok/instagram/facebook): {url}")


def playwright_profile_cookies(profile: Path) -> list[dict]:
    """Playwright/MCP Chrome profiles encrypt cookies with a mock keychain; only a Playwright browser can read them."""
    src = profile / "Cookies"
    if not src.is_file():
        raise SystemExit(f"No Cookies file in {profile}")
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "Default").mkdir()
        shutil.copy2(src, Path(tmp) / "Default" / "Cookies")
        with sync_playwright() as p:
            ctx = p.chromium.launch_persistent_context(tmp, headless=True, channel="chromium")
            cookies = ctx.cookies()
            ctx.close()
    return [c for c in cookies if c["domain"].lstrip(".").endswith(COOKIE_DOMAINS)]


def browser_cookies(browser: str | None) -> list[dict]:
    if not browser:
        return []
    name, _, profile = browser.partition(":")
    if name == "playwright":
        cookies = playwright_profile_cookies(Path(profile).expanduser())
    else:
        from yt_dlp.cookies import extract_cookies_from_browser
        jar = extract_cookies_from_browser(name, profile or None)
        cookies = [{"name": c.name, "value": c.value, "domain": c.domain, "path": c.path or "/", "secure": bool(c.secure)}
                   for c in jar if c.domain.lstrip(".").endswith(COOKIE_DOMAINS)]
    if cookies and not any(c["value"] for c in cookies):
        raise SystemExit(f"Cookies from {browser!r} could not be decrypted (all values empty). "
                         "For a Playwright/MCP Chrome profile use --cookies-from-browser playwright:<profile dir>.")
    return cookies


def capture(page_url: str, cookies: list[dict], max_scrolls: int = 60) -> tuple[list[str], str]:
    """Load the page in headless Chromium, scroll until no new network data, return response bodies + page text."""
    bodies: list[str] = []

    def on_resp(r):
        if r.request.resource_type in ("xhr", "fetch", "document"):
            try:
                bodies.append(r.text())
            except Exception:  # redirects / evicted bodies have no text; nothing to parse
                pass

    with sync_playwright() as p:
        b = p.chromium.launch(headless=True, channel="chromium", args=["--disable-blink-features=AutomationControlled"])
        ctx = b.new_context(user_agent=UA, locale="en-US")
        if cookies:
            ctx.add_cookies(cookies)
        pg = ctx.new_page()
        pg.on("response", on_resp)
        resp = pg.goto(page_url, wait_until="domcontentloaded", timeout=60000)
        if resp is None or resp.status >= 400:
            raise PlatformError(f"GET {page_url} -> HTTP {resp.status if resp else 'no response'}")
        pg.wait_for_timeout(6000)
        idle = 0
        while idle < 3 and max_scrolls > 0:
            n = len(bodies)
            pg.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            pg.mouse.wheel(0, 3000)
            pg.wait_for_timeout(2500)
            idle = idle + 1 if len(bodies) == n else 0
            max_scrolls -= 1
        text = pg.inner_text("body")
        b.close()
    return bodies, text


def parse_count(s: str) -> tuple[int, bool]:
    m = re.fullmatch(r"([\d.,]+)\s*([KMB]?)", s.strip(), re.I)
    if not m:
        raise PlatformError(f"Unparseable view count: {s!r}")
    mult = {"": 1, "K": 1_000, "M": 1_000_000, "B": 1_000_000_000}[m.group(2).upper()]
    return int(float(m.group(1).replace(",", "")) * mult), mult > 1


def ytdlp_meta(url: str, cookies_browser: str | None) -> tuple[str, date | None]:
    cmd = [YTDLP, "-J", "--skip-download", url] + (["--cookies-from-browser", cookies_browser]
                                                          if cookies_browser and not cookies_browser.startswith("playwright:") else [])
    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    if r.returncode != 0:
        raise PlatformError(f"yt-dlp metadata failed for {url}: {r.stderr.strip().splitlines()[-1]}")
    d = json.loads(r.stdout)
    up = datetime.strptime(d["upload_date"], "%Y%m%d").date() if d.get("upload_date") else None
    return d.get("description") or d.get("title") or "", up


def scrape_tiktok(url: str, cookies: list[dict]) -> Result:
    bodies, _ = capture(url, cookies)
    items: dict[str, dict] = {}
    expected = None
    handle = re.search(r"@([\w.]+)", url).group(1)
    for t in bodies:
        if expected is None and f'"uniqueId":"{handle}"' in t and (m := re.search(r'"videoCount":(\d+)', t)):
            expected = int(m.group(1))
        if t.startswith("{") and '"itemList"' in t:
            for it in json.loads(t).get("itemList") or []:
                if it.get("author", {}).get("uniqueId", "").lower() == handle.lower():
                    items[it["id"]] = it
    if not items:
        raise PlatformError(f"No videos by @{handle} returned by TikTok (item_list API empty or blocked)")
    vids = [Video(url=f"https://www.tiktok.com/@{handle}/video/{i['id']}", views=int(i["stats"]["playCount"]),
                  caption=i.get("desc", ""), uploaded=datetime.fromtimestamp(int(i["createTime"]), timezone.utc).date())
            for i in items.values()]
    note = f"profile counter says {expected} videos" if expected is not None else ""
    return Result("TikTok", url, len(vids), sorted(vids, key=lambda v: v.views, reverse=True)[:5], note)


def walk(o):
    if isinstance(o, dict):
        yield o
        for v in o.values():
            yield from walk(v)
    elif isinstance(o, list):
        for v in o:
            yield from walk(v)


def json_blobs(bodies: list[str]):
    for t in bodies:
        # API bodies may be newline-delimited JSON (Facebook GraphQL streams); HTML embeds JSON in script tags
        chunks = t.splitlines() if t.lstrip().startswith("{") else re.findall(r'<script type="application/json"[^>]*>(.*?)</script>', t, re.S)
        for c in chunks:
            try:
                yield json.loads(c)
            except json.JSONDecodeError:
                continue


def scrape_instagram(url: str, cookies: list[dict], cookies_browser: str | None) -> Result:
    user = re.search(r"instagram\.com/([\w.]+)", url).group(1)
    bodies, _ = capture(f"https://www.instagram.com/{user}/reels/", cookies)
    found: dict[str, Video] = {}
    more = False
    for blob in json_blobs(bodies):
        for d in walk(blob):
            if isinstance(d.get("code"), str) and isinstance(d.get("play_count"), int):
                v = found.setdefault(d["code"], Video(f"https://www.instagram.com/reel/{d['code']}/", d["play_count"]))
                v.views = max(v.views, d["play_count"])
                if d.get("taken_at"):
                    v.uploaded = datetime.fromtimestamp(d["taken_at"], timezone.utc).date()
                if (d.get("caption") or {}).get("text"):
                    v.caption = d["caption"]["text"]
            if isinstance(d.get("has_next_page"), bool):
                more = d["has_next_page"]
    if not found:
        raise PlatformError("No reels with play counts in Instagram responses (login wall or layout change)")
    return finish("Instagram", url, list(found.values()), more, bool(cookies), cookies_browser)


def scrape_facebook(url: str, cookies: list[dict], cookies_browser: str | None) -> Result:
    bodies, _ = capture(url.rstrip("/") + "/?sk=reels_tab", cookies)
    found: dict[str, tuple[int, bool]] = {}
    more = False
    for blob in json_blobs(bodies):
        for d in walk(blob):
            conn = d.get("aggregated_fb_shorts")
            if not isinstance(conn, dict):
                continue
            for edge in conn.get("edges") or []:
                node = edge["profile_reel_node"]["node"]
                count = next(m["play_count_reduced"] for m in walk(node) if "play_count_reduced" in m)
                vid = base64.b64decode(node["id"] + "==").decode(errors="replace").rsplit(":", 1)[-1]
                found[vid] = parse_count(count)
            more = bool((conn.get("page_info") or {}).get("has_next_page"))
    if not found:
        raise PlatformError("No reels with play counts in Facebook responses (login wall or layout change)")
    vids = [Video(f"https://www.facebook.com/reel/{v}/", n, approx=a) for v, (n, a) in found.items()]
    return finish("Facebook", url, vids, more, bool(cookies), cookies_browser)


def finish(name: str, url: str, vids: list[Video], partial: bool, logged_in: bool, cookies_browser: str | None) -> Result:
    top = sorted(vids, key=lambda v: v.views, reverse=True)[:5]
    for v in top:
        if v.uploaded is None:
            # the IG reels feed has no caption/date; yt-dlp reads public reels fine without cookies
            v.caption, v.uploaded = ytdlp_meta(v.url, None if name == "Instagram" else cookies_browser)
    note = ""
    if partial and logged_in:
        note = f"PARTIAL: {name} still reported more reels after {len(vids)} were loaded (scrolling stopped early)."
    elif partial:
        note = (f"PARTIAL: {name} only shows the latest {len(vids)} reels to logged-out visitors. "
                f"Log into {name} in Chrome and rerun with --cookies-from-browser chrome for the full list.")
    if any(v.approx for v in vids):
        note += " Some counts are rounded by Facebook (e.g. 1.2K)."
    return Result(name, url, len(vids), top, note.strip())


def lm_topics(res: Result, model: str | None) -> None:
    try:
        models = json.load(urllib.request.urlopen(f"{LM_URL}/api/v0/models", timeout=5))["data"]
    except urllib.error.URLError as e:
        raise PlatformError(f"LM Studio not reachable at {LM_URL}: {e.reason}. Start LM Studio's server.") from e
    if not model:
        loaded = [m["id"] for m in models if m.get("state") == "loaded" and m.get("type") in ("llm", "vlm")]
        if not loaded:
            raise PlatformError("LM Studio is running but no model is loaded. Load one, or pass --lm-model <id>.")
        model = loaded[0]
    caps = "\n".join(f"{i}. {v.caption[:300]}" for i, v in enumerate(res.top, 1))
    prompt = (f"These are the top {len(res.top)} most-viewed {res.platform} videos, ranked. Captions:\n{caps}\n\n"
              'Reply with JSON only: {"topics": ["2-5 word topic label per video, same order"], '
              '"summary": "one line: which topic wins"}')
    body = json.dumps({"model": model, "temperature": 0.2, "messages": [{"role": "user", "content": prompt}]}).encode()
    req = urllib.request.Request(f"{LM_URL}/v1/chat/completions", body, {"Content-Type": "application/json"})
    try:
        out = json.load(urllib.request.urlopen(req, timeout=600))["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        raise PlatformError(f"LM Studio chat call failed (model {model}): HTTP {e.code} {e.read()[:200]!r}") from e
    m = re.search(r"\{.*\}", re.sub(r"<think>.*?</think>", "", out, flags=re.S), re.S)
    if not m:
        raise PlatformError(f"LM Studio ({model}) returned no JSON: {out[:200]!r}")
    data = json.loads(m.group(0))
    res.topics, res.summary = data["topics"], data["summary"]


def fmt_row(i: int, v: Video, topic: str | None) -> list[str]:
    return [str(i), f"{'~' if v.approx else ''}{v.views:,}", str(v.uploaded or "?"),
            f"{v.per_day:,.1f}" if v.per_day is not None else "?", (topic + " | " if topic else "") + v.caption.replace("\n", " ")[:60], v.url]


def print_result(r: Result) -> None:
    print(f"\n=== {r.platform}  {r.url}")
    if r.error:
        print(f"  FAILED: {r.error}")
        return
    print(f"  scanned {r.scanned} videos" + (f" ({r.note})" if r.note else ""))
    rows = [["#", "views", "uploaded", "views/day", "caption", "url"]]
    rows += [fmt_row(i, v, r.topics[i - 1] if r.topics and i <= len(r.topics) else None) for i, v in enumerate(r.top, 1)]
    w = [max(len(row[c]) for row in rows) for c in range(5)]
    for row in rows:
        print("  " + "  ".join(row[c].ljust(w[c]) for c in range(5)) + "  " + row[5])
    if r.summary:
        print(f"  Topic winner: {r.summary}")


def html_report(results: list[Result]) -> str:
    e = html.escape
    secs = []
    for r in results:
        if r.error:
            secs.append(f"<section><h2>{r.platform}</h2><p class=err>FAILED: {e(r.error)}</p></section>")
            continue
        rows = "".join(
            f"<tr><td>{i}</td><td class=n>{'~' if v.approx else ''}{v.views:,}</td><td>{v.uploaded or '?'}</td>"
            f"<td class=n>{f'{v.per_day:,.1f}' if v.per_day is not None else '?'}</td>"
            f"<td>{e(r.topics[i - 1]) if r.topics and i <= len(r.topics) else ''}</td>"
            f"<td>{e(v.caption[:140])}</td><td><a href='{e(v.url)}'>open</a></td></tr>" for i, v in enumerate(r.top, 1))
        secs.append(f"<section><h2>{r.platform}</h2><p class=meta><a href='{e(r.url)}'>{e(r.url)}</a> &middot; scanned {r.scanned} videos</p>"
                    + (f"<p class=warn>{e(r.note)}</p>" if r.note else "")
                    + (f"<p class=win>Topic winner: {e(r.summary)}</p>" if r.summary else "")
                    + f"<table><tr><th>#</th><th>Views</th><th>Uploaded</th><th>Views/day</th><th>Topic</th><th>Caption</th><th></th></tr>{rows}</table></section>")
    return f"""<!doctype html><html><head><meta charset=utf-8><title>Top Views {date.today()}</title><style>
body{{background:#0f1115;color:#e6e6e6;font:14px/1.5 -apple-system,system-ui,sans-serif;max-width:1100px;margin:40px auto;padding:0 20px}}
h1{{font-size:22px}}h2{{font-size:18px;margin-top:36px;border-bottom:1px solid #2a2e37;padding-bottom:6px}}
table{{width:100%;border-collapse:collapse}}th,td{{text-align:left;padding:8px;border-bottom:1px solid #22252d;vertical-align:top}}
th{{color:#8b93a7;font-weight:500}}.n{{text-align:right;font-variant-numeric:tabular-nums}}a{{color:#7aa2ff}}
.meta{{color:#8b93a7}}.warn{{color:#f0b429}}.err{{color:#ff6b6b}}.win{{color:#5ad19a}}</style></head><body>
<h1>Top 5 most-viewed videos per platform</h1><p class=meta>Generated {datetime.now():%Y-%m-%d %H:%M}. Sorted by numeric view count.</p>
{''.join(secs)}</body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Top 5 most-viewed videos per social profile (public data).")
    ap.add_argument("urls", nargs="+")
    ap.add_argument("--topics", action="store_true", help="label topics with LM Studio")
    ap.add_argument("--lm-model", help="LM Studio model id (default: the currently loaded model)")
    ap.add_argument("--cookies-from-browser", metavar="BROWSER", help="e.g. chrome; uses your logged-in session")
    ap.add_argument("--out-dir", type=Path, default=REPORT_DIR, help="where reports are saved (default: ./reports)")
    a = ap.parse_args()
    cookies = browser_cookies(a.cookies_from_browser)
    results = []
    for url in a.urls:
        kind = platform_of(url)
        try:
            if kind == "tiktok":
                r = scrape_tiktok(url, cookies)
            elif kind == "instagram":
                r = scrape_instagram(url, cookies, a.cookies_from_browser)
            else:
                r = scrape_facebook(url, cookies, a.cookies_from_browser)
        except (PlatformError, PlaywrightTimeout, subprocess.TimeoutExpired) as ex:
            r = Result(kind.capitalize(), url, error=str(ex))
        if a.topics and not r.error:
            try:
                lm_topics(r, a.lm_model)
            except PlatformError as ex:
                r.note = f"{r.note}. TOPICS FAILED: {ex}".lstrip(". ")
        results.append(r)
        print_result(r)
    a.out_dir.mkdir(parents=True, exist_ok=True)
    out = a.out_dir / f"top-views-{date.today()}.html"
    out.write_text(html_report(results), encoding="utf-8")
    print(f"\nHTML report: {out}")
    csv_out = out.with_suffix(".csv")
    with csv_out.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["platform", "rank", "views", "views_approx", "uploaded", "views_per_day", "topic", "caption", "url"])
        for r in results:
            for i, v in enumerate(r.top or [], 1):
                w.writerow([r.platform, i, v.views, v.approx, v.uploaded or "",
                            f"{v.per_day:.1f}" if v.per_day is not None else "",
                            r.topics[i - 1] if r.topics and i <= len(r.topics) else "", v.caption.replace("\n", " "), v.url])
    print(f"CSV report:  {csv_out}")
    return 1 if any(r.error for r in results) else 0


if __name__ == "__main__":
    sys.exit(main())
