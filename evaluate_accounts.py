r"""Offline evaluation of reviewed saved election posts against official totals.

Run: python .\evaluate_accounts.py
No credentials, network access or third-party packages are needed. New posts,
changed source files and changed images require review before recalculation.
"""
import hashlib
import json
import math
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parent
SUPPORT = ROOT / 'analysis/accounts'
YEARS = ('2020', '2022', '2023')
ERROR_SCALE_PP = 2.0
PARTIAL_WEIGHT = 0.75
PRIOR_YEAR_WEIGHT = 1.0
CUTOFFS = (('election_day_22_00', 0, 22), ('next_day_00_00', 1, 0),
           ('next_day_02_00', 1, 2), ('end_next_day_00_00', 2, 0))


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def comparison(key, estimate, actual):
    error = estimate - actual
    return {'party': key, 'estimate': estimate, 'official': actual,
            'signed_error': error, 'absolute_error': abs(error)}


def metrics(rows):
    """Same transparent error measures as evaluate_2023.py, without pandas."""
    require(bool(rows), 'Cannot calculate accuracy from zero observations.')
    errors = [r['signed_error'] for r in rows]
    return {'n': len(errors), 'mae_pp': mean(abs(x) for x in errors),
            'rmse_pp': math.sqrt(mean(x*x for x in errors)),
            'max_absolute_error_pp': max(abs(x) for x in errors)}


def check_bound(actual, lower, upper, lower_inclusive=True):
    covered = lower is None or (actual >= lower if lower_inclusive else actual > lower)
    covered = covered and (upper is None or actual <= upper)
    return {'official': actual, 'lower': lower, 'upper': upper,
            'lower_inclusive': lower_inclusive, 'contains_official': covered,
            'distance_outside_pp': max(0, lower-actual if lower is not None else 0,
                                       actual-upper if upper is not None else 0),
            'width_pp': upper-lower if lower is not None and upper is not None else None}


def score_claim(claim, reference):
    kind, values = claim['kind'], claim['values']
    result = dict(claim)
    parties = reference['parties']
    if kind == 'vote_share_partial':
        require(bool(values) and set(values) < set(parties), 'Partial vector must contain a strict subset of known lists.')
        rows = [comparison(k, v, 100*parties[k]['votes']/reference[claim['basis']]) for k,v in values.items()]
        result.update(unit='percentage_points', reported_lists=rows, reported_lists_metrics=metrics(rows),
                      missing_lists=sorted(set(parties)-set(values)), top_six_metrics=None,
                      normalized_valid_votes=None, confidence_eligible=False,
                      evaluation_note='Incomplete vector: only named lists are checked. No full-vector normalization or comparable top-six score.')
    elif kind == 'vote_share':
        require(set(values) == set(parties), 'Incomplete or mismatched list vector: '+claim['claim_id'])
        require(all(isinstance(v, (int,float)) and math.isfinite(v) and 0 <= v <= 100 for v in values.values()), 'Invalid percentage.')
        denominator = reference[claim['basis']]
        rows = [comparison(k, v, 100*parties[k]['votes']/denominator) for k,v in values.items()]
        top6 = [r for r in rows if r['party'] in reference['top_six_lists']]
        total = sum(values.values())
        require(90 <= total <= 101, 'Unexpected complete-chart sum; review percentage basis.')
        normalized = [comparison(k, 100*v/total, 100*parties[k]['votes']/reference['valid_ballots']) for k,v in values.items()]
        normalized6 = [r for r in normalized if r['party'] in reference['top_six_lists']]
        alternate = {}
        for basis in ('valid_ballots','ballots_cast','voters_who_turned_out'):
            alt = [comparison(k, values[k], 100*parties[k]['votes']/reference[basis]) for k in reference['top_six_lists']]
            alternate[basis] = metrics(alt)
        result.update(unit='percentage_points', denominator=denominator, chart_sum_pct=total,
                      all_lists=rows, all_lists_metrics=metrics(rows), top_six_lists=reference['top_six_lists'],
                      top_six_metrics=metrics(top6),
                      normalized_valid_votes={'formula':'estimate = 100 * displayed_share / sum(all displayed shares); actual = 100 * votes / valid_ballots',
                                              'all_lists':normalized,'top_six_metrics':metrics(normalized6)},
                      sensitivity_raw_chart_against_other_denominators=alternate)
    elif kind == 'seats':
        require(set(values) == set(parties), 'Incomplete seat allocation.')
        require(all(isinstance(v, int) and v >= 0 for v in values.values()) and sum(values.values()) == 250, 'Seat projection must total 250.')
        rows = [comparison(k, v, parties[k]['seats']) for k,v in values.items()]
        distance = sum(r['absolute_error'] for r in rows)/2
        result.update(unit='seats', all_lists=rows, minimum_seats_to_reassign=distance,
                      allocation_agreement_pct=100*(1-distance/250),
                      note=claim['note']+' Seat overlap is descriptive, not a reliability probability.')
    elif kind == 'vote_share_bounds':
        rows=[]
        for k,v in values.items():
            rows.append({'party':k, **check_bound(100*parties[k]['votes']/reference[claim['basis']], **v)})
        valid = [{'party':k, **check_bound(100*parties[k]['votes']/reference['valid_ballots'], **v)} for k,v in values.items()]
        result.update(unit='percentage_points', bounds=rows, tested_bounds=len(rows),
                      bounds_containing_final=sum(r['contains_official'] for r in rows),
                      mean_distance_outside_pp=mean(r['distance_outside_pp'] for r in rows),
                      valid_vote_basis_sensitivity=valid, point_estimate_mae_pp=None)
    elif kind == 'turnout':
        scope=reference.get('turnout_scope_without_kosovo_prisons_abroad')
        if claim.get('comparable') is False or not scope:
            result.update(unit='percentage_points', comparison=None, evaluation_status='not_comparable',
                          evaluation_note='No official turnout benchmark with the same stated population scope.')
        else:
            actual=100*scope['voters_who_turned_out']/scope['registered_voters']
            result.update(unit='percentage_points', scope_reference=scope,
                          comparison=comparison('turnout',values['turnout_pct'],actual))
    elif kind == 'turnout_bounds':
        actual=100*reference['voters_who_turned_out']/reference['registered_voters']
        result.update(unit='percentage_points', comparison=check_bound(actual, **values))
    elif kind == 'invalid_ballot_share':
        actual=100*reference['invalid_ballots']/reference['ballots_cast']
        result.update(unit='percentage_points',comparison=comparison('invalid_ballots',values['invalid_pct'],actual))
    elif kind == 'below_threshold':
        checks=[{'party':k,'official_share_pct':100*parties[k]['votes']/reference['voters_who_turned_out'],
                 'below_threshold':100*parties[k]['votes']/reference['voters_who_turned_out'] < values['threshold_pct']} for k in values['lists']]
        result.update(checks=checks,all_consistent=all(r['below_threshold'] for r in checks))
    elif kind == 'winner':
        winner=max(parties,key=lambda k:parties[k]['votes'])
        result.update(official_winner=winner,consistent=winner==values['party'],
                      comparison_scope='context_only' if claim.get('scope_inferred') else 'national_parliament')
    elif kind != 'registered_voters':
        raise ValueError('Unknown claim kind: '+kind)
    return result


