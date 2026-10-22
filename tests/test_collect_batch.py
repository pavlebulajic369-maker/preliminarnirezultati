"""Offline multi-year collection tests: no real credentials or network calls."""

import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import call, patch

import collect_x as collector


WINDOWS = {
    "election2020": "2020-06-21T20:00:00+02:00/2020-06-22T00:00:00+02:00",
    "election2022": "2022-04-03T20:00:00+02:00/2022-04-04T00:00:00+02:00",
    "election2023": "2023-12-17T20:00:00+01:00/2023-12-18T00:00:00+01:00",
}
ARGS = ["--account", "Example", "--years", "2020", "2022", "2023", "--max-posts", "10"]


def page(count, start=1, cursor=None):
    result = {"data": [{"id": str(i), "text": "Result", "created_at": "2023-12-17T21:00:00Z"}
                       for i in range(start, start + count)], "meta": {"result_count": count}}
    if cursor:
        result["meta"]["next_token"] = cursor
    return result


class BatchTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.windows_file = self.root / "election_windows.json"
        self.windows_file.write_text(json.dumps(WINDOWS), encoding="utf-8")
        root_patch = patch.object(collector, "ROOT", self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)
        self.output = io.StringIO()
        redirect = contextlib.redirect_stdout(self.output)
        redirect.__enter__()
        self.addCleanup(redirect.__exit__, None, None, None)

    def test_batch_preview_uses_correct_year_windows_without_auth_or_writes(self):
        with patch.object(collector, "read_bearer_token") as auth, \
                patch.object(collector, "request_bytes") as network:
            self.assertEqual(collector.main(ARGS), 0)
        auth.assert_not_called()
        network.assert_not_called()
        self.assertFalse((self.root / "data").exists())
        text = self.output.getvalue()
        self.assertIn("up to 30 total this run", text)
        for year, start, end in [(2020, "2020-06-21T18:00:00Z", "2020-06-21T22:00:00Z"),
                                 (2022, "2022-04-03T18:00:00Z", "2022-04-03T22:00:00Z"),
                                 (2023, "2023-12-17T19:00:00Z", "2023-12-17T23:00:00Z")]:
            self.assertIn(f"UTC interval: [{start}, {end})", text)
            self.assertIn(str(self.root / "data" / str(year) / "example"), text)

    def test_batch_caps_resume_and_completed_searches_are_independent(self):
        official = self.root / "data" / "2020_official" / "results.json"
        official.parent.mkdir(parents=True)
        official.write_text('{"official": true}', encoding="utf-8")
        originals = official.read_bytes()
        with patch.object(collector, "read_bearer_token", return_value="fake-secret"), \
                patch.object(collector.time, "sleep") as sleep, \
                patch.object(collector, "fetch_page", side_effect=[page(5, cursor="next-2020"),
                                                                  page(2),
                                                                  page(10, cursor="next-2023")]) as api:
            self.assertEqual(collector.main(ARGS + ["--fetch"]), 0)
        self.assertEqual(api.call_count, 3)
        self.assertEqual([c.args[0]["max_results"] for c in api.call_args_list], [10, 10, 10])
        self.assertEqual([c.args[0]["start_time"][:4] for c in api.call_args_list], ["2020", "2022", "2023"])
        self.assertEqual(sleep.call_args_list, [call(1.1), call(1.1)])
        self.assertIn("Total new API posts: 17", self.output.getvalue())

        with patch.object(collector, "read_bearer_token", return_value="fake-secret"), \
                patch.object(collector.time, "sleep"), \
                patch.object(collector, "fetch_page", side_effect=[page(1, start=6), page(0)]) as api:
            self.assertEqual(collector.main(ARGS + ["--fetch"]), 0)
        self.assertEqual(api.call_count, 2)
        self.assertEqual([c.args[0]["next_token"] for c in api.call_args_list], ["next-2020", "next-2023"])
        for year, count in [(2020, 6), (2022, 2), (2023, 10)]:
            folder = self.root / "data" / str(year) / "example"
            self.assertEqual(len((folder / "posts.jsonl").read_text().splitlines()), count)
            state = collector.read_json(next(folder.glob("search_*.json")))
            self.assertTrue(state["search_exhausted"])
        self.assertEqual(official.read_bytes(), originals)
        self.assertNotIn("fake-secret", self.output.getvalue())

        with patch.object(collector, "read_bearer_token", return_value="fake-secret"), \
                patch.object(collector, "fetch_page") as api, \
                patch.object(collector.time, "sleep") as sleep:
            self.assertEqual(collector.main(ARGS + ["--fetch"]), 0)
        api.assert_not_called()
        sleep.assert_not_called()

    def test_invalid_batch_options_fail_before_any_fetch(self):
        invalid_options = [
            ["--year", "2020", "--years", "2022", "2023"],
            ["--years", "2020", "2022", "--window", WINDOWS["election2020"]],
            ["--years", "2020", "2020"],
            ["--years", "2020", "2018"],
        ]
        for options in invalid_options:
            with self.subTest(options=options), contextlib.redirect_stderr(io.StringIO()), \
                    patch.object(collector, "read_bearer_token") as auth, \
                    patch.object(collector, "collect") as collect:
                with self.assertRaises(SystemExit) as error:
                    collector.main(["--account", "example", "--fetch"] + options)
                self.assertEqual(error.exception.code, 2)
                auth.assert_not_called()
                collect.assert_not_called()
        self.assertFalse((self.root / "data").exists())

    def test_later_invalid_window_is_validated_before_first_year_fetch(self):
        self.windows_file.write_text(json.dumps({**WINDOWS, "election2023": "invalid"}), encoding="utf-8")
        with contextlib.redirect_stderr(io.StringIO()), \
                patch.object(collector, "read_bearer_token") as auth, \
                patch.object(collector, "collect") as collect:
            with self.assertRaises(SystemExit):
                collector.main(ARGS + ["--fetch"])
        auth.assert_not_called()
        collect.assert_not_called()
        self.assertFalse((self.root / "data").exists())

    def test_fetch_error_stops_later_years_and_preserves_completed_work(self):
        with patch.object(collector, "read_bearer_token", return_value="fake-secret"), \
                patch.object(collector.time, "sleep"), \
                patch.object(collector, "fetch_page", side_effect=[page(2), collector.FetchError("HTTP 429")]) as api:
            with self.assertRaisesRegex(collector.FetchError, "HTTP 429"):
                collector.main(ARGS + ["--fetch"])
        self.assertEqual(api.call_count, 2)
        self.assertEqual(len((self.root / "data/2020/example/posts.jsonl").read_text().splitlines()), 2)
        self.assertFalse((self.root / "data/2023").exists())
        self.assertIn("Stopped during 2022", self.output.getvalue())

    def test_other_options_are_applied_to_every_selected_year(self):
        with patch.object(collector, "read_bearer_token", return_value="fake-secret"), \
                patch.object(collector.time, "sleep"), \
                patch.object(collector, "fetch_page", side_effect=[page(0), page(0), page(0)]) as api:
            collector.main(ARGS + ["--fetch", "--include-reposts"])
        self.assertEqual([c.args[0]["query"] for c in api.call_args_list], ["from:example"] * 3)


if __name__ == "__main__":
    unittest.main()
