"""Watch CeSID and CRTA from noon to midnight in Europe/Belgrade.

Preview: python watch_x.py --date 2026-MM-DD
Run:     python watch_x.py --date 2026-MM-DD --fetch
Test Windows notifications without contacting X: python watch_x.py --test-notification

The process schedules its own checks every 60 seconds. See WATCH_X.md.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, contextmanager
from datetime import date, datetime, time as daytime, timedelta, timezone
import hashlib
import json
import logging
import math
import os
from pathlib import Path
from queue import SimpleQueue
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, build_opener
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import collect_x as collector


ROOT = Path(__file__).resolve().parent
ACCOUNTS = ("cesidbeograd", "crtars")
API_URL = "https://api.x.com/2/tweets/search/recent"
INTERVAL = 60
OVERLAP = timedelta(minutes=5)
INDEX_DELAY = timedelta(seconds=15)
FINAL_GRACE = timedelta(minutes=2)
LOG = logging.getLogger("watch_x")


def utcnow():
    return datetime.now(timezone.utc)


def stamp(value):
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def parse_stamp(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError("Saved timestamps must include a timezone.")
    return parsed.astimezone(timezone.utc)


def belgrade_zone():
    try:
        return ZoneInfo("Europe/Belgrade")
    except ZoneInfoNotFoundError:
        raise collector.FetchError(
            "Install the watcher dependencies first: python -m pip install -r requirements-watch.txt"
        ) from None


def election_window(day, zone):
    start = datetime.combine(day, daytime(12), zone)
    end = datetime.combine(day + timedelta(days=1), daytime.min, zone)
    return start.astimezone(timezone.utc), end.astimezone(timezone.utc)


def next_minute(start, current):
    """Keep the cadence anchored to noon, including after slow calls or sleep."""
    slot = max(0, math.floor((current - start).total_seconds() / INTERVAL) + 1)
    return start + timedelta(seconds=slot * INTERVAL)


class APIError(collector.FetchError):
    def __init__(self, message, *, fatal=False, retry_after=60):
        super().__init__(message)
        self.fatal = fatal
        self.retry_after = retry_after


def fetch_page(params, token):
    """No internal retry: the event loop retries without blocking the other account."""
    request = Request(API_URL + "?" + urlencode(params), headers={
        "Authorization": "Bearer " + token,
        "User-Agent": "SerbianElectionResearch/1.0",
    })
    try:
        with build_opener(collector.NoRedirect()).open(request, timeout=30) as response:
            body = response.read(10 * 1024 * 1024 + 1)
    except HTTPError as error:
        delay = 60
        for header, absolute in (("retry-after", False), ("x-rate-limit-reset", True)):
            try:
                value = float(error.headers.get(header, ""))
                if absolute:
                    value -= time.time()
                if math.isfinite(value):
                    delay = max(delay, value + 1)
            except (TypeError, ValueError):
                pass
        hints = {400: "Check the query or saved pagination cursor.",
                 401: "Check X_BEARER_TOKEN.", 402: "Check X API credits.",
                 403: "Check recent-search access.", 429: "X rate limit reached."}
        # Do not expose response bodies, credentials, or request headers.
        raise APIError(f"HTTP {error.code}. {hints.get(error.code, 'X request failed.')}",
                       fatal=400 <= error.code < 500 and error.code not in (408, 429),
                       retry_after=delay) from None
    except (URLError, TimeoutError, OSError) as error:
        raise APIError(f"Network failure ({type(error).__name__}).") from None
    if len(body) > 10 * 1024 * 1024:
        raise APIError("X response exceeds the size limit.", fatal=True)
    try:
        page = json.loads(body)
    except (ValueError, UnicodeError):
        raise APIError("X returned invalid JSON.") from None
    if not isinstance(page, dict):
        raise APIError("X returned an unexpected response format.")
    return page


@contextmanager
def account_lock(folder):
    """Share the original collector's lock so the two programs cannot overwrite data."""
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / ".fetch.lock"
    try:
        handle = path.open("x", encoding="utf-8")
    except FileExistsError:
        raise collector.FetchError(
            f"Collection lock exists: {path}. If the old process crashed, first check "
            "that it has stopped, then remove this lock and restart."
        ) from None
    try:
        with handle:
            handle.write(f"watch_x.py PID={os.getpid()}\n")
        yield
    finally:
        path.unlink(missing_ok=True)


