# Serbian parliamentary election search windows

Updated 2026-10-18. Scope: the five national parliamentary election cycles in this project: 2014, 2016, 2020, 2022 and 2023. Presidential, provincial and local elections are outside this file's scope.

`election_windows.json` contains ISO 8601 interval strings, `start/end`. Each window covers **20:00 on election day to midnight in Europe/Belgrade**, as requested. Midnight ending election day is written as **00:00 on the next calendar day**. Each interval lasts four hours, with start inclusive and end exclusive. The start is the scheduled close of voting, not a claim that every polling station actually closed at that moment. The end is a user-selected collection boundary, independent of RIK announcement times.

| Key | Start (Belgrade) | Exclusive end (Belgrade) |
| --- | --- | --- |
| election2014 | 16 March 2014, 20:00 CET | 17 March 2014, 00:00 CET |
| election2016 | 24 April 2016, 20:00 CEST | 25 April 2016, 00:00 CEST |
| election2020 | 21 June 2020, 20:00 CEST | 22 June 2020, 00:00 CEST |
| election2022 | 3 April 2022, 20:00 CEST | 4 April 2022, 00:00 CEST |
| election2023 | 17 December 2023, 20:00 CET | 18 December 2023, 00:00 CET |

## Election-date sources

- [2014 RIK election archive](https://arhiva.rik.parlament.gov.rs/latinica/arhiva-izbori-za-narodne-poslanike-2014.php)
- [2016 RIK total results](https://arhiva.rik.parlament.gov.rs/latinica/izbori-za-narodne-poslanike-2016-rezultati.php)
- [2020 RIK election archive](https://www.rik.parlament.gov.rs/tekst/sr/1550/izbori-za-narodne-poslanike-narodne-skupstine-21-jun-2020-godine-.php)
- [2022 RIK report identifying the original election date and repeat votes](https://www.rik.parlament.gov.rs/vest/sr/324925/79-sednica-republicke-izborne-komisije.php)
- [2023 RIK report identifying the original election date and repeat votes](https://www.rik.parlament.gov.rs/vest/564488/51-sednica-republicke-izborne-komisije.php)

## Interpretation and collection

Being inside a window does not prove that a post offered an independent prediction or preceded RIK's preliminary figures. Preserve publication time, sample coverage, geography, attribution and corrections. Compare each national parliamentary estimate with final national parliamentary totals using the same denominator. Assess turnout separately from vote shares.

Pictures and post records remain under `data/<election-year>/<accountname>/`. Changing a saved interval creates a different search checkpoint. Existing downloaded records remain in place, including any outside the new interval; `search_ids` identifies their searches. Local deduplication does not guarantee that X will not charge for overlapping API reads. The collector's per-run post cap still applies.
