"""Collect X posts and photos. Preview by default; --fetch enables paid reads.

Examples:
    python collect_x.py --account accountname --year 2023
    python collect_x.py --account accountname --year 2023 --fetch --max-posts 10
    python collect_x.py --account accountname --years 2020 2022 2023 --fetch --max-posts 10

Authentication: X_BEARER_TOKEN environment variable or .env beside this script.
Output: data/<year>/<account>/, with photo files directly in that folder.
Only Python's standard library is required. See COLLECT_X.md for details.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

ROOT = Path(__file__).resolve().parent
API_URL = "https://api.x.com/2/tweets/search/all"
POST_READ_PRICE_USD = 0.005  # Estimate; verify the Developer Console rate.
MAX_IMAGE_BYTES = 25 * 1024 * 1024

# Word beginnings intentionally match inflections, e.g. rezultat/rezultati.
# Applied locally: all returned posts are saved, regardless of these matches.
KEYWORDS = [
    "izbor", "preliminarni rezultati", "prvi rezultati",
    "privremeni rezultati", "nezvanični rezultati", "rezultat",
    "preliminar", "privremen", "nezvanič", "projekcij", "procen",
    "procent", "odsto", "glasov", "glasal", "prebroj", "brojanj",
    "obrađen", "obradjen", "obraden", "uzor", "mandat", "cenzus",
    "biračk", "izlaznost", "presek", "paralelno brojanje", "osvoj",
    "parlament", "skupštin", "izborna noć", "exit poll", "exitpoll",
    "ekzit pol", "rik", "rzs", "cesid", "ipsos", "crta",
    "sns", "sps", "srs", "ds", "dss", "ndss", "djb", "dveri",
    "zavetnici", "nada", "poks", "spas", "moramo", "spn", "svm",
    "sda", "spp", "srbija protiv nasilja", "ujedinjeni za pobedu",
    "mi glas iz naroda", "vučić", "dačić", "nestorović",
    # English equivalents, reporting vocabulary and common compact hashtags.
    "election", "result", "preliminary results", "provisional results",
    "unofficial results", "partial results", "initial results", "early results",
    "first results", "final results", "official results", "preliminary",
    "provisional", "unofficial", "projection", "projected", "forecast",
    "predict", "estimat", "percent", "per cent", "turnout", "turn out",
    "voter participation", "voter", "voting", "vote", "ballot",
    "count", "recount", "tally", "tallies", "tallied", "tabulat",
    "processed", "processing", "sample", "sampling", "coverage",
    "seat", "mandate", "threshold", "parliament", "assembly",
    "election night", "election day", "electionnight", "electionday",
    "parallel vote tabulation", "parallel count", "pvt", "vote share",
    "share of the vote", "margin", "confidence interval", "majority",
    "minority", "coalition", "winner", "winning", "wins", "won",
    "polling station", "polling place", "precinct", "constituenc", "district",
    "electoral commission", "election commission", "republic electoral commission",
    "serbiaelection", "serbianelection", "serbiavote", "serbiadecides",
    "serbian progressive party", "socialist party of serbia", "serbian radical party",
    "democratic party", "new democratic party", "serbia against violence",
    "united for victory", "we must", "voice of the people", "serbia must not stop",
]
CYRILLIC = str.maketrans(dict(zip(
    "абвгдђежзијклљмнњопрстћуфхцчџш",
    ["a", "b", "v", "g", "d", "dj", "e", "z", "z", "i", "j", "k",
     "l", "lj", "m", "n", "nj", "o", "p", "r", "s", "t", "c", "u",
     "f", "h", "c", "c", "dz", "s"],
)))


class FetchError(Exception):
    """A fetch failed; do not automatically repeat a potentially billed call."""


def read_bearer_token():
    """Read only X_BEARER_TOKEN; a nonempty environment value takes priority."""
    token = os.environ.get("X_BEARER_TOKEN", "").strip()
    if not token:
        try:
            contents = (ROOT / ".env").read_text(encoding="utf-8-sig")
        except FileNotFoundError:
            contents = ""
        except (OSError, UnicodeError):
            raise FetchError("Cannot read .env; save it as readable UTF-8 text.") from None
        for number, line in enumerate(contents.splitlines(), 1):
            match = re.fullmatch(r"\s*(?:export\s+)?X_BEARER_TOKEN\s*=\s*(.*)", line)
            if not match:
                continue
            value = match.group(1).strip()
            if value.startswith(("'", '"')):
                closing = value.find(value[0], 1)
                trailing = value[closing + 1:].strip() if closing >= 0 else ""
                if closing < 0 or (trailing and not trailing.startswith("#")):
                    raise FetchError(f"Invalid X_BEARER_TOKEN quoting in .env at line {number}.")
                token = value[1:closing].strip()
            else:
                token = re.split(r"\s+#", value, maxsplit=1)[0].strip()
            break
    if not token or any(c.isspace() or not 33 <= ord(c) <= 126 for c in token):
        raise FetchError("Set X_BEARER_TOKEN in .env or the environment to a nonempty, single-line bearer token.")
    return token


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # In particular, never forward an API Authorization header elsewhere.
        return None


def now():
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def normalise(text):
    text = text.casefold().translate(CYRILLIC).replace("đ", "dj")
    text = "".join(c for c in unicodedata.normalize("NFD", text)
                   if not unicodedata.combining(c))
    return re.sub(r"[^\w]+", " ", text).strip()


def parse_window(window):
    bounds = window.split("/")
    if len(bounds) != 2:
        raise ValueError("Window must be start/end with explicit UTC offsets.")
    dates = [datetime.fromisoformat(v.replace("Z", "+00:00")) for v in bounds]
    if any(d.tzinfo is None for d in dates):
        raise ValueError("Both datetimes must include a UTC offset.")
    if dates[0] >= dates[1]:
        raise ValueError("Window start must precede end.")
    return tuple(d.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
                 for d in dates)


def atomic_text(path, text):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def write_json(path, value):
    atomic_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def request_bytes(url, token=None, limit=MAX_IMAGE_BYTES):
    headers = {"User-Agent": "SerbianElectionResearch/1.0"}
    if token:
        if urlsplit(url).hostname != "api.x.com":
            raise FetchError("Refusing to send API credentials to another host.")
        headers["Authorization"] = "Bearer " + token
    try:
        with build_opener(NoRedirect()).open(Request(url, headers=headers), timeout=30) as response:
            body = response.read(limit + 1)
            if len(body) > limit:
                raise FetchError("Response exceeds the configured size limit.")
            return body, response.headers.get_content_type()
    except HTTPError as error:
        hints = {
            400: "Check the query, dates, fields, or saved pagination token.",
            401: "Check X_BEARER_TOKEN.",
            402: "Check API credits and spending limits.",
            403: "Check the app's full-archive search access.",
            429: "Rate limit reached; wait before running again.",
        }
        # Never persist headers, the token, or a response echoing credentials.
        raise FetchError(f"HTTP {error.code}. {hints.get(error.code, 'Request failed.')} "
                         "No automatic retry was made.") from None
    except (URLError, TimeoutError) as error:
        raise FetchError(f"Network failure ({type(error).__name__}); no automatic retry was made.") from None


def fetch_page(params, token):
    body, _ = request_bytes(API_URL + "?" + urlencode(params), token, 10 * 1024 * 1024)
    try:
        page = json.loads(body)
    except (ValueError, UnicodeError):
        raise FetchError("X returned an invalid JSON response.") from None
    if not isinstance(page, dict):
        raise FetchError("Unexpected X response format.")
    return page


def save_photo(media, post_id, folder):
    media = dict(media)
    if media.get("type") != "photo":
        return media
    key = str(media.get("media_key", ""))
    if not re.fullmatch(r"[A-Za-z0-9_]+", key):
        media["download_error"] = "Invalid or missing media key."
        return media
    stem = f"{post_id}_{key}"
    for suffix in (".jpg", ".png", ".webp", ".gif"):
        existing = folder / (stem + suffix)
        if existing.is_file() and existing.stat().st_size:
            media["local_file"] = existing.name
            return media
    try:
        url = urlsplit(media.get("url", ""))
        if url.scheme != "https" or url.hostname != "pbs.twimg.com":
            raise FetchError("Missing or unexpected X photo URL.")
        query = dict(parse_qsl(url.query))
        query["name"] = "orig"  # Request the original available image size.
        original_url = urlunsplit(url._replace(query=urlencode(query)))
        body, mime = request_bytes(original_url)  # No bearer token for images.
        suffix = {"image/jpeg": ".jpg", "image/png": ".png",
                  "image/webp": ".webp", "image/gif": ".gif"}.get(mime)
        if not suffix or not body:
            raise FetchError("Photo response was empty or not a supported image.")
        target = folder / (stem + suffix)
        temporary = target.with_name(target.name + ".part")
        temporary.write_bytes(body)
        temporary.replace(target)
        media["local_file"] = target.name
        media["download_url"] = original_url
    except (FetchError, OSError) as error:
        media["download_error"] = str(error)
    return media


def classify(record, year):
    media = record.get("media", [])
    body = (record.get("note_tweet") or record.get("note_post") or {}).get(
        "text", record.get("text", ""))
    text = normalise(body + " " + " ".join(m.get("alt_text") or "" for m in media))
    hits = [word for word in [*KEYWORDS, f"izbori{year}"]
            if re.search(r"\b" + re.escape(normalise(word)) + r"\w*", text)]
    reasons = []
    if hits:
        reasons.append("keyword")
    if any(m.get("type") == "photo" for m in media) or record.get("missing_media_keys"):
        reasons.append("image_or_unresolved_media")
    if re.search(r"\d+(?:[.,]\d+)?\s*%", body):
        reasons.append("percentage")
    record.update(full_text=body, matched_keywords=hits,
                  candidate=bool(reasons), candidate_reasons=reasons)
    return record


def save_records(folder, records, year):
    ordered = sorted((classify(r, year) for r in records.values()),
                     key=lambda r: (r.get("created_at", ""), r["id"]))
    def lines(items):
        return "".join(json.dumps(item, ensure_ascii=False) + "\n" for item in items)
    atomic_text(folder / "posts.jsonl", lines(ordered))
    atomic_text(folder / "candidates.jsonl", lines(r for r in ordered if r["candidate"]))


def collect(folder, account, year, window, params, max_posts, token):
    # Identify the search independently of this invocation's page/budget limit.
    search_id = hashlib.sha256(json.dumps(params, sort_keys=True).encode()).hexdigest()[:16]
    state_path = folder / f"search_{search_id}.json"
    raw_folder = folder / "raw" / search_id
    raw_folder.mkdir(parents=True, exist_ok=True)
    records_path = folder / "posts.jsonl"
    state = None
    fetched = 0
    calls = 0
    lock_path = folder / ".fetch.lock"
    try:
        lock = lock_path.open("x")
    except FileExistsError:
        raise FetchError("Another collection may be running. If a previous process crashed, "
                         "remove .fetch.lock only after checking that it has stopped.") from None
    lock.close()
    try:
        # Acquire the lock before reading state, so another process cannot make
        # our checkpoint or output snapshot stale while we wait for the lock.
        state = read_json(state_path) if state_path.exists() else {
            "query": params["query"], "window": window, "params": params,
            "pages_processed": 0, "returned_posts_total": 0,
            "next_token": None, "search_exhausted": False,
        }
        records = {}
        if records_path.exists():
            records = {r["id"]: r for r in
                       (json.loads(line) for line in records_path.read_text(encoding="utf-8").splitlines())}
        state.update(last_run_started_at=now(), last_run_status="running")
        write_json(state_path, state)
        while not state["search_exhausted"]:
            raw_path = raw_folder / f"page_{state['pages_processed'] + 1:04d}.json"
            if raw_path.exists():
                # Recover a saved but unprocessed response without another paid read.
                saved = read_json(raw_path)
                page = saved["response"]
            else:
                remaining = max_posts - fetched
                if remaining < 10:
                    break  # X requires max_results >= 10; never round above the cap.
                request_params = dict(params, max_results=min(100, remaining))
                if state["next_token"]:
                    request_params["next_token"] = state["next_token"]
                if calls:
                    time.sleep(1.1)
                calls += 1
                page = fetch_page(request_params, token)
                fetched += len(page.get("data", []))
                saved = {"fetched_at": now(), "params": request_params, "response": page}
                write_json(raw_path, saved)

            batch = page.get("data", [])
            if not isinstance(batch, list) or (not batch and page.get("errors")):
                raise FetchError("X returned no usable posts and reported errors; inspect the raw page.")
            if not batch and "meta" not in page:
                raise FetchError("Response lacks posts and pagination metadata; inspect the raw page.")
            if page.get("errors"):
                print("API reported partial errors; preserved in", raw_path)
            media_by_key = {m["media_key"]: m for m in page.get("includes", {}).get("media", [])}
            for post in batch:
                if not re.fullmatch(r"\d+", str(post.get("id", ""))):
                    raise FetchError("Unexpected post ID in the response; inspect the raw page.")
                keys = post.get("attachments", {}).get("media_keys", [])
                media = [save_photo(media_by_key[k], post["id"], folder)
                         for k in keys if k in media_by_key]
                previous = records.get(post["id"], {})
                searches = sorted(set(previous.get("search_ids", [])) | {search_id})
                records[post["id"]] = {
                    **post, "post_url": f"https://x.com/{account}/status/{post['id']}",
                    "fetched_at": saved["fetched_at"], "media": media,
                    "missing_media_keys": [k for k in keys if k not in media_by_key],
                    "search_ids": searches,
                }
            # Save data before advancing the checkpoint; writes can be replayed.
            save_records(folder, records, year)
            next_token = page.get("meta", {}).get("next_token")
            if next_token and next_token == state["next_token"]:
                raise FetchError("X repeated its pagination token; stopping to avoid repeated reads.")
            state.update(pages_processed=state["pages_processed"] + 1,
                         returned_posts_total=state["returned_posts_total"] + len(batch),
                         next_token=next_token, search_exhausted=not bool(next_token))
            write_json(state_path, state)

        save_records(folder, records, year)
        state["last_run_status"] = "exhausted" if state["search_exhausted"] else "post_limit"
        failures = sum(bool(m.get("download_error")) for r in records.values() for m in r.get("media", []))
        state["photo_download_failures_in_saved_posts"] = failures
        print(f"New API posts: {fetched}; API requests: {calls}; saved unique posts: {len(records)}")
        print(f"Estimated new post-read cost: ${fetched * POST_READ_PRICE_USD:.3f}")
        if state["search_exhausted"]:
            print("Search exhausted (including cached work).")
        elif fetched >= max_posts:
            print(f"PARTIAL: reached this run's cap of {max_posts} new posts; a pagination cursor remains.")
        else:
            print(f"PARTIAL: returned {fetched} of at most {max_posts} new posts. "
                  f"Only {max_posts - fetched} slots remain, below X's minimum page size of 10. "
                  "Stopped to avoid exceeding your cap; a pagination cursor remains.")
        if not state["search_exhausted"]:
            print("Repeat --fetch to resume from the saved cursor with a fresh per-run cap.")
        if failures:
            print(f"{failures} photo download(s) failed; details and URLs are saved in posts.jsonl.")
        print("Output:", folder)
    except (Exception, KeyboardInterrupt):
        if state is not None:
            state["last_run_status"] = "interrupted_or_error"
        raise
    finally:
        try:
            if state is not None:
                state.update(last_run_finished_at=now(), last_run_api_requests=calls,
                             last_run_returned_posts=fetched,
                             last_run_estimated_post_read_cost_usd=round(fetched * POST_READ_PRICE_USD, 3))
                write_json(state_path, state)
        finally:
            lock_path.unlink(missing_ok=True)
    return state


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--account", required=True, help="X handle, with or without @")
    year_options = parser.add_mutually_exclusive_group()
    year_options.add_argument("--year", type=int, help="One election year (default when omitted: 2023)")
    year_options.add_argument("--years", type=int, nargs="+", help="Election years to run sequentially, e.g. 2020 2022 2023")
    parser.add_argument("--window", help="Override interval for a single year only: start/end with UTC offsets")
    parser.add_argument("--max-posts", type=int, default=10, help="Maximum NEW API posts PER YEAR this run (default: 10)")
    parser.add_argument("--include-reposts", action="store_true", help="Include reposts; referenced media is not expanded")
    parser.add_argument("--fetch", action="store_true", help="Enable network calls and paid API reads; default is preview only")
    args = parser.parse_args(argv)
    account = args.account.lstrip("@").lower()
    if not re.fullmatch(r"[a-z0-9_]{1,15}", account):
        parser.error("--account must be an X handle, not a URL.")
    if account in {"con", "prn", "aux", "nul"} or re.fullmatch(r"(?:com|lpt)[1-9]", account):
        parser.error("This handle is a reserved Windows directory name.")
    if args.max_posts < 10:
        parser.error("--max-posts must be >= 10 (X's minimum page size).")
    years = args.years if args.years is not None else [args.year if args.year is not None else 2023]
    if any(not 2006 <= year <= 9999 for year in years):
        parser.error("Invalid election year.")
    if len(set(years)) != len(years):
        parser.error("List each year only once.")
    if args.window and len(years) != 1:
        parser.error("--window can only be used with one year; multiple years use their saved JSON windows.")

    # Validate every window before credentials, output writes or paid requests.
    windows = {} if args.window else read_json(ROOT / "election_windows.json")
    query = f"from:{account}" + ("" if args.include_reposts else " -is:retweet")
    searches = []
    for year in years:
        window = args.window or windows.get(f"election{year}")
        if not window:
            parser.error(f"No saved window for {year}; add it to election_windows.json or run that year with --window.")
        try:
            start, end = parse_window(window)
        except ValueError as error:
            parser.error(f"Invalid window for {year}: {error}")
        params = {
            "query": query, "start_time": start, "end_time": end, "sort_order": "recency",
            "tweet.fields": "created_at,author_id,attachments,entities,referenced_tweets,conversation_id,note_tweet",
            "expansions": "attachments.media_keys",
            "media.fields": "media_key,type,url,preview_image_url,alt_text,width,height",
        }
        searches.append((year, window, params, ROOT / "data" / str(year) / account))

    if len(years) > 1:
        total_limit = args.max_posts * len(years)
        print(f"Years: {', '.join(map(str, years))}; cap: {args.max_posts} new posts per year, "
              f"up to {total_limit} total this run.")
        print(f"Estimated maximum total post-read cost at the configured rate: "
              f"${total_limit * POST_READ_PRICE_USD:.3f}")
    for year, window, params, folder in searches:
        print(f"\nYear: {year}")
        print("Query:", query)
        print(f"UTC interval: [{params['start_time']}, {params['end_time']})")
        print(f"New post limit: {args.max_posts}; estimated maximum post-read cost: "
              f"${args.max_posts * POST_READ_PRICE_USD:.3f}")
        print("Destination:", folder)
        if not args.window:
            print(f"Saved window (Belgrade offsets): {window}")
    if not args.fetch:
        print("DRY RUN: no network calls, no files written, no credits used. Add --fetch to collect.")
        return 0
    token = read_bearer_token()
    summaries = []
    previous_made_requests = False
    for year, window, params, folder in searches:
        if previous_made_requests:
            time.sleep(1.1)  # Keep search calls in separate years spaced as well.
        print(f"\nCollecting {year} for @{account}")
        try:
            state = collect(folder, account, year, window, params, args.max_posts, token)
        except (FetchError, ValueError, OSError):
            print(f"Stopped during {year}; later years were not attempted. Saved progress can be resumed.")
            raise
        previous_made_requests = bool(state.get("last_run_api_requests", 0))
        summaries.append((year, state))
    if len(years) > 1:
        print("\nBatch summary (new posts in this run):")
        for year, state in summaries:
            status = "exhausted" if state["search_exhausted"] else "partial; rerun to continue"
            print(f"  {year}: {state['last_run_returned_posts']} posts; {status}")
        total_fetched = sum(state["last_run_returned_posts"] for _, state in summaries)
        print(f"Total new API posts: {total_fetched}; estimated post-read cost: "
              f"${total_fetched * POST_READ_PRICE_USD:.3f}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (FetchError, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        print("Interrupted; saved pages can be resumed.", file=sys.stderr)
        sys.exit(130)
