#!/usr/bin/env python3
"""Build the WoW Forever roster dashboard. Python 3.10+, no dependencies."""
import argparse
import base64
import concurrent.futures
import datetime
import json
import re
import tempfile
import os
import time
import urllib.request
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read_json(path, default=None):
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else default


def atomic_write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as f:
        temp = Path(f.name)
        f.write(text)
    try:
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def download(url):
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={'User-Agent': 'ForeverRoster/1.0'})
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read(), response.headers.get_content_type()
        except Exception:
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def validate(config):
    if config.get('region') not in ('eu', 'us'):
        raise ValueError('region must be eu or us')
    endpoint = config.get('refreshEndpoint')
    if endpoint:
        url = urllib.parse.urlsplit(endpoint)
        if url.scheme != 'https' or not url.hostname or url.path != '/refresh' or url.username or url.password or url.query or url.fragment:
            raise ValueError('refreshEndpoint must be a public HTTPS URL ending in /refresh')
    owners = config.get('owners')
    if not isinstance(owners, dict) or not owners:
        raise ValueError('owners must be a non-empty object')
    if not any(owners.values()):
        raise ValueError('At least one character is required')
    seen = set()
    for owner, names in owners.items():
        if not owner.strip() or not isinstance(names, list):
            raise ValueError('Each owner needs a name and an array of characters')
        for name in names:
            if not isinstance(name, str) or len(name.split()) != 2:
                raise ValueError(f'Expected name and surname: {name!r}')
            key = name.casefold().strip()
            if key in seen:
                raise ValueError(f'Duplicate character: {name}')
            seen.add(key)


def collect(pair, region, cached, offline):
    owner, name = pair
    slug = urllib.parse.quote('-'.join(name.lower().split()), safe='-')
    url = f'https://worldofwarcraft.blizzard.com/en-gb/forever/{region}/armory/character/{slug}'
    row = {'owner': owner, 'name': name, 'url': url, 'character': None}
    previous = cached.get(url, {})
    if offline:
        return {**previous, **row, 'character': previous.get('character'),
                'status': previous.get('status', 'Нет сохранённого профиля'),
                'stale': previous.get('stale', False)}
    try:
        body, _ = download(url)
        match = re.search(r'(?:var\s+)?characterProfileInitialState\s*=\s*', body.decode('utf-8'))
        if not match:
            raise ValueError('Не найден JSON профиля в оружейной')
        payload, _ = json.JSONDecoder().raw_decode(body.decode('utf-8')[match.end():])
        if not payload.get('character'):
            raise ValueError('Оружейная не вернула персонажа')
        row.update(character=payload['character'], status='ok', fetchedAt=now())
    except Exception as exc:
        row.update(character=previous.get('character'), status=str(exc),
                   stale=bool(previous.get('character')), fetchedAt=previous.get('fetchedAt'))
    print(f"{name}: {row['status']}", flush=True)
    return row


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def update_icons(heroes, icons):
    urls = {}
    portraits = {}
    for row in heroes:
        c = row.get('character')
        if not c:
            continue
        cls, race, gender = c.get('class', {}), c.get('race', {}), c.get('gender', {})
        region = row['url'].split('/forever/')[1].split('/')[0]
        base = f'https://render.worldofwarcraft.com/forever-{region}/icons/56/'
        if cls.get('slug'):
            urls['class:' + cls['name']] = base + 'classicon_' + cls['slug'] + '.jpg'
        if race.get('slug') and gender.get('slug'):
            r, g = race['slug'], gender['slug']
            portraits[f'race:{r}:{g}'] = c.get('avatar', {}).get('url')
            urls[f'race:{r}:{g}'] = (c.get('avatar', {}).get('url') if 'skyborne' in r
                                     else base + 'race_' + ('scourge' if r == 'undead' else r) + '_' + g + '.jpg')
        for group in ('primaries', 'secondaries'):
            for skill in c.get('professions', {}).get(group, []):
                urls['prof:' + skill['name']] = skill.get('icon', {}).get('url')
    for key, url in urls.items():
        if icons.get(key) or not url:
            continue
        try:
            try:
                content, mime = download(url)
            except Exception:
                if '/icons/' not in url:
                    raise
                fallback = re.sub(r'/forever-(?:eu|us)/', '/classic-us/', url)
                try:
                    content, mime = download(fallback)
                except Exception:
                    if not portraits.get(key):
                        raise
                    content, mime = download(portraits[key])
            if not mime.startswith('image/'):
                raise ValueError('Expected image')
            icons[key] = 'data:' + mime + ';base64,' + base64.b64encode(content).decode('ascii')
        except Exception as exc:
            print(f'Иконка {key}: {exc}', flush=True)
    return icons


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--roster', type=Path, default=ROOT / 'roster.json')
    parser.add_argument('--output', type=Path, default=ROOT / 'index.html')
    parser.add_argument('--allow-partial', action='store_true', help='Explicitly allow a partial snapshot; never used by the scheduled workflow')
    parser.add_argument('--offline', action='store_true', help='Build using the saved snapshot without network access')
    args = parser.parse_args()
    config = read_json(args.roster)
    validate(config)
    cached_data = read_json(ROOT / 'cache.json', {})
    cached = {row['url'].rstrip('/'): row for row in cached_data.get('heroes', [])}
    pairs = [(owner, name) for owner, names in config['owners'].items() for name in names]
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        heroes = list(pool.map(lambda pair: collect(pair, config['region'], cached, args.offline), pairs))
    failures = [h for h in heroes if h.get('status') != 'ok']
    if not args.offline and failures and not args.allow_partial:
        raise SystemExit('Сбор не завершён: ' + ', '.join(h['name'] for h in failures) + '. Последняя рабочая страница и время обновления сохранены.')
    data = {'roster': config['owners'], 'heroes': heroes,
            'fetchedAt': cached_data.get('fetchedAt') if args.offline else now(),
            'complete': not failures}
    if not args.offline and config.get('refreshEndpoint'):
        data['refreshEndpoint'] = config['refreshEndpoint']
    icons = read_json(ROOT / 'icons.json', {})
    if not args.offline:
        icons = update_icons(heroes, icons)
    html = (ROOT / 'template.html').read_text(encoding='utf-8')
    for marker, obj in [('__DATA__', data), ('__ICONS__', icons)]:
        html = html.replace(marker, json.dumps(obj, ensure_ascii=False).replace('</', '<\\/'))
    html = html.replace('WoW Forever · EU', 'WoW Forever · ' + config['region'].upper())
    atomic_write(args.output, html)
    marker = {'fetchedAt': data['fetchedAt'], 'complete': data['complete']}
    atomic_write(args.output.with_name('snapshot.json'), json.dumps(marker))
    if not args.offline:
        atomic_write(ROOT / 'cache.json', json.dumps(data, ensure_ascii=False, indent=2))
        atomic_write(ROOT / 'icons.json', json.dumps(icons))
    print(f'HTML: {args.output.resolve()}')


if __name__ == '__main__':
    main()
