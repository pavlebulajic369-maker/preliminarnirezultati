# Collect one account's historical election posts

Run from the project root. Only Python 3.10+ is needed; there are no pip dependencies.
The script reads a nonempty `X_BEARER_TOKEN` from the current process environment first, otherwise from `.env` beside `collect_x.py`. It does not accept tokens as command-line arguments. Never put the token in the script or commit it.

## Save your token in .env

The project root contains a blank `.env`. Edit it locally and put your bearer token after the equals sign:

```dotenv
X_BEARER_TOKEN=your_bearer_token_here
```

Use the token exactly as provided, without a `Bearer ` prefix. Optional single or double quotes, comment lines, and trailing comments after whitespace are supported. Only this one key is read; shell commands, variable substitutions and escape sequences are not evaluated. `.env` is excluded by `.gitignore`. The preview does not read credentials.

If you previously set the token in PowerShell, clear that value once so the script uses `.env`:

```powershell
Remove-Item Env:X_BEARER_TOKEN -ErrorAction SilentlyContinue
```

## Free preview

Replace `accountname` with the actual handle. A leading `@` is optional.

```powershell
.\.venv\Scripts\python.exe .\collect_x.py --account accountname --year 2023
```

The default is a dry run: it displays the exact UTC interval, query, output folder and estimated post-read limit. It makes no network requests, writes no files and does not need a token. Every current saved window covers **20:00 on election day through the end of the following day in Belgrade**, a 28-hour interval. In ISO timestamps, the end is `00:00` two calendar dates after election day. Start is inclusive and end is exclusive. See `election_windows.sources.md` for the dates and sources, and `README.md` for the Serbian guide and evaluation results.

For 2023 the window is 17 December at 20:00 through 19 December at 00:00; files go in `data/2023/accountname/`. Changing the window creates a new search checkpoint. Previously saved posts remain in place, including any outside the new window; use `search_ids` to identify records from a particular search.

## First live test: at most 10 newly returned posts

After saving your token in `.env`, set a spending limit suitable for your $5 credit balance in the X Developer Console and disable auto-recharge if you want a fixed initial budget. Then run:

```powershell
.\.venv\Scripts\python.exe .\collect_x.py --account accountname --year 2023 --fetch --max-posts 10
```

This requests at most 10 new posts, normally in one API request. At the published rate of $0.005 per post, the estimated post-read charge is at most $0.05. Photographs attached to those posts are downloaded too; ten posts can contain more than ten photographs. If there are no photographs among the returned posts, no image files will be created. Results arrive newest first, so this test samples posts closest to the end of the selected window.

The cap applies to all newly returned posts, not just keyword matches, and resets for each year each time you run the command. There are no automatic retries, profile lookups, count queries or referenced-post lookups. A timeout may still have been billed by X; the console remains the authority for actual charges. The script's cost figures are estimates, not an account-wide spending limit.

After checking `posts.jsonl`, `candidates.jsonl` and any pictures, continue with a larger capped batch:

```powershell
.\.venv\Scripts\python.exe .\collect_x.py --account accountname --year 2023 --fetch --max-posts 100
```

That permits up to 100 additional post reads (estimated $0.50). The same search resumes from its saved pagination token. Once exhausted, repeating it makes no additional X search request. If fewer than ten slots remain under a cap, the script stops rather than exceeding the cap to meet X's minimum page size.

To use another interval:

```powershell
.\.venv\Scripts\python.exe .\collect_x.py --account accountname --year 2023 --window "2023-12-17T20:00:00+01:00/2023-12-17T21:00:00+01:00"
```

Preview first, then add `--fetch`. The `--year` selects the output folder; keep it consistent with a custom window. Changing the interval or repost setting creates a separate search checkpoint. Overlapping searches can return already-saved posts and still consume credits; local deduplication is not a billing guarantee.

Alternatively, to use a token only for this terminal session instead of saving it in `.env`:

```powershell
$tokenSecret = Read-Host "Paste X bearer token" -AsSecureString
$env:X_BEARER_TOKEN = [System.Net.NetworkCredential]::new('', $tokenSecret).Password
Remove-Variable tokenSecret
```

When finished with a token set in the terminal, remove it below. This does not erase `.env`:

```powershell
Remove-Item Env:X_BEARER_TOKEN -ErrorAction SilentlyContinue
```

## Run 2020, 2022 and 2023 for one account

With the virtual environment active, set the account once and preview all three searches:

```powershell
$account = "CeSIDBeograd"
python .\collect_x.py --account $account --years 2020 2022 2023 --max-posts 10
```

