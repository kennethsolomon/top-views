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
   Use 3.13 (3.10 to 3.14 also work). Very new releases like 3.15 don't have prebuilt packages yet and the install fails with an `ensurepip` error.

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
| `--cookies-from-browser chrome` | Uses your Chrome login. Needed for the **full** Instagram and Facebook list (see below). |
| `--cookies-from-browser chrome:<profile dir>` | Same, for a specific Chrome profile folder. |
| `--cookies-from-browser playwright:<profile dir>` | For a Playwright-launched Chrome profile (e.g. `~/Library/Caches/ms-playwright-mcp/mcp-chrome-xxxx/Default`). |
| `--out-dir <folder>` | Save reports somewhere else (default: `reports/`). |
| `--topics` | Labels each video's topic using LM Studio (optional, see below). |
| `--lm-model <id>` | LM Studio model to use with `--topics`. |

### Getting the full Instagram and Facebook list

Logged out, Instagram shows only the latest 12 reels and Facebook only the latest ~10, so the top list would be wrong. To get everything:

1. Open **Google Chrome** and log into instagram.com and facebook.com (any account works).
2. **Quit Chrome completely** (Cmd + Q) so the login is saved to disk.
3. Run with `--cookies-from-browser chrome`.
4. macOS asks to access "Chrome Safe Storage" in your Keychain. Enter your Mac password and click **Always Allow**.

If the output says `PARTIAL`, the login wasn't picked up.

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
| `ensurepip ... returned non-zero exit status 1` | Your Python is too new (e.g. 3.15). `brew install python@3.13`, then `sh install.sh` (it picks 3.13 automatically) |
| `(.venv)` shows in your prompt, or install keeps failing after a manual fix | Run `deactivate`, then `rm -rf .venv` and `sh install.sh` |
| `command not found: python` | Normal on macOS. Use `python3.13`, or just run `sh install.sh`, which finds it for you |
| `permission denied: ./top-views` | `chmod +x top-views` |
| `Executable doesn't exist ... chromium` | `.venv/bin/python -m playwright install chromium` |
| Instagram/Facebook still `PARTIAL` | Log in to Chrome, quit Chrome, rerun with `--cookies-from-browser chrome`, allow Keychain access |
| `every cookie decrypted to empty` | You pointed at a Playwright profile with `chrome:`; use `playwright:<profile dir>` instead |
