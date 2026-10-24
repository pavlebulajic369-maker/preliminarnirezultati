# Live election-day collection: noon to midnight

`watch_x.py` checks `CeSIDBeograd` and `crtars` every **60 seconds** from **12:00 noon until 00:00 at the end of the selected day**, using **Europe/Belgrade** time. It schedules the checks itself: **start it once and leave it running**. You do not need to launch another copy every minute.

The date is configurable; no 2026 election date is assumed. `--date YYYY-MM-DD` chooses the election date. Without it, the program uses today's date in Belgrade.

## Setup once

In PowerShell, from this project folder:

```powershell
Set-Location "C:\Users\pavleb\.vscode\VsCodeFolders\election"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-watch.txt
```

If `.venv` already exists, skip the `python -m venv` command. The dependencies are Windows-Toasts for Windows notifications and tzdata for Belgrade's timezone rules. No activation is required when using the full `.venv\Scripts\python.exe` command.

The watcher reads the same `X_BEARER_TOKEN` environment variable or `.env` file as `collect_x.py`. Put the token in `.env` beside the scripts if it is not already configured:

```dotenv
X_BEARER_TOKEN=your_token_here
```

## Check desktop notifications without spending X credits

```powershell
.\.venv\Scripts\python.exe .\watch_x.py --test-notification
```

This submits a local Windows notification and makes no X API request. Clicking it opens CeSID's profile. For real posts, clicking opens the specific post. A notification includes the account, publication time in Belgrade, and a text preview. Windows provides the normal notification sound according to your notification settings.

If the banner is absent, check **Settings > System > Notifications**, disable **Do not disturb / Focus assist**, and inspect Notification Center (`Win+N` on Windows 11). The sender is **Election X Monitor**. A successful submission does not guarantee that Windows displayed a banner or that you saw it.

## Start the watcher

On election day, preview and then start:

```powershell
.\.venv\Scripts\python.exe .\watch_x.py
.\.venv\Scripts\python.exe .\watch_x.py --fetch
```

The first command is a dry run: no network, credentials, file writes, or notifications. `--fetch` enables paid X reads and notifications. Start before noon and the process waits; start after noon and it catches up from noon before continuing every minute. Leave the terminal open, the computer awake and connected, and your Windows account signed in. Press `Ctrl+C` to stop cleanly. Restart the same command to resume saved progress.

To prepare for a particular date, use this instead (replace the placeholder with the actual date):

```powershell
$electionDate = Read-Host "Election date (YYYY-MM-DD)"
.\.venv\Scripts\python.exe .\watch_x.py --date $electionDate
.\.venv\Scripts\python.exe .\watch_x.py --date $electionDate --fetch
```

Polling targets a 60-second cadence. Slow API responses and rate limits can delay a check; the process does not start overlapping searches for the same account. The accounts and photo downloads use separate workers, so a slow image does not prevent searching or notifying.

The search cutoff trails the current time by 15 seconds. At **00:00:15**, the watcher makes a final pass over the full noon-to-midnight interval to catch the last minute and posts that became searchable late. Only posts **published before midnight** are eligible. Final retries and queued work have a two-minute grace period after midnight; in-flight network calls can take up to another 30 seconds to finish. The program then exits and reports any incomplete collection or pending photos/notifications. X's indexing delay means complete coverage cannot be guaranteed by a fixed stop time.

## Optional: start automatically with Windows Task Scheduler

Create **one task**, with the trigger set to the actual election date at **11:59 Belgrade time**. If Windows uses another timezone, convert the trigger time; the Python schedule itself always uses Belgrade time.

Use these settings:

- **General:** select **Run only when user is logged on** so notifications appear in your desktop session. Administrator privileges are not needed.
- **Action > Start a program:** `C:\Users\pavleb\.vscode\VsCodeFolders\election\.venv\Scripts\python.exe`
- **Add arguments:** `"C:\Users\pavleb\.vscode\VsCodeFolders\election\watch_x.py" --date YYYY-MM-DD --fetch` (replace `YYYY-MM-DD`).
- **Start in:** `C:\Users\pavleb\.vscode\VsCodeFolders\election`
- **Settings:** enable **Run task as soon as possible after a scheduled start is missed**; select **Do not start a new instance** if it is already running.
- Do **not** configure one-minute task repetition: Python already does that.
- Keep the PC awake for the entire window. A wake trigger alone does not prevent it sleeping again.

Do not run the manual command and the scheduled task simultaneously. Do not configure unattended repeated restarts for invalid credentials or exhausted credits: fix the reported error first.

## Output and recovery

For 2026, the folders are:

```text
data/2026/cesidbeograd/
data/2026/crtars/
```

Each contains the original `posts.jsonl` and `candidates.jsonl` formats, photos named `<post-id>_<media-key>.<extension>`, `watch_<date>_<query-hash>.json` checkpoints, and raw API pages under `raw/watch_<date>_<query-hash>/`. The combined operational log is `data/2026/watch_<date>.log`. Another selected year uses that year's folder.

All returned posts are saved, including non-candidates. Replies and quotes are included. Reposts remain excluded unless `--include-reposts` is supplied. As in the original collector, directly attached photos are downloaded at the original available size; videos and media inside referenced posts are not downloaded. The watcher does not perform OCR or evaluate election results.

The watcher adds first/last-seen times and notification submission status to the post records. New posts and pending notification intent are saved together before advancing the search checkpoint. Repeated searches and ordinary restarts do not duplicate records or submitted notifications. A crash between Windows accepting a toast and saving that fact can repeat an alert; stable Windows notification tags reduce duplicate entries in Notification Center. Failed submissions remain pending for retry. Newly discovered posts from a catch-up also generate notifications, spaced one second apart.

Each poll overlaps the previous completed interval by five minutes. Pagination is fully processed before advancing the completed interval. Network failures use backoff; HTTP 429 honors retry/reset headers. Authentication, permission, credit, and invalid-request errors stop the monitor with an error. Raw responses are saved before processing so an interrupted page can be replayed without another X request. There is no automatic spend cap: use the X Developer Console spending limit. The watcher does not reuse the historical collector's ten-post batch cap, which would otherwise omit busy periods.

If the process was forcibly killed, its `.fetch.lock` may remain. Check that neither collector is running, then remove only that account's stale `.fetch.lock` and restart. `Ctrl+C` normally releases the locks. Do not delete saved checkpoints or raw responses.

For a one-time catch-up or retry after midnight, using the original election date:

```powershell
$electionDate = Read-Host "Election date to catch up (YYYY-MM-DD)"
.\.venv\Scripts\python.exe .\watch_x.py --date $electionDate --fetch --once
```

`--once` checks the full interval from noon to the current searchable time, capped at midnight. Its retry window is two minutes. It also retries pending photos and notifications. Use it within seven days of the start time; older intervals require the original full-archive collector. `--no-notifications` collects without toast delivery and keeps pending alerts for a future run with notifications enabled.

## Validation and references

Run offline tests without X credentials:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_collect*.py"
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_watch_x.py"
```

- [X recent search and pagination](https://docs.x.com/x-api/posts/search/quickstart/recent-search)
- [X pricing and spending controls](https://docs.x.com/x-api/getting-started/pricing)
- [Windows-Toasts notification behavior](https://windows-toasts.readthedocs.io/en/latest/advanced_usage.html)
- [Microsoft interactive scheduled tasks](https://learn.microsoft.com/en-us/windows/win32/taskschd/principal-logontype)
