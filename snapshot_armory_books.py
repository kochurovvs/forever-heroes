"""One-time EU armory snapshot of profession recipes and library book turn-ins."""
import concurrent.futures
import datetime as dt
import json
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request

from dungeons.quests import access_token, character_key, quest_ids, request_json

# Library book turn-in IDs from https://wowcalc.net/en/forever/wiki/library-books
BOOKS = {
    79091: 'Archmage Antonidas: The Unabridged Autobiography',
    79092: "Archmage Theocritus' Research Journal",
    79093: 'Rumi of Gnomeregan: The Collected Works',
    78142: 'Bewitchments and Glamours',
    78147: 'Crimes Against Anatomy',
    78148: 'Runes of the Sorcerer-Kings',
    78146: 'Goaz Scrolls',
    79095: "The Apothecary's Metaphysical Primer",
    78127: 'The Dalaran Digest, Vol. 23',
    79096: 'Ataeric: On Arcane Curiosities',
    78145: 'Arcanic Systems Manual',
    79097: 'Baxtan: On Destructive Magics',
    78143: 'Secrets of the Dreamers',
    78124: "Nar'thalas Almanac, Vol. 74",
    78149: 'Fury of the Land',
    79094: "The Lessons of Ta'zo",
    79535: 'Basilisks: Should Petrification be Feared?',
    79947: 'Geomancy: The Stone-Cold Truth',
    79948: 'Defensive Magics 101',
    79952: 'RwlRwlRwlRwl!',
    79949: 'A Web of Lies: Debunking Myths and Legends',
    79950: 'Demons and You',
    79951: 'Mummies: A Guide to the Unsavory Undead',
    81947: 'Sanguine Sorcery',
    81949: 'Legends of the Tidesages',
    81952: 'Everyday Etiquette',
    81953: 'Stonewrought Design',
    81954: 'Venomous Journeys',
    81955: 'A Mind of Metal',
    81956: "Conjurer's Codex",
    84395: 'Undead Potatoes',
    84396: 'Magma or Lava?',
    84397: 'Northern Kalimdor - A Comprehensive Guide',
    84398: 'A Study of the Light',
    84399: 'Ka-Boom!',
    84400: 'The Knight and the Lady',
    84401: 'Scourge: Undead Menace or Misunderstood?',
    84402: 'Necromancy 101',
}
# Reward IDs from https://www.wowhead.com/forever/guide/library-book-locations-and-rewards
REWARDS = {78150, 79536, 82208, 84394}


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
        result = {'name': name, 'slug': slug}
        for key in ('professions', 'library'):
            try:
                if key == 'professions':
                    result[key] = profession_book(get(base + '/professions', 'profile'))
                else:
                    completed = quest_ids(get(base + '/quests/completed', 'profile'), 'quests')
                    result[key] = {'turnedIn': sorted(completed & BOOKS.keys()),
                                   'rewardQuestsCompleted': sorted(completed & REWARDS)}
            except (RuntimeError, ValueError, KeyError, TypeError) as error:
                result[key] = None
                result[key + 'Error'] = str(error)[:120]
        return result

    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        heroes = list(pool.map(collect, names))
    recipe_ids = {r['id'] for h in heroes for p in h['professions'] or [] for t in p['tiers']
                  for r in t['recipes'] or []}
    def recipe_output(recipe_id):
        try:
            detail = get('/data/wow/recipe/' + str(recipe_id), 'static')
            item = detail.get('crafted_item') or {}
            return recipe_id, {'craftedItemId': item.get('id'), 'craftedItemName': label(item.get('name'))}
        except (RuntimeError, ValueError, TypeError) as error:
            return recipe_id, {'error': str(error)[:120]}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        outputs = dict(pool.map(recipe_output, sorted(recipe_ids)))
    snapshot = {'fetchedAt': dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds'),
                'region': 'eu', 'bookQuests': BOOKS, 'characters': heroes, 'recipeOutputs': outputs}
    Path('armory-books-recipes.json').write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + '\n')
    print('Profile summaries:', len(names), 'characters,', len(recipe_ids), 'distinct recipe IDs.')
    for h in heroes:
        print(h['name'], 'professions:', len(h['professions']) if h['professions'] is not None else h['professionsError'],
              '| library:', len(h['library']['turnedIn']) if h['library'] is not None else h['libraryError'])


if __name__ == '__main__':
    take_snapshot()
