# top-views

Finds the **top most-viewed videos** (10 by default, set with `--top`) on a TikTok, Instagram (Reels) and Facebook (Reels) profile, sorted by the real view count. Prints a table in the terminal and saves an HTML report and a CSV.

Works on public data only. No API keys, no account access to the profile being checked.

## Quick start

Already have Homebrew? It's four commands:

```sh
brew install python@3.13
git clone https://github.com/kennethsolomon/top-views.git && cd top-views
sh install.sh
./top-views https://www.tiktok.com/@abi_asija
```

New Mac, or something fails? Follow the full steps below.

## Prerequisites (macOS)

| What | Why | How to check |
|---|---|---|
| macOS 12+ (Apple Silicon or Intel) | Tested on macOS | Apple menu > About This Mac |
| Xcode Command Line Tools | Gives you `git` | `git --version` |
| Homebrew | Easiest way to get a current Python | `brew --version` |
| Python 3.10 to 3.14 (3.13 recommended) | Runs the script | `python3.13 --version` |
| Google Chrome | Only needed for the full Instagram/Facebook list (login) | Open Chrome |
| ~500 MB free disk | Playwright downloads its own Chromium | |

The `python3` that ships with macOS is 3.9, which is too old. Install a newer one with Homebrew.

## Install (step by step)

1. **Open Terminal** (Cmd + Space, type "Terminal", press Enter).

2. **Install Xcode Command Line Tools** (skip if `git --version` already works):
   ```sh
   xcode-select --install
   ```
   Click Install in the popup and wait for it to finish.

3. **Install Homebrew** (skip if `brew --version` works):
   ```sh
   /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
   ```
   At the end, Homebrew prints two "Next steps" commands (`echo ... >> ~/.zprofile` and `eval ...`). Run them, then close and reopen Terminal.