def confidence(evidence):
    """A deliberately uncalibrated support score, not a probability."""
    effective_years=sum(e['weight'] for e in evidence)
    if not effective_years:
        return {'score':1, 'status':'insufficient_quantitative_evidence', 'effective_election_years':0,
                'weighted_error_pp':None, 'quality_factor':None,
                'interpretation':'1 is the floor for no eligible original full-list parliamentary percentage forecasts at the cutoffs; it does not mean 1% accuracy or dishonesty.'}
    error=sum(e['error_pp']*e['weight'] for e in evidence)/effective_years
    quality=max(0,1-error/ERROR_SCALE_PP)
    shrink=effective_years/(effective_years+PRIOR_YEAR_WEIGHT)
    score=max(1,min(100,int(math.floor(100*quality*shrink+.5))))
    return {'score':score,'status':'provisional_evidence_score','effective_election_years':effective_years,
            'weighted_error_pp':error,'quality_factor':quality,'evidence_factor':shrink,
            'interpretation':'Coverage-dependent support for original numerical parliamentary projections. Not calibrated, not an account-wide trust rating, and not a head-to-head ranking when accounts cover different years or cutoffs.'}


def validate_inputs(review, refs):
    actual={p.relative_to(ROOT).as_posix() for y in YEARS for p in (ROOT/'data'/y).glob('*/posts.jsonl')}
    require(actual==set(review['input_posts_sha256']), 'Account/year files changed. Review new data before evaluation.')
    posts={}
    for filename,expected in review['input_posts_sha256'].items():
        path=ROOT/filename
        require(sha256(path)==expected, 'Posts changed: '+filename+'. Review new or changed posts before evaluation.')
        for line in path.read_text(encoding='utf-8').splitlines():
            p=json.loads(line)
            require(p['id'] not in posts, 'Duplicate saved post ID.')
            posts[p['id']]=p
    require(len(review['records'])==len(posts) and {r['post_id'] for r in review['records']}==set(posts), 'Every post needs exactly one review disposition.')
    for record in review['records']:
        p=posts[record['post_id']]
        require(record['text']==p.get('full_text',p['text']), 'Reviewed text mismatch.')
        photo_media=[m for m in p.get('media',[]) if m.get('type')=='photo']
        other_media=[m for m in p.get('media',[]) if m.get('type')!='photo']
        require(len(record['images'])==len(photo_media), 'Image review missing.')
        require({(m.get('type'),m.get('media_key')) for m in record.get('unreviewed_media',[])} ==
                {(m.get('type'),m.get('media_key')) for m in other_media}, 'Unreviewed video/other attachment audit missing.')
        for img in record['images']:
            path=ROOT/img['file']
            require(path.is_file() and sha256(path)==img['sha256'], 'Image changed or missing: '+img['file'])
            require(path.name in {m.get('local_file') for m in photo_media}, 'Image is not attached to its stated post.')
    for year,ref in refs.items():
        require(sha256(ROOT/ref['source']['file'])==ref['source']['sha256'],'Official source changed: '+year)
        require(sum(p['votes'] for p in ref['parties'].values())==ref['valid_ballots'],'Votes do not reconcile: '+year)
        require(ref['valid_ballots']+ref['invalid_ballots']==ref['ballots_cast'],'Ballots do not reconcile: '+year)
    require(len({c['claim_id'] for c in review['claims']})==len(review['claims']), 'Duplicate claim ID.')
    records={r['post_id']:r for r in review['records']}
    for claim in review['claims']:
        require(claim['post_id'] in records, 'Claim refers to an unreviewed post.')
        record=records[claim['post_id']]
        require(claim['account']==record['account'] and claim['year']==record['year'],
                'Claim account/year does not match the reviewed source.')
        sources=claim.get('source_post_ids',[claim['post_id']])
        require(bool(sources) and claim['post_id'] in sources and len(sources)==len(set(sources)), 'Invalid constituent post IDs.')
        for source_id in sources:
            require(source_id in records, 'Unreviewed composite source post.')
            require(records[source_id]['account']==claim['account'] and records[source_id]['year']==claim['year'],
                    'Composite claim mixes accounts or elections.')
        available=max(parse_time(posts[source_id]['created_at']) for source_id in sources)
        require(parse_time(posts[claim['post_id']]['created_at'])==available, 'Composite claim post_id must be its latest constituent.')
        if claim.get('available_at'):
            require(parse_time(claim['available_at'])==available, 'Claim availability disagrees with original post timestamps.')
    return posts


