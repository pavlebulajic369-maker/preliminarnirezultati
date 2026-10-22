# Saved election-account accuracy review

Reviewed 103 saved posts and 41 photo attachments across seven accounts and three election years.

| Account | 2020 | 2022 | 2023 | Confidence / 100 |
| --- | --- | --- | --- | ---: |
| @cesidbeograd | 0.170 pp | 0.162 pp | 0.154 pp | 63 |
| @crtars | 3/3 bounds contain final | No numerical forecast | No numerical forecast | 20 |
| @miikialeksic | No numerical forecast | No numerical forecast | No numerical forecast | 1 |
| @milos_vucevic | No numerical forecast | No numerical forecast | No numerical forecast | 1 |
| @narodnipokrets | No numerical forecast | No numerical forecast | No numerical forecast | 1 |
| @slobodaipravda | No numerical forecast | No numerical forecast | No numerical forecast | 1 |
| @sns_srbija | No numerical forecast | No numerical forecast | No numerical forecast | 1 |

Table errors are latest saved top-six MAE using each chart’s inferred percentage basis. Lower is better. Confidence incorporates all saved point snapshots, averaged within each year, on a common valid-vote basis. A floor of 1 means insufficient quantitative evidence, not 1% accuracy.

## Model

```text
error_i = estimate_i - official_i
MAE = mean(abs(error_i))
normalized_estimate_i = 100 * displayed_share_i / sum(all displayed shares)
normalized_official_i = 100 * votes_i / valid_ballots
year_error = mean(top-six normalized MAE across that year’s snapshots)
N = sum(year evidence weights)
E = weighted mean(year_error)
confidence = clamp(round_half_up(100 * max(0, 1 - E/2) * N/(N+1)), 1, 100)
```

One full-list forecast year carries weight 1. A bounds-only year carries 0.25. An incomplete saved search multiplies that weight by 0.75. Turnout, seats, registration and winner-only claims do not add evidence years. The 2 pp scale and evidence weights are judgment choices, not statistically fitted parameters.

CeSID worked score: E = 0.230287 pp, N = 2.50. 100 × (1 − E/2) × N/(N+1) = 63.204, rounded to 63. The three elections contribute weights 0.75, 1.00, 0.75 because 2020 and 2023 still have pagination cursors. This score is not the percentage of correct forecasts.

## National vote snapshots

