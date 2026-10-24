"""Offline watcher tests. No real X requests or Windows notifications."""

from concurrent.futures import Future
from contextlib import redirect_stdout
from datetime import date, timedelta
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from urllib.error import HTTPError

import collect_x as collector
import watch_x as watcher


class ImmediatePool:
    """Deterministic network workers for scheduler tests."""
    def __init__(self, **kwargs):
        pass

    def submit(self, function, *args):
        future = Future()
        try:
            future.set_result(function(*args))
        except Exception as error:
            future.set_exception(error)
        return future

    def shutdown(self, **kwargs):
        pass


class WatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.day = date(2026, 11, 1)
        self.zone = watcher.belgrade_zone()
        self.start, self.end = watcher.election_window(self.day, self.zone)
        self.folder = self.root / "data" / "2026" / "cesidbeograd"
        self.current = self.start + timedelta(hours=1)
        self.output = io.StringIO()
        self.redirect = redirect_stdout(self.output)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)
        # Any accidentally unmocked API call fails, rather than reaching the network.
        self.network_guard = patch.object(watcher, "build_opener", side_effect=AssertionError("Real API call"))
        self.network_guard.start()
        self.addCleanup(self.network_guard.stop)
        self.photo_guard = patch.object(collector, "request_bytes", side_effect=AssertionError("Real photo call"))
        self.photo_guard.start()
        self.addCleanup(self.photo_guard.stop)

    def make_watch(self, account="cesidbeograd"):
        return watcher.AccountWatch(self.root / "data" / "2026" / account,
                                    account, self.day, self.start, self.end)

    def page(self, ids=("1",), next_token=None, photo=False):
        data = [{"id": str(i), "text": "Ordinary post", "created_at": watcher.stamp(self.start + timedelta(minutes=1))}
                for i in ids]
        response = {"data": data, "meta": {"result_count": len(data)}}
        if next_token:
            response["meta"]["next_token"] = next_token
        if photo:
            data[0]["attachments"] = {"media_keys": ["3_123"]}
            response["includes"] = {"media": [{"media_key": "3_123", "type": "photo",
                                                   "url": "https://pbs.twimg.com/media/example.png"}]}
        return {"response": response, "fetched_at": watcher.stamp(self.current)}

    def accept(self, watch, page=None):
        watch.begin_poll(self.current)
        saved = page or self.page()
        collector.write_json(watch.raw_path(), saved)
        watch.accept_page(saved)

    def run_simulated(self, watches, fetch, once=True, sleeper=None, notifier=None):
        def advance(seconds):
            self.current += timedelta(seconds=max(1, seconds))
        with patch.object(watcher, "ThreadPoolExecutor", ImmediatePool), \
                patch.object(watcher, "utcnow", side_effect=lambda: self.current), \
                patch.object(watcher.time, "sleep", side_effect=sleeper or advance), \
                patch.object(watcher, "fetch_page", side_effect=fetch):
            return watcher.run_watch(watches, "fake-token", notifier, once=once)

    def test_preview_has_no_side_effects_or_credentials(self):
        with patch.object(watcher, "ROOT", self.root), \
                patch.object(collector, "read_bearer_token") as token, \
                patch.object(watcher, "WindowsNotifier") as notifier:
            self.assertEqual(watcher.main(["--date", "2026-11-01"]), 0)
        token.assert_not_called()
        notifier.assert_not_called()
        self.assertEqual(list(self.root.iterdir()), [])
        self.assertIn("12:00", self.output.getvalue())
        self.assertIn("2026-11-02 00:00", self.output.getvalue())

    def test_window_uses_belgrade_summer_and_winter_offsets(self):
        summer = watcher.election_window(date(2026, 6, 1), self.zone)
        winter = watcher.election_window(date(2026, 12, 1), self.zone)
        self.assertEqual(watcher.stamp(summer[0]), "2026-06-01T10:00:00Z")
        self.assertEqual(watcher.stamp(winter[0]), "2026-12-01T11:00:00Z")
        for start, end in (summer, winter):
            self.assertEqual(end - start, timedelta(hours=12))

    def test_all_posts_saved_but_only_candidates_classified(self):
        watch = self.make_watch()
        self.accept(watch, self.page(("1", "2")))
        self.assertEqual(len(watch.records), 2)
        self.assertEqual((self.folder / "candidates.jsonl").read_text(), "")
        self.assertEqual(len(watch.pending_notifications(self.current)), 2)
        self.assertEqual(watch.request_params() if watch.state["pending"] else watch.query,
                         "from:cesidbeograd -is:retweet")

    def test_no_duplicate_records_or_notifications_after_restart(self):
        watch = self.make_watch()
        self.accept(watch)
        notifier = Mock()
        self.assertTrue(watcher.deliver_one([watch], notifier, self.current))
        restarted = self.make_watch()
        self.current += timedelta(minutes=1)
        self.accept(restarted)
        self.assertEqual(len(restarted.records), 1)
        self.assertFalse(watcher.deliver_one([restarted], notifier, self.current))
        self.assertEqual(notifier.send_post.call_count, 1)

    def test_notification_failure_remains_pending_across_restart(self):
        watch = self.make_watch()
        self.accept(watch)
        notifier = Mock()
        notifier.send_post.side_effect = RuntimeError("Windows unavailable")
        watcher.deliver_one([watch], notifier, self.current)
        self.assertEqual(self.make_watch().records["1"]["watch_notification_status"], "pending")
        self.assertFalse(watch.pending_notifications(self.current))

    def test_pagination_does_not_advance_checkpoint_early(self):
        watch = self.make_watch()
        self.accept(watch, self.page(next_token="page-two"))
        self.assertEqual(watch.state["covered_until"], watcher.stamp(self.start))
        restarted = self.make_watch()
        self.assertEqual(restarted.request_params()["next_token"], "page-two")
        restarted.accept_page(self.page(("2",)))
        self.assertEqual(restarted.state["covered_until"], watcher.stamp(self.current))
        self.assertEqual(set(restarted.records), {"1", "2"})

    def test_overlap_starts_from_checkpoint_after_outage(self):
        watch = self.make_watch()
        self.accept(watch)
        checkpoint = self.current
        self.current += timedelta(hours=2)
        watch.begin_poll(self.current)
        self.assertEqual(watch.request_params()["start_time"], watcher.stamp(checkpoint - watcher.OVERLAP))

    def test_late_indexed_post_in_overlap_is_saved_and_notified(self):
        watch = self.make_watch()
        self.accept(watch, self.page(("2",)))
        self.current += timedelta(minutes=1)
        self.accept(watch, self.page(("1", "2")))
        self.assertEqual(set(watch.records), {"1", "2"})
        self.assertEqual(len(watch.pending_notifications(self.current)), 2)

    def test_post_filter_includes_noon_and_excludes_midnight(self):
        watch = self.make_watch()
        saved = self.page(("1", "2", "3", "4"))
        for post, timestamp in zip(saved["response"]["data"],
                                   (self.start - timedelta(seconds=1), self.start,
                                    self.end - timedelta(seconds=1), self.end)):
            post["created_at"] = watcher.stamp(timestamp)
        self.accept(watch, saved)
        self.assertEqual(set(watch.records), {"2", "3"})

    def test_saved_raw_page_survives_crash_before_export(self):
        watch = self.make_watch()
        watch.begin_poll(self.current)
        collector.write_json(watch.raw_path(), self.page())
        restarted = self.make_watch()
        restarted.accept_page(collector.read_json(restarted.raw_path()))
        self.assertEqual(set(restarted.records), {"1"})
        self.assertEqual(restarted.records["1"]["watch_notification_status"], "pending")

    def test_crash_after_export_before_checkpoint_does_not_lose_notification(self):
        watch = self.make_watch()
        watch.begin_poll(self.current)
        collector.write_json(watch.raw_path(), self.page())
        with patch.object(watch, "save_state", side_effect=OSError("Interrupted write")):
            with self.assertRaises(OSError):
                watch.accept_page(self.page())
        restarted = self.make_watch()
        self.assertIsNotNone(restarted.state["pending"])
        restarted.accept_page(collector.read_json(restarted.raw_path()))
        self.assertEqual(len(restarted.records), 1)
        self.assertEqual(len(restarted.pending_notifications(self.current)), 1)

    def test_photo_failure_does_not_block_notification_and_can_recover(self):
        watch = self.make_watch()
        self.accept(watch, self.page(photo=True))
        key, media = next(watch.pending_photos(self.current))
        watch.accept_photo(key, {**media, "download_error": "Offline"}, self.current)
        self.assertTrue(watcher.deliver_one([watch], Mock(), self.current))
        self.assertFalse(list(watch.pending_photos(self.current)))
        later = self.current + timedelta(minutes=5)
        self.assertEqual(len(list(watch.pending_photos(later))), 1)
        (self.folder / "1_3_123.png").write_bytes(b"test")
        watch.accept_photo(key, {**media, "local_file": "1_3_123.png", "download_error": "Old error"}, later)
        self.assertNotIn("download_error", watch.records["1"]["media"][0])
        self.assertFalse(list(watch.pending_photos(later)))

    def test_once_drains_all_pages_for_both_accounts(self):
        watches = [self.make_watch(account) for account in watcher.ACCOUNTS]
        requests = []
        def fetch(params, token):
            requests.append(params)
            return self.page(("2",) if "next_token" in params else ("1",),
                             None if "next_token" in params else "next")["response"]
        self.assertEqual(self.run_simulated(watches, fetch), 0)
        self.assertEqual(len(requests), 4)
        for watch in watches:
            self.assertEqual(set(watch.records), {"1", "2"})
            self.assertTrue(watch.final_done)

    def test_scheduler_waits_for_noon_and_reconciles_through_midnight(self):
        watches = [self.make_watch(account) for account in watcher.ACCOUNTS]
        self.current = self.start - timedelta(seconds=30)
        requests = []
        def sleep(seconds):
            if self.current >= self.start + timedelta(minutes=2) and self.current < self.end:
                self.current = self.end + watcher.INDEX_DELAY
            else:
                self.current += timedelta(seconds=max(1, seconds))
        def fetch(params, token):
            self.assertGreater(self.current, self.start)
            requests.append(params)
            return self.page(())["response"]
        self.assertEqual(self.run_simulated(watches, fetch, once=False, sleeper=sleep), 0)
        for watch in watches:
            self.assertEqual(watch.state["covered_until"], watcher.stamp(self.end))
        final = [r for r in requests if r["end_time"] == watcher.stamp(self.end)]
        self.assertEqual(len(final), 2)
        self.assertTrue(all(r["start_time"] == watcher.stamp(self.start) for r in final))
        self.assertIn(watcher.stamp(self.start + timedelta(seconds=45)), [r["end_time"] for r in requests])

    def test_rate_limited_account_does_not_stop_other_account(self):
        watches = [self.make_watch(account) for account in watcher.ACCOUNTS]
        def fetch(params, token):
            if "cesidbeograd" in params["query"]:
                raise watcher.APIError("Rate limited", retry_after=120)
            return self.page()["response"]
        self.assertEqual(self.run_simulated(watches, fetch), 1)
        self.assertFalse(watches[0].final_done)
        self.assertTrue(watches[1].final_done)
        self.assertEqual(set(watches[1].records), {"1"})

    def test_invalid_cached_response_is_quarantined_then_retried(self):
        watch = self.make_watch()
        watch.begin_poll(self.current)
        collector.write_json(watch.raw_path(), {"response": {}, "fetched_at": watcher.stamp(self.current)})
        self.assertEqual(self.run_simulated([watch], lambda *_: self.page()["response"]), 0)
        self.assertTrue(list(watch.raw_folder.glob("*_error_*.json")))
        self.assertEqual(set(watch.records), {"1"})

    def test_repeated_pagination_token_is_fatal(self):
        watch = self.make_watch()
        self.accept(watch, self.page(next_token="same"))
        with self.assertRaises(watcher.APIError) as caught:
            watch.accept_page(self.page(("2",), next_token="same"))
        self.assertTrue(caught.exception.fatal)
        self.assertEqual(watch.state["covered_until"], watcher.stamp(self.start))

    def test_http_rate_limit_uses_reset_headers_without_exposing_secrets(self):
        error = HTTPError(watcher.API_URL, 429, "secret", {"retry-after": "180"}, io.BytesIO(b"secret"))
        self.addCleanup(error.close)
        with patch.object(watcher, "build_opener") as opener:
            opener.return_value.open.side_effect = error
            with self.assertRaises(watcher.APIError) as caught:
                watcher.fetch_page({"query": "from:crtars"}, "fake-secret")
        self.assertFalse(caught.exception.fatal)
        self.assertGreaterEqual(caught.exception.retry_after, 180)
        self.assertNotIn("secret", str(caught.exception))

    def test_missing_token_stops_before_writing(self):
        with patch.object(watcher, "ROOT", self.root), \
                patch.object(watcher, "utcnow", return_value=self.current), \
                patch.object(collector, "read_bearer_token", side_effect=collector.FetchError("Missing token")):
            with self.assertRaises(collector.FetchError):
                watcher.main(["--date", "2026-11-01", "--fetch"])
        self.assertEqual(list(self.root.iterdir()), [])

    def test_account_lock_prevents_overlapping_writes_and_releases(self):
        with watcher.account_lock(self.folder):
            with self.assertRaises(collector.FetchError):
                with watcher.account_lock(self.folder):
                    self.fail("Second writer acquired the lock")
        self.assertFalse((self.folder / ".fetch.lock").exists())

    def test_notification_test_never_contacts_x_or_reads_token(self):
        with patch.object(watcher, "WindowsNotifier") as notifier, \
                patch.object(collector, "read_bearer_token") as token, \
                patch.object(watcher.time, "sleep"):
            self.assertEqual(watcher.main(["--test-notification"]), 0)
        notifier.return_value.show.assert_called_once()
        token.assert_not_called()


if __name__ == "__main__":
    unittest.main()
