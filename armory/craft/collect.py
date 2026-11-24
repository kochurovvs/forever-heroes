"""Resolve learned Blizzard recipes to catalog items for one roster at build time."""
import json
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import subprocess
from urllib.parse import quote, unquote, urlencode
from urllib.request import Request

from dungeons.quests import JournalNotFound, access_token, request_json

ROOT = Path(__file__).resolve().parent


def recipe_ids(profile, professions):
    if not any(key in profile for key in ('character', 'primaries', 'secondaries')):
        raise ValueError('Неизвестный формат профиля профессий')
    result = {}
    for skill in profile.get('primaries') or []:
        name = skill['profession']['name']
        if name not in professions:
            continue
        tiers = skill.get('tiers') or [skill]
        result[name] = {r['id'] for tier in tiers for r in tier.get('known_recipes') or []}
    return result


def collect(region, heroes):
    catalog = json.loads((ROOT / 'recipes.json').read_text())
    professions = {r['profession'] for r in catalog}
    supported = {r['id'] for r in catalog}
    slugs = []
    for hero in heroes:
        character = hero.get('character') or {}
        skills = (character.get('professions') or {}).get('primaries') or []
        if hero.get('status') == 'ok' and not hero.get('stale') and character.get('slug'):
            if any(skill.get('name') in professions for skill in skills):
                slugs.append(character['slug'])
    if not slugs:
        return []
    token = access_token()

    def get(path, namespace):
        query = urlencode({'namespace': f'{namespace}-forever-{region}', 'locale': 'en_GB'})
        url = f'https://{region}.api.blizzard.com{path}?{query}'
        return request_json(Request(url, headers={'Authorization': 'Bearer ' + token}))

    def learned(slug):
        try:
            profile = get('/profile/wow/character/' + quote(unquote(slug), safe='-') + '/professions', 'profile')
        except JournalNotFound:
            print(f'{slug}: список изученных рецептов недоступен (404)', flush=True)
            return slug, {}
        return slug, recipe_ids(profile, professions)

    # API recipe IDs and spell IDs are distinct. Seed with verified static API results;
    # also resolve newly encountered recipes so training another recipe takes effect.
    outputs = {int(k): v for k, v in json.loads((ROOT / 'recipe-outputs.json').read_text()).items()}

    def output(recipe_id):
        try:
            details = get('/data/wow/recipe/' + str(recipe_id), 'static')
        except JournalNotFound:
            return recipe_id, None
        return recipe_id, (details.get('crafted_item') or {}).get('id')

    with ThreadPoolExecutor(max_workers=4) as pool:
        books = dict(pool.map(learned, slugs))
        missing = {r for skills in books.values() for ids in skills.values() for r in ids} - outputs.keys()
        outputs.update(pool.map(output, sorted(missing)))
    known = {slug: {p: sorted({outputs[r] for r in ids} & supported) for p, ids in skills.items()}
             for slug, skills in books.items()}
    proc = subprocess.run(['node', str(ROOT / 'build.cjs')], check=True, text=True, stdout=subprocess.PIPE,
                          input=json.dumps({'heroes': heroes, 'known': known}, ensure_ascii=False))
    matches = json.loads(proc.stdout)
    print(f'Крафт: доступных замен {len(matches)}.', flush=True)
    return matches