def parse_time(value):
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    require(parsed.tzinfo is not None, 'A timestamp must include a UTC offset.')
    return parsed


def parse_window(window):
    start,end=map(parse_time,window.split('/'))
    require(end>start, 'Window end must follow its start.')
    return start,end


def local_time(created_at, year, window=None):
    # These elections do not span a DST transition. Use the saved offset, not
    # the computer's timezone or an assumption that all years use UTC+1.
    window=window or read(ROOT/'election_windows.json')['election'+str(year)]
    start,_=parse_window(window)
    return parse_time(created_at).astimezone(start.tzinfo).isoformat()


def cutoff_schedule(window):
    start,end=parse_window(window)
    election_midnight=start.replace(hour=0,minute=0,second=0,microsecond=0)
    result=[]
    for key,days,hour in CUTOFFS:
        cutoff=election_midnight+timedelta(days=days,hours=hour)
        require(start<=cutoff<=end, 'Configured collection window does not contain all four cutoffs.')
        result.append({'key':key,'at_belgrade':cutoff.isoformat(),
                       'at_utc':cutoff.astimezone(timezone.utc).isoformat(),
                       'collection_end_exclusive':cutoff==end})
    return result


def matched_cutoffs(results, window):
    """Latest eligible information actually available by each common deadline."""
    start,end=parse_window(window)
    eligible=[r for r in results if r['kind']=='vote_share' and r.get('source_role')=='original_projection'
              and start<=parse_time(r.get('available_at_belgrade',r['created_at_belgrade']))<end]
    slots={}
    previous=None
    for spec in cutoff_schedule(window):
        cutoff=parse_time(spec['at_belgrade'])
        available=[r for r in eligible if parse_time(r.get('available_at_belgrade',r['created_at_belgrade']))<=cutoff]
        selected=max(available,key=lambda r:(parse_time(r.get('available_at_belgrade',r['created_at_belgrade'])),r['claim_id'])) if available else None
        slot={**spec,'status':'available' if selected else 'no_eligible_forecast_by_cutoff',
              'forecast':None,'normalized_top_six_mae_pp':None,'age_minutes':None,
              'reused_from_previous_cutoff':False}
        if selected:
            available_at=selected.get('available_at_belgrade',selected['created_at_belgrade'])
            slot.update(forecast=short_snapshot(selected),
                        normalized_top_six_mae_pp=selected['normalized_valid_votes']['top_six_metrics']['mae_pp'],
                        age_minutes=(cutoff-parse_time(available_at)).total_seconds()/60,
                        reused_from_previous_cutoff=previous==selected['claim_id'])
            previous=selected['claim_id']
        slots[spec['key']]=slot
    return slots


