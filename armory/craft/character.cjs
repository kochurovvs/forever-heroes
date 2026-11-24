function armoryItem(item) {
  const stats = {}, flags = [];
  for (const {type, value} of item.stats || []) {
    if (type?.name && Number.isFinite(value)) stats[type.name] = (stats[type.name] || 0) + value;
  }
  if (item.armor) stats.Armor = item.armor.value;
  if (item.weapon?.dps) stats.DPS = item.weapon.dps.value;
  if (item.shield_block) stats['Shield Block'] = item.shield_block.value;
  let setBonus = '';
  if (item.set) {
    const count = item.set.items?.filter(part => part.is_equipped).length;
    if (!count || !Array.isArray(item.set.effects)) flags.push('неизвестен бонус комплекта');
    for (const effect of item.set.effects || []) {
      if (effect.required_count !== count) continue;
      setBonus = effect.display_string || 'бонус комплекта';
      const fixed = setBonus.match(/Set: \+(\d+) ([A-Za-z ]+)\.?$/);
      if (fixed) stats[fixed[2]] = (stats[fixed[2]] || 0) + Number(fixed[1]);
      else flags.push('при снятии пропадёт эффект комплекта');
    }
  }
  for (const effect of item.spells || []) {
    const name = effect.spell?.name || item.name;
    flags.push('не оценён эффект «'+name+'»');
  }
  for (const enchant of item.enchantments || []) {
    const label = (enchant.display_string || '').replace(/^Enchanted: /, '');
    if (/^[a-zA-Z ]+ \+\d+(?: and [a-zA-Z ]+ \+\d+)*$/.test(label)) {
      for (const part of label.split(' and ')) {
        const [name, value] = part.split(' +');
        stats[name] = (stats[name] || 0) + Number(value);
      }
    } else flags.push('не оценены чары «'+(label || 'неизвестно')+'»');
  }
  return {id:item.id, name:item.name, type:item.item_subclass?.name, stats, flags, setBonus, school:item.weapon?.damage?.damage_class?.type};
}

function armoryHero(entry) {
  const c = entry.character;
  if (!c || entry.stale || entry.status !== 'ok') return null;
  const gear = Object.fromEntries(Object.entries(c.gear || {})
    .filter(([, item]) => item?.name)
    .map(([slot, item]) => [slot, armoryItem(item)]));
  const attributes = Object.fromEntries((c.stats?.overview || []).map(stat => [stat.enum, stat.value?.value]));
  const parry = c.stats?.groups?.flatMap(g=>g.stats||[]).find(s=>s.enum==='PARRY')?.value?.value;
  const talents = (c.specs || []).flatMap(tree => tree.talents || []);
  const passive = (name, expression) => {
    const talent = talents.find(t => t.name === name && t.rank > 0);
    const percent = talent?.description?.match(expression)?.[1];
    return Number(percent || 0) / 100;
  };
  const learned = Object.fromEntries(talents.filter(t => t.rank > 0).map(t => [t.name, t.rank]));
  const modifiers = {
    wand: 1 + passive('Wand Specialization', /with Wands by (\d+)%/),
    meditation: passive('Meditation', /Allows (\d+)%/),
    intellect: 1 + passive('Ancestral Knowledge', /Intellect by (\d+)%/) + passive('Mental Strength', /Intellect by (\d+)%/),
    apFromInt: passive('Mental Dexterity', /equal to (\d+)% of your Intellect/),
    mana: 1 + passive('Fel Vitality', /your maximum Mana by (\d+)%/),
    health: c.race?.name === 'Tauren' ? 1.05 : 1
  };
  const aliases = {'Elemental Combat':'Elemental', 'Shadow Magic':'Shadow', 'Holy Combat':'Holy', 'Feral':'Feral Combat'};
  const trees = Object.fromEntries((c.specs || []).map(t => [aliases[t.name] || t.name, t.spentPoints || 0]));
  return {key:c.slug, name:entry.name, owner:entry.owner, cls:c.class?.name, level:c.level, gear, attributes, parry, modifiers, talents:{trees, learned}};
}

module.exports = armoryHero;
