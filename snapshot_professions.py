"""Collect learned professions and crafted item IDs for the private armory preview."""
import concurrent.futures
import datetime as dt
import json
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request

from dungeons.quests import access_token, character_key, request_json

def take_snapshot():
    roster = json.loads(Path('roster.json').read_text())
    if roster['region'] != 'eu':
        raise ValueError('Expected EU roster')
    names = list(dict.fromkeys(n for group in roster['owners'].values() for n in group))
    token = access_token()

    def get(path, namespace):
        query = urlencode({'namespace': namespace + '-forever-eu', 'locale': 'en_GB'})
        return request_json(Request('https://eu.api.blizzard.com' + path + '?' + query,
                                    headers={'Authorization': 'Bearer ' + token}))

    def label(value):
        return value if isinstance(value, str) else (value or {}).get('en_GB') or (value or {}).get('en_US')

    def profession_book(payload):
        result = []
        for group in ('primaries', 'secondaries'):
            for row in payload.get(group, []):
                prof = row['profession']
                record = {'id': prof['id'], 'name': label(prof['name']), 'group': group, 'tiers': []}
                for tier in row.get('tiers', []):
                    skill = tier.get('tier') or tier.get('skill_tier') or {}
                    recipes = tier.get('known_recipes')
                    record['tiers'].append({
                        'id': skill.get('id'), 'name': label(skill.get('name')),
                        'skill': tier.get('skill_points'), 'maxSkill': tier.get('max_skill_points'),
                        'recipes': [{'id': r['id'], 'name': label(r.get('name'))} for r in recipes]
                                   if isinstance(recipes, list) else None})
                if not record['tiers'] and ('skill_points' in row or 'known_recipes' in row):
                    recipes = row.get('known_recipes')
                    record['tiers'].append({'id': None, 'name': None, 'skill': row.get('skill_points'),
                                            'maxSkill': row.get('max_skill_points'),
                                            'recipes': [{'id': r['id'], 'name': label(r.get('name'))} for r in recipes]
                                                       if isinstance(recipes, list) else None})
                result.append(record)
        if not result and not any(k in payload for k in ('primaries', 'secondaries', 'character')):
            raise ValueError('Unrecognized profession profile')
        return result

    def collect(name):
        slug = character_key(name)
        base = '/profile/wow/character/' + quote(slug, safe='-')
        return {'name': name, 'slug': slug,
                'professions': profession_book(get(base + '/professions', 'profile'))}

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        heroes = list(pool.map(collect, names))
    recipe_ids = {r['id'] for h in heroes for p in h['professions'] or [] for t in p['tiers']
                  for r in t['recipes'] or []}
    def recipe_output(recipe_id):
        detail = get('/data/wow/recipe/' + str(recipe_id), 'static')
        item = detail.get('crafted_item') or {}
        return recipe_id, {'craftedItemId': item.get('id'), 'craftedItemName': label(item.get('name'))}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        outputs = dict(pool.map(recipe_output, sorted(recipe_ids)))
    snapshot = {'fetchedAt': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                'region': 'eu', 'characters': heroes, 'recipeOutputs': outputs}
    Path('armory-professions.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n')
    print('Profile summaries:', len(names), 'characters,', len(recipe_ids), 'distinct recipe IDs.')


if __name__ == '__main__':
    take_snapshot()
