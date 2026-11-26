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
  const verdictSigns={direct:'✓',role:'◇',marginal:'≈',unknown:'?'};
  const verdictLabels={
    'Уверенная замена':{text:'Явно лучше'}, 'Для ближних ударов':{text:'Ближний бой',tone:'melee'},
    'Для дальних атак':{text:'Дальний бой',tone:'ranged'}, 'Для урона заклинаниями':{text:'Заклинания'},
    'Для ударов в облике кошки':{text:'В кошке',tone:'cat'}, 'Для защиты со щитом':{text:'Со щитом',tone:'shield'},
    'Для долгого лечения':{text:'Лечение',tone:'healing'}, 'Для стрельбы жезлом':{text:'Жезл',tone:'wand'},
    'Зависит от боя':{text:'По ситуации'}, 'Малый перевес':{text:'На грани',tone:'narrow'}, 'Нужны данные':{text:'Неясно'}
  };
  function verdictClasses(m) {
    const tone=verdictLabels[m.label]?.tone;
    return 'wc-'+m.kind+(tone?' wc-'+tone:'');
  }
  function markerBadge(m) {
    const useVerdictSign=m.kind==='unknown' || m.label==='Малый перевес';
    const symbol=useVerdictSign ? verdictSigns[m.kind] : '';
    return '<span class="wc-arrow-badge" aria-hidden="true">'+symbol+'</span>';
  }
  function renderColorKey(heroKey) {
    const types=new Map((received.get(heroKey)||[]).map(m=>[m.label,m]));
    if (!types.size) return '';
    const entries=Array.from(types.values(),m=>'<span class="wc-key-entry '+verdictClasses(m)+'">'+
      markerBadge(m)+html(verdictLabels[m.label]?.text||m.label)+'</span>');
    return '<div class="wc-color-key" role="group" aria-label="Типы замен"><span>Тип замены</span>'+entries.join('')+'</div>';
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
    const verdict='<span class="wc-verdict '+verdictClasses(m)+'"><span aria-hidden="true">'+verdictSigns[m.kind]+'</span> '+
      html(verdictLabels[m.label]?.text||m.label)+'</span>';
    return '<span class="wc-craft-title">'+item+' '+verdict+'</span>';
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
      const quality=qualityColors[String(m.r.quality||'').toUpperCase()]||'#998e77';
      const label='Рекомендуемая замена · '+m.r.name+' · '+slots[slot]+' · '+m.label;
      button='<button type="button" class="wc-candidate '+verdictClasses(m)+'" style="--quality:'+quality+'" data-tip="'+html(label)+'" aria-label="'+html(label)+'">'+
        '<span class="slot-icon">'+icon(m.r.icon)+'</span>'+
        markerBadge(m)+'</button><template class="wc-tip">'+detailsMarkup(m,true)+'</template>';
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
