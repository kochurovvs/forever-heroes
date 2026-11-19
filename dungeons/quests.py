import base64
import concurrent.futures
import datetime
import json
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import quote, unquote, urlencode
from urllib.request import Request, urlopen


def character_key(name):
    return '-'.join(name.lower().split())


def applies(quest, character):
    if quest.get('excludeRace') and quest['excludeRace'] == (character.get('race') or {}).get('name'):
        return False
    return all(not quest.get(rule) or quest[rule] == (character.get(field) or {}).get('name')
               for rule, field in (('cls','class'), ('race','race'), ('faction','faction')))


def tracked_ids(catalog, character=None):
    ids = set()
    for dungeon in catalog:
        for quest in dungeon['quests']:
            if character is None or applies(quest, character):
                ids.add(quest['id'])
                ids.update(step['id'] for step in quest.get('prereqs', []))
    return ids


class JournalNotFound(RuntimeError):
    """Battle.net returned 404 for a character resource."""


def request_json(request):
    for attempt in range(3):
        try:
            with urlopen(request, timeout=20) as response:
                return json.load(response)
        except HTTPError as error:
            if error.code == 404:
                raise JournalNotFound('HTTP 404') from None
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


def collect(region, heroes, catalog, allow_partial=False, allow_missing_journals=False):
    token = access_token()
    query = '?' + urlencode({'namespace': f'profile-forever-{region}', 'locale': 'en_GB'})
    allowed = tracked_ids(catalog)
    def fetch(hero):
        slug = character_key(hero['name'])
        character = hero.get('character') or {}
        cls = (character.get('class') or {}).get('name')
        if not cls:
            return slug, None, 'неизвестен класс'
        applicable = tracked_ids(catalog, character)
        profile_slug = unquote(character.get('slug') or slug)
        base = f'https://{region}.api.blizzard.com/profile/wow/character/{quote(profile_slug, safe="-")}/quests'
        def read(suffix):
            return request_json(Request(base + suffix + query, headers={'Authorization':'Bearer '+token}))
        try:
            active = quest_ids(read(''), 'in_progress') & applicable
            done = quest_ids(read('/completed'), 'quests') & applicable
        except JournalNotFound as error:
            if allow_missing_journals:
                print(f'{hero["name"]}: журнал квестов Battle.net недоступен ({profile_slug}, HTTP 404)', flush=True)
                return slug, None, None
            return slug, None, str(error)
        except (RuntimeError, ValueError) as error:
            return slug, None, str(error)
        return slug, {'active':sorted(active - done), 'done':sorted(done),
                      'time':datetime.datetime.now(datetime.timezone.utc).isoformat(timespec='seconds')}, None

    snapshots, failures = {}, []
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        for slug, record, error in pool.map(fetch, heroes):
            if error:
                failures.append(f'{slug} ({error})')
            elif record is not None:
                snapshots[slug] = record
    if failures:
        message = 'Квесты недоступны: ' + ', '.join(failures)
        if not allow_partial:
            raise RuntimeError(message)
        print(message)
    print(f'Battle.net: проверено героев {len(snapshots)}/{len(heroes)}, подземелий {len(catalog)}.', flush=True)
    return {'region':region, 'catalog':sorted(allowed), 'heroes':snapshots}