class AccountWatch:
    """All state changes happen on the main thread; workers only perform I/O."""

    def __init__(self, folder, account, day, start, end, include_reposts=False):
        self.folder, self.account, self.day = folder, account, day
        self.start, self.end = start, end
        self.query = f"from:{account}" + ("" if include_reposts else " -is:retweet")
        signature = hashlib.sha256(self.query.encode()).hexdigest()[:8]
        self.watch_id = f"watch_{day.isoformat()}_{signature}"
        self.state_path = folder / f"{self.watch_id}.json"
        self.raw_folder = folder / "raw" / self.watch_id
        self.raw_folder.mkdir(parents=True, exist_ok=True)
        self.state = collector.read_json(self.state_path) if self.state_path.exists() else {
            "query": self.query, "start": stamp(start), "end": stamp(end),
            "covered_until": stamp(start), "cycle": 0, "pending": None,
        }
        if any(self.state.get(k) != v for k, v in {
            "query": self.query, "start": stamp(start), "end": stamp(end)
        }.items()):
            raise collector.FetchError(f"Checkpoint does not match the requested window: {self.state_path}")
        records_path = folder / "posts.jsonl"
        self.records = {}
        if records_path.exists():
            self.records = {r["id"]: r for r in (
                json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines()
                if line.strip())}
        self.photo_retry_at = {}
        self.notification_retry_at = {}
        self.retry_at = start
        self.failures = 0
        self.next_poll_at = start
        self.final_started = False
        self.final_done = False

    def save_state(self):
        collector.write_json(self.state_path, self.state)

    def save_records(self):
        collector.save_records(self.folder, self.records, self.day.year)

    def begin_poll(self, cutoff, *, reconcile=False):
        if self.state["pending"] or cutoff <= self.start:
            return False
        beginning = self.start if reconcile else max(
            self.start, parse_stamp(self.state["covered_until"]) - OVERLAP)
        if cutoff <= beginning:
            return False
        self.state["cycle"] += 1
        self.state["pending"] = {"start": stamp(beginning), "end": stamp(cutoff),
                                 "next_token": None, "page": 1, "tokens": [],
                                 "reconcile": reconcile}
        self.save_state()
        return True

    def request_params(self):
        pending = self.state["pending"]
        params = {
            "query": self.query, "start_time": pending["start"], "end_time": pending["end"],
            "sort_order": "recency", "max_results": 100,
            "tweet.fields": "created_at,author_id,attachments,entities,referenced_tweets,conversation_id,note_tweet",
            "expansions": "attachments.media_keys",
            "media.fields": "media_key,type,url,preview_image_url,alt_text,width,height",
        }
        if pending["next_token"]:
            params["next_token"] = pending["next_token"]
        return params

    def raw_path(self):
        pending = self.state["pending"]
        return self.raw_folder / f"cycle_{self.state['cycle']:05d}_page_{pending['page']:04d}.json"

    def accept_page(self, saved):
        """Persist records + notification intent before advancing the saved cursor."""
        page = saved["response"]
        batch = page.get("data", [])
        if not isinstance(batch, list) or not isinstance(page.get("meta"), dict):
            raise APIError("X response lacks valid posts or pagination metadata.")
        if not batch and page.get("errors"):
            raise APIError("X reported errors without usable posts; see the saved raw response.")
        pending = self.state["pending"]
        next_token = page["meta"].get("next_token")
        if next_token and (not isinstance(next_token, str) or next_token in pending["tokens"]):
            raise APIError("X repeated or returned an invalid pagination token.", fatal=True)
        media_by_key = {m["media_key"]: m for m in page.get("includes", {}).get("media", [])}
        new_count = 0
        for post in batch:
            post_id = str(post.get("id", ""))
            if not re.fullmatch(r"\d+", post_id) or not post.get("created_at"):
                raise APIError("X returned a post without a valid ID or timestamp.", fatal=True)
            published = parse_stamp(post["created_at"])
            if not self.start <= published < self.end:
                continue
            previous = self.records.get(post_id, {})
            old_media = {m["media_key"]: m for m in previous.get("media", [])}
            keys = post.get("attachments", {}).get("media_keys", [])
            media = [{**old_media.get(key, {}), **media_by_key.get(key, {})}
                     for key in keys if key in media_by_key or key in old_media]
            record = {
                **previous, **post, "id": post_id,
                "post_url": f"https://x.com/{self.account}/status/{post_id}",
                "fetched_at": previous.get("fetched_at", saved["fetched_at"]),
                "first_seen_at": previous.get("first_seen_at", saved["fetched_at"]),
                "last_seen_at": saved["fetched_at"], "media": media,
                "missing_media_keys": [key for key in keys if key not in media_by_key and key not in old_media],
                "search_ids": sorted(set(previous.get("search_ids", [])) | {self.watch_id}),
            }
            if not previous:
                record["watch_notification_status"] = "pending"
                new_count += 1
            self.records[post_id] = collector.classify(record, self.day.year)
        self.save_records()
        if page.get("errors"):
            LOG.warning("@%s: partial API errors preserved in %s", self.account, self.raw_path())
        if next_token:
            pending["tokens"].append(next_token)
            pending["next_token"] = next_token
            pending["page"] += 1
        else:
            self.state["covered_until"] = max(self.state["covered_until"], pending["end"])
            if pending["reconcile"] and self.final_started:
                self.final_done = True
            self.state["pending"] = None
        self.state["last_success_at"] = saved["fetched_at"]
        self.state.pop("last_error", None)
        self.save_state()
        self.failures = 0
        LOG.info("@%s: %d returned, %d new, %d saved", self.account, len(batch), new_count, len(self.records))

    def pending_photos(self, current):
        for record in self.records.values():
            if not self.start <= parse_stamp(record["created_at"]) < self.end:
                continue
            for media in record.get("media", []):
                key = (record["id"], media.get("media_key", ""))
                if media.get("type") != "photo" or self.photo_retry_at.get(key, self.start) > current:
                    continue
                local = media.get("local_file")
                if not local or not (self.folder / local).is_file():
                    yield key, media

    def accept_photo(self, key, media, current):
        record = self.records[key[0]]
        for index, existing in enumerate(record["media"]):
            if existing.get("media_key") == key[1]:
                if media.get("local_file"):
                    media.pop("download_error", None)
                record["media"][index] = media
                break
        if media.get("download_error"):
            self.photo_retry_at[key] = current + timedelta(minutes=5)
            LOG.warning("@%s post %s: photo download failed; retained for retry", self.account, key[0])
        self.save_records()

    def pending_notifications(self, current):
        return sorted((r for r in self.records.values()
                       if r.get("watch_notification_status") == "pending"
                       and self.start <= parse_stamp(r["created_at"]) < self.end
                       and self.notification_retry_at.get(r["id"], self.start) <= current),
                      key=lambda r: (r["created_at"], r["id"]))


