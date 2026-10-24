# Saved election-account accuracy review

Reviewed 244 posts and 102 photo attachments across 7 accounts. 12 video/other attachments were not transcribed.

Collection window: election day 20:00 through midnight ending the following day, Belgrade time. Four matching cutoffs: 22:00, first midnight, 02:00 and final midnight. There is no 06:00 cutoff.

## Account evidence

| Account | 2020 cutoff coverage | 2022 cutoff coverage | 2023 cutoff coverage | Confidence / 100 |
| --- | ---: | ---: | ---: | ---: |
| @cesidbeograd | 4/4 | 3/4 | 4/4 | 67 |
| @crtars | 1/4 | 2/4 | 2/4 | 50 |
| @miikialeksic | 0/4 | 0/4 | 0/4 | 1 |
| @milos_vucevic | 0/4 | 0/4 | 0/4 | 1 |
| @narodnipokrets | 0/4 | 0/4 | 0/4 | 1 |
| @slobodaipravda | 0/4 | 0/4 | 0/4 | 1 |
| @sns_srbija | 0/4 | 0/4 | 0/4 | 1 |

Coverage counts original full-list parliamentary projections available by each cutoff. An earlier projection can remain the latest available at later cutoffs. Missing values are unavailable, not zero error. Confidence is an uncalibrated, coverage-dependent screening score, not percentage accuracy or an account-wide trust rating. Accounts with different covered slots must not be ranked by this score alone.

## Matched-time comparisons

Errors below are top-six MAE after normalizing complete chart shares and official votes to valid votes. All accounts in one row group share an election year and deadline. They are listed alphabetically. Age shows how old the latest eligible information was at that deadline.

| Year | Cutoff (Belgrade) | Account | Top-six MAE (pp) | Age (minutes) | Same source as previous cutoff |
| --- | --- | --- | ---: | ---: | --- |
| 2020 | 2020-06-21T22:00:00+02:00 | @cesidbeograd | 0.234 | 19.6 | no |
| 2020 | 2020-06-22T00:00:00+02:00 | @cesidbeograd | 0.200 | 26.9 | no |
| 2020 | 2020-06-22T02:00:00+02:00 | @cesidbeograd | 0.200 | 146.9 | yes |
| 2020 | 2020-06-23T00:00:00+02:00 | @cesidbeograd | 0.200 | 1466.9 | yes |
| 2020 | 2020-06-23T00:00:00+02:00 | @crtars | 0.092 | 667.0 | no |
| 2022 | 2022-04-03T22:00:00+02:00 | No eligible forecast | unavailable | — | — |
| 2022 | 2022-04-04T00:00:00+02:00 | @cesidbeograd | 0.168 | 38.6 | no |
| 2022 | 2022-04-04T02:00:00+02:00 | @cesidbeograd | 0.080 | 40.5 | no |
| 2022 | 2022-04-04T02:00:00+02:00 | @crtars | 0.360 | 84.3 | no |
| 2022 | 2022-04-05T00:00:00+02:00 | @cesidbeograd | 0.080 | 723.0 | no |
| 2022 | 2022-04-05T00:00:00+02:00 | @crtars | 0.273 | 512.0 | no |
| 2023 | 2023-12-17T22:00:00+01:00 | @cesidbeograd | 0.227 | 0.6 | no |
| 2023 | 2023-12-18T00:00:00+01:00 | @cesidbeograd | 0.156 | 31.9 | no |
| 2023 | 2023-12-18T02:00:00+01:00 | @cesidbeograd | 0.156 | 151.8 | yes |
| 2023 | 2023-12-18T02:00:00+01:00 | @crtars | 0.179 | 101.5 | no |
| 2023 | 2023-12-19T00:00:00+01:00 | @cesidbeograd | 0.156 | 1471.8 | yes |
| 2023 | 2023-12-19T00:00:00+01:00 | @crtars | 0.116 | 610.2 | no |

## Model