def cutoff_evidence(year, slots, complete):
    available=[s for s in slots.values() if s['forecast'] is not None]
    if not available:
        return None
    coverage=len(available)/len(slots)
    return {'year':year,'type':'original_full_list_forecasts_at_matched_cutoffs',
            'weight':coverage*(1 if complete else PARTIAL_WEIGHT),
            'error_pp':mean(s['normalized_top_six_mae_pp'] for s in available),
            'available_cutoffs':len(available),'requested_cutoffs':len(slots),'cutoff_coverage_fraction':coverage,
            'distinct_forecast_claims':len({s['forecast']['claim_id'] for s in available}),
            'collection_multiplier':1 if complete else PARTIAL_WEIGHT,
            'available_cutoff_keys':[s['key'] for s in available]}


def collection_coverage(states, account, window):
    """Exhausted searches with the current query must cover the active interval.

    Old partial checkpoints do not invalidate a newer exhausted search. Separate
    exhausted adjacent intervals can cover the active interval without refetching.
    """
    start,end=parse_window(window)
    query=f'from:{account.lower()} -is:retweet'
    intervals=[]
    details=[]
    for state in states:
        item=dict(state)
        params=state.get('params',{})
        observed=' '.join(str(params.get('query',state.get('query',''))).lower().split())
        matching_query=observed==query
        interval=None
        try:
            interval=(parse_time(params['start_time']),parse_time(params['end_time'])) if params.get('start_time') and params.get('end_time') else parse_window(state['window'])
            require(interval[1]>interval[0], 'Empty search interval.')
            if state.get('window'):
                require(interval==parse_window(state['window']), 'Checkpoint window and API parameters disagree.')
        except (ValueError,KeyError,TypeError):
            interval=None
        overlaps=bool(interval and interval[0]<end and interval[1]>start)
        contributes=bool(matching_query and overlaps and state.get('search_exhausted',False))
        item.update(matches_active_query=matching_query,overlaps_active_window=overlaps,
                    contributes_exhausted_coverage=contributes)
        details.append(item)
        if contributes:
            intervals.append((max(start,interval[0]),min(end,interval[1])))
    cursor=start
    gaps=[]
    for left,right in sorted(intervals):
        if left>cursor:
            gaps.append((cursor,left))
        cursor=max(cursor,right)
    if cursor<end:
        gaps.append((cursor,end))
    missing_seconds=sum((b-a).total_seconds() for a,b in gaps)
    return {'window':window,'query':query,'search_exhausted':not gaps,
            'exhausted_coverage_fraction':1-missing_seconds/(end-start).total_seconds(),
            'uncovered_intervals':[f'{a.isoformat()}/{b.isoformat()}' for a,b in gaps],
            'checkpoints':details}


def short_snapshot(r):
    result={k:r.get(k) for k in ('claim_id','post_id','source_post_ids','post_url','created_at_belgrade',
            'available_at_belgrade','source_role','source_family','sample_processed_pct','chart_sum_pct',
            'basis','basis_explicit','all_lists_metrics','top_six_metrics')}
    result['normalized_top_six_metrics']=r['normalized_valid_votes']['top_six_metrics']
    return result