| Account/year | Local time | Sample processed | Main basis | Top-six MAE | All-list MAE | Top-six maximum error |
| --- | --- | ---: | --- | ---: | ---: | ---: |
| @cesidbeograd / 2020 | [21:40:23](https://x.com/cesidbeograd/status/1274789282079703047) | 63.9% | valid_ballots | 0.224 | 0.120 | 0.620 |
| @cesidbeograd / 2020 | [22:15:42](https://x.com/cesidbeograd/status/1274798166576189443) | 75.5% | valid_ballots | 0.174 | 0.095 | 0.520 |
| @cesidbeograd / 2020 | [23:09:43](https://x.com/cesidbeograd/status/1274811761041051649) | 87.4% | valid_ballots | 0.136 | 0.104 | 0.220 |
| @cesidbeograd / 2020 | [23:33:04](https://x.com/cesidbeograd/status/1274817636006846465) | 91.1% | valid_ballots | 0.170 | 0.108 | 0.420 |
| @cesidbeograd / 2022 | [22:38:07](https://x.com/cesidbeograd/status/1510718307967582218) | 62.5% | ballots_cast | 0.383 | 0.160 | 0.875 |
| @cesidbeograd / 2022 | [23:21:24](https://x.com/cesidbeograd/status/1510729200650629126) | 77.1% | ballots_cast | 0.162 | 0.084 | 0.475 |
| @cesidbeograd / 2023 | [21:59:26](https://x.com/cesidbeograd/status/1736491315691446389) | 72.6% | ballots_cast | 0.239 | 0.098 | 0.555 |
| @cesidbeograd / 2023 | [23:28:09](https://x.com/cesidbeograd/status/1736513641321546053) | 88.4% | ballots_cast | 0.154 | 0.075 | 0.555 |

## Interpretation

- CeSID/Ipsos supplies all eight full national vote-share charts in this sample. Two 2023 seat projections need two seats and one seat reassigned respectively to match the final 250-seat allocation.
- CeSID’s 2020 full-party charts sum near 100 and the final post separately states 4% invalid ballots. Comparing these charts directly with RIK’s published shares of all voters would mix denominators. The valid-vote comparison is an explicit inference; alternative raw comparisons remain in the detailed JSON.
- CeSID’s 2020 47.7% turnout claim explicitly excludes Kosovo, prisons and abroad. Its matched benchmark uses Central Serbia plus Vojvodina, not the national total.
- CRTA’s 2020 SNS >58%, SPS 9–11%, and SPAS 3.5–4.5% statements all contain the final official shares. Their broad bounds do not establish the precision of a full-party forecast. Its final turnout interval is checked separately.
- CRTA’s saved 2022/2023 percentages are intraday turnout and sample progress. It explicitly waits for 95% sample coverage. The midnight window therefore does not contain a national vote projection for those years. Two 2023 registration numbers match the official benchmarks but are not forecasts.
- SNS’s explicit 2023 largest-list statement is consistent with the final result. Miloš Vučević’s victory message is only contextual corroboration because the election scope and margin are unspecified. Neither provides numerical accuracy evidence in the saved posts or photos.
- Miki Aleksić has two 2020 comments and no numerical forecast. Narodni pokret Srbije and Stranka slobode i pravde have livestream links without saved/transcribed video claims. Their accuracy is unavailable from this material.
- Presidential and Belgrade city charts were transcribed but excluded from national parliamentary scoring. The official XLSX/PDF files do not benchmark those different elections.

## Sources and reproducibility

2020: `data/2020_official/G202019004.xlsx`, Резултати!A4:BB4; station rows independently reconcile with national totals. Turnout subset uses C5:D6.

2022: `data/2022_official/G202219002.xlsx`, Sheet1!F2:AC8268; 8,267 unique municipality/station records; final empty row ignored. All station rows pass vote/ballot reconciliation. National totals and party votes also match the [RIK final report](https://www.rik.parlament.gov.rs/vest/sr/324925/79-sednica-republicke-izborne-komisije.php).

2023: `data/2023_official/G20246006.pdf`, file pages 8–9 (printed pages 6–7), Tables 1.1 and 1.2. Text extracted and national totals/party counts/seats visually checked on page renders. Existing reviewed CeSID 2023 transcriptions were reused with hashes checked.

All 103 posts have individual review dispositions. All 41 photo attachments were visually reviewed, including ten missing local attachments recovered from their saved public image URLs under `analysis/accounts/recovered_media/`. Linked websites and video streams are not part of the saved evidence. No paid X API calls were made.

Run `python .\evaluate_accounts.py` from the root. It uses the standard library and checked-in reviewed JSON inputs. It verifies original-source, post and image hashes before writing `executive_decision.json` and detailed comparisons. New or changed data requires review; it will fail instead of silently scoring unreviewed images.

## Limits

- Only three historical election nights. Accounts with no saved forecasts are unassessed, not demonstrated inaccurate.
- Midnight cutoff can omit later high-quality forecasts. API exhaustion only covers the configured query/window; deleted posts and external linked content remain absent.
- Final official results include repeat voting and administrative corrections. Retrospective differences do not by themselves demonstrate a reporting mistake on election night.
- Updates on the same night are correlated. CeSID/Ipsos joint estimates form one source family, not two independent confirmations.
- Forecasts are rounded, mainly to 0.1 pp. Sampling design is unavailable, so no statistical confidence interval or calibrated probability is claimed.
- Final official counts are the requested benchmark; this does not assess electoral integrity or resolve reported irregularities.
- The fixed confidence weights and 2 pp scale express a conservative screening rule. Use underlying errors and evidence counts for decisions, not score alone.
