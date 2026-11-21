"""Read public dungeon statistics for the test page's roster."""
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote, urlencode
from urllib.request import Request

from dungeons.quests import JournalNotFound, access_token, character_key, request_json


def dungeon_statistics(node, ancestry=()):
    path = (*ancestry, str(node.get('name', '')))
    for statistic in node.get('statistics', []):
        name = statistic.get('name', '')
        label = ' '.join((*path, name)).lower()
        if any(word in label for word in ('dungeon', 'raid', 'boss kills')):
            yield {key: statistic[key] for key in ('id', 'name', 'quantity', 'last_updated_timestamp')
                   if key in statistic}
    for field in ('categories', 'sub_categories'):
        for category in node.get(field, []):
            yield from dungeon_statistics(category, path)


def main():
    roster = json.loads(Path('roster.json').read_text())
    region = roster['region']
    token = access_token()
    query = urlencode({'locale': 'en_GB', 'namespace': f'profile-forever-{region}'})

    def read_character(name):
        slug = quote(character_key(name), safe='-')
        url = f'https://{region}.api.blizzard.com/profile/wow/character/{slug}/achievements/statistics?{query}'
        try:
            payload = request_json(Request(url, headers={'Authorization': 'Bearer ' + token}))
        except (RuntimeError, JournalNotFound) as error:
            return name, {'status': str(error)}
        if not isinstance(payload.get('categories'), list):
            return name, {'status': 'statistics unavailable'}
        return name, {'status': 'ok', 'stats': list(dungeon_statistics(payload))}

    names = [name for heroes in roster['owners'].values() for name in heroes]
    with ThreadPoolExecutor(max_workers=3) as pool:
        heroes = dict(pool.map(read_character, names))
    data = {'asOf': datetime.now(timezone.utc).isoformat(), 'region': region, 'heroes': heroes}
    Path('dungeon-statistics.json').write_text(json.dumps(data, ensure_ascii=False))
    print(f"Collected {sum(v['status'] == 'ok' for v in heroes.values())}/{len(heroes)} public profiles.")


if __name__ == '__main__':
    main()
