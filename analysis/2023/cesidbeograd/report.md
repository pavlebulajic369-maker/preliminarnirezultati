# CeSID/Ipsos: 2023 parliamentary estimate accuracy

Evaluated from the seven locally fetched @CeSIDBeograd posts. Four contain national estimates, forming two successive sample updates; three concern the separate Belgrade city election and are excluded. All times below are Belgrade CET on 17 December 2023.

The six individually stored lists have mean absolute vote-share error **0.239 pp** in the first saved update and **0.154 pp** in the later one. The later seat allocation needs **one seat reassigned** to match the final result. This supports good accuracy in this limited sample, not a calibrated account reliability score.

## Benchmark audit

The Parquet has 8,273 unique stations. Every station's eight vote groups sum to its valid-ballot count, counts are nonnegative, and no required counts are missing. National sums reconcile exactly with the cited RIK report. This validates the totals used here; it does not independently validate every station's data or timing features.

RIK source: [51st session, final national results adopted 12 January 2024](https://www.rik.parlament.gov.rs/vest/564488/51-sednica-republicke-izborne-komisije.php).

The file's `turnout_2023` sums to 3,820,746 voters who turned out. RIK separately records **3,815,007 ballots cast**, equal to 3,710,978 valid plus 104,029 invalid ballots. Use ballots cast for the published RIK percentage convention. The Parquet lacks the invalid-ballot total and seat columns, so those come from the cited RIK reference. Party vote numerators for the six main lists and eight groups come directly from the Parquet.

The charts do not explicitly state their percentage denominator. Their 18 entries sum to 97.1% and 97.2%, which supports comparing them with shares including invalid ballots, rather than treating the entries as percentages of valid votes. This remains an assumption; sensitivity results appear below.

## Observations and scores

| Post time CET | Metric | Processed sample | Main-list MAE | Main-list RMSE | Maximum main-list error |
| --- | --- | ---: | ---: | ---: | ---: |
| [21:59:26](https://x.com/cesidbeograd/status/1736491315691446389) | Vote share | 72.6% | 0.239 pp | 0.293 pp | 0.555 pp |
| [23:28:09](https://x.com/cesidbeograd/status/1736513641321546053) | Vote share | 88.4% | 0.154 pp | 0.238 pp | 0.555 pp |

The primary set is SNS, SPN, SPS, MI, NADA and Zavetnici-Dveri: exactly the six lists stored individually in the Parquet. Equal weight is given to each. Coverage is the share of CeSID/Ipsos's sample processed, not the share of all Serbian votes counted and not a score weight.

| List | Final RIK share | 21:59 estimate | Error | 23:28 estimate | Error |
| --- | ---: | ---: | ---: | ---: | ---: |
| SNS | 46.7549% | 46.6% | -0.155 pp | 46.2% | -0.555 pp |
| SPN | 23.6553% | 23.1% | -0.555 pp | 23.7% | +0.045 pp |
| SPS | 6.5509% | 6.9% | +0.349 pp | 6.6% | +0.049 pp |
| MI | 4.6875% | 4.8% | +0.112 pp | 4.8% | +0.112 pp |
| NADA | 5.0178% | 4.8% | -0.218 pp | 4.9% | -0.118 pp |
| ZAV_DVERI | 2.7566% | 2.8% | +0.043 pp | 2.8% | +0.043 pp |

Later SPN, SPS and NADA estimates improve, while SNS moves farther below its final share. MI and Zavetnici-Dveri are unchanged. A later update is therefore better on average without being better for every party.

## Scoring model

```text
official_share_i = 100 * sum(station_votes_i) / 3,815,007
error_i = published_share_i - official_share_i
MAE = sum(abs(error_i)) / number_of_lists
RMSE = sqrt(sum(error_i ** 2) / number_of_lists)
seat_distance = sum(abs(projected_seats_i - final_seats_i)) / 2
seat_agreement = 100 * (1 - seat_distance / 250)
```

Worked example, latest SNS: `100 * 1,783,701 / 3,815,007 = 46.754855%`; error is `46.2 - 46.754855 = -0.554855 pp`. Absolute error is 0.554855 pp. Average the six absolute errors to obtain 0.153735 pp. Computation uses unrounded official shares.

Percentage points measure the difference between percentages; they are not relative percentage error. Lower MAE/RMSE is better. There is no arbitrary `100 - MAE` reliability percentage, no trained prediction model, and no pooling of the two correlated updates as independent evidence.

## Seat projections

| Post time CET | Processed sample | Seats needing reassignment | Allocation agreement | Exact list allocations |
| --- | ---: | ---: | ---: | ---: |
| [22:21:20](https://x.com/cesidbeograd/status/1736496827044634778) | 72.6% | 2 / 250 | 99.2% | 15 / 18 |
| [23:32:02](https://x.com/cesidbeograd/status/1736514618996961555) | 88.4% | 1 / 250 | 99.6% | 16 / 18 |

At 22:21 the discrepancies are SPN 63 versus 65, SPS 19 versus 18, and SPP/DSHV 3 versus 2. At 23:32 only SNS 128 versus 129 and SPP/DSHV 3 versus 2 differ. Both projections total 250 and identify the same ten seat-winning lists as the final result. Allocation agreement describes seat overlap, not the probability this account will be accurate next time.

## Grouping and denominator sensitivity

| Measure | 72.6% update | 88.4% update |
| --- | ---: | ---: |
| Primary six, RIK ballots-cast denominator | 0.239 pp | 0.154 pp |
| Eight Parquet groups, RIK denominator | 0.210 pp | 0.159 pp |
| All 18 lists, supplemental RIK breakdown | 0.098 pp | 0.075 pp |
| Six lists, literal Parquet turnout denominator | 0.223 pp | 0.150 pp |
| Six lists, both sides normalized to valid votes | 0.227 pp | 0.156 pp |

All rows are MAE. The 18-list result includes many small parties and is not directly comparable to the six-list headline. Eight-group results can hide offsetting errors among grouped lists. For valid-vote sensitivity, each chart's shares are divided by the sum of all 18 displayed shares, while official counts are divided by valid ballots.

`MANJINE` combines SVM, SPP/DSHV, SDA, PDD, Russian Party, Peace and Tolerance, and ADA. `OSTALI` combines SRS, DJB/SDS, Narodna stranka, LDP and Srbija na Zapadu. Each mapping reconciles exactly with its Parquet column. Full per-list and per-group calculations are in `evaluation.json`.

## Excluded observations and limits

- [22:45:55](https://x.com/cesidbeograd/status/1736503013278179328): Belgrade city assembly vote_share, 42% processed sample. Excluded because the national Parquet cannot benchmark this different election.
- [22:52:08](https://x.com/cesidbeograd/status/1736504577833181469): Belgrade city assembly seats, 42% processed sample. Excluded because the national Parquet cannot benchmark this different election.
- [23:57:09](https://x.com/cesidbeograd/status/1736520939683168370): Belgrade city assembly vote_share, 77% processed sample. Excluded because the national Parquet cannot benchmark this different election.

The national 88.4% posts use `#izboribeograd` despite their national captions and chart titles. Scope was decided from the actual claim and image, not the hashtag.

- Only two national vote-share snapshots and two linked seat snapshots from one joint CeSID/Ipsos source and one election.
- The saved fetch is partial; earlier posts may remain. Earliest saved is not necessarily first published.
- Values were manually read from images; this script checks input hashes and recomputes scores, not OCR.
- Vote estimates are displayed to 0.1 percentage point. No sample size/design information supports confidence intervals.
- Belgrade city assembly results require a separate benchmark; national votes cast in Belgrade are not that benchmark.
- Final results include repeat voting. These are retrospective final-outcome errors, not errors against contemporaneous sample totals.
- No inference of publication latency or independence from RIK is made from timestamp_cet or speed_percentile in the Parquet.

The latest saved national estimate arrives at 23:28 CET (3 hours 28 minutes after scheduled closing); its seat projection follows at 23:32. The first saved estimate at 21:59 is not proven to be the account's earliest estimate. The checkpoint still has a next-page cursor. No extra X calls were made for this evaluation.

## Reproduce and audit

From the project root, with the existing virtual environment active:

```powershell
python .\evaluate_2023.py
```

Inputs: the original Parquet, saved `posts.jsonl`, local images, `claims.json` (reviewed image transcriptions) and `rik_reference.json` (supplemental official data and grouping). Input/image SHA-256 hashes are recorded and checked. Outputs: this report and `evaluation.json`. The original Parquet, fetched posts, images and collector checkpoints are unchanged.

To extend the account evaluation, collect and review the remaining posts, then repeat this method across elections at comparable times after closing. Keep source attribution: these posts are joint CeSID/Ipsos estimates, not independent observations from two accounts.