class WindowsNotifier:
    def __init__(self, zone):
        if sys.platform != "win32":
            raise collector.FetchError("Desktop notifications need Windows. Use --no-notifications elsewhere.")
        try:
            from windows_toasts import Toast, WindowsToaster
        except ImportError:
            raise collector.FetchError(
                "Install notifications: python -m pip install -r requirements-watch.txt"
            ) from None
        self.Toast = Toast
        self.toaster = WindowsToaster("Election X Monitor")
        self.zone = zone

        self.failed = SimpleQueue()

    def show(self, title, body, url=None, *, account=None, post_id=None):
        toast = self.Toast()
        toast.text_fields = [title, body]
        if url:
            toast.launch_action = url
        if account and post_id:
            toast.group = account
            toast.tag = hashlib.sha256(post_id.encode()).hexdigest()[:16]
            toast.on_failed = lambda _: self.failed.put((account, post_id))
        self.toaster.show_toast(toast)

    def send_post(self, account, record):
        published = parse_stamp(record["created_at"]).astimezone(self.zone).strftime("%H:%M")
        text = " ".join(record.get("full_text", record.get("text", "")).split())
        preview = text[:240] + ("…" if len(text) > 240 else "")
        self.show(f"@{account} · {published}", preview or "New post with media", record["post_url"],
                  account=account, post_id=record["id"])

    def retry_failed(self, watches, current):
        while not self.failed.empty():
            account, post_id = self.failed.get()
            watch = next(w for w in watches if w.account == account)
            watch.records[post_id]["watch_notification_status"] = "pending"
            watch.records[post_id].pop("watch_notification_submitted_at", None)
            watch.notification_retry_at[post_id] = current + timedelta(seconds=60)
            watch.save_records()
            LOG.warning("@%s post %s: Windows reported a failed notification; queued for retry", account, post_id)


