import base64
import concurrent.futures
import datetime
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


def character_key(name):
    return '-'.join(name.lower().split())


def request_json(request):
    for attempt in range(3):
        try:
            with urlopen(request, timeout=20) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise RuntimeError(f'HTTP {error.code}') from None
            delay = error.headers.get('Retry-After', '')
            wait = min(20, int(delay)) if delay.isdigit() else 2 ** attempt
        except (URLError, OSError):
            if attempt == 2:
                raise RuntimeError('соединение с Battle.net недоступно') from None
            wait = 2 ** attempt
        time.sleep(wait)


def access_token():
    client_id = os.getenv('BLIZZARD_CLIENT_ID')
    secret = os.getenv('BLIZZARD_CLIENT_SECRET')
    if not client_id or not secret:
        raise RuntimeError('Для загрузки квестов нужны BLIZZARD_CLIENT_ID и BLIZZARD_CLIENT_SECRET')
    basic = base64.b64encode(f'{client_id}:{secret}'.encode()).decode()
    payload = request_json(Request('https://oauth.battle.net/token',
        data=b'grant_type=client_credentials', headers={'Authorization':'Basic '+basic,
        'Content-Type':'application/x-www-form-urlencoded'}))
    if not isinstance(payload.get('access_token'), str) or not payload['access_token']:
        raise RuntimeError('Battle.net не выдал токен приложения')
    return payload['access_token']


def quest_ids(payload, field):
    entries = payload.get(field)
    if not isinstance(entries, list):
        raise ValueError('В ответе Battle.net отсутствует список ' + field)
    result = set()
    for entry in entries:
        quest = entry.get('quest', entry) if isinstance(entry, dict) else None
        if not isinstance(quest, dict) or type(quest.get('id')) is not int:
            raise ValueError('Неизвестный формат задания Battle.net')
        result.add(quest['id'])
    return result


def collect(region, heroes, catalog, allow_partial=False):
    token = access_token()
    query = '?' + urlencode({'namespace': f'profile-forever-{region}', 'locale': 'en_GB'})
    allowed = {q['id'] for dungeon in catalog for q in dungeon['quests']}
    def fetch(hero):
        slug = character_key(hero['name'])
        character = hero.get('character') or {}
        cls = (character.get('class') or {}).get('name')
        if not cls:
            return slug, None, 'неизвестен класс'
        applicable = {q['id'] for d in catalog for q in d['quests'] if not q.get('cls') or q['cls'] == cls}
        base = f'https://{region}.api.blizzard.com/profile/wow/character/{quote(slug, safe="-")}/quests'
        def read(suffix):
            return request_json(Request(base + suffix + query, headers={'Authorization':'Bearer '+token}))
        try:
            active = quest_ids(read(''), 'in_progress') & applicable
            done = quest_ids(read('/completed'), 'quests') & applicable
        except (RuntimeError, ValueError) as error:
            return slug, None, str(error)
        return slug, {'active':sorted(active - done), 'done':sorted(done),
                      'time':datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}, None

    snapshots, failures = {}, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for slug, record, error in pool.map(fetch, heroes):
            if error:
                failures.append(f'{slug} ({error})')
            else:
                snapshots[slug] = record
    if failures:
        message = 'Квесты недоступны: ' + ', '.join(failures)
        if not allow_partial:
            raise RuntimeError(message)
        print(message)
    print(f'Battle.net: проверено героев {len(snapshots)}/{len(heroes)}, подземелий {len(catalog)}.', flush=True)
    return {'region':region, 'catalog':sorted(allowed), 'heroes':snapshots}