def build():
    review=read(SUPPORT/'reviewed_claims.json')
    refs=read(SUPPORT/'official_reference.json')
    windows=read(ROOT/'election_windows.json')
    posts=validate_inputs(review,refs)
    scored=[]
    for c in review['claims']:
        r=score_claim(c,refs[c['year']])
        source_ids=c.get('source_post_ids',[c['post_id']])
        available=max(parse_time(posts[source_id]['created_at']) for source_id in source_ids)
        r.update(post_url=posts[c['post_id']]['post_url'],source_post_ids=source_ids,
                 created_at_belgrade=local_time(posts[c['post_id']]['created_at'],c['year'],windows['election'+c['year']]),
                 available_at_belgrade=local_time(available.isoformat(),c['year'],windows['election'+c['year']]))
        if c['kind']=='registered_voters':
            r['checks']={y:{'estimate':n,'official':refs[y]['registered_voters'],'difference':n-refs[y]['registered_voters']} for y,n in c['values'].items()}
        scored.append(r)
    accounts=[]
    checkpoint_hashes={}
    for account in sorted({Path(p).parent.name for p in review['input_posts_sha256']}):
        year_results={}
        evidence=[]
        for year in YEARS:
            window=windows['election'+year]
            records=[r for r in review['records'] if r['account']==account and r['year']==year]
            results=sorted([r for r in scored if r['account']==account and r['year']==year],key=lambda r:r['created_at_belgrade'])
            states=[]
            for path in sorted((ROOT/'data'/year/account).glob('search_*.json')):
                state=read(path)
                checkpoint_hashes[path.relative_to(ROOT).as_posix()]=sha256(path)
                states.append({'file':path.relative_to(ROOT).as_posix(),'window':state.get('window'),
                               'query':state.get('query'),'search_exhausted':state.get('search_exhausted',False),
                               'params':state.get('params',{}),
                               'has_next_token':bool(state.get('next_token'))})
            coverage=collection_coverage(states,account,window)
            complete=coverage['search_exhausted']
            start,end=parse_window(window)
            active_results=[r for r in results if start<=parse_time(r['available_at_belgrade'])<end]
            points=[r for r in active_results if r['kind']=='vote_share' and r.get('source_role')=='original_projection']
            other_points=[r for r in active_results if r['kind']=='vote_share' and r.get('source_role')!='original_projection']
            partial_points=[r for r in active_results if r['kind']=='vote_share_partial']
            bounds=[r for r in results if r['kind']=='vote_share_bounds']
            seats=[r for r in results if r['kind']=='seats']
            supplementary=[r for r in results if r['kind'] not in ('vote_share','vote_share_partial','vote_share_bounds','seats')]
            slots=matched_cutoffs(active_results,window)
            contribution=cutoff_evidence(year,slots,complete)
            yr={'saved_posts':len(records),'reviewed_photos':sum(len(r['images']) for r in records),
                'unreviewed_non_photo_attachments':sum(len(r.get('unreviewed_media',[])) for r in records),
                'collection_exhausted':complete,'active_collection':coverage,'collection':coverage['checkpoints'],
                'status':'point_estimates_evaluated' if points else 'bounds_only_evaluated' if bounds else 'no_saved_posts' if not records else 'no_quantitative_result_forecast',
                'point_forecast_snapshots':len(points),'bounds_snapshots':len(bounds),'seat_snapshots':len(seats),
                'cutoffs':slots,
                'cutoff_coverage':{'available':sum(s['forecast'] is not None for s in slots.values()),'requested':len(slots),
                                   'missing':[key for key,s in slots.items() if s['forecast'] is None]},
                'mean_cutoff_normalized_top_six_mae_pp':contribution['error_pp'] if contribution else None,
                'top_six_lists':refs[year]['top_six_lists'],
                'latest_forecast':short_snapshot(points[-1]) if points else None,
                'first_saved_forecast':short_snapshot(points[0]) if points else None,
                'mean_snapshot_top_six_mae_pp':mean(r['top_six_metrics']['mae_pp'] for r in points) if points else None,
                'mean_snapshot_valid_normalized_top_six_mae_pp':mean(r['normalized_valid_votes']['top_six_metrics']['mae_pp'] for r in points) if points else None,
                'quoted_or_official_full_charts':[short_snapshot(r) for r in other_points],
                'partial_point_checks':partial_points,
                'bounds_checks':[{'post_id':r['post_id'],'tested_bounds':r['tested_bounds'],'bounds_containing_final':r['bounds_containing_final'],
                                 'mean_distance_outside_pp':r['mean_distance_outside_pp'],'point_estimate_mae_pp':None} for r in bounds],
                'seat_checks':[{'post_id':r['post_id'],'minimum_seats_to_reassign':r['minimum_seats_to_reassign'],
                               'allocation_agreement_pct':r['allocation_agreement_pct']} for r in seats],
                'supplementary_checks':supplementary,
                'review_dispositions':dict(Counter(r['category'] for r in records)),
                'notes':[]}
            if not complete:
                yr['notes'].append('Exhausted searches do not cover the full current query/window. Missing early estimates may be collection gaps; first saved is not necessarily first published.')
            if not points:
                yr['notes'].append('No eligible original full-list parliamentary vote-share forecast in this saved window; comparable point accuracy is unavailable, not zero. Bounds, partial vectors and official/quoted charts remain separate.')
            if year=='2020' and account=='cesidbeograd':
                yr['notes'].append('Valid-vote percentage basis inferred from chart totals near 100. Turnout benchmark separately matches the explicit exclusions of Kosovo, prisons and abroad.')
            if contribution:
                evidence.append(contribution)
            year_results[year]=yr
        components=confidence(evidence)
        if evidence:
            decision='provisional_numerical_source'
            reason='Original full-list estimates are available at some common cutoffs. Compare only matching year/cutoff cells; retain coverage, publication time and source family.'
        elif any(y['bounds_checks'] or y['partial_point_checks'] for y in year_results.values()):
            decision='retain_for_further_collection'
            reason='Saved bounds or partial vectors are testable, but do not establish comparable full-list point-forecast accuracy.'
        else:
            decision='insufficient_evidence_for_numerical_use'
            reason='Saved material cannot establish numerical forecasting accuracy. This is not a judgment about the account outside the collected windows.'
        accounts.append({'account':account,'years':year_results,'confidence_score':components.pop('score'),
                         'confidence_components':{**components,'year_contributions':evidence},'decision':decision,'decision_reason':reason})
    total_photos=sum(len(r['images']) for r in review['records'])
    methodology={
        'scope':'National parliamentary-result estimates in active election_windows.json: election day 20:00 through the end of the following day (28 hours), Europe/Belgrade.',
        'time_cutoffs':{'timezone':'Europe/Belgrade','keys':[c[0] for c in CUTOFFS],
                        'rule':'Four cutoffs: election day 22:00, next day 00:00, next day 02:00, and midnight ending the next day. There is no 06:00 cutoff.',
                        'selection':'Use the latest original full-list projection available at or before the cutoff, within the active collection interval. A post exactly at the final collection end is excluded. Composite charts become available only at the latest constituent post timestamp.',
                        'carry_forward':'An earlier forecast remains the latest known forecast until updated; report its age and repeated selection. Reuse does not add independent evidence years.',
                        'missing':'No eligible forecast is null, never a perfect forecast or zero error. Missing slots reduce year evidence weight.'},
        'comparison_rule':'Compare accounts only in the same year and cutoff with available point metrics. Overall confidence depends on coverage and is not a ranking when slot/year coverage differs. matched_time_comparisons is alphabetical, not a leaderboard.',
        'source_attribution':'Only source_role=original_projection enters cutoff accuracy and confidence. Quotes, official results, incomplete vectors, bounds, winner and seat claims are retained separately. CeSID/Ipsos is one source family.',
        'error':'published share minus corresponding official share; MAE = mean absolute error, RMSE = sqrt(mean squared error); units percentage points (pp).',
        'headline_party_set':'Six largest lists by final vote count in each election, equal weight. All-list metrics also retained; small-list dilution is therefore visible.',
        'denominator':'2020 CeSID valid ballots inferred from complete charts summing near 100; 2022/2023 CeSID ballots cast inferred from sums near 97. Alternative bases included.',
        'confidence_error':'Normalize the complete forecast vector and official counts to valid votes, calculate top-six MAE, then average equally over available fixed cutoff slots within each year. Extra intermediate updates do not receive extra weight. Normalization removes denominator assumptions from this score but does not assess invalid-ballot predictions.',
        'bounds':'Keep one-sided and two-sided statements as bounds. Measure containment and distance outside them; do not invent point estimates or call broad containment 100% forecasting accuracy.',
        'confidence_formula':'clamp(round_half_up(100 * max(0, 1 - E/2) * N/(N+1)), 1, 100)',
        'E':'Weighted mean of yearly equal-cutoff normalized top-six MAE. Only original complete-list point forecasts contribute.',
        'N':'Sum of year weights = (number of available cutoffs / 4) * collection multiplier. The multiplier is 1 for an exhausted current query/window, otherwise 0.75. Each year contributes at most 1 regardless of the number of posts or repeated cutoff selections.',
        'model_change':'Schema 2 replaces averaging all snapshots with fixed-cutoff averaging and coverage weighting. Bounds-only years no longer raise the point-forecast confidence score. Scores are not directly comparable with schema 1.',
        'collection_rule':'Only exhausted checkpoints with the current account query are used to cover the active window. Old partial narrower searches do not invalidate a completed wider search. Exhausted adjacent intervals can jointly cover the window.',
        'constants':{'error_scale_pp':ERROR_SCALE_PP,'requested_cutoffs':len(CUTOFFS),'partial_collection_multiplier':PARTIAL_WEIGHT,'shrinkage_years':PRIOR_YEAR_WEIGHT},
        'confidence_interpretation':'User-requested heuristic support score, not a calibrated probability, statistical confidence interval, general trust score, or percentage of correct posts. Constants are explicit judgment choices, not fitted to data.',
        'no_evidence':'Score 1 is a required-scale floor for no quantitative forecast evidence. Accuracy metrics are null; do not treat this floor as evidence the account is wrong.',
        'seats':'Minimum seats to reassign = sum(abs(projected-final))/2. Allocation agreement = 100*(1-distance/250). Separate from vote accuracy and confidence to avoid double counting.',
        'supplementary':'Turnout, invalid ballots, voter registration, threshold and winner statements are checked separately and do not increase numerical-forecast confidence.',
        'exclusions':'Separate presidential/local elections; turnout at 19:00; percentages of sample received; process/irregularity reports; linked videos/pages not present in saved data.'}
    matched={}
    for year in YEARS:
        matched[year]={}
        for spec in cutoff_schedule(windows['election'+year]):
            rows=[]
            for account in accounts:
                slot=account['years'][year]['cutoffs'][spec['key']]
                if slot['forecast']:
                    rows.append({'account':account['account'],'post_id':slot['forecast']['post_id'],
                                 'source_post_ids':slot['forecast']['source_post_ids'],
                                 'available_at_belgrade':slot['forecast']['available_at_belgrade'],
                                 'source_family':slot['forecast']['source_family'],
                                 'normalized_top_six_mae_pp':slot['normalized_top_six_mae_pp'],
                                 'age_minutes':slot['age_minutes'],'reused_from_previous_cutoff':slot['reused_from_previous_cutoff'],
                                 'collection_exhausted':account['years'][year]['collection_exhausted']})
            matched[year][spec['key']]={**spec,'available_accounts':rows,
                                       'unavailable_accounts':[a['account'] for a in accounts if a['years'][year]['cutoffs'][spec['key']]['forecast'] is None],
                                       'head_to_head_available':len(rows)>=2}
    output={'schema_version':2,'reviewed_on':review['reviewed_on'],
            'coverage':{'accounts':len(accounts),'years':list(YEARS),'saved_posts_reviewed':len(posts),'photos_reviewed':total_photos,
                        'active_windows':windows,
                        'unreviewed_non_photo_attachments':sum(len(r.get('unreviewed_media',[])) for r in review['records']),
                        'photos_recovered_from_saved_public_urls':sum(img['recovered_from_saved_public_url'] for r in review['records'] for img in r['images']),
                        'point_forecast_posts':sum(r['kind']=='vote_share' and r.get('source_role')=='original_projection' for r in scored),
                        'comparison_records':len(scored),'paid_x_api_calls':0},
            'methodology':methodology,
            'official_sources':{y:ref['source'] for y,ref in refs.items()},
            'accounts':accounts,
            'matched_time_comparisons':matched,
            'limitations':[
                'Only three historical election nights. Accounts with no saved forecasts are unassessed, not demonstrated inaccurate.',
                'API exhaustion only covers the current account query/window; deleted posts and external linked content remain absent. Unavailable videos are audited but not transcribed or assumed to contain no numerical claims.',
                'Missing cutoff data can reflect late publication or incomplete collection. Compare accounts only where year and cutoff match, and check collection coverage.',
                'Full-list normalization cannot be applied to a few selected parties. Bounds and partial vectors do not receive a comparable point-forecast score.',
                'Final official results include repeat voting and administrative corrections. Retrospective differences do not by themselves demonstrate a reporting mistake on election night.',
                'Updates on the same night are correlated. CeSID/Ipsos joint estimates form one source family, not two independent confirmations.',
                'Forecasts are rounded, mainly to 0.1 pp. Sampling design is unavailable, so no statistical confidence interval or calibrated probability is claimed.',
                'Final official counts are the requested benchmark; this does not assess electoral integrity or resolve reported irregularities.',
                'The fixed confidence weights and 2 pp scale express a conservative screening rule. Use underlying errors and evidence counts for decisions, not score alone.'],
            'audit_files':{'claims':'analysis/accounts/reviewed_claims.json','official_reference':'analysis/accounts/official_reference.json','full_comparisons':'analysis/accounts/comparisons.json','report':'analysis/accounts/report.md'},
            'input_hashes':{'reviewed_claims':sha256(SUPPORT/'reviewed_claims.json'),'official_reference':sha256(SUPPORT/'official_reference.json'),
                            'election_windows':sha256(ROOT/'election_windows.json'),'checkpoints':checkpoint_hashes}}
    return output,scored