def deliver_one(watches, notifier, current):
    """Submit one toast per second, rather than flooding Windows after a catch-up."""
    if notifier is None:
        return False
    for watch in watches:
        pending = watch.pending_notifications(current)
        if not pending:
            continue
        record = pending[0]
        try:
            notifier.send_post(watch.account, record)
        except Exception as error:
            watch.notification_retry_at[record["id"]] = current + timedelta(seconds=60)
            LOG.warning("@%s: notification failed (%s); queued for retry", watch.account, type(error).__name__)
        else:
            record["watch_notification_status"] = "submitted"
            record["watch_notification_submitted_at"] = stamp(current)
            watch.save_records()
        return True
    return False


def record_api_error(watch, error, current, notifier):
    watch.state["last_error"] = {"at": stamp(current), "message": str(error)}
    watch.save_state()
    LOG.error("@%s: %s", watch.account, error)
    if error.fatal:
        if notifier:
            try:
                notifier.show("Election monitor stopped", str(error))
            except Exception:
                pass
        raise error
    watch.failures += 1
    delay = max(error.retry_after, min(900, 60 * 2 ** min(watch.failures - 1, 4)))
    watch.retry_at = current + timedelta(seconds=delay)
    # A malformed response must not be replayed forever. Preserve it for audit.
    raw = watch.raw_path()
    if raw.exists():
        raw.replace(raw.with_name(raw.stem + f"_error_{time.time_ns()}.json"))


