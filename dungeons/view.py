from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path

from .quests import applies, character_key

HERE = Path(__file__).parent


def stamp(iso):
    return datetime.fromisoformat(iso).astimezone(timezone(timedelta(hours=3))).strftime('%d.%m · %H:%M МСК')


def chain_details(q, progress):
    steps = q.get('prereqs', [])
    if not steps:
        return ''
    if q['inside']:
        tip = 'Возьми первое задание до входа. Сдай его внутри, затем возьми продолжение.'
    else:
        tip = 'Сдай предыдущие задания до входа. Пока цепочка не пройдена, принять этот квест от группы нельзя.'
    items = []
    for step in steps:
        state = ''
        if progress is not None:
            active, done = progress
            state = 'Сдан' if step['id'] in done else 'В журнале' if step['id'] in active else 'Не взят'
            state = f' <small>{state}</small>'
        items.append(f'<li><a href="https://www.wowhead.com/forever/quest={step["id"]}" target="_blank" rel="noopener noreferrer">{escape(step["name"])}</a>{state}</li>')
    return f'<div class="dg-chain"><p>{tip}</p><ol>{"".join(items)}</ol></div>'


def quest_card(q, level=None, progress=None):
    tags = []
    if q.get('prereqs'):
        tags.append('<span class="dg-tag chain">Цепочка</span>')
    if q.get('personal'):
        tags.append('<span class="dg-tag">Взять лично</span>')
    if q['inside']:
        tags.append('<span class="dg-tag inner">Внутри данжа</span>')
    if q.get('cls'):
        tags.append('<span class="dg-tag">'+escape(q['cls'])+'</span>')
    if level is not None and q['min'] > level:
        tags.append(f'<span class="dg-tag">С {q["min"]} ур.</span>')
    return (f'<article class="dg-row"><div class="dg-row-head"><a href="https://www.wowhead.com/forever/quest={q["id"]}" rel="noopener noreferrer" target="_blank">{escape(q["name"])}</a>'
            + ''.join(tags) + '</div>' + chain_details(q, progress) + f'<p><b>{escape(q["giver"])}</b> · {escape(q["place"])}</p><p>{escape(q["how"])}</p></article>')


def quest_groups(quests, level=None, progress=None):
    groups = []
    for inside, label in ((False, 'До входа'), (True, 'Внутри данжа')):
        cards = [quest_card(q, level, progress) for q in quests if q['inside'] == inside]
        if cards:
            groups.append(f'<section class="dg-group"><h4>{label} · {len(cards)}</h4>'+''.join(cards)+'</section>')
    return ''.join(groups)


def member(dungeon, hero, record):
    character = hero.get('character') or {}
    cls = character.get('class') or {}
    level = character.get('level')
    available = [q for q in dungeon['quests'] if applies(q, character)]
    key = character_key(hero['name'])
    ratio, kind, amount, status = -1, 'unknown', '—', 'Нет данных'
    blocked = ''
    if record is None or not cls.get('name'):
        detail = '<p>Нет снимка Battle.net для этого героя.</p>'
    else:
        done_ids, active_ids = set(record['done']), set(record['active'])
        done = [q for q in available if q['id'] in done_ids]
        active = [q for q in available if q['id'] in active_ids and q['id'] not in done_ids]
        missing = [q for q in available if q['id'] not in active_ids | done_ids]
        missing.sort(key=lambda q: not bool(q.get('prereqs')))
        needs_chain = any(not q['inside'] and any(step['id'] not in done_ids for step in q.get('prereqs', [])) for q in missing)
        if needs_chain:
            blocked = '<small class="dg-blocked">Цепочка</small>'
        total = sum(not q['inside'] for q in available)
        left = sum(not q['inside'] for q in missing)
        ratio = (total-left)/total if total else 1
        kind = 'ready' if not left else 'partial' if ratio else 'empty'
        amount, status = f'{total-left}/{total}', f'Взять {left}' if left else 'Готов'
        detail = f'<p class="dg-stamp">Battle.net · {stamp(record["time"])}</p>'
        for label, rows, opened in [('Не взяты',missing,True), ('В журнале',active,False), ('Сданы',done,False)]:
            if rows:
                detail += f'<details class="dg-quest-list"'+(' open' if opened else '')+f'><summary>{label} · {len(rows)}</summary>{quest_groups(rows, level, (active_ids, done_ids) if opened else None)}</details>'
            else:
                detail += f'<p class="dg-zero">{label} · 0</p>'
    name = escape(hero['name'])
    owner = escape(hero['owner'])
    char_class = escape(cls.get('slug',''),quote=True)
    body = f'''<details class="dg-member is-{kind}" name="members-{dungeon["id"]}" data-member="{escape(key,quote=True)}">
<summary class="dg-line"><span class="dg-person"><i class="dg-dot class-{char_class}" aria-hidden="true"></i><span class="dg-name">{name}</span><small class="dg-owner">{owner}</small></span><span class="dg-score"><i class="dg-bar" aria-hidden="true"><i style="width:{max(0,ratio)*100:.2f}%"></i></i><b>{amount}</b></span><span class="dg-state">{status}{blocked}</span></summary>
<div class="dg-body"><div class="dg-profile">{owner} · {escape(cls.get("name","—"))} · {level if level is not None else "—"} ур.</div>{detail}</div></details>'''
    return ratio, body


