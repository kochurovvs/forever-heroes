(() => {
  'use strict';
  const {heroes, events, asOf, catalogDungeons} = JSON.parse(document.getElementById('cc-data').textContent);
  const root = document.getElementById('cc-preview');
  const node = (tag, cls, label) => {
    const item = document.createElement(tag);
    if (cls) item.className = cls;
    if (label !== undefined) item.textContent = label;
    return item;
  };
  const byId = id => document.getElementById('cc-' + id);
  const options = (select, pairs) => select.replaceChildren(...pairs.map(([value, label]) => new Option(label, value)));
  const names = Object.keys(heroes).sort((a,b) => a.localeCompare(b, 'en'));
  const date = new Intl.DateTimeFormat('ru-RU', {timeZone:'Asia/Jerusalem', day:'numeric', month:'short'});
  const time = new Intl.DateTimeFormat('ru-RU', {timeZone:'Asia/Jerusalem',hour:'2-digit',minute:'2-digit',second:'2-digit',hourCycle:'h23'});
  const format = t => date.format(t) + ' · ' + time.format(t);
  const heroSelect = byId('hero'), dungeonSelect = byId('dungeon'), rawSelect = byId('raw-hero');
  const heroOptions = names.map(name => [name, name + ' · ' + heroes[name].owner]);
  options(heroSelect,[['','Вся компания'], ...heroOptions]);
  options(rawSelect,heroOptions);
  const observed = Array.from(new Set([...catalogDungeons, ...Object.values(heroes).flatMap(h => h.bosses.map(b => b.dungeon))])).sort();
  options(dungeonSelect,[['','Все подземелья'], ...observed.map(name => [name,name])]);
  const first = heroes['Dargor Springhill'] ? 'Dargor Springhill' : names[0];
  heroSelect.value = rawSelect.value = first;
  let companion = '';

  function person(name, className, tag = 'div') {
    const h = heroes[name], wrap = node(tag,className), img = node('img','cc-port');
    if (tag === 'button') wrap.type = 'button';
    img.src = h.portrait; img.alt = ''; img.width = img.height = 37;
    const txt = node('div');
    txt.append(node('div','cc-name',name), node('div','cc-owner',h.owner + ' · ' + h.cls));
    wrap.append(img,txt); return wrap;
  }
  function chooseCompanion(name) {
    if (!heroSelect.value) { heroSelect.value = name; companion = ''; }
    else companion = name === companion ? '' : name;
    render();
  }
  function record(event, selected) {
    const card = node('article','cc-event'), head = node('div','cc-event-top');
    const stamp = node('time','cc-date',format(event.timestamp)); stamp.dateTime = new Date(event.timestamp).toISOString();
    head.append(node('span','cc-kicker',event.dungeon),stamp);
    card.append(head,node('div','cc-boss',event.boss));
    const party = node('div','cc-party');
    for (const name of event.heroes) {
      const active = name === selected, member = person(name,'cc-person' + (active || name === companion ? ' active' : ''),active ? 'div' : 'button');
      if (!active) {
        member.setAttribute('aria-label',(selected ? 'Выбрать напарника ' : 'Показать встречи героя ') + name);
        member.setAttribute('aria-pressed',String(name === companion));
        member.onclick = () => chooseCompanion(name);
      }
      party.append(member);
    }
    const proof = node('details','cc-proof');
    proof.append(node('summary','', 'Основание совпадения'),node('p','','У всех перечисленных героев Battle.net вернул один ID босса (' + event.id + ') и одинаковое время обновления счётчика — ' + format(event.timestamp) + ' по Израилю. Боевой лог к записи не привязан.'));
    card.append(party,proof); return card;
  }
  function render() {
    const selected = heroSelect.value, dungeon = dungeonSelect.value;
    const visible = events.filter(e => (!dungeon || e.dungeon === dungeon) && (!selected || e.heroes.includes(selected)));
    const peers = names.filter(name => name !== selected && visible.some(e=>e.heroes.includes(name)));
    if (!peers.includes(companion)) companion = '';
    const identity = byId('identity');
    if (selected) {
      const el = person(selected,'cc-ident'); el.querySelector('.cc-name').className='cc-identityname';
      el.querySelector('.cc-owner').className='cc-hero-note'; identity.replaceChildren(el);
      rawSelect.value = selected;
    } else {
      const el=node('div','cc-ident');el.append(node('div','cc-identityname','Side Quest Company'));
      identity.replaceChildren(el);
    }
    root.querySelector('.cc-aside h3').textContent=selected?'Напарники':'Герои в записях';
    byId('companions').replaceChildren(...peers.map(name => {
      const btn = person(name,'cc-comp','button');
      btn.setAttribute('aria-pressed',String(name === companion));btn.onclick=()=>chooseCompanion(name);return btn;
    }));
    if (!peers.length) byId('companions').append(node('p','cc-empty','В этом срезе нет совпадающих отметок.'));
    const pair = byId('pair');pair.replaceChildren();
    if (companion) {
      const tag = node('div','cc-pairtag'), clear = node('button','cc-clear','Сбросить пару');clear.type='button';
      clear.onclick=()=>{companion='';render()};
      tag.append(node('span','',selected + ' + ' + companion),clear); pair.append(tag);
    }
    const filtered = visible.filter(e => !companion || e.heroes.includes(companion));
    byId('count').textContent = 'Отметок: ' + filtered.length;
    byId('events').replaceChildren(...filtered.map(e=>record(e,selected)));
    if (!filtered.length) byId('events').append(node('p','cc-empty','В выгрузке нет общей отметки босса для этого выбора. Более ранние встречи могли исчезнуть после повторного убийства.'));
    rawStats();
  }
  function rawStats() {
    const h = heroes[rawSelect.value], box = byId('raw-fields');box.replaceChildren();
    if (!h) return;
    if (h.status !== 'ok') { box.append(node('p','cc-empty','Профиль статистики недоступен.'));return; }
    const entries = [...h.counters, ...h.bosses.map(b=>({...b, label: b.boss + ' · ' + b.dungeon}))];
    if (!entries.length) box.append(node('p','cc-empty','В ответе по этому герою нет заполненных счётчиков подземелий.'));
    entries.forEach(r=>{
      const row=node('div','cc-statline');row.append(node('span','',r.label),node('span','',String(r.quantity)+(r.timestamp?' · '+format(r.timestamp):'')));box.append(row);
    });
  }
  const preparation = document.querySelector('#sq-dungeons > .dg-layout');
  const toolbarStamp = document.querySelector('#sq-dungeons > .dg-toolbar small');
  const questStamp = toolbarStamp.textContent;
  toolbarStamp.textContent = 'Тестовая версия';
  for (const button of root.querySelectorAll('[data-cc-mode]')) button.onclick=()=>{
    const mode=button.dataset.ccMode;
    toolbarStamp.textContent = mode === 'quests' ? questStamp : 'Тестовая версия';
    for (const other of root.querySelectorAll('[data-cc-mode]')) other.setAttribute('aria-pressed',String(other===button));
    byId('company').hidden=mode!=='company';byId('catalog').hidden=mode!=='catalog';preparation.hidden=mode!=='quests';
  };
  heroSelect.onchange=()=>{companion='';render()};
  dungeonSelect.onchange=render;rawSelect.onchange=rawStats;
  preparation.hidden=true;render();
  byId('asof').textContent='Выгрузка Battle.net: '+format(new Date(asOf))+' · время Израиля.';
})();
