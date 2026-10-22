"""Numerical and evidence-integrity tests; no network calls or source edits."""
import tempfile
import unittest
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
        self.assertEqual(output['coverage']['saved_posts_reviewed'],103)
        self.assertEqual(output['coverage']['photos_reviewed'],41)
        self.assertEqual(len(output['accounts']),7)
        latest=next(r for r in comparisons if r['post_id']=='1736513641321546053')
        self.assertAlmostEqual(latest['top_six_metrics']['mae_pp'],0.15373530550970424)
        ce=next(a for a in output['accounts'] if a['account']=='cesidbeograd')
        self.assertEqual(ce['confidence_components']['effective_election_years'],2.5)
        for account in output['accounts']:
            self.assertEqual(set(account['years']),{'2020','2022','2023'})
            self.assertTrue(1<=account['confidence_score']<=100)


if __name__=='__main__':
    unittest.main()