def run_watch(watches, token, notifier, *, once=False):
    start, end = watches[0].start, watches[0].end
    deadline = utcnow() + FINAL_GRACE if once else end + FINAL_GRACE
    api_jobs, photo_jobs = {}, {}
    next_notification = start
    api_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="x-search")
    photo_pool = ThreadPoolExecutor(max_workers=2, thread_name_prefix="x-photo")
    try:
        while True:
            current = utcnow()
            # A successful response is saved before processing; a crash can replay it.
            for watch, future in list(api_jobs.items()):
                if not future.done():
                    continue
                del api_jobs[watch]
                try:
                    page = future.result()
                    saved = {"fetched_at": stamp(current), "params": watch.request_params(), "response": page}
                    collector.write_json(watch.raw_path(), saved)
                    watch.accept_page(saved)
                except APIError as error:
                    record_api_error(watch, error, current, notifier)

            for job_key, future in list(photo_jobs.items()):
                if future.done():
                    del photo_jobs[job_key]
                    watch, key = job_key
                    watch.accept_photo(key, future.result(), current)

            if notifier:
                notifier.retry_failed(watches, current)
            if current >= next_notification:
                if deliver_one(watches, notifier, current):
                    next_notification = current + timedelta(seconds=1)

            expired = current >= deadline
            for watch in watches:
                if watch in api_jobs or current < watch.retry_at or expired:
                    continue
                if not watch.state["pending"]:
                    if (once or current >= end + INDEX_DELAY) and not watch.final_started:
                        watch.final_started = True
                        watch.begin_poll(min(end, current - INDEX_DELAY), reconcile=True)
                    elif not once and current < end and current >= watch.next_poll_at:
                        watch.next_poll_at = next_minute(start, current)
                        watch.begin_poll(min(end, current - INDEX_DELAY))
                if watch.state["pending"]:
                    raw = watch.raw_path()
                    if raw.exists():
                        # Replay only already-saved successful pages, without another X read.
                        try:
                            watch.accept_page(collector.read_json(raw))
                        except APIError as error:
                            record_api_error(watch, error, current, notifier)
                    else:
                        api_jobs[watch] = api_pool.submit(fetch_page, watch.request_params(), token)

            # Bound concurrent downloads. Failed photos remain in posts.jsonl for retry.
            if not expired:
                for watch in watches:
                    for key, media in watch.pending_photos(current):
                        if len(photo_jobs) >= 2:
                            break
                        if (watch, key) not in photo_jobs:
                            photo_jobs[(watch, key)] = photo_pool.submit(
                                collector.save_photo, dict(media), key[0], watch.folder)

            pending_notices = notifier is not None and any(
                r.get("watch_notification_status") == "pending"
                and watch.start <= parse_stamp(r["created_at"]) < watch.end
                for watch in watches for r in watch.records.values())
            if expired and not api_jobs and not photo_jobs:
                break
            if all(w.final_done for w in watches) and not api_jobs and not photo_jobs and not pending_notices:
                break
            time.sleep(0.25 if current >= start else min(30, (start - current).total_seconds()))
    finally:
        api_pool.shutdown(wait=True, cancel_futures=True)
        photo_pool.shutdown(wait=True, cancel_futures=True)
    incomplete = any(not watch.final_done for watch in watches)
    if incomplete:
        LOG.warning("Collection is incomplete. Run the same date with --fetch --once to catch up.")
    for watch in watches:
        photos = sum(1 for _ in watch.pending_photos(deadline + timedelta(days=1)))
        notices = len(watch.pending_notifications(deadline + timedelta(days=1)))
        LOG.info("@%s finished: %d saved, %d pending photos, %d pending notifications",
                 watch.account, len(watch.records), photos, notices)
    return 1 if incomplete else 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--date", type=date.fromisoformat, help="Election date YYYY-MM-DD; default: today in Belgrade")
    parser.add_argument("--fetch", action="store_true", help="Enable continuous paid X reads; otherwise preview only")
    parser.add_argument("--once", action="store_true", help="One catch-up pass from noon to now (or midnight for a past date)")
    parser.add_argument("--include-reposts", action="store_true", help="Include reposts, as in the original collector")
    parser.add_argument("--no-notifications", action="store_true", help="Collect without desktop alerts; retain pending alerts")
    parser.add_argument("--test-notification", action="store_true", help="Send a local test toast without contacting X")
    args = parser.parse_args(argv)
    zone = belgrade_zone()
    if args.test_notification:
        if args.fetch or args.no_notifications:
            parser.error("Use --test-notification on its own, without --fetch or --no-notifications.")
        WindowsNotifier(zone).show("Election X Monitor", "Notifications work. Click to open CeSID on X.",
                                   "https://x.com/CeSIDBeograd")
        print("Test notification submitted. Check the Windows banner or Notification Center.")
        time.sleep(2)
        return 0
    day = args.date or utcnow().astimezone(zone).date()
    start, end = election_window(day, zone)
    print(f"Accounts: {', '.join(ACCOUNTS)}", flush=True)
    print(f"Window: {day} 12:00 through {(day + timedelta(days=1))} 00:00 Europe/Belgrade (end excluded)")
    print(f"Mode: {'one catch-up pass' if args.once else 'every 60 seconds; final catch-up 15 seconds after midnight'}")
    print(f"Output: {ROOT / 'data' / str(day.year)} / <account>")
    print("Notifications:", "disabled" if args.no_notifications else "Windows desktop")
    if not args.fetch:
        print("DRY RUN: no network calls, files, credentials or notifications. Add --fetch to run.")
        return 0
    current = utcnow()
    if start < current - timedelta(days=7):
        parser.error("The start is outside recent search's seven-day window. Use collect_x.py for historical data.")
    if args.once and current <= start + INDEX_DELAY:
        print("No searchable interval yet. Start the continuous monitor without --once, or retry after noon.")
        return 0
    if not args.once and current >= end + FINAL_GRACE:
        parser.error("This monitoring window has ended. Add --once for a catch-up, or choose a future --date.")
    token = collector.read_bearer_token()
    notifier = None if args.no_notifications else WindowsNotifier(zone)
    with ExitStack() as stack:
        watches = []
        for account in ACCOUNTS:
            folder = ROOT / "data" / str(day.year) / account
            stack.enter_context(account_lock(folder))
            watches.append(AccountWatch(folder, account, day, start, end, args.include_reposts))
        log_path = ROOT / "data" / str(day.year) / f"watch_{day}.log"
        handlers = [logging.StreamHandler(sys.stdout), logging.FileHandler(log_path, encoding="utf-8")]
        LOG.setLevel(logging.INFO)
        LOG.propagate = False
        for handler in handlers:
            handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
            LOG.addHandler(handler)
            stack.callback(LOG.removeHandler, handler)
            stack.callback(handler.close)
        LOG.info("Monitor started. Noon-to-midnight times are Europe/Belgrade; logs use the computer's local time.")
        if current < start and not args.once:
            LOG.info("Waiting until noon on %s. Keep this process running.", day)
        return run_watch(watches, token, notifier, once=args.once)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("Stopped. Saved progress and pending notifications will resume on the next run.", file=sys.stderr)
        sys.exit(130)
    except (collector.FetchError, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
