"""Rebuild the reviewed manifest from the frozen, individually reviewed batches.

This does not infer claims or approve new posts. Unknown/changed text, timestamps
or photos fail validation. Ordinary users should run evaluate_accounts.py.
"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    base = read(HERE / 'reviewed_claims_4h.json')
    updates = [read(HERE / name) for name in (
        'review_cesid_update.json', 'review_crta_update.json', 'review_other_update.json')]
    records = {r['post_id']: r for r in base['records']}
    claims = {c['claim_id']: c for c in base['claims']}
    for batch in updates:
        for r in batch['records']:
            assert r['post_id'] not in records, 'Duplicate reviewed post'
            records[r['post_id']] = r
        for c in batch['claims']:
            assert c['claim_id'] not in claims, 'Duplicate reviewed claim'
            claims[c['claim_id']] = c
        changes = batch.get('old_claim_updates', {})
        if isinstance(changes, list):
            changes = {c['claim_id']: c['add'] for c in changes}
        for claim_id, fields in changes.items():
            assert claim_id in claims, claim_id
            claims[claim_id].update(fields)

    manifest, seen = {}, set()
    for year in ('2020', '2022', '2023'):
        for path in sorted((ROOT / 'data' / year).glob('*/posts.jsonl')):
            manifest[path.relative_to(ROOT).as_posix()] = digest(path)
            for line in path.read_text(encoding='utf-8').splitlines():
                if not line.strip():
                    continue
                p = json.loads(line)
                assert p['id'] not in seen, 'Duplicate saved ID'
                seen.add(p['id'])
                assert p['id'] in records, 'New post needs review: ' + p['id']
                r = records[p['id']]
                assert (r['account'], r['year']) == (path.parent.name, year)
                assert r['text'] == p.get('full_text', p['text']), 'Changed text: ' + p['id']
                assert r['created_at'] == p['created_at'], 'Changed timestamp: ' + p['id']
                photos = [m for m in p.get('media', []) if m['type'] == 'photo']
                assert len(photos) == len(r['images']), 'Changed attachments: ' + p['id']
                expected_names = {m['local_file'] for m in photos}
                assert {Path(i['file']).name for i in r['images']} == expected_names
                for i in r['images']:
                    assert i['reviewed_visually'] and digest(ROOT / i['file']) == i['sha256'], i['file']
                    saved_copy = path.parent / Path(i['file']).name
                    if saved_copy.is_file():
                        assert digest(saved_copy) == i['sha256'], 'Saved photo changed: ' + str(saved_copy)
                other = [m for m in p.get('media', []) if m['type'] != 'photo']
                r.setdefault('unreviewed_media', [])
                assert {(m['type'], m['media_key']) for m in other} == {
                    (m['type'], m['media_key']) for m in r['unreviewed_media']}, 'Unreviewed-media audit missing'
                assert not p.get('missing_media_keys'), 'Missing attachments need review'
    assert seen == set(records), 'Reviewed posts missing from current data'

    for c in claims.values():
        if 'source_role' not in c:
            c['source_role'] = ('original_projection' if c['account'] in ('cesidbeograd', 'crtars')
                                else 'political_statement')
        c.setdefault('source_family', {'cesidbeograd': 'CeSID/Ipsos', 'crtars': 'CRTA'}.get(c['account'], c['account']))
        c['confidence_scoring_eligible'] = c['kind'] == 'vote_share' and c['source_role'] == 'original_projection'

    output = {
        'reviewed_on': '2026-10-22',
        'scope': 'Saved 2020/2022/2023 posts from election-day 20:00 to the end of the following day (28 hours), Europe/Belgrade. Photos reviewed; unsaved videos and linked pages excluded.',
        'input_posts_sha256': manifest,
        'records': sorted(records.values(), key=lambda r: (r['year'], r['account'], r['created_at'], r['post_id'])),
        'claims': list(claims.values()),
        'scope_sources': updates[1]['scope_sources'],
        'review_batches': ['reviewed_claims_4h.json', 'review_cesid_update.json', 'review_crta_update.json', 'review_other_update.json'],
        'note': 'Reviewed transcriptions, not automatic OCR. New or changed evidence requires explicit review before recalculation. No paid X API calls made for this evaluation.'}
    (HERE / 'reviewed_claims.json').write_text(json.dumps(output, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    print(f"Merged {len(records)} reviewed posts, {sum(len(r['images']) for r in records.values())} photos, {len(claims)} claims.")


if __name__ == '__main__':
    main()
