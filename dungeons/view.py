from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

from .quests import character_key

HERE = Path(__file__).parent


def stamp(iso):
    return datetime.fromisoformat(iso).astimezone(timezone(timedelta(hours=3))).strftime('%d.%m · %H:%M МСК')


def applies(q, cls):
    return not q.get('cls') or q['cls'] == cls


def quest_card(q, level=None):
    tags = []
    if q['inside']:
        tags.append('<span class="dg-tag inner">Внутри данжа</span>')
    if q.get('cls'):
        tags.append('<span class="dg-tag">'+escape(q['cls'])+'</span>')
    if level is not None and q['min'] > level:
        tags.append(f'<span class="dg-tag">С {q["min"]} ур.</span>')
    return (f'<article class="dg-row"><div class="dg-row-head"><a href="https://www.wowhead.com/forever/quest={q["id"]}" rel="noopener noreferrer" target="_blank">{escape(q["name"])}</a>'
            + ''.join(tags) + f'</div><p><b>{escape(q["giver"])}</b> · {escape(q["place"])}</p><p>{escape(q["how"])}</p></article>')


def quest_groups(quests, level=None):
    groups = []
    for inside, label in ((False, 'До входа'), (True, 'Внутри данжа')):
        cards = [quest_card(q, level) for q in quests if q['inside'] == inside]
        if cards:
            groups.append(f'<section class="dg-group"><h4>{label} · {len(cards)}</h4>'+''.join(cards)+'</section>')
    return ''.join(groups)


def member(dungeon, hero, record):
    character = hero.get('character') or {}
    cls = character.get('class') or {}
    level = character.get('level')
    available = [q for q in dungeon['quests'] if applies(q, cls.get('name'))]
    key = character_key(hero['name'])
    ratio, kind, amount, status = -1, 'unknown', '—', 'Нет данных'
    if record is None or not cls.get('name'):
        detail = '<p>Нет снимка Battle.net для этого героя.</p>'
    else:
        done_ids, active_ids = set(record['done']), set(record['active'])
        done = [q for q in available if q['id'] in done_ids]
        active = [q for q in available if q['id'] in active_ids and q['id'] not in done_ids]
        missing = [q for q in available if q['id'] not in active_ids | done_ids]
        total = sum(not q['inside'] for q in available)
        left = sum(not q['inside'] for q in missing)
        ratio = (total-left)/total if total else 1
        kind = 'ready' if not left else 'partial' if ratio else 'empty'
        amount, status = f'{total-left}/{total}', f'Взять {left}' if left else 'Готов'
        detail = f'<p class="dg-stamp">Battle.net · {stamp(record["time"])}</p>'
        for label, rows, opened in [('Не взяты',missing,True), ('В журнале',active,False), ('Сданы',done,False)]:
            if rows:
                detail += f'<details class="dg-quest-list"'+(' open' if opened else '')+f'><summary>{label} · {len(rows)}</summary>{quest_groups(rows, level)}</details>'
            else:
                detail += f'<p class="dg-zero">{label} · 0</p>'
    name = escape(hero['name'])
    owner = escape(hero['owner'])
    char_class = escape(cls.get('slug',''),quote=True)
    body = f'''<details class="dg-member is-{kind}" name="members-{dungeon["id"]}" data-member="{escape(key,quote=True)}">
<summary class="dg-line"><span class="dg-person"><i class="dg-dot class-{char_class}" aria-hidden="true"></i><span class="dg-name">{name}</span><small class="dg-owner">{owner}</small></span><span class="dg-score"><i class="dg-bar" aria-hidden="true"><i style="width:{max(0,ratio)*100:.2f}%"></i></i><b>{amount}</b></span><span class="dg-state">{status}</span></summary>
<div class="dg-body"><div class="dg-profile">{owner} · {escape(cls.get("name","—"))} · {level if level is not None else "—"} ур.</div>{detail}</div></details>'''
    return ratio, body


def report(d, heroes, records):
    rows = [(member(d, h, records.get(character_key(h['name']))), h['name']) for h in heroes]
    rows.sort(key=lambda item:(-item[0][0],item[1].casefold()))
    complete = sum(score == 1 for (score, _), _ in rows)
    group = ''.join(row for (_, row), _ in rows)
    outside = [q for q in d['quests'] if not q['inside']]
    inside = len(d['quests']) - len(outside)
    counts = {sum(applies(q, (h['character'].get('class') or {}).get('name')) for q in outside) for h in heroes if h.get('character')}
    before = '—' if not counts else str(min(counts)) if len(counts)==1 else f'{min(counts)}–{max(counts)}'
    sources = ' · '.join(f'<a target="_blank" rel="noopener noreferrer" href="{escape(url,quote=True)}">{escape(url.split("/")[2].removeprefix("www."))}</a>' for url in d['sources'])
    return f'''<section class="dg-report dg-{d["id"]}" id="dg-report-{d["id"]}" data-report="{d["id"]}" aria-label="{escape(d["name"],quote=True)}">
<header class="dg-report-head"><div><div class="dg-zone">{escape(d["zone"])}</div><h2>{escape(d["name"])}</h2></div><div class="dg-total"><strong>{complete}<small>/{len(heroes)}</small></strong><span>полностью готовы</span></div></header>
<p class="dg-legend">До входа <b>{before}</b> · Внутри данжа <b>{inside}</b><span>Засчитаны взятые и сданные квесты для класса героя.</span></p>
<div class="dg-colheads dg-line" aria-hidden="true"><span>Герой</span><span>До входа</span><span>Статус</span></div>
<div class="dg-people">{group}</div><details class="dg-guide"><summary>Где взять квесты</summary>{quest_groups(d["quests"])}<div class="dg-refs">{sources}</div></details></section>'''


def add_dungeons(page, heroes, catalog, snapshot):
    records = snapshot.get('heroes', {})
    times = [r['time'] for r in records.values()]
    when = stamp(max(times)) if times else 'нет снимка'
    radios = ''.join(f'<input type="radio" class="dg-radio" name="dungeon" id="pick-{d["id"]}" aria-controls="dg-report-{d["id"]}" '+('checked' if d['id']=='wc' else '')+'>' for d in catalog)
    tabs = ''.join(f'<label for="pick-{d["id"]}" class="dg-{d["id"]}">{escape(d["name"])}</label>' for d in catalog)
    nav = '<span id="heroes"></span><nav class="sqc-tabs" aria-label="Раздел страницы"><a href="#heroes">Heroes</a><a href="#dungeons">Dungeons</a></nav>'
    box = (f'<section id="sq-dungeons" aria-label="Подземелья"><div class="dg-toolbar"><h1>Подземелья</h1><small>Battle.net · {when}</small></div>'
           f'<div class="dg-layout">{radios}<div class="dg-switch" role="group" aria-label="Выбор подземелья">{tabs}</div>'
           + ''.join(report(d,heroes,records) for d in catalog) + '</div></section>')
    for marker in ('</style><main>', '</header><h1>', '</main><div id="hover-tip"'):
        if marker not in page:
            raise ValueError('Изменился шаблон страницы: '+marker)
    return (page.replace('</style><main>', (HERE/'styles.css').read_text(encoding='utf-8')+'</style><main>',1)
            .replace('</header><h1>', '</header>'+nav+box+'<div id="sq-heroes"><h1>',1)
            .replace('</main><div id="hover-tip"', '</div></main><div id="hover-tip"',1)
            .replace('<title>Side Quest Company — Сравнение героев</title>', '<title>Side Quest Company · Heroes &amp; Dungeons</title>',1))
