"""Offline tests: never contact X or read a real bearer token."""

import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import collect_x as collector


WINDOW = "2023-12-17T20:00:00+01:00/2023-12-18T00:00:00+01:00"
PARAMS = {"query": "from:example -is:retweet", "start_time": "2023-12-17T19:00:00Z",
          "end_time": "2023-12-17T23:00:00Z", "sort_order": "recency"}


def page(start=1, count=10, next_token=None, photo=False):
    response = {"data": [{"id": str(i), "text": "Just a post",
                          "created_at": "2023-12-17T19:10:00Z"}
                         for i in range(start, start + count)],
                "meta": {"result_count": count}}
    if next_token:
        response["meta"]["next_token"] = next_token
    if photo:
        response["data"][0]["text"] = "Evo"
        response["data"][0]["attachments"] = {"media_keys": ["3_123"]}
        response["includes"] = {"media": [{"media_key": "3_123", "type": "photo",
                                             "url": "https://pbs.twimg.com/media/test.png"}]}
    return response


class CollectorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.folder = self.root / "data" / "2023" / "example"
        self.output = io.StringIO()
        self.redirect = contextlib.redirect_stdout(self.output)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)

    def collect(self, cap=10):
        return collector.collect(self.folder, "example", 2023, WINDOW,
                                 dict(PARAMS), cap, "fake-secret")

    def test_preview_needs_no_token_and_makes_no_files_or_requests(self):
        (self.root / "election_windows.json").write_text(json.dumps({"election2023": WINDOW}))
        with patch.object(collector, "ROOT", self.root), patch.dict(os.environ, {}, clear=True), \
                patch.object(collector, "request_bytes") as network:
            self.assertEqual(collector.main(["--account", "Example"]), 0)
        network.assert_not_called()
        self.assertFalse((self.root / "data").exists())
        self.assertIn("DRY RUN", self.output.getvalue())

    def test_fetch_without_token_stops_before_network_or_output(self):
        with patch.object(collector, "ROOT", self.root), patch.dict(os.environ, {}, clear=True), \
                patch.object(collector, "request_bytes") as network:
            with self.assertRaisesRegex(collector.FetchError, "X_BEARER_TOKEN"):
                collector.main(["--account", "example", "--window", WINDOW, "--fetch"])
        network.assert_not_called()
        self.assertFalse((self.root / "data").exists())

    def test_dotenv_token_reaches_fetch_without_being_printed(self):
        secret = "fake%2Fsecret%3D"
        for value in (secret, f'"{secret}" # comment', f"'{secret}'", f"{secret} # comment"):
            with self.subTest(value=value):
                (self.root / ".env").write_text(
                    f"# Local credentials\nOTHER_SETTING=ignored\nX_BEARER_TOKEN={value}\n",
                    encoding="utf-8-sig",
                )
                with patch.object(collector, "ROOT", self.root), patch.dict(os.environ, {}, clear=True), \
                        patch.object(collector, "collect") as collect, \
                        patch.object(collector, "request_bytes") as network:
                    collector.main(["--account", "example", "--window", WINDOW, "--fetch"])
                    self.assertEqual(collect.call_args.args[-1], secret)
                    self.assertNotIn("X_BEARER_TOKEN", os.environ)
                    self.assertNotIn("OTHER_SETTING", os.environ)
                network.assert_not_called()
        self.assertNotIn(secret, self.output.getvalue())

    def test_nonempty_environment_token_overrides_dotenv(self):
        (self.root / ".env").write_text('X_BEARER_TOKEN="broken-file-secret\n')
        with patch.object(collector, "ROOT", self.root), \
                patch.dict(os.environ, {"X_BEARER_TOKEN": "environment-secret"}, clear=True):
            self.assertEqual(collector.read_bearer_token(), "environment-secret")

    def test_empty_environment_token_falls_back_to_dotenv(self):
        (self.root / ".env").write_text("X_BEARER_TOKEN=file-secret\n")
        with patch.object(collector, "ROOT", self.root), \
                patch.dict(os.environ, {"X_BEARER_TOKEN": ""}, clear=True):
            self.assertEqual(collector.read_bearer_token(), "file-secret")

    def test_invalid_dotenv_stops_before_network_without_echoing_secret(self):
        for value in ('"secret-without-closing-quote', "secret with spaces", ""):
            with self.subTest(value=value):
                (self.root / ".env").write_text(f"X_BEARER_TOKEN={value}\n")
                with patch.object(collector, "ROOT", self.root), patch.dict(os.environ, {}, clear=True), \
                        patch.object(collector, "request_bytes") as network:
                    with self.assertRaises(collector.FetchError) as error:
                        collector.main(["--account", "example", "--window", WINDOW, "--fetch"])
                network.assert_not_called()
                if value:
                    self.assertNotIn(value, str(error.exception))
                self.assertFalse((self.root / "data").exists())

    def test_preview_does_not_read_credentials(self):
        with patch.object(collector, "ROOT", self.root), \
                patch.object(collector, "read_bearer_token", side_effect=AssertionError("Credential read")):
            self.assertEqual(collector.main(["--account", "example", "--window", WINDOW]), 0)

    def test_serbian_variants_and_numeric_posts_are_candidates(self):
        variants = ["Прелиминарни резултати: обрађено 50%", "Preliminarni rezultati: obrađeno 50%",
                    "Preliminarni rezultati: obradjeno 50%"]
        self.assertEqual(len(set(map(collector.normalise, variants))), 1)
        for text in variants + ["#Избори2023", "47,2%"]:
            record = collector.classify({"text": text, "media": []}, 2023)
            self.assertTrue(record["candidate"])
        self.assertFalse(collector.classify({"text": "Good morning", "media": []}, 2023)["candidate"])

    def test_timezone_and_exclusive_end_are_preserved(self):
        self.assertEqual(collector.parse_window(WINDOW),
                         ("2023-12-17T19:00:00Z", "2023-12-17T23:00:00Z"))
        with self.assertRaises(ValueError):
            collector.parse_window("2023-12-17T20:00:00/2023-12-17T21:00:00")

    def test_small_test_saves_photo_in_requested_folder_without_token(self):
        picture = b"\x89PNG\r\n\x1a\nfixture"
        with patch.object(collector, "fetch_page", return_value=page(next_token="next", photo=True)) as api, \
                patch.object(collector, "request_bytes", return_value=(picture, "image/png")) as cdn:
            state = self.collect()
        api.assert_called_once()
        self.assertEqual(api.call_args.args[0]["max_results"], 10)
        cdn.assert_called_once_with("https://pbs.twimg.com/media/test.png?name=orig")
        self.assertEqual((self.folder / "1_3_123.png").read_bytes(), picture)
        records = [json.loads(s) for s in (self.folder / "posts.jsonl").read_text().splitlines()]
        self.assertEqual(len(records), 10)
        self.assertEqual(records[0]["media"][0]["local_file"], "1_3_123.png")
        candidates = [json.loads(s) for s in (self.folder / "candidates.jsonl").read_text().splitlines()]
        self.assertEqual(len(candidates), 1)
        self.assertFalse(state["search_exhausted"])
        self.assertEqual(state["last_run_estimated_post_read_cost_usd"], 0.05)
        for file in self.folder.rglob("*.json*"):
            self.assertNotIn("fake-secret", file.read_text())

    def test_resume_then_completed_search_does_not_refetch(self):
        with patch.object(collector, "fetch_page", return_value=page(next_token="cursor")):
            self.collect()
        with patch.object(collector, "fetch_page", return_value=page(11, 2)) as api:
            state = self.collect()
        self.assertEqual(api.call_args.args[0]["next_token"], "cursor")
        self.assertTrue(state["search_exhausted"])
        with patch.object(collector, "fetch_page") as api:
            state = self.collect()
        api.assert_not_called()
        self.assertEqual(state["last_run_returned_posts"], 0)
        self.assertEqual(len((self.folder / "posts.jsonl").read_text().splitlines()), 12)

    def test_remaining_budget_below_minimum_page_does_not_overspend(self):
        with patch.object(collector, "fetch_page", return_value=page(next_token="cursor")) as api:
            state = self.collect(cap=11)
        api.assert_called_once()
        self.assertEqual(api.call_args.args[0]["max_results"], 11)
        self.assertEqual(state["last_run_returned_posts"], 10)
        self.assertEqual(state["last_run_status"], "post_limit")

    def test_short_page_explains_why_it_stops_before_the_cap(self):
        with patch.object(collector, "fetch_page", return_value=page(count=5, next_token="cursor")) as api:
            state = self.collect(cap=10)
        api.assert_called_once()
        self.assertEqual(state["last_run_returned_posts"], 5)
        self.assertEqual(state["next_token"], "cursor")
        self.assertFalse(state["search_exhausted"])
        self.assertIn("Only 5 slots remain", self.output.getvalue())
        self.assertIn("Stopped to avoid exceeding your cap", self.output.getvalue())

    def test_saved_response_is_recovered_without_a_paid_request(self):
        search_id = hashlib.sha256(json.dumps(PARAMS, sort_keys=True).encode()).hexdigest()[:16]
        raw = self.folder / "raw" / search_id
        raw.mkdir(parents=True)
        collector.write_json(raw / "page_0001.json", {"fetched_at": "2026-10-18T12:00:00Z",
                                                      "response": page(count=2)})
        with patch.object(collector, "fetch_page") as api:
            state = self.collect()
        api.assert_not_called()
        self.assertTrue(state["search_exhausted"])
        self.assertEqual(len((self.folder / "posts.jsonl").read_text().splitlines()), 2)

    def test_photo_failure_keeps_post_and_reports_failure(self):
        with patch.object(collector, "fetch_page", return_value=page(count=1, photo=True)), \
                patch.object(collector, "request_bytes", side_effect=collector.FetchError("HTTP 404")):
            state = self.collect()
        record = json.loads((self.folder / "posts.jsonl").read_text())
        self.assertEqual(record["media"][0]["download_error"], "HTTP 404")
        self.assertEqual(state["photo_download_failures_in_saved_posts"], 1)
        self.assertTrue(state["search_exhausted"])

    def test_api_http_error_is_not_retried_and_does_not_expose_token(self):
        error = HTTPError(collector.API_URL, 401, "Unauthorized", {}, io.BytesIO(b"secret"))
        self.addCleanup(error.close)
        with patch.object(collector, "build_opener") as opener:
            opener.return_value.open.side_effect = error
            with self.assertRaises(collector.FetchError) as context:
                collector.request_bytes(collector.API_URL, "fake-secret")
        self.assertEqual(opener.return_value.open.call_count, 1)
        self.assertNotIn("fake-secret", str(context.exception))
        self.assertIn("401", str(context.exception))


if __name__ == "__main__":
    unittest.main()
