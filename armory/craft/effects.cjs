const STAT_RATES = require('./stat-rates.json');

// Changes on the character sheet, with current passive bonuses applied only to the swap.
function resourceChange(current, change, perPoint) {
  if (!change) return 0;
  if (!Number.isFinite(current)) return null;
  const fromAttribute = value => Math.min(value, 20) + Math.max(value - 20, 0) * perPoint;
  return fromAttribute(current + change) - fromAttribute(current);
}
function effectiveAttributeChange(current, delta, multiplier) {
  if (!delta || multiplier === 1) return delta;
  const raw = Math.ceil(current / multiplier - 1e-8);
  const integer = value => Math.floor(value * multiplier + 1e-8);
  return Number.isFinite(current) && integer(raw) === current
    ? integer(raw + delta) - current : null;
}
const schools = ['Fire','Frost','Arcane','Nature','Shadow','Holy'];
function project(h, r, changes) {
  const raw = Object.fromEntries(changes.map(row => [row.stat, row.diff]));
  const delta = stat => raw[stat] || 0;
  const rates = STAT_RATES.classes[h.cls];
  const manaUser = !['Rogue','Warrior'].includes(h.cls);
  const hasShield = h.gear.offhand?.type === 'Shield';
  const agi = delta('Agility'), str = delta('Strength'), spirit = delta('Spirit');
  const int = effectiveAttributeChange(h.attributes.INTELLECT,delta('Intellect'),h.modifiers.intellect);
  const resource = (attr, change, perPoint, flat, multiplier) => {
    const diff = change === null ? null : resourceChange(h.attributes[attr],change,perPoint);
    return diff === null ? null : Math.sign(diff+flat)*Math.round(Math.abs((diff+flat)*multiplier));
  };
  const crit = (base, change, rate) => change === 0 ? base :
    (change !== null && Number.isFinite(rate) ? base + change*rate : null);
  const melee = rates && (h.modifiers.apFromInt === 0 || int !== null)
    ? delta('Attack Power') + str*rates.meleeApPerStr + agi*rates.meleeApPerAgi + (int || 0)*h.modifiers.apFromInt : null;
  const p = {
    hp:resource('STAMINA',delta('Stamina'),10,delta('Health'),h.modifiers.health),
    mana:manaUser ? resource('INTELLECT',int,15,delta('Mana'),h.modifiers.mana) : 0,
    armor:delta('Armor')+delta('Bonus Armor')+2*agi,
    melee, ranged: rates?.rangedApPerAgi ? delta('Attack Power')+delta('Ranged Attack Power')+agi*rates.rangedApPerAgi : 0,
    cat:melee === null ? null : melee+agi*(rates?.catApPerAgi || 0),
    physicalCrit:crit(delta('Critical Strike'),agi,rates?.meleeCritPerAgi?.[h.level]),
    spellCrit:manaUser ? crit(delta('Critical Strike'),int,rates?.spellCritPerInt?.[h.level]) : 0,
    damage:delta('Spell Power')+delta('Spell Damage'), healing:delta('Spell Power')+delta('Spell Healing'),
    hit:delta('Hit'), weapon:delta('DPS')*(r.type==='Wand' ? h.modifiers.wand : 1),
    mp5:manaUser ? delta('Mana Regeneration per 5 sec') : 0, hp5:delta('Health Per 5 Sec.'),
    block:hasShield ? delta('Block') : 0, blockValue:hasShield ? delta('Shield Block') : 0,
    parry:Number.isFinite(h.parry) ? Math.max(0,h.parry+delta('Parry'))-h.parry : (delta('Parry') ? null : 0),
    defense:delta('Defense'), spirit, manaUser
  };
  for (const school of schools) p[school]=p.damage+delta(school+' Damage');
  const effects = [];
  const add = (label,value,unit='') => {
    if (Number.isFinite(value) && Math.abs(value)>=0.005) effects.push({label,value,unit});
  };
  add('HP',p.hp); add('маны',p.mana); add(h.cls==='Druid'?'брони вне формы':'брони',p.armor);
  add('силы атаки вблизи',melee);
  if (h.cls==='Druid') add('силы атаки в облике кошки',p.cat);
  if (rates?.rangedApPerAgi) add('силы атаки вдаль',p.ranged);
  add('физ. крита',p.physicalCrit,' п.п.'); add('крита заклинаний',p.spellCrit,' п.п.');
  if (p.damage===p.healing) add('к силе заклинаний',p.damage);
  else { add('к урону заклинаний',p.damage); add('к исцелению',p.healing); }
  add('к меткости до порога',p.hit,' п.п.');
  add(r.type==='Wand'?'DPS при стрельбе жезлом':'DPS оружия',p.weapon);
  add('к защите',p.defense); add('к рейтингу блока',p.block); add('к величине блока',p.blockValue);
  add('к шансу парирования',p.parry,' п.п.');
  for (const school of schools) {
    add(school+' Damage',delta(school+' Damage')); add(school+' Resistance',delta(school+' Resistance'));
  }
  add('силы атаки против зверей',delta('Attack Power Vs Beasts'));
  add('HP за 5 с',p.hp5); add('маны за 5 с',p.mp5);
  if (spirit) {
    const direction = Math.sign(spirit);
    effects.push({label:'реген HP вне боя',direction});
    if (manaUser) effects.push({label:'реген маны от Spirit после 5 с без затрат маны',direction});
    if (h.modifiers.meditation) effects.push({label:'реген от Spirit во время каста · Meditation',direction});
  }
  return {values:p,effects};
}

module.exports = project;