4. **Install Python 3.13:**
   ```sh
   brew install python@3.13
   python3.13 --version
   ```
   Use 3.13 (3.10 to 3.14 also work). On macOS 26, if `sh install.sh` fails with an `ensurepip` error, see [macOS 26: empty `mac_ver` breaks pip](#macos-26-empty-mac_ver-breaks-pip).

5. **Download this project:**
   ```sh
   git clone https://github.com/kennethsolomon/top-views.git
   cd top-views
   ```
   For a private repo, run `brew install gh && gh auth login` first, or download the ZIP from GitHub and unzip it.

6. **Run the installer:**
   ```sh
   sh install.sh
   ```
   This picks a supported Python (3.13 first), creates a fresh Python environment in `.venv/`, installs the packages, and downloads Playwright's Chromium. It takes a few minutes the first time. The first line of output says which Python it used.

   You don't need to activate the environment (`source .venv/bin/activate`). The `./top-views` command uses it for you.

7. **Test it:**
   ```sh
   ./top-views https://www.tiktok.com/@abi_asija
   ```
   You should see a table of 10 videos. Reports are saved in the `reports/` folder.

## Updating to the latest version

```sh
cd top-views
git pull
sh install.sh
```

Rerunning `install.sh` is safe. It rebuilds `.venv/` from scratch each time.

## Usage

```sh
./top-views <profile url> [<profile url> ...] [options]
```

Example with all three platforms:

```sh
./top-views https://www.tiktok.com/@abi_asija \
            https://www.instagram.com/abiasija/ \
            https://www.facebook.com/people/Honest-Wealth-Builders/61574869258101/ \
            --cookies-from-browser chrome
```

Output:
- Terminal table per platform
- `reports/top-views-YYYY-MM-DD.html`: report to open in a browser or share
- `reports/top-views-YYYY-MM-DD.csv`: one sheet for Excel / Google Sheets (platform, rank, views, views_approx, uploaded, views_per_day, topic, caption, url)

### Options

| Option | What it does |
|---|---|
| `--top N` | How many top videos per platform (default: 10). E.g. `--top 5`, `--top 20`. |
| `--since YYYY-MM-DD` | Optional. Only videos uploaded on or after this date. |
| `--until YYYY-MM-DD` | Optional. Only videos uploaded on or before this date. |
| `--cookies-from-browser chrome` | Uses your Chrome login. Needed for the **full** Instagram and Facebook list (see below). |
| `--cookies-from-browser chrome:<profile dir>` | Same, for a specific Chrome profile folder. |
| `--cookies-from-browser playwright:<profile dir>` | For a Playwright-launched Chrome profile (e.g. `~/Library/Caches/ms-playwright-mcp/mcp-chrome-xxxx/Default`). |
| `--out-dir <folder>` | Save reports somewhere else (default: `reports/`). |
| `--topics` | Labels each video's topic using LM Studio (optional, see below). |
| `--lm-model <id>` | LM Studio model to use with `--topics`. |

### Filtering by date range (optional)

Use `--since` and/or `--until` to rank only videos uploaded in a date range. Both are optional and can be combined with `--top`:

```sh
# top 10 from Q3
./top-views <urls...> --since 2026-07-01 --until 2026-09-30

# top 5 from October onward
./top-views <urls...> --since 2026-10-01 --top 5

# top 10 up to the end of June
./top-views <urls...> --until 2026-06-30
```

- Dates are inclusive and use the upload date.
- The output shows the range and how many videos matched (fewer than `--top` if the range is small).
- Instagram and Facebook look up upload dates one video at a time, so a narrow range on a big profile can take a few minutes.

### Getting the full Instagram and Facebook list

Logged out, Instagram shows only the latest 12 reels and Facebook only the latest ~10, so the top list would be wrong. To get everything:

1. Open **Google Chrome** and log into instagram.com and facebook.com (any account works).
2. **Quit Chrome completely** (Cmd + Q) so the login is saved to disk.
3. Run with `--cookies-from-browser chrome`.
4. macOS asks to access "Chrome Safe Storage" in your Keychain. Enter your Mac password and click **Always Allow**.

If the output says `PARTIAL`, the login wasn't picked up.

#### Using a different Chrome profile

`--cookies-from-browser chrome` reads Chrome's **Default** profile. If you're logged into Instagram/Facebook in another Chrome profile:

1. In that Chrome window, open `chrome://version` and look at **Profile Path**. The last part is the profile name:

   | Profile Path ends in | Use |
   |---|---|
   | `.../Google/Chrome/Default` | `--cookies-from-browser chrome` |
   | `.../Google/Chrome/Profile 1` | `--cookies-from-browser "chrome:Profile 1"` |
   | `.../Google/Chrome/Profile 2` | `--cookies-from-browser "chrome:Profile 2"` |

2. Quit Chrome (Cmd + Q), then run, e.g.:
   ```sh
   ./top-views https://www.tiktok.com/@abi_asija \
               https://www.instagram.com/abiasija/ \
               https://www.facebook.com/people/Honest-Wealth-Builders/61574869258101/ \
               --cookies-from-browser "chrome:Profile 1"
   ```

Keep the quotes; the profile name has a space.

TikTok gives the full list without logging in.

### Topic labels with LM Studio (optional)

1. Install [LM Studio](https://lmstudio.ai), download a model (an 8B+ instruct model, larger is better), and start the local server (Developer tab > Start Server, port 1234).
2. Add `--topics` (and `--lm-model <id>` if no model is loaded).

The per-video labels are reliable; the one-line "topic winner" summary from small models can be off.

## Notes and limits

- Counts come from the JSON the site itself loads, so they're exact numbers. Facebook rounds big ones (e.g. "5K"); those show with `~` and `views_approx = True` in the CSV.
- TikTok's own "Popular" tab is **not** sorted by views. That's why many third-party tools look wrong.
- `views_per_day` helps compare old vs new videos fairly.
- These sites change often. If a platform starts failing, update the packages first:
  ```sh
  .venv/bin/pip install -U yt-dlp playwright && .venv/bin/python -m playwright install chromium
  ```
- Exit code is 1 if any platform failed; each failure prints its reason.

## Troubleshooting

| Problem | Fix |
|---|---|
| `No supported Python found` | `brew install python@3.13`, then rerun `sh install.sh` |
| `ensurepip ... returned non-zero exit status 1` | Most likely the macOS 26 Homebrew Python bug below. Check with `python3.13 -c "import platform; print(platform.mac_ver())"`. If it prints `('', ...)`, apply the fix in [macOS 26: empty `mac_ver` breaks pip](#macos-26-empty-mac_ver-breaks-pip) |
| `(.venv)` shows in your prompt, or install keeps failing after a manual fix | Run `deactivate`, then `rm -rf .venv` and `sh install.sh` |
| `command not found: python` | Normal on macOS. Use `python3.13`, or just run `sh install.sh`, which finds it for you |
| `permission denied: ./top-views` | `chmod +x top-views` |
| `Executable doesn't exist ... chromium` | `.venv/bin/python -m playwright install chromium` |
| Instagram/Facebook still `PARTIAL` | Log in to Chrome, quit Chrome, rerun with `--cookies-from-browser chrome`, allow Keychain access |
| `every cookie decrypted to empty` | You pointed at a Playwright profile with `chrome:`; use `playwright:<profile dir>` instead |

### macOS 26: empty `mac_ver` breaks pip

On some macOS 26 Macs, Homebrew's Python links its XML module (`pyexpat`) to Apple's `/usr/lib/libexpat.1.dylib`, which doesn't work with that build. Python then reports an empty macOS version, and pip crashes with `ValueError: invalid literal for int() with base 10: ''` (shown by `install.sh` as an `ensurepip` error). Reinstalling Python doesn't help. Known upstream issue: Homebrew/homebrew-core #277330, CPython #135675.

Check:
```sh
python3.13 -c "import platform; print(platform.mac_ver())"   # ('', ...) means you have it
```

Fix (relinks `pyexpat` to Homebrew's expat):
```sh
brew install expat
PYEXPAT="$(python3.13 -c 'import importlib.util; print(importlib.util.find_spec("pyexpat").origin)')"
otool -L "$PYEXPAT" | grep expat        # should show /usr/lib/libexpat.1.dylib
install_name_tool -change /usr/lib/libexpat.1.dylib "$(brew --prefix expat)/lib/libexpat.1.dylib" "$PYEXPAT"
codesign --sign - --force "$PYEXPAT"
python3.13 -c "import platform; print(platform.mac_ver())"   # now shows ('26.x', ...)
rm -rf .venv && PYTHON=python3.13 sh install.sh
```

`brew upgrade` / `brew reinstall python@3.13` undoes this; rerun the fix after. Updating macOS to the latest 26.x may also resolve it.
