"""Reproduce the saved CeSID/Ipsos 2023 evaluation, entirely offline.

Run: python evaluate_2023.py
Requires pandas and pyarrow (already installed in this project's .venv).
Image values are reviewed transcriptions in analysis/2023/cesidbeograd/claims.json.
This script does not infer numbers from images, fetch posts, or read credentials.
"""

import hashlib
import json
import math
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "analysis" / "2023" / "cesidbeograd"
DATA = ROOT / "data" / "2023" / "cesidbeograd"
CET = timezone(timedelta(hours=1))  # All evaluated posts are in December 2023.


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def metrics(rows):
    errors = [r["signed_error"] for r in rows]
    return {
        "n": len(errors),
        "mae": sum(abs(e) for e in errors) / len(errors),
        "rmse": math.sqrt(sum(e * e for e in errors) / len(errors)),
        "max_absolute_error": max(abs(e) for e in errors),
    }


def comparison(key, estimate, actual):
    return {"party": key, "estimate": estimate, "actual": actual,
            "signed_error": estimate - actual, "absolute_error": abs(estimate - actual)}


def main():
    claims_path = OUT / "claims.json"
    reference_path = OUT / "rik_reference.json"
    parquet_path = ROOT / "election_master_baseline.parquet"
    claims = read_json(claims_path)
    reference = read_json(reference_path)
    parties = reference["parties"]
    groups = reference["parquet_groups"]
    primary = reference["primary_individual_parties"]
    df = pd.read_parquet(parquet_path)
    columns = [f"votes_2023_{key}" for key in groups]
    required = ["station_id", "reg_2023", "turnout_2023", "valid_2023"] + columns
    require(set(required) <= set(df.columns), "Required Parquet columns are missing.")
    require(not df[required].isna().any().any(), "Missing values in the baseline.")
    require(df.station_id.is_unique, "Duplicate station IDs in the baseline.")
    require((df[required] >= 0).all().all(), "Negative baseline counts.")
    require((df[columns].sum(axis=1) == df.valid_2023).all(), "Station party totals do not equal valid ballots.")
    require(((df.valid_2023 <= df.turnout_2023) & (df.turnout_2023 <= df.reg_2023)).all(), "Invalid station turnout ordering.")
    sums = {c: int(df[c].sum()) for c in required if c != "station_id"}
    checks = {
        "polling_stations": (len(df), reference["polling_stations"]),
        "registered_voters": (sums["reg_2023"], reference["registered_voters"]),
        "voters_who_turned_out": (sums["turnout_2023"], reference["voters_who_turned_out"]),
        "valid_ballots": (sums["valid_2023"], reference["valid_ballots"]),
    }
    members = [p for items in groups.values() for p in items]
    require(len(members) == len(set(members)) == len(parties) and set(members) == set(parties), "Party grouping must be a complete disjoint partition.")
    for key, members in groups.items():
        checks[key] = (sums[f"votes_2023_{key}"], sum(parties[p]["votes"] for p in members))
    for key, (actual, expected) in checks.items():
        require(actual == expected, f"Parquet does not reconcile with RIK: {key}.")
    require(sum(p["votes"] for p in parties.values()) == reference["valid_ballots"], "RIK party counts do not sum to valid ballots.")
    require(reference["valid_ballots"] + reference["invalid_ballots"] == reference["ballots_cast"], "RIK ballots-cast denominator does not reconcile.")
    require(sum(p["seats"] for p in parties.values()) == 250, "RIK seats do not total 250.")

    posts = {p["id"]: p for p in map(json.loads, (DATA / "posts.jsonl").read_text(encoding="utf-8").splitlines())}
    reviewed = claims["claims"] + claims["excluded_posts"]
    require(len({p["post_id"] for p in reviewed}) == len(reviewed), "Duplicate claim/exclusion records.")
    require({p["post_id"] for p in reviewed} == set(posts), "Saved posts changed; review newly fetched posts before rerunning.")
    for claim in reviewed:
        post = posts[claim["post_id"]]
        require(sha256(ROOT / claim["image"]) == claim["image_sha256"], "An image changed; review its transcription again.")
        require(Path(claim["image"]).name in [m.get("local_file") for m in post.get("media", [])], "Claim image is not attached to its stated post.")

    results = []
    for claim in claims["claims"]:
        values = claim["values"]
        require(set(values) == set(parties), "Each scored chart must contain all 18 lists.")
        require(all(isinstance(v, (int, float)) and math.isfinite(v) and v >= 0 for v in values.values()), "Invalid extracted values.")
        post = posts[claim["post_id"]]
        local = datetime.fromisoformat(post["created_at"].replace("Z", "+00:00")).astimezone(CET)
        result = {"post_id": post["id"], "post_url": post["post_url"],
                  "created_at_cet": local.isoformat(), "metric": claim["metric"],
                  "sample_processed_pct": claim["sample_processed_pct"], "image": claim["image"]}
        if claim["metric"] == "vote_share":
            denominator = reference["ballots_cast"]
            individual = [comparison(k, values[k], 100 * sums[f"votes_2023_{k}"] / denominator) for k in primary]
            grouped = [comparison(k, sum(values[p] for p in members), 100 * sums[f"votes_2023_{k}"] / denominator) for k, members in groups.items()]
            all_lists = [comparison(k, values[k], 100 * p["votes"] / denominator) for k, p in parties.items()]
            literal_parquet = [comparison(k, values[k], 100 * sums[f"votes_2023_{k}"] / sums["turnout_2023"]) for k in primary]
            normalized = [comparison(k, 100 * values[k] / sum(values.values()), 100 * sums[f"votes_2023_{k}"] / sums["valid_2023"]) for k in primary]
            result.update(unit="percentage_points", denominator=denominator,
                          displayed_party_share_sum=sum(values.values()),
                          primary_six=individual, metrics_primary_six=metrics(individual),
                          grouped_eight=grouped, metrics_grouped_eight=metrics(grouped),
                          all_eighteen=all_lists, metrics_all_eighteen=metrics(all_lists),
                          sensitivity={"literal_parquet_turnout_denominator": {"denominator": sums["turnout_2023"], "metrics_primary_six": metrics(literal_parquet)},
                                       "both_sides_normalized_to_valid_votes": {"metrics_primary_six": metrics(normalized)}})
        else:
            require(claim["metric"] == "seats", "Unknown claim metric.")
            require(all(int(v) == v for v in values.values()) and sum(values.values()) == 250, "Projected seats must be integers totaling 250.")
            rows = [comparison(k, values[k], p["seats"]) for k, p in parties.items()]
            l1 = sum(r["absolute_error"] for r in rows)
            result.update(unit="seats", all_eighteen=rows, metrics_all_eighteen=metrics(rows),
                          minimum_seats_to_reassign=l1 / 2,
                          seat_allocation_agreement_pct=100 * (1 - l1 / (2 * 250)),
                          exact_party_allocations=sum(r["absolute_error"] == 0 for r in rows),
                          parties_with_seats_match={k for k, v in values.items() if v > 0} == {k for k, p in parties.items() if p["seats"] > 0})
        results.append(result)

    checkpoints = []
    for path in sorted(DATA.glob("search_*.json")):
        state = read_json(path)
        checkpoints.append({"file": str(path.relative_to(ROOT)), "window": state.get("window"),
                            "search_exhausted": state.get("search_exhausted"), "has_next_token": bool(state.get("next_token")),
                            "returned_posts_total": state.get("returned_posts_total")})
    excluded = [{**c, "post_url": posts[c["post_id"]]["post_url"], "created_at": posts[c["post_id"]]["created_at"]} for c in claims["excluded_posts"]]
    output = {
        "model": {"type": "deterministic retrospective scoring, not a trained predictive model",
                  "official_share": "100 * national party votes / ballots_cast",
                  "signed_error": "published estimate - official share (percentage points)",
                  "mae": "mean(abs(signed_error))", "rmse": "sqrt(mean(signed_error**2))",
                  "primary_party_set": primary, "weighting": "equal weight per list within a snapshot; no pooling of correlated snapshots",
                  "seat_distance": "0.5 * sum(abs(projected_seats - official_seats))",
                  "seat_agreement": "100 * (1 - seat_distance / 250); descriptive allocation overlap, not a probability of reliability",
                  "share_denominator_assumption": "Charts do not name a denominator. Compare published shares to RIK ballots-cast shares; their displayed sums of 97.1 and 97.2 are consistent with inclusion of invalid ballots. Sensitivity metrics are also supplied."},
        "inputs_sha256": {"parquet": sha256(parquet_path), "claims": sha256(claims_path), "rik_reference": sha256(reference_path), "posts": sha256(DATA / "posts.jsonl")},
        "baseline_audit": {"status": "passed", "parquet_totals": sums, "reconciliation": {k: {"parquet": a, "rik": b} for k, (a, b) in checks.items()}, "ballots_cast_from_rik": reference["ballots_cast"]},
        "source_url": reference["source_url"], "collection": checkpoints,
        "scored_posts": results, "excluded_posts": excluded,
        "limitations": ["Only two national vote-share snapshots and two linked seat snapshots from one joint CeSID/Ipsos source and one election.",
                        "The saved fetch is partial; earlier posts may remain. Earliest saved is not necessarily first published.",
                        "Values were manually read from images; this script checks input hashes and recomputes scores, not OCR.",
                        "Vote estimates are displayed to 0.1 percentage point. No sample size/design information supports confidence intervals.",
                        "Belgrade city assembly results require a separate benchmark; national votes cast in Belgrade are not that benchmark.",
                        "Final results include repeat voting. These are retrospective final-outcome errors, not errors against contemporaneous sample totals.",
                        "No inference of publication latency or independence from RIK is made from timestamp_cet or speed_percentile in the Parquet."]}
    (OUT / "evaluation.json").write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(output, reference, claims)
    print("Baseline reconciled with RIK; 4 national posts scored; 3 city posts excluded.")
    for r in results:
        score = f"MAE6={r['metrics_primary_six']['mae']:.6f} pp" if r["metric"] == "vote_share" else f"seats to reassign={r['minimum_seats_to_reassign']:g}"
        print(r["created_at_cet"], r["metric"], score)
    print("Report:", OUT / "report.md")


