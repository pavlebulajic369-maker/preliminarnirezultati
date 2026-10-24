"""Numerical and evidence-integrity tests; no network calls or source edits."""
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest.mock import patch

import evaluate_accounts as ev


class AccuracyTests(unittest.TestCase):
    def test_percentage_basis_is_not_silently_mixed(self):
        reference = {'valid_ballots':90,'ballots_cast':100,'voters_who_turned_out':100,
                     'parties':{'A':{'votes':54},'B':{'votes':36}},'top_six_lists':['A','B']}
        claim = {'kind':'vote_share','claim_id':'example','basis':'valid_ballots','values':{'A':60,'B':40}}
        result = ev.score_claim(claim,reference)
        self.assertEqual(result['all_lists_metrics']['mae_pp'],0)
        self.assertEqual(result['sensitivity_raw_chart_against_other_denominators']['ballots_cast']['mae_pp'],5)

    def test_rounding_normalization_preserves_full_vector(self):
        reference = {'valid_ballots':100,'ballots_cast':100,'voters_who_turned_out':100,
                     'parties':{'A':{'votes':60},'B':{'votes':40}},'top_six_lists':['A','B']}
        claim = {'kind':'vote_share','claim_id':'example','basis':'ballots_cast','values':{'A':60.06,'B':40.04}}
        result=ev.score_claim(claim,reference)
        self.assertAlmostEqual(result['normalized_valid_votes']['top_six_metrics']['mae_pp'],0)
        self.assertGreater(result['all_lists_metrics']['mae_pp'],0)

    def test_bounds_keep_open_and_closed_endpoints(self):
        self.assertFalse(ev.check_bound(58,58,None,False)['contains_official'])
        self.assertTrue(ev.check_bound(60.65,58,None,False)['contains_official'])
        self.assertTrue(ev.check_bound(11,9,11)['contains_official'])
        self.assertAlmostEqual(ev.check_bound(11.2,9,11)['distance_outside_pp'],.2)

    def test_no_data_is_unavailable_not_perfect(self):
        self.assertIsNone(ev.confidence([])['weighted_error_pp'])
        self.assertEqual(ev.confidence([])['score'],1)
        with self.assertRaises(ValueError):
            ev.metrics([])

    def test_evidence_shrinkage_and_error_penalty(self):
        perfect=[{'weight':1,'error_pp':0}]*3
        self.assertEqual(ev.confidence(perfect)['score'],75)
        self.assertLess(ev.confidence([{'weight':.75,'error_pp':0}]*3)['score'],75)
        self.assertLess(ev.confidence([{'weight':1,'error_pp':1}]*3)['score'],75)
        self.assertEqual(ev.confidence([{'weight':.25,'error_pp':0}])['score'],20)

    def test_one_seat_transfer_counts_once(self):
        claim={'kind':'seats','values':{'A':128,'B':122},'note':''}
        ref={'parties':{'A':{'seats':129},'B':{'seats':121}}}
        result=ev.score_claim(claim,ref)
        self.assertEqual(result['minimum_seats_to_reassign'],1)
        self.assertAlmostEqual(result['allocation_agreement_pct'],99.6)

    def test_changed_posts_are_rejected_before_scoring(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)
            path=root/'data/2020/example/posts.jsonl'
            path.parent.mkdir(parents=True)
            path.write_text('original',encoding='utf-8')
            review={'input_posts_sha256':{'data/2020/example/posts.jsonl':ev.sha256(path)}}
            path.write_text('changed',encoding='utf-8')
            with patch.object(ev,'ROOT',root), self.assertRaisesRegex(ValueError,'Posts changed'):
                ev.validate_inputs(review,{})

    def test_current_review_reconciles_and_preserves_previous_2023_result(self):
        output, comparisons=ev.build()
        self.assertEqual(output['coverage']['saved_posts_reviewed'],244)
        self.assertEqual(output['coverage']['photos_reviewed'],102)
        self.assertEqual(output['coverage']['unreviewed_non_photo_attachments'],12)
        self.assertEqual(len(output['accounts']),7)
        latest=next(r for r in comparisons if r['post_id']=='1736513641321546053')
        self.assertAlmostEqual(latest['top_six_metrics']['mae_pp'],0.15373530550970424)
        ce=next(a for a in output['accounts'] if a['account']=='cesidbeograd')
        self.assertEqual(ce['confidence_components']['effective_election_years'],2.75)
        self.assertEqual(ce['confidence_score'],67)
        self.assertEqual(ce['years']['2022']['cutoffs']['end_next_day_00_00']['forecast']['post_id'],'1510919362894565385')
        self.assertEqual(ce['years']['2022']['quoted_or_official_full_charts'][0]['post_id'],'1511060336501211147')
        crta=next(a for a in output['accounts'] if a['account']=='crtars')
        self.assertEqual(crta['confidence_score'],50)
        self.assertEqual(sum(y['cutoff_coverage']['available'] for y in crta['years'].values()),5)
        self.assertIsNone(crta['years']['2023']['cutoffs']['next_day_00_00']['forecast'])
        self.assertEqual(crta['years']['2023']['cutoffs']['next_day_02_00']['forecast']['post_id'],'1736526322761883686')
        self.assertEqual(sum(y['collection_exhausted'] for a in output['accounts'] for y in a['years'].values()),20)
        for account in output['accounts']:
            self.assertEqual(set(account['years']),{'2020','2022','2023'})
            self.assertTrue(1<=account['confidence_score']<=100)


