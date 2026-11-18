const leftSlots = [['head','Head'],['neck','Neck'],['shoulder','Shoulders'],['back','Back'],['chest','Chest'],['shirt','Shirt'],['tabard','Tabard'],['wrist','Wrist']];
const rightSlots = [['hand','Hands'],['waist','Waist'],['leg','Legs'],['foot','Feet'],['leftFinger','Ring 1'],['rightFinger','Ring 2'],['leftTrinket','Trinket 1'],['rightTrinket','Trinket 2']];
const weaponSlots = [['weapon','Main Hand'],['offhand','Off Hand'],['ranged','Ranged']];

function renderSlot(gear, [key, label]) {
  const item = gear[key];
  const filled = Boolean(item?.name);
  const color = filled ? (qualityColors[item.quality?.type] || '#ede9db') : '#998e77';
  const asset = item?.media?.content?.assets?.find(a => a.key === 'icon')?.value;
  const iconUrl = filled ? (armoryAssets.icons[asset] || asset) : armoryAssets.slots[key];
  const icon = typeof iconUrl === 'string' && /^(https:\/\/|data:image\/|assets\/)/.test(iconUrl) ? '<img src="'+esc(iconUrl)+'" alt="">' : '';
  const level = item?.level?.value;
  const caption = filled ? item.name : 'Пусто';
  const tip = filled ? [item.name, label + (Number.isFinite(level) ? ' · Item level '+level : ''), itemTooltip(item)].join('\n') : label+' · Пустой слот';
  return '<button type="button" class="paper-slot '+(filled?'occupied':'vacant')+'" style="--quality:'+color+'" data-tip="'+esc(tip)+'" aria-label="'+esc(label+' · '+caption)+'">'+
    '<span class="slot-icon">'+icon+'</span><span class="slot-copy"><small>'+esc(label)+'</small><span>'+esc(caption)+'</span></span></button>';
}

function details(h) {
  const profile = '<a target="_blank" rel="noopener noreferrer" href="'+esc(h.url)+'">В оружейную ↗</a>';
  const c = h.character;
  if (!c) return '<div class="empty">Профиль недоступен. '+profile+'</div>';
  const fullBody = c.render?.foreground?.url || c.media?.['main-raw']?.url;
  const photo = armoryAssets.heroes[fullBody] || fullBody || c.avatar?.url;
  const background = armoryAssets.backgrounds[c.render?.background?.url];
  const appearance = photo ? '<img class="paper-hero" src="'+esc(photo)+'" alt="'+esc(h.name)+'">' : '<span class="no-render">Изображение недоступно</span>';
  const spec = c.specs?.find(s => s.active)?.name;
  const gear = c.gear || {};
  const column = (side, slots) => '<div class="paper-'+side+'">'+slots.map(slot => renderSlot(gear, slot)).join('')+'</div>';
  const weapons = c.showRangedSlot || gear.ranged ? weaponSlots : weaponSlots.slice(0,2);
  const subtitle = [c.race?.name,c.class?.name,spec].filter(Boolean).map(esc).join(' · ');
  const stamp = time(c.lastUpdatedTimestamp?.iso8601);
  return '<section class="armory-sheet" aria-label="Экипировка '+esc(h.name)+'">'+
    '<div class="sheet-top"><div><div class="sheet-kicker">Экипировка</div><h3>'+esc(h.name)+'</h3><p>'+subtitle+'</p></div>'+profile+'</div>'+
    '<div class="paper-stage"'+(background?' style="--backdrop:url('+esc(background)+')"':'')+'>'+
    column('left',leftSlots)+'<div class="paper-figure">'+appearance+'</div>'+column('right',rightSlots)+column('weapons',weapons)+'</div>'+
    '<div class="sheet-foot"><span>Характеристики предмета — при наведении или касании.</span><span>Снимок профиля · '+stamp+' МСК</span></div></section>';
}