def write_report(output, reference, claims):
    votes = [r for r in output["scored_posts"] if r["metric"] == "vote_share"]
    seats = [r for r in output["scored_posts"] if r["metric"] == "seats"]
    first, last = votes
    lines = ["# CeSID/Ipsos: 2023 parliamentary estimate accuracy", "",
             "Evaluated from the seven locally fetched @CeSIDBeograd posts. Four contain national estimates, forming two successive sample updates; three concern the separate Belgrade city election and are excluded. All times below are Belgrade CET on 17 December 2023.", "",
             f"The six individually stored lists have mean absolute vote-share error **{first['metrics_primary_six']['mae']:.3f} pp** in the first saved update and **{last['metrics_primary_six']['mae']:.3f} pp** in the later one. The later seat allocation needs **one seat reassigned** to match the final result. This supports good accuracy in this limited sample, not a calibrated account reliability score.", "",
             "## Benchmark audit", "",
             "The Parquet has 8,273 unique stations. Every station's eight vote groups sum to its valid-ballot count, counts are nonnegative, and no required counts are missing. National sums reconcile exactly with the cited RIK report. This validates the totals used here; it does not independently validate every station's data or timing features.", "",
             f"RIK source: [51st session, final national results adopted 12 January 2024]({reference['source_url']}).", "",
             "The file's `turnout_2023` sums to 3,820,746 voters who turned out. RIK separately records **3,815,007 ballots cast**, equal to 3,710,978 valid plus 104,029 invalid ballots. Use ballots cast for the published RIK percentage convention. The Parquet lacks the invalid-ballot total and seat columns, so those come from the cited RIK reference. Party vote numerators for the six main lists and eight groups come directly from the Parquet.", "",
             "The charts do not explicitly state their percentage denominator. Their 18 entries sum to 97.1% and 97.2%, which supports comparing them with shares including invalid ballots, rather than treating the entries as percentages of valid votes. This remains an assumption; sensitivity results appear below.", "",
             "## Observations and scores", "",
             "| Post time CET | Metric | Processed sample | Main-list MAE | Main-list RMSE | Maximum main-list error |",
             "| --- | --- | ---: | ---: | ---: | ---: |"]
    for r in votes:
        m = r["metrics_primary_six"]
        lines.append(f"| [{r['created_at_cet'][11:19]}]({r['post_url']}) | Vote share | {r['sample_processed_pct']}% | {m['mae']:.3f} pp | {m['rmse']:.3f} pp | {m['max_absolute_error']:.3f} pp |")
    lines += ["", "The primary set is SNS, SPN, SPS, MI, NADA and Zavetnici-Dveri: exactly the six lists stored individually in the Parquet. Equal weight is given to each. Coverage is the share of CeSID/Ipsos's sample processed, not the share of all Serbian votes counted and not a score weight.", "",
              "| List | Final RIK share | 21:59 estimate | Error | 23:28 estimate | Error |",
              "| --- | ---: | ---: | ---: | ---: | ---: |"]
    for a, b in zip(first["primary_six"], last["primary_six"]):
        lines.append(f"| {a['party']} | {a['actual']:.4f}% | {a['estimate']:.1f}% | {a['signed_error']:+.3f} pp | {b['estimate']:.1f}% | {b['signed_error']:+.3f} pp |")
    lines += ["", "Later SPN, SPS and NADA estimates improve, while SNS moves farther below its final share. MI and Zavetnici-Dveri are unchanged. A later update is therefore better on average without being better for every party.", "",
              "## Scoring model", "", "```text",
              "official_share_i = 100 * sum(station_votes_i) / 3,815,007",
              "error_i = published_share_i - official_share_i",
              "MAE = sum(abs(error_i)) / number_of_lists",
              "RMSE = sqrt(sum(error_i ** 2) / number_of_lists)",
              "seat_distance = sum(abs(projected_seats_i - final_seats_i)) / 2",
              "seat_agreement = 100 * (1 - seat_distance / 250)", "```", "",
              f"Worked example, latest SNS: `100 * 1,783,701 / 3,815,007 = {last['primary_six'][0]['actual']:.6f}%`; error is `46.2 - {last['primary_six'][0]['actual']:.6f} = {last['primary_six'][0]['signed_error']:.6f} pp`. Absolute error is 0.554855 pp. Average the six absolute errors to obtain 0.153735 pp. Computation uses unrounded official shares.", "",
              "Percentage points measure the difference between percentages; they are not relative percentage error. Lower MAE/RMSE is better. There is no arbitrary `100 - MAE` reliability percentage, no trained prediction model, and no pooling of the two correlated updates as independent evidence.", "",
              "## Seat projections", "",
              "| Post time CET | Processed sample | Seats needing reassignment | Allocation agreement | Exact list allocations |",
              "| --- | ---: | ---: | ---: | ---: |"]
    for r in seats:
        lines.append(f"| [{r['created_at_cet'][11:19]}]({r['post_url']}) | {r['sample_processed_pct']}% | {r['minimum_seats_to_reassign']:g} / 250 | {r['seat_allocation_agreement_pct']:.1f}% | {r['exact_party_allocations']} / 18 |")
    lines += ["", "At 22:21 the discrepancies are SPN 63 versus 65, SPS 19 versus 18, and SPP/DSHV 3 versus 2. At 23:32 only SNS 128 versus 129 and SPP/DSHV 3 versus 2 differ. Both projections total 250 and identify the same ten seat-winning lists as the final result. Allocation agreement describes seat overlap, not the probability this account will be accurate next time.", "",
              "## Grouping and denominator sensitivity", "",
              "| Measure | 72.6% update | 88.4% update |",
              "| --- | ---: | ---: |"]
    measures = [("Primary six, RIK ballots-cast denominator", lambda r: r["metrics_primary_six"]["mae"]),
                ("Eight Parquet groups, RIK denominator", lambda r: r["metrics_grouped_eight"]["mae"]),
                ("All 18 lists, supplemental RIK breakdown", lambda r: r["metrics_all_eighteen"]["mae"]),
                ("Six lists, literal Parquet turnout denominator", lambda r: r["sensitivity"]["literal_parquet_turnout_denominator"]["metrics_primary_six"]["mae"]),
                ("Six lists, both sides normalized to valid votes", lambda r: r["sensitivity"]["both_sides_normalized_to_valid_votes"]["metrics_primary_six"]["mae"])]
    for label, get in measures:
        lines.append(f"| {label} | {get(first):.3f} pp | {get(last):.3f} pp |")
    lines += ["", "All rows are MAE. The 18-list result includes many small parties and is not directly comparable to the six-list headline. Eight-group results can hide offsetting errors among grouped lists. For valid-vote sensitivity, each chart's shares are divided by the sum of all 18 displayed shares, while official counts are divided by valid ballots.", "",
              "`MANJINE` combines SVM, SPP/DSHV, SDA, PDD, Russian Party, Peace and Tolerance, and ADA. `OSTALI` combines SRS, DJB/SDS, Narodna stranka, LDP and Srbija na Zapadu. Each mapping reconciles exactly with its Parquet column. Full per-list and per-group calculations are in `evaluation.json`.", "",
              "## Excluded observations and limits", ""]
    for r in output["excluded_posts"]:
        local = datetime.fromisoformat(r["created_at"].replace("Z", "+00:00")).astimezone(CET)
        lines.append(f"- [{local.strftime('%H:%M:%S')}]({r['post_url']}): Belgrade city assembly {r['metric']}, {r['sample_processed_pct']}% processed sample. Excluded because the national Parquet cannot benchmark this different election.")
    lines += ["", "The national 88.4% posts use `#izboribeograd` despite their national captions and chart titles. Scope was decided from the actual claim and image, not the hashtag.", ""]
    lines += ["- " + item for item in output["limitations"]]
    lines += ["", "The latest saved national estimate arrives at 23:28 CET (3 hours 28 minutes after scheduled closing); its seat projection follows at 23:32. The first saved estimate at 21:59 is not proven to be the account's earliest estimate. The checkpoint still has a next-page cursor. No extra X calls were made for this evaluation.", "",
              "## Reproduce and audit", "", "From the project root, with the existing virtual environment active:", "", "```powershell", "python .\\evaluate_2023.py", "```", "",
              "Inputs: the original Parquet, saved `posts.jsonl`, local images, `claims.json` (reviewed image transcriptions) and `rik_reference.json` (supplemental official data and grouping). Input/image SHA-256 hashes are recorded and checked. Outputs: this report and `evaluation.json`. The original Parquet, fetched posts, images and collector checkpoints are unchanged.", "",
              "To extend the account evaluation, collect and review the remaining posts, then repeat this method across elections at comparable times after closing. Keep source attribution: these posts are joint CeSID/Ipsos estimates, not independent observations from two accounts.", ""]
    (OUT / "report.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