class CutoffTests(unittest.TestCase):
    window='2023-12-17T20:00:00+01:00/2023-12-19T00:00:00+01:00'

    def forecast(self,pid,at,role='original_projection',kind='vote_share'):
        return {'claim_id':pid+':'+kind,'post_id':pid,'kind':kind,'source_role':role,
                'created_at_belgrade':at,'available_at_belgrade':at,
                'normalized_valid_votes':{'top_six_metrics':{'mae_pp':0.2}}}

    def test_four_cutoffs_use_saved_summer_and_winter_offsets(self):
        for window,utc_hour in [(self.window,21),('2022-04-03T20:00:00+02:00/2022-04-05T00:00:00+02:00',20)]:
            schedule=ev.cutoff_schedule(window)
            self.assertEqual(len(schedule),4)
            self.assertEqual([ev.parse_time(s['at_belgrade']).hour for s in schedule],[22,0,2,0])
            self.assertEqual(ev.parse_time(schedule[0]['at_utc']).hour,utc_hour)
            self.assertEqual(ev.parse_time(schedule[-1]['at_belgrade']),ev.parse_window(window)[1])
            self.assertTrue(schedule[-1]['collection_end_exclusive'])

    def test_no_lookahead_carry_forward_and_missing_are_explicit(self):
        p=self.forecast('overnight','2023-12-18T00:18:33+01:00')
        slots=ev.matched_cutoffs([p],self.window)
        self.assertIsNone(slots['election_day_22_00']['normalized_top_six_mae_pp'])
        self.assertIsNone(slots['next_day_00_00']['forecast'])
        self.assertEqual(slots['next_day_02_00']['forecast']['post_id'],'overnight')
        self.assertAlmostEqual(slots['next_day_02_00']['age_minutes'],101.45)
        self.assertTrue(slots['end_next_day_00_00']['reused_from_previous_cutoff'])
        self.assertFalse(slots['next_day_02_00']['reused_from_previous_cutoff'])

    def test_intermediate_boundary_inclusive_collection_end_exclusive(self):
        rows=[self.forecast('before','2023-12-17T19:59:59+01:00'),
              self.forecast('at22','2023-12-17T22:00:00+01:00'),
              self.forecast('after22','2023-12-17T22:00:01+01:00'),
              self.forecast('last','2023-12-18T23:59:59+01:00'),
              self.forecast('excluded','2023-12-19T00:00:00+01:00')]
        slots=ev.matched_cutoffs(rows,self.window)
        self.assertEqual(slots['election_day_22_00']['forecast']['post_id'],'at22')
        self.assertEqual(slots['next_day_00_00']['forecast']['post_id'],'after22')
        self.assertEqual(slots['end_next_day_00_00']['forecast']['post_id'],'last')

    def test_official_quotes_and_partial_charts_do_not_replace_own_forecast(self):
        rows=[self.forecast('own','2023-12-17T21:00:00+01:00'),
              self.forecast('rik','2023-12-18T12:00:00+01:00','official_result'),
              self.forecast('quote','2023-12-18T13:00:00+01:00','quoted_projection'),
              self.forecast('partial','2023-12-18T14:00:00+01:00',kind='vote_share_partial')]
        slots=ev.matched_cutoffs(rows,self.window)
        self.assertTrue(all(s['forecast']['post_id']=='own' for s in slots.values()))

    def test_repeated_source_adds_coverage_but_not_independent_years(self):
        slots=ev.matched_cutoffs([self.forecast('one','2023-12-17T21:00:00+01:00')],self.window)
        evidence=ev.cutoff_evidence('2023',slots,True)
        self.assertEqual(evidence['weight'],1)
        self.assertEqual(evidence['distinct_forecast_claims'],1)
        self.assertAlmostEqual(evidence['error_pp'],0.2)
        self.assertEqual(ev.cutoff_evidence('2023',slots,False)['weight'],0.75)
        late=ev.matched_cutoffs([self.forecast('late','2023-12-18T12:00:00+01:00')],self.window)
        self.assertEqual(ev.cutoff_evidence('2023',late,True)['weight'],0.25)
        self.assertIsNone(ev.cutoff_evidence('2023',ev.matched_cutoffs([],self.window),True))

    def test_old_partial_search_does_not_invalidate_completed_expansion(self):
        states=[{'query':'from:example -is:retweet','window':self.window,'search_exhausted':True},
                {'query':'from:example -is:retweet','window':'2023-12-17T20:00:00+01:00/2023-12-18T00:00:00+01:00','search_exhausted':False}]
        self.assertTrue(ev.collection_coverage(states,'example',self.window)['search_exhausted'])
        states[0]['search_exhausted']=False
        states[1]['search_exhausted']=True
        result=ev.collection_coverage(states,'example',self.window)
        self.assertFalse(result['search_exhausted'])
        self.assertAlmostEqual(result['exhausted_coverage_fraction'],4/28)

    def test_adjacent_searches_cover_window_but_gap_or_wrong_query_does_not(self):
        states=[{'query':'from:example -is:retweet','window':'2023-12-17T20:00:00+01:00/2023-12-18T00:00:00+01:00','search_exhausted':True},
                {'query':'from:example -is:retweet','window':'2023-12-18T00:00:00+01:00/2023-12-19T00:00:00+01:00','search_exhausted':True}]
        self.assertTrue(ev.collection_coverage(states,'example',self.window)['search_exhausted'])
        states[1]['window']='2023-12-18T00:00:01+01:00/2023-12-19T00:00:00+01:00'
        self.assertFalse(ev.collection_coverage(states,'example',self.window)['search_exhausted'])
        states[1].update(window=self.window,query='from:other -is:retweet')
        self.assertFalse(ev.collection_coverage(states,'example',self.window)['search_exhausted'])

    def test_scoped_turnout_bounds_do_not_use_national_denominator(self):
        ref={'parties':{},'registered_voters':100,'voters_who_turned_out':80,
             'turnout_scope_without_kosovo_prisons_abroad':{'registered_voters':80,'voters_who_turned_out':40}}
        claim={'kind':'turnout_bounds','scope':'without_kosovo_prisons_abroad','values':{'lower':49,'upper':51}}
        scored=ev.score_claim(claim,ref)
        self.assertEqual(scored['comparison']['official'],50)
        self.assertTrue(scored['comparison']['contains_official'])
        claim['scope']='unspecified'
        self.assertIsNone(ev.score_claim(claim,ref)['comparison'])

    def test_composite_available_only_after_all_constituents(self):
        review=ev.read(ev.SUPPORT/'reviewed_claims.json')
        refs=ev.read(ev.SUPPORT/'official_reference.json')
        claim=next(c for c in review['claims'] if len(c.get('source_post_ids',[]))>1)
        self.assertEqual(claim['post_id'],'1275018957607575552')
        claim['available_at']='2020-06-22T10:34:46Z'
        with self.assertRaisesRegex(ValueError,'availability disagrees'):
            ev.validate_inputs(review,refs)

    def test_review_timestamp_cannot_be_changed_to_move_a_forecast_earlier(self):
        review=deepcopy(ev.read(ev.SUPPORT/'reviewed_claims.json'))
        refs=ev.read(ev.SUPPORT/'official_reference.json')
        review['records'][0]['created_at']='2020-06-21T18:00:00Z'
        with self.assertRaisesRegex(ValueError,'timestamp mismatch'):
            ev.validate_inputs(review,refs)


if __name__=='__main__':
    unittest.main()