def report(d, heroes, records):
    rows = [(member(d, h, records.get(character_key(h['name']))), h['name']) for h in heroes]
    rows.sort(key=lambda item:(-item[0][0],item[1].casefold()))
    complete = sum(score == 1 for (score, _), _ in rows)
    group = ''.join(row for (_, row), _ in rows)
    outside = [q for q in d['quests'] if not q['inside']]
    inside = len(d['quests']) - len(outside)
    counts = {sum(applies(q, h['character']) for q in outside) for h in heroes if h.get('character')}
    before = '—' if not counts else str(min(counts)) if len(counts)==1 else f'{min(counts)}–{max(counts)}'
    sources = ' · '.join(f'<a target="_blank" rel="noopener noreferrer" href="{escape(url,quote=True)}">{escape(url.split("/")[2].removeprefix("www."))}</a>' for url in d['sources'])
    return f'''<section class="dg-report dg-{d["id"]}" id="dg-report-{d["id"]}" data-report="{d["id"]}" aria-label="{escape(d["name"],quote=True)}">
<header class="dg-report-head"><div><div class="dg-zone">{escape(d["zone"])} · {d['levels'][0]}–{d['levels'][1]} ур.</div><h2>{escape(d["name"])}</h2><div class="dg-recommended">Для группы · {d["recommended"]} ур.</div></div><div class="dg-total"><strong>{complete}<small>/{len(heroes)}</small></strong><span>полностью готовы</span></div></header>
<p class="dg-legend">До входа <b>{before}</b> · Внутри данжа <b>{inside}</b><span>Засчитаны взятые и сданные квесты для класса героя.</span></p>
<div class="dg-colheads dg-line" aria-hidden="true"><span>Герой</span><span>До входа</span><span>Статус</span></div>
<div class="dg-people">{group}</div><details class="dg-guide"><summary>Где взять квесты</summary>{quest_groups(d["quests"])}<div class="dg-refs">{sources}</div></details></section>'''


def add_dungeons(page, heroes, catalog, snapshot):
    records = snapshot.get('heroes', {})
    times = [r['time'] for r in records.values()]
    when = stamp(max(times)) if times else 'нет снимка'
    radios = ''.join(f'<input type="radio" class="dg-radio" name="dungeon" id="pick-{d["id"]}" aria-controls="dg-report-{d["id"]}" '+('checked' if d['id']=='wc' else '')+'>' for d in catalog)
    tabs = []
    for d in catalog:
        planned = '<span class="dg-planned-label">В планах</span>' if d['planned'] else ''
        style = ' dg-planned' if d['planned'] else ''
        tabs.append(f'<label for="pick-{d["id"]}" class="dg-{d["id"]}{style}"><span>{escape(d["name"])}</span><small>{d["levels"][0]}–{d["levels"][1]} ур. {planned}</small></label>')
    tabs = ''.join(tabs)
    css = (HERE/'styles.css').read_text(encoding='utf-8')
    selectors = {
        '__DG_SELECTED__': '#pick-{id}:checked~.dg-switch [for="pick-{id}"]',
        '__DG_FOCUSED__': '#pick-{id}:focus-visible~.dg-switch [for="pick-{id}"]',
        '__DG_VISIBLE__': '#pick-{id}:checked~#dg-report-{id}',
    }
    for marker, selector in selectors.items():
        css = css.replace(marker, ','.join(selector.format(id=d['id']) for d in catalog) or ':not(*)')
    nav = '<span id="dungeons"></span><nav class="sqc-tabs" aria-label="Раздел страницы"><a href="#heroes">Heroes</a><a href="#dungeons">Dungeons</a></nav>'
    box = (f'<section id="sq-dungeons" aria-label="Подземелья"><div class="dg-toolbar"><h1>Подземелья</h1><small>Battle.net · {when}</small></div>'
           f'<div class="dg-layout">{radios}<div class="dg-switch" role="group" aria-label="Выбор подземелья">{tabs}</div>'
           + ''.join(report(d,heroes,records) for d in catalog) + '</div></section>')
    for marker in ('</style><main>', '</header><h1>', '</main><div id="hover-tip"'):
        if marker not in page:
            raise ValueError('Изменился шаблон страницы: '+marker)
    return (page.replace('</style><main>', css+'</style><main>',1)
            .replace('</header><h1>', '</header>'+nav+box+'<div id="sq-heroes"><span id="heroes"></span><h1>',1)
            .replace('</main><div id="hover-tip"', '</div></main><div id="hover-tip"',1)
            .replace('<title>Side Quest Company — Сравнение героев</title>', '<title>Side Quest Company · Heroes &amp; Dungeons</title>',1))
