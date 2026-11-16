#!/usr/bin/env python3
"""Build the WoW Forever roster dashboard. Python 3.10+, no dependencies."""
from decimal import Decimal, ROUND_HALF_UP
from html import escape
import math
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

from dungeons import quests
from dungeons.view import add_dungeons

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


CLASS_COLORS = {
    'Shaman': '#409cff', 'Warrior': '#c79c6e', 'Priest': '#eee', 'Mage': '#69ccf0',
    'Warlock': '#b6a1ef', 'Druid': '#ff9549', 'Rogue': '#fff49b', 'Hunter': '#abd473',
    'Paladin': '#f58cba',
}


def glyph_class(key):
    return 'glyph-' + re.sub('[^a-z0-9-]+', '-', key.lower()).strip('-')


def stat_text(value):
    if not value:
        return ''
    kind = value.get('type')
    if kind == 'RANGE':
        low, high = stat_text(value.get('min')), stat_text(value.get('max'))
        return f'{low}–{high}' if low and high else ''
    number = value.get('value')
    if not isinstance(number, (int, float)) or not math.isfinite(number):
        return ''
    if kind == 'WHOLE':
        text = f'{math.floor(number + 0.5):,}'
    else:
        rounded = Decimal(str(number)).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)
        text = f'{rounded:,.2f}'.rstrip('0').rstrip('.')
    return text.replace(',', '\N{NO-BREAK SPACE}').replace('.', ',') + (' %' if kind == 'PERCENTAGE' else '')


def snapshot_row(hero):
    character = hero.get('character') or {}
    stats = character.get('stats') or {}
    basic = stats.get('basic') or {}
    values = {}
    for group in [basic.get('primary'), basic.get('secondary'), stats.get('overview'),
                  *(g.get('stats') for g in stats.get('groups') or [])]:
        for entry in group or []:
            text = stat_text(entry.get('value'))
            if text:
                values[entry['enum']] = text
    professions = character.get('professions') or {}
    for group in ('primaries', 'secondaries'):
        for skill in professions.get(group) or []:
            tiers = [t for t in skill.get('tiers') or [] if isinstance(t.get('skillPoints'), (int, float))]
            if tiers:
                tier = max(tiers, key=lambda t: t['skillPoints'])
                maximum = tier.get('maxSkillPoints')
                values[skill['name']] = str(tier['skillPoints']) + (f'/{maximum}' if maximum is not None else '')

    race, cls = character.get('race') or {}, character.get('class') or {}
    race_key = "race:{}:{}".format(race.get('slug', ''), (character.get('gender') or {}).get('slug', ''))
    race_name = escape(race.get('name') or '—')
    class_name = escape(cls.get('name') or '—')
    color = CLASS_COLORS.get(cls.get('name'), '#d3c2a5')
    race_glyph = f'<i class="glyph {glyph_class(race_key)}" role="img" aria-label="{race_name}"></i>' if race else ''
    class_glyph = f'<i class="glyph {glyph_class("class:" + cls["name"])}" role="img" aria-label="{class_name}"></i>' if cls.get('name') else ''
    identity = (
        f'<tr><th class="who" scope="row"><span style="color:{color}">{escape(hero["name"])}</span>'
        f'<span class="avatar">{race_glyph}{class_glyph}<span class="owner-name">{escape(hero["owner"])}</span></span></th>'
        f'<td class="profile-v"><span class="profile-field field-race">{race_glyph}<span>{race_name}</span></span></td>'
        f'<td class="profile-v"><span class="profile-field field-class" style="color:{color}">{class_glyph}<span>{class_name}</span></span></td>'
    )
    level_cell = f'<td class="lvl"><span class="level-number">{escape(str(character.get("level", "—")))}</span></td></tr>'
    return identity, values, level_cell


def render_dashboard(template, data, icons):
    # Render the script-free view from the same snapshot and column definitions as the interactive table.
    heroes = sorted(data['heroes'], key=lambda hero: hero['name'].casefold())
    rows = [snapshot_row(hero) for hero in heroes]

    def render_group(match):
        header = match[1]
        keys = re.findall(r' data-key="([^"]+)"', header)
        result = [header]
        for identity, values, level in rows:
            result.append(identity)
            for i, key in enumerate(keys):
                result.append(f'<td class="v c2-{i // 2} c3-{i // 3}">{escape(values.get(key, "—"))}</td>')
            result.append(level)
        return ''.join(result)

    html = re.sub(r'(<table class="paper"[^>]*>.*?<tbody>)__SNAPSHOT_ROWS__', render_group, template, flags=re.S)
    styles = [f"#snapshot-roster .{glyph_class(key)}{{background-image:url('{src}')}}"
              for key, src in icons.items() if re.fullmatch(r'data:image/[\w.+-]+;base64,[A-Za-z0-9+/=]+', src)]
    stamp = 'время не указано'
    if data.get('fetchedAt'):
        try:
            timestamp = datetime.datetime.fromisoformat(data['fetchedAt'].replace('Z', '+00:00'))
            stamp = timestamp.astimezone(datetime.timezone(datetime.timedelta(hours=3))).strftime('%d.%m.%Y, %H:%M МСК')
        except ValueError:
            pass
    html = html.replace('__DISPLAY_TIME__', stamp).replace('__SNAPSHOT_ICON_STYLES__', '\n'.join(styles))
    html = html.replace('__SNAPSHOT_LABEL__', 'Последнее успешное обновление' if data['complete'] else 'Частичный снимок')
    for marker, obj in [('__CLASS_COLORS__', CLASS_COLORS), ('__DATA__', data), ('__ICONS__', icons)]:
        html = html.replace(marker, json.dumps(obj, ensure_ascii=False).replace('<', '\\u003c'))
    return html


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
    icons = read_json(ROOT / 'icons.json', {})
    if not args.offline:
        icons = update_icons(heroes, icons)
    catalog = read_json(ROOT / 'dungeons' / 'catalog.json')
    quest_cache = ROOT / '.dungeon-quests-cache.json'
    if args.offline:
        snapshot = read_json(quest_cache, {})
        catalog_ids = sorted(quests.tracked_ids(catalog))
        if snapshot.get('region') != config['region'] or snapshot.get('catalog') != catalog_ids:
            snapshot = {}
    else:
        try:
            snapshot = quests.collect(config['region'], heroes, catalog, args.allow_partial)
        except RuntimeError as error:
            raise SystemExit(str(error)) from None
    html = render_dashboard((ROOT / 'template.html').read_text(encoding='utf-8'), data, icons)
    html = html.replace('WoW Forever · EU', 'WoW Forever · ' + config['region'].upper())
    html = add_dungeons(html, heroes, catalog, snapshot)
    atomic_write(args.output, html)
    if not args.offline:
        atomic_write(quest_cache, json.dumps(snapshot, ensure_ascii=False))
        atomic_write(ROOT / 'cache.json', json.dumps(data, ensure_ascii=False, indent=2))
        atomic_write(ROOT / 'icons.json', json.dumps(icons))
    print(f'HTML: {args.output.resolve()}')


if __name__ == '__main__':
    main()
