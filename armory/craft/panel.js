function createGuildCraft(matches,armoryAssets,html) {
  const slots = {head:'Head',neck:'Neck',shoulder:'Shoulders',back:'Back',chest:'Chest',wrist:'Wrist',hand:'Hands',waist:'Waist',leg:'Legs',foot:'Feet',weapon:'Main Hand',offhand:'Off Hand',ranged:'Ranged'};
  const chances = new Set(['Hit','Critical Strike','Parry']);
  const decimal=new Intl.NumberFormat('ru-RU',{maximumFractionDigits:2});
  const signed=n=>(n<0?'−':'+')+decimal.format(Math.abs(n));
  const icon=key=>{
    const url=armoryAssets.icons[key]||key;
    return url?'<img src="'+html(url)+'" alt="" loading="lazy">':'';
  };

  const received=new Map(), offered=new Map();
  for (const m of matches) {
    if (!received.has(m.h.key)) received.set(m.h.key,[]);
    received.get(m.h.key).push(m);
    for (const maker of m.makers) {
      if (!offered.has(maker.key)) offered.set(maker.key,[]);
      offered.get(maker.key).push(m);
    }
  }
  for (const orders of offered.values())
    orders.sort((a,b)=>a.h.name.localeCompare(b.h.name)||a.r.slot.localeCompare(b.r.slot));
  const verdictLabels={
    'Уверенная замена':{text:'Явно лучше',icon:'up',why:'Расчёт показывает преимущество перед надетой вещью.'},
    'Для ближних ударов':{text:'Ближний бой',icon:'sword',why:'Замена даёт преимущество при ударах в ближнем бою.'},
    'Для дальних атак':{text:'Дальний бой',icon:'bow',why:'Замена даёт преимущество при стрельбе из оружия.'},
    'Для урона заклинаниями':{text:'Заклинания',icon:'magic',why:'Замена усиливает урон от заклинаний.'},
    'Для ударов в облике кошки':{text:'В кошке',icon:'paw',why:'Преимущество проявляется в облике кошки.'},
    'Для защиты со щитом':{text:'Со щитом',icon:'shield',why:'Замена полезна, когда персонаж носит щит.'},
    'Для долгого лечения':{text:'Лечение',icon:'heal',why:'Замена полезна для продолжительного лечения.'},
    'Для стрельбы жезлом':{text:'Жезл',icon:'wand',why:'Преимущество относится к атакам жезлом.'},
    'Зависит от боя':{text:'По ситуации',icon:'approx',why:'Условия боя определяют, какая вещь окажется лучше.'},
    'Малый перевес':{text:'На грани',icon:'approx',tone:'narrow',why:'Выигрыш по одним характеристикам близок к потерям по другим.'},
    'Нужны данные':{text:'Неясно',icon:'unknown',tone:'unknown',why:'Для уверенного сравнения пока не хватает данных.'}
  };
  const shapes={
    up:'<path d="M6 1 11 6H7.3v5H4.7V6H1z"/>',
    sword:'<path d="m10.9.9-.65 3.45-5.1 4.95-1.45-1.5L8.7 2z"/><path d="m2.5 6.5 3.2 3.2M3.95 8.1 1.4 10.65" fill="none" stroke="currentColor" stroke-width="1.55" stroke-linecap="round"/>',
    bow:'<g fill="none" stroke="currentColor" stroke-linecap="round" stroke-linejoin="round"><path d="M1.5 3C5 .3 11.7 6.3 9.3 10.8" stroke-width="1.55"/><path d="m1.5 3 7.8 7.8" stroke-width=".85"/><path d="m2 10 8.2-8.2M7.8 1.8h2.4v2.4" stroke-width="1.3"/></g>',
    magic:'<path d="m4.5 1.2 1.15 3.1L8.8 5.5 5.65 6.7 4.5 10 3.3 6.7.2 5.5l3.1-1.2zM9.4.2l.65 1.7 1.7.65-1.7.7L9.4 5l-.7-1.75L7 2.55l1.7-.65zM9.6 7.7l.53 1.32 1.35.53-1.35.5-.53 1.35-.5-1.35-1.36-.5 1.36-.53z"/>',
    paw:'<ellipse cx="1.85" cy="5.1" rx="1.15" ry="1.6"/><ellipse cx="4.25" cy="2.75" rx="1.2" ry="1.7"/><ellipse cx="7.65" cy="2.75" rx="1.2" ry="1.7"/><ellipse cx="10.1" cy="5.1" rx="1.15" ry="1.6"/><path d="M6 5.4c1.45 0 2.03 1.4 3.05 2.55 1.45 1.7.55 3.15-1.15 2.88-.85-.12-1.23-.5-1.9-.5s-1.07.38-1.9.5c-1.75.26-2.6-1.25-1.14-2.88C3.96 6.82 4.55 5.4 6 5.4z"/>',
    shield:'<path fill-rule="evenodd" d="m6 .7 4.7 1.65v3.2c0 2.7-2.5 4.9-4.7 5.85-2.2-.95-4.7-3.15-4.7-5.85v-3.2zm0 1.65v7.3c1.75-1.05 3.2-2.55 3.2-4.3V3.4z"/>',
    heal:'<path d="M4.3 1h3.4v3.3H11v3.4H7.7V11H4.3V7.7H1V4.3h3.3z"/>',
    wand:'<path d="M1.4 10.6 7 5" stroke="currentColor" stroke-width="1.85" stroke-linecap="round"/><path d="m8.8.2.8 2.4 2.35.8-2.35.85-.8 2.3-.88-2.3-2.3-.85 2.3-.8zM3 1l.42 1.2 1.18.48-1.18.45L3 4.3l-.48-1.17-1.15-.45 1.15-.48z"/>'
  };
  function verdictFor(m) {
    return verdictLabels[m.label] || verdictLabels['Нужны данные'];
  }
  function verdictClass(v) {
    return 'wc-'+(v.tone || 'improvement');
  }
  function glyph(v) {
    if (v.icon==='approx' || v.icon==='unknown') return '<span class="wc-glyph wc-sign" aria-hidden="true">'+(v.icon==='approx'?'≈':'?')+'</span>';
    return '<svg class="wc-glyph" viewBox="0 0 12 12" aria-hidden="true" focusable="false" fill="currentColor">'+shapes[v.icon]+'</svg>';
  }
  function badge(v) {
    return '<span class="wc-badge" aria-hidden="true">'+glyph(v)+'</span>';
  }
  function verdictText(v) {
    return '<span class="wc-verdict '+verdictClass(v)+'">'+glyph(v)+' '+html(v.text)+'</span>';
  }
  function renderColorKey(heroKey) {
    const types=new Set((received.get(heroKey)||[]).map(verdictFor));
    if (!types.size) return '';
    const entries=Object.values(verdictLabels).filter(v=>types.has(v)).map(v=>
      '<button type="button" class="wc-key-entry '+verdictClass(v)+'" data-tip="'+html(v.text)+'">'+badge(v)+html(v.text)+'</button>'+
      '<template class="wc-tip"><div class="wc-craft-title">'+verdictText(v)+'</div><div class="wc-line">'+html(v.why)+'</div></template>');
    return '<div class="wc-color-key" role="group" aria-label="Типы замен"><span class="wc-key-label">Типы замен</span><div class="wc-key-items">'+entries.join('')+'</div></div>';
  }
  function best(key) {return received.get(key)?.[0];}
  function deltas(entries) {
    return entries.map(({value,direction,label,unit=''})=>{
      const n=direction??value;
      const number=direction ? (n>0?'↑':'↓') : signed(n)+unit;
      return '<span class="wc-number '+(n>0?'wc-up':'wc-down')+'">'+html(number)+'</span> '+html(label);
    }).join(' · ');
  }
  function itemTitle(m,link=false) {
    const name=html(m.r.name);
    const item=link ? '<a class="wc-item-name" href="'+html(m.r.recipeUrl)+'" target="_blank" rel="noopener noreferrer">'+name+'</a>' :
      '<span class="wc-item-name">'+name+'</span>';
    return '<span class="wc-craft-title">'+item+' '+verdictText(verdictFor(m))+'</span>';
  }
  function detailsMarkup(m,full) {
    const raw=m.changes.map(c=>({label:c.stat,value:c.diff,unit:chances.has(c.stat)?' п.п.':''}));
    const line=(label,value)=>'<div class="wc-line"><span class="wc-heading">'+label+'</span> '+value+'</div>';
    const title=full?'<span class="wc-tip-label">Сейчас надето · '+html(slots[m.r.slot])+'</span>'+
      '<span class="wc-tip-equipped">'+html(m.old?.name||'Пустой слот')+'</span>'+
      '<span class="wc-tip-label wc-tip-suggestion">Рекомендуемая замена</span>'+itemTitle(m):'';
    return title+'<div class="wc-why">'+html(m.why)+'</div>'+
      (full?line('На предмете ·',deltas(raw)):'')+
      (m.effects.length?line('На герое ·',deltas(m.effects)):(!full?line('На предмете ·',deltas(raw)):''))+
      (m.note?'<div class="wc-talent">'+html(m.note)+'</div>':'')+
      (m.old?.setBonus?line('При снятии ·',html(m.old.setBonus)):'')+
      (full?line('Мастер ·',html(m.makers.map(h=>h.name).join(', '))):'');
  }
  function renderSlotPair(heroKey,slot,equipped) {
    const incoming=received.get(heroKey);
    if (!incoming?.length) return equipped;
    const m=incoming.find(m=>m.r.slot===slot);
    let button='';
    if (m) {
      const verdict=verdictFor(m);
      const quality=qualityColors[String(m.r.quality||'').toUpperCase()]||'#998e77';
      const label='Рекомендуемая замена · '+m.r.name+' · '+slots[slot]+' · '+verdict.text;
      button='<button type="button" class="wc-candidate '+verdictClass(verdict)+'" style="--quality:'+quality+'" data-tip="'+html(label)+'" aria-label="'+html(label)+'">'+
        '<span class="slot-icon">'+icon(m.r.icon)+'</span>'+
        badge(verdict)+'</button><template class="wc-tip">'+detailsMarkup(m,true)+'</template>';
    }
    return '<div class="wc-slot-pair">'+equipped+button+'</div>';
  }
  function renderPanel(entry) {
    const orders=offered.get(entry.character?.slug);
    if (!orders?.length) return '';
    const label=html('Кому может помочь '+entry.name);
    const items=orders.map(m=>'<li>'+icon(m.r.icon)+'<div class="wc-order">'+itemTitle(m,true)+'<p>'+html(m.h.name+' · '+slots[m.r.slot]+' · '+(m.old?'вместо '+m.old.name:'пустой слот'))+'</p>'+
      '<div class="wc-effects">'+detailsMarkup(m,false)+'</div></div></li>').join('');
    return '<section class="wc-panel" aria-label="'+label+'"><details class="wc-extra"><summary>'+label+' <span>· '+orders.length+
      '</span></summary><ul>'+items+'</ul></details></section>';
  }
  return {best,renderPanel,renderSlotPair,renderColorKey};
}