```text
error_i = estimate_i - official_i
MAE = mean(abs(error_i))
normalized_estimate_i = 100 * displayed_share_i / sum(all displayed shares)
normalized_official_i = 100 * votes_i / valid_ballots
cutoff_error = MAE across the six largest lists by final votes
year_error = equal mean(cutoff_error for available cutoff slots)
year_weight = (available_cutoffs / 4) * (1 if collection exhausted else 0.75)
N = sum(year_weight); E = weighted mean(year_error)
confidence = clamp(round_half_up(100 * max(0, 1 - E/2) * N/(N+1)), 1, 100)
```

One election contributes at most one effective year. Repeated snapshots and repeated use of the same forecast at several cutoffs do not add independent years. Bounds, partial party vectors, official figures quoted by an account, seats and turnout do not increase this point-forecast score. The error scale and evidence weights are judgment choices, not fitted statistical parameters. Schema 1 scores used all snapshots and credited bounds; schema 2 scores are not directly comparable.

## Reviewed numerical claims

| Account/year | Available in Belgrade | Kind | Source role | Detail |
| --- | --- | --- | --- | --- |
| @cesidbeograd / 2020 | [2020-06-21T21:40:23+02:00](https://x.com/cesidbeograd/status/1274789282079703047) | vote_share | original_projection | Native-basis top-six MAE 0.224 pp; normalized 0.234 pp |
| @cesidbeograd / 2020 | [2020-06-21T22:15:42+02:00](https://x.com/cesidbeograd/status/1274798166576189443) | vote_share | original_projection | Native-basis top-six MAE 0.174 pp; normalized 0.184 pp |
| @cesidbeograd / 2020 | [2020-06-21T23:09:43+02:00](https://x.com/cesidbeograd/status/1274811761041051649) | vote_share | original_projection | Native-basis top-six MAE 0.136 pp; normalized 0.175 pp |
| @cesidbeograd / 2020 | [2020-06-21T23:33:04+02:00](https://x.com/cesidbeograd/status/1274817636006846465) | vote_share | original_projection | Native-basis top-six MAE 0.170 pp; normalized 0.200 pp |
| @cesidbeograd / 2020 | [2020-06-21T23:33:04+02:00](https://x.com/cesidbeograd/status/1274817636006846465) | invalid_ballot_share | original_projection | Supplementary; see detailed JSON |
| @cesidbeograd / 2020 | [2020-06-21T23:04:05+02:00](https://x.com/cesidbeograd/status/1274810342326046721) | turnout | original_projection | Supplementary; see detailed JSON |
| @cesidbeograd / 2022 | [2022-04-03T22:38:07+02:00](https://x.com/cesidbeograd/status/1510718307967582218) | vote_share | original_projection | Native-basis top-six MAE 0.383 pp; normalized 0.398 pp |
| @cesidbeograd / 2022 | [2022-04-03T23:21:24+02:00](https://x.com/cesidbeograd/status/1510729200650629126) | vote_share | original_projection | Native-basis top-six MAE 0.162 pp; normalized 0.168 pp |
| @cesidbeograd / 2023 | [2023-12-17T21:59:26+01:00](https://x.com/cesidbeograd/status/1736491315691446389) | vote_share | original_projection | Native-basis top-six MAE 0.239 pp; normalized 0.227 pp |
| @cesidbeograd / 2023 | [2023-12-17T22:21:20+01:00](https://x.com/cesidbeograd/status/1736496827044634778) | seats | original_projection | 2 seats to reassign; supplementary |
| @cesidbeograd / 2023 | [2023-12-17T23:28:09+01:00](https://x.com/cesidbeograd/status/1736513641321546053) | vote_share | original_projection | Native-basis top-six MAE 0.154 pp; normalized 0.156 pp |
| @cesidbeograd / 2023 | [2023-12-17T23:32:02+01:00](https://x.com/cesidbeograd/status/1736514618996961555) | seats | original_projection | 1 seats to reassign; supplementary |
| @crtars / 2020 | [2020-06-21T22:51:45+02:00](https://x.com/crtars/status/1274807242198585346) | vote_share_bounds | original_projection | 3/3 bounds contain final; not point accuracy |
| @crtars / 2020 | [2020-06-21T22:49:06+02:00](https://x.com/crtars/status/1274806574821842944) | turnout_bounds | original_projection | Supplementary; see detailed JSON |
| @crtars / 2020 | [2020-06-21T22:53:07+02:00](https://x.com/crtars/status/1274807584248209411) | below_threshold | original_projection | Supplementary; see detailed JSON |
| @crtars / 2023 | [2023-12-17T20:46:52+01:00](https://x.com/crtars/status/1736473053465313303) | registered_voters | original_projection | Supplementary; see detailed JSON |
| @sns_srbija / 2023 | [2023-12-17T22:54:21+01:00](https://x.com/sns_srbija/status/1736505133297451187) | winner | political_statement | Supplementary; see detailed JSON |
| @milos_vucevic / 2023 | [2023-12-17T23:41:38+01:00](https://x.com/milos_vucevic/status/1736517035817886148) | winner | political_statement | Supplementary; see detailed JSON |
| @cesidbeograd / 2022 | [2022-04-04T01:19:27+02:00](https://x.com/cesidbeograd/status/1510758910382284805) | vote_share | original_projection | Native-basis top-six MAE 0.082 pp; normalized 0.080 pp |
| @cesidbeograd / 2022 | [2022-04-04T11:57:02+02:00](https://x.com/cesidbeograd/status/1510919362894565385) | vote_share | original_projection | Native-basis top-six MAE 0.082 pp; normalized 0.080 pp |
| @cesidbeograd / 2022 | [2022-04-04T12:00:00+02:00](https://x.com/cesidbeograd/status/1510920112391528448) | turnout | original_projection | No comparable scope benchmark; accuracy unavailable |
| @cesidbeograd / 2022 | [2022-04-04T21:17:13+02:00](https://x.com/cesidbeograd/status/1511060336501211147) | vote_share | official_result | Native-basis top-six MAE 0.048 pp; normalized 0.051 pp |
| @cesidbeograd / 2023 | [2023-12-18T00:41:33+01:00](https://x.com/cesidbeograd/status/1736532114634428580) | turnout | original_projection | No comparable scope benchmark; accuracy unavailable |
| @crtars / 2020 | [2020-06-22T12:53:02+02:00](https://x.com/crtars/status/1275018957607575552) | vote_share | original_projection | Native-basis top-six MAE 0.100 pp; normalized 0.092 pp |
| @crtars / 2020 | [2020-06-22T12:34:46+02:00](https://x.com/crtars/status/1275014360839135241) | invalid_ballot_share | original_projection | Supplementary; see detailed JSON |
| @crtars / 2020 | [2020-06-22T12:40:55+02:00](https://x.com/crtars/status/1275015905072816128) | turnout | original_projection | Supplementary; see detailed JSON |
| @crtars / 2022 | [2022-04-04T00:35:42+02:00](https://x.com/crtars/status/1510747898912415748) | vote_share | original_projection | Native-basis top-six MAE 0.340 pp; normalized 0.360 pp |
| @crtars / 2022 | [2022-04-04T00:35:42+02:00](https://x.com/crtars/status/1510747898912415748) | turnout | original_projection | No comparable scope benchmark; accuracy unavailable |
| @crtars / 2022 | [2022-04-04T00:35:42+02:00](https://x.com/crtars/status/1510747898912415748) | invalid_ballot_share | original_projection | Supplementary; see detailed JSON |
| @crtars / 2022 | [2022-04-04T15:28:01+02:00](https://x.com/crtars/status/1510972458236579840) | vote_share | original_projection | Native-basis top-six MAE 0.275 pp; normalized 0.273 pp |
| @crtars / 2022 | [2022-04-04T15:28:01+02:00](https://x.com/crtars/status/1510972458236579840) | turnout | original_projection | No comparable scope benchmark; accuracy unavailable |
| @crtars / 2022 | [2022-04-04T15:28:01+02:00](https://x.com/crtars/status/1510972458236579840) | invalid_ballot_share | original_projection | Supplementary; see detailed JSON |
| @crtars / 2023 | [2023-12-18T00:18:33+01:00](https://x.com/crtars/status/1736526322761883686) | vote_share | original_projection | Native-basis top-six MAE 0.183 pp; normalized 0.179 pp |
| @crtars / 2023 | [2023-12-18T00:18:33+01:00](https://x.com/crtars/status/1736526322761883686) | turnout | original_projection | No comparable scope benchmark; accuracy unavailable |
| @crtars / 2023 | [2023-12-18T00:18:33+01:00](https://x.com/crtars/status/1736526322761883686) | invalid_ballot_share | original_projection | Supplementary; see detailed JSON |
| @crtars / 2023 | [2023-12-18T13:49:50+01:00](https://x.com/crtars/status/1736730489866670440) | vote_share | original_projection | Native-basis top-six MAE 0.104 pp; normalized 0.116 pp |
| @crtars / 2023 | [2023-12-18T13:49:50+01:00](https://x.com/crtars/status/1736730489866670440) | turnout | original_projection | No comparable scope benchmark; accuracy unavailable |
| @crtars / 2023 | [2023-12-18T13:49:50+01:00](https://x.com/crtars/status/1736730489866670440) | invalid_ballot_share | original_projection | Supplementary; see detailed JSON |
| @crtars / 2023 | [2023-12-18T13:49:50+01:00](https://x.com/crtars/status/1736730489866670440) | seats | original_projection | 0 seats to reassign; supplementary |

## Claim notes

- 1274789282079703047:vote_share: Valid-vote basis inferred from complete 21-list chart summing to approximately 100%. Last post separately states 4% invalid ballots. Alternative denominator errors are retained.
- 1274798166576189443:vote_share: Valid-vote basis inferred from complete 21-list chart summing to approximately 100%. Last post separately states 4% invalid ballots. Alternative denominator errors are retained.
- 1274811761041051649:vote_share: Valid-vote basis inferred from complete 21-list chart summing to approximately 100%. Last post separately states 4% invalid ballots. Alternative denominator errors are retained.
- 1274817636006846465:vote_share: Valid-vote basis inferred from complete 21-list chart summing to approximately 100%. Last post separately states 4% invalid ballots. Alternative denominator errors are retained.
- 1274817636006846465:invalid_ballot_share: Text says invalid ballots 4%; denominator is assumed ballots cast.
- 1274810342326046721:turnout: Compare with matching territorial scope, not national turnout; earlier-year bars are historical context.
- 1510718307967582218:vote_share: Ballots-cast basis inferred from chart total below 100%; valid-normalized sensitivity also calculated.
- 1510729200650629126:vote_share: Ballots-cast basis inferred from chart total below 100%; valid-normalized sensitivity also calculated.
- 1736491315691446389:vote_share: Reused previously reviewed transcription; image hash rechecked. Caption/chart scope overrides misleading Belgrade hashtag.
- 1736496827044634778:seats: Reused previously reviewed transcription; image hash rechecked. Caption/chart scope overrides misleading Belgrade hashtag. Seat overlap is descriptive, not a reliability probability.
- 1736513641321546053:vote_share: Reused previously reviewed transcription; image hash rechecked. Caption/chart scope overrides misleading Belgrade hashtag.
- 1736514618996961555:seats: Reused previously reviewed transcription; image hash rechecked. Caption/chart scope overrides misleading Belgrade hashtag. Seat overlap is descriptive, not a reliability probability.
- 1274807242198585346:vote_share_bounds: Literal bounds remain unchanged; full national benchmark includes excluded territories and reruns. No fabricated midpoint estimate.
- 1274806574821842944:turnout_bounds: Previously labelled national; CRTA sample actually excludes Kosovo, abroad and prisons. Compare with matching territorial subtotal, with rerun caveat.
- 1274807584248209411:below_threshold: Threshold statement from CRTA own sample, not an independent point forecast; full final official national benchmark also contains excluded territories and reruns.
- 1736473053465313303:registered_voters: Known registration counts, not a preliminary-result forecast; excluded from forecast confidence.
- 1736505133297451187:winner: Text explicitly says SNS list received the most votes. Correct qualitative claim alone cannot establish numerical forecasting accuracy.
- 1736517035817886148:winner: Victory statement interpreted from party slogan and press-conference photos; no numerical margin and no explicit election level. Keep as contextual corroboration, outside numerical score.
- 1510758910382284805:vote_share: Complete national parliamentary chart. Ballots-cast basis inferred from displayed total below 100%; retain valid-vote normalization. Final-projection graphic repeats the same rounded percentages as the earlier 90%-sample chart; this is not independent evidence.
- 1510919362894565385:vote_share: Complete national parliamentary chart. Ballots-cast basis inferred from displayed total below 100%; retain valid-vote normalization. Final-projection graphic repeats the same rounded percentages as the earlier 90%-sample chart; this is not independent evidence.
- 1510920112391528448:turnout: 2022 turnout estimate. Reply 1510926464165855234 explicitly excludes Kosovo, prisons and diaspora; corresponding scoped official denominator has not been established, so no numerical error is assigned. Historical 2016/2017/2020 bars are context.
- 1511060336501211147:vote_share: Photograph of the official RIK preliminary table, processed 4 April 2022 20:29 local. Not an independent CeSID/Ipsos forecast and excluded from forecast selection/confidence. Published shares divide by ballots in processed boxes (3,668,149); comparison with final national totals is descriptive and includes incomplete count and later reruns.
- 1736532114634428580:turnout: Graphic projects 2023 turnout through 20:00 at 59.3%. Geographic exclusions are not specified in this saved post. Do not silently compare with national final turnout; historical bars are context.
- 1275018957607575552:vote_share: Composite of contiguous ranked panels posted at 12:34:46, 12:38:43 and 12:53:02 local; available only when the last panel was posted. First two panels alone are partial lists. Total party shares 96.14 plus invalid 3.85 approximately 100. Basis voters-who-turned-out inferred consistently with 2020 official table; ballots-cast sensitivity should also be retained.
- 1275014360839135241:invalid_ballot_share: Shown on every ranked panel; one copy retained. Denominator inferred.
- 1275015905072816128:turnout: Final turnout headline. Compare matching territorial scope where available; final official subset still includes reruns. Historical 2016 value and intraday series are not forecasts for this benchmark.
- 1510747898912415748:vote_share: Ballots-cast basis inferred from party total plus invalid shares; valid-normalized sensitivity retained. Graph labels determine parliamentary scope.
- 1510747898912415748:turnout: No official reference subtotal matching CRTA excluded territories is supplied for 2022; retain extraction and do not score against the broader national turnout.
- 1510747898912415748:invalid_ballot_share: Supplementary national-benchmark comparison only; denominator inferred and sample territory differs.
- 1510972458236579840:vote_share: Ballots-cast basis inferred from party total plus invalid shares; valid-normalized sensitivity retained. Graph labels determine parliamentary scope.
- 1510972458236579840:turnout: No official reference subtotal matching CRTA excluded territories is supplied for 2022; retain extraction and do not score against the broader national turnout.
- 1510972458236579840:invalid_ballot_share: Supplementary national-benchmark comparison only; denominator inferred and sample territory differs.
- 1736526322761883686:vote_share: Ballots-cast basis inferred from party total plus 2.8% invalid. Error labels below 0.1 retained as bounds, not as exact 0.1. This is CRTA own sample projection, not RIK republication.
- 1736526322761883686:turnout: No matching territorial subtotal in supplied 2023 official reference; retain extraction, do not score against broader national turnout.
- 1736526322761883686:invalid_ballot_share: Supplementary national-benchmark comparison; denominator inferred, geographic scope differs.
- 1736730489866670440:vote_share: Ballots-cast basis inferred from party total plus 2.8% invalid. Error labels below 0.1 retained as bounds, not as exact 0.1. This is CRTA own sample projection, not RIK republication.
- 1736730489866670440:turnout: No matching territorial subtotal in supplied 2023 official reference; retain extraction, do not score against broader national turnout.
- 1736730489866670440:invalid_ballot_share: Supplementary national-benchmark comparison; denominator inferred, geographic scope differs.
- 1736730489866670440:seats: Complete projected national allocation; dash in graphic means zero seats. This allocation sums to 250. Seat overlap is descriptive, not a reliability probability.

## Collection gaps

- @slobodaipravda / 2023: active-window search remains incomplete. Missing forecasts may reflect collection gaps.

## Sources and reproducibility

- 2020: `data/2020_official/G202019004.xlsx`. See official_reference.json for extraction details and source hashes.
- 2022: `data/2022_official/G202219002.xlsx`. See official_reference.json for extraction details and source hashes.
- 2023: `data/2023_official/G20246006.pdf`. See official_reference.json for extraction details and source hashes.
- [CRTA 2020 sampling scope](https://crta.rs/wp-content/uploads/2020/10/Parlamentarni-izbori-2020_Crta_Zavrsni-izvestaj.pdf): Kosovo voters, prisons and abroad excluded.
- [CRTA 2022 sampling scope](https://crta.rs/wp-content/uploads/2022/04/Preliminarni-izvestaj-o-izbornom-danu-2022.pdf): Kosovo voters, prisons and abroad excluded.
- [CRTA 2023 sampling scope](https://crta.rs/wp-content/uploads/2024/02/CRTA_Zavrsni-izborni-izvestaj-2023.pdf): Kosovo voters, prisons and abroad excluded.

Run `python .\evaluate_accounts.py` from the project root. It uses only reviewed local inputs, checks post/image/source hashes, validates composite availability against constituent post timestamps, and writes the executive JSON and detailed comparisons. New or changed evidence requires review; this program does not automatically transcribe new images or videos.

Full-party normalization corrects denominator differences but cannot correct geographic sample exclusions. A comparison with national final totals can include a benchmark-scope discrepancy; it is not automatically a pure forecasting error. See each claim’s notes.

## Limitations

- Only three historical election nights. Accounts with no saved forecasts are unassessed, not demonstrated inaccurate.
- API exhaustion only covers the current account query/window; deleted posts and external linked content remain absent. Unavailable videos are audited but not transcribed or assumed to contain no numerical claims.
- Missing cutoff data can reflect late publication or incomplete collection. Compare accounts only where year and cutoff match, and check collection coverage.
- Full-list normalization cannot be applied to a few selected parties. Bounds and partial vectors do not receive a comparable point-forecast score.
- Final official results include repeat voting and administrative corrections. Retrospective differences do not by themselves demonstrate a reporting mistake on election night.
- CRTA sample exclusions differ from the national benchmark. Latest CRTA 2022 chart also contains an ambiguous literal 0 for the Russian minority list; it is preserved rather than silently corrected.
- Updates on the same night are correlated. CeSID/Ipsos joint estimates form one source family, not two independent confirmations.
- Forecasts are rounded, mainly to 0.1 pp. Sampling design is unavailable, so no statistical confidence interval or calibrated probability is claimed.
- Final official counts are the requested benchmark; this does not assess electoral integrity or resolve reported irregularities.
- The fixed confidence weights and 2 pp scale express a conservative screening rule. Use underlying errors and evidence counts for decisions, not score alone.