Then enable fetching:

```powershell
python .\collect_x.py --account $account --years 2020 2022 2023 --fetch --max-posts 10
```

The same options apply to every selected year. `--max-posts 10` allows up to **10 newly returned posts per year**, hence up to **30 total per invocation** for three years. The preview shows a combined cost estimate at the configured rate. Years run sequentially in the order listed, with independent saved cursors and caps. The final summary identifies which searches are exhausted and which remain partial.

Output follows the existing layout:

```text
data/2020/cesidbeograd/
data/2022/cesidbeograd/
data/2023/cesidbeograd/
```

Each account folder contains its post records, photos, raw API pages and search checkpoint. Official-results folders are not read or modified by collection. Changing `$account` selects the next account; the actual handle is `CeSIDBeograd` (with the `e`), and folder names are lowercase.

Repeat the same batch command to continue partial searches. Exhausted searches make no further X search requests. Existing records and photos are retained. Ten posts is a batch limit, not evidence that most relevant posts were collected; continue until every selected year reports exhausted to finish these 28-hour windows. Results outside the windows are excluded from the search, and keyword matching happens locally after collection.

The existing `--year 2023` command still works; omitting both year options defaults to 2023. Use either `--year` or `--years`, and list each year once. A custom `--window` requires a single year. All requested windows are validated before fetching begins. An error stops the batch; saved progress remains available for another invocation.

## Files saved

```text
data/2023/accountname/
  posts.jsonl
  candidates.jsonl
  1736500000000000000_3_1736499999999999999.jpg
  search_<search-id>.json
  raw/<search-id>/page_0001.json
```

- `posts.jsonl`: one JSON object per unique post, ordered by publication time. Includes text, long-form text when returned, post ID, author ID, timestamp, URL, reference IDs, matching keywords, candidate reasons, media metadata and relative image filenames. A post can belong to several searches via `search_ids`.
- `candidates.jsonl`: the subset with a keyword match, percentage, photograph or unresolved attachment. This is a broad review queue, not a claim that every entry reports an election result.
- Pictures live **directly in `data/2023/accountname/`**. Filenames use `<post-id>_<media-key>.<extension>`, so multiple photographs on one post stay distinct. The extension follows the downloaded content type. The script requests original-size photos from X's image CDN and never sends the bearer token to it. Existing nonempty picture files are reused.
- `search_<search-id>.json`: query, window, pagination cursor, exhausted/partial/error status, counts and estimated cost of the last invocation. `search_exhausted` concerns post pagination; inspect the photo failure count separately.
- `raw/<search-id>/page_*.json`: original successful API responses, their request parameters and retrieval times. These allow auditing and replay after an interruption. They contain no authentication headers.

A transient `.fetch.lock` prevents simultaneous writes to an account's output. If the process is forcibly killed, check it is no longer running before deleting that lock. Do not delete checkpoints or raw pages just to repeat a test: that can cause previously retrieved pages to be fetched again.

Photo failures and URLs are retained as `download_error` in `posts.jsonl`. A photo download failure does not discard the post or stop all other downloads. Completed searches are not automatically re-fetched to retry photos. Only directly attached photographs are downloaded; videos, GIF animations and images inside quoted/reposted posts are not fetched as additional content. Their available metadata/reference IDs are retained. Deleted/protected/unindexed content may not be obtainable.

## Keywords and attribution

Edit `KEYWORDS` near the top of `collect_x.py`. The list includes Serbian and English election, turnout, results, counting, projection, seat-allocation and party/coalition terms, plus common hashtags. Matching normalizes Serbian Cyrillic and Latin, strips accents and accepts word endings. The API fetch is account-and-time based, so an incomplete keyword list does not discard raw posts or image-only tables. Re-running a completed search also rebuilds the local candidate list with your current keywords without another search request. Keywords cannot bring in posts outside the selected date window, and image text is not read by OCR.

Replies and quotes are included; reposts are excluded unless `--include-reposts` is supplied. Images are not OCR'd, and historical edits are not reconstructed. Review whether a claim is about national parliamentary results, another election, turnout or another source's estimate before scoring it.

## Sources checked 2026-10-18

- X full-archive endpoint, fields and pagination: https://docs.x.com/x-api/posts/search/quickstart/full-archive-search
- X pricing ($0.005 per Post read), spending limits and recharge settings: https://docs.x.com/x-api/getting-started/pricing

No separate CDN photo-download fee is listed on that pricing page. Check your console before a larger run. The implementation has offline tests; actual access, historical coverage and billing require your first authorized live request.