def write_report(output, scored):
    coverage=output['coverage']
    lines=['# Saved election-account accuracy review', '',
           f"Reviewed {coverage['saved_posts_reviewed']} posts and {coverage['photos_reviewed']} photo attachments across {coverage['accounts']} accounts. {coverage['unreviewed_non_photo_attachments']} video/other attachments were not transcribed.",
           '', 'Collection window: election day 20:00 through midnight ending the following day, Belgrade time. Four matching cutoffs: 22:00, first midnight, 02:00 and final midnight. There is no 06:00 cutoff.',
           '', '## Account evidence', '',
           '| Account | 2020 cutoff coverage | 2022 cutoff coverage | 2023 cutoff coverage | Confidence / 100 |',
           '| --- | ---: | ---: | ---: | ---: |']
    for account in output['accounts']:
        cells=[str(account['years'][y]['cutoff_coverage']['available'])+'/4' for y in YEARS]
        lines.append('| @'+account['account']+' | '+' | '.join(cells)+f" | {account['confidence_score']} |")
    lines += ['', 'Coverage counts original full-list parliamentary projections available by each cutoff. An earlier projection can remain the latest available at later cutoffs. Missing values are unavailable, not zero error. Confidence is an uncalibrated, coverage-dependent screening score, not percentage accuracy or an account-wide trust rating. Accounts with different covered slots must not be ranked by this score alone.',
              '', '## Matched-time comparisons', '',
              'Errors below are top-six MAE after normalizing complete chart shares and official votes to valid votes. All accounts in one row group share an election year and deadline. They are listed alphabetically. Age shows how old the latest eligible information was at that deadline.',
              '', '| Year | Cutoff (Belgrade) | Account | Top-six MAE (pp) | Age (minutes) | Same source as previous cutoff |',
              '| --- | --- | --- | ---: | ---: | --- |']
    for year,year_slots in output['matched_time_comparisons'].items():
        for slot in year_slots.values():
            for row in slot['available_accounts']:
                lines.append(f"| {year} | {slot['at_belgrade']} | @{row['account']} | {row['normalized_top_six_mae_pp']:.3f} | {row['age_minutes']:.1f} | {'yes' if row['reused_from_previous_cutoff'] else 'no'} |")
            if not slot['available_accounts']:
                lines.append(f"| {year} | {slot['at_belgrade']} | No eligible forecast | unavailable | — | — |")
    lines += ['', '## Model', '', '```text',
              'error_i = estimate_i - official_i',
              'MAE = mean(abs(error_i))',
              'normalized_estimate_i = 100 * displayed_share_i / sum(all displayed shares)',
              'normalized_official_i = 100 * votes_i / valid_ballots',
              'cutoff_error = MAE across the six largest lists by final votes',
              'year_error = equal mean(cutoff_error for available cutoff slots)',
              'year_weight = (available_cutoffs / 4) * (1 if collection exhausted else 0.75)',
              'N = sum(year_weight); E = weighted mean(year_error)',
              'confidence = clamp(round_half_up(100 * max(0, 1 - E/2) * N/(N+1)), 1, 100)',
              '```', '',
              'One election contributes at most one effective year. Repeated snapshots and repeated use of the same forecast at several cutoffs do not add independent years. Bounds, partial party vectors, official figures quoted by an account, seats and turnout do not increase this point-forecast score. The error scale and evidence weights are judgment choices, not fitted statistical parameters. Schema 1 scores used all snapshots and credited bounds; schema 2 scores are not directly comparable.',
              '', '## Reviewed numerical claims', '',
              '| Account/year | Available in Belgrade | Kind | Source role | Detail |',
              '| --- | --- | --- | --- | --- |']
    for r in scored:
        detail='Supplementary; see detailed JSON'
        if r['kind']=='vote_share':
            detail=f"Native-basis top-six MAE {r['top_six_metrics']['mae_pp']:.3f} pp; normalized {r['normalized_valid_votes']['top_six_metrics']['mae_pp']:.3f} pp"
        elif r['kind']=='vote_share_partial':
            detail=f"Only {r['reported_lists_metrics']['n']} reported lists; no comparable full-vector score"
        elif r['kind']=='vote_share_bounds':
            detail=f"{r['bounds_containing_final']}/{r['tested_bounds']} bounds contain final; not point accuracy"
        elif r['kind']=='seats':
            detail=f"{r['minimum_seats_to_reassign']:g} seats to reassign; supplementary"
        elif r.get('evaluation_status')=='not_comparable':
            detail='No comparable scope benchmark; accuracy unavailable'
        lines.append(f"| @{r['account']} / {r['year']} | [{r['available_at_belgrade']}]({r['post_url']}) | {r['kind']} | {r.get('source_role','unspecified')} | {detail} |")
    lines += ['', '## Claim notes', '']
    for r in scored:
        if r.get('note'):
            lines.append(f"- {r['claim_id']}: {r['note']}")
    lines += ['', '## Collection gaps', '']
    for account in output['accounts']:
        for year,yr in account['years'].items():
            if not yr['collection_exhausted']:
                lines.append(f"- @{account['account']} / {year}: active-window search remains incomplete. Missing forecasts may reflect collection gaps.")
    lines += ['', '## Sources and reproducibility', '']
    for year,source in output['official_sources'].items():
        lines.append(f"- {year}: `{source['file']}`. See official_reference.json for extraction details and source hashes.")
    lines += ['', 'Run `python .\\evaluate_accounts.py` from the project root. It uses only reviewed local inputs, checks post/image/source hashes, validates composite availability against constituent post timestamps, and writes the executive JSON and detailed comparisons. New or changed evidence requires review; this program does not automatically transcribe new images or videos.',
              '', 'Full-party normalization corrects denominator differences but cannot correct geographic sample exclusions. A comparison with national final totals can include a benchmark-scope discrepancy; it is not automatically a pure forecasting error. See each claim’s notes.',
              '', '## Limitations', '']
    lines.extend('- '+s for s in output['limitations'])
    (SUPPORT/'report.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')


def main():
    output,scored=build()
    (ROOT/'executive_decision.json').write_text(json.dumps(output,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    (SUPPORT/'comparisons.json').write_text(json.dumps(scored,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    write_report(output,scored)
    for a in output['accounts']:
        print(f"@{a['account']}: confidence {a['confidence_score']}/100; {a['decision']}")
    print('Saved:',ROOT/'executive_decision.json')


if __name__=='__main__':
    main()
