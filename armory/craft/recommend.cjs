const catalog = require('./recipes.json');
const {classes} = require('./weights.json');
const project = require('./effects.cjs');
const armoryHero = require('./character.cjs');

const armorTypes = {Warrior:'Mail',Paladin:'Mail',Rogue:'Leather',Hunter:'Leather',Druid:'Leather',Shaman:'Leather',Mage:'Cloth',Priest:'Cloth',Warlock:'Cloth'};

// Pawn supplies a tie-breaker and a fallback for mixed trades; it cannot prove a verdict.
function fallbackWeights(h) {
  const entries = Object.entries(h.talents.trees).filter(([,points])=>points>0);
  const total = entries.reduce((sum,[,points])=>sum+points,0);
  const scale = {};
  for (const [tree,points] of entries) {
    const weights = classes[h.cls]?.[tree]?.[h.level<60?'leveling':'max'];
    if (!weights) return {};
    for (const [stat,weight] of Object.entries(weights)) scale[stat]=(scale[stat]||0)+weight*points/total;
  }
  return scale;
}
function wearable(h,r) {
  if (h.level<r.level || !r.slot) return false;
  if (r.slot==='back') return true;
  if (r.slot==='ranged') return (r.type==='Wand' && ['Mage','Priest','Warlock'].includes(h.cls)) ||
    (r.type==='Gun' && ['Hunter','Warrior','Rogue'].includes(h.cls) && h.gear.ranged?.type==='Gun');
  let type=armorTypes[h.cls];
  if (h.level>=40 && ['Hunter','Shaman'].includes(h.cls)) type='Mail';
  if (h.level>=40 && ['Warrior','Paladin'].includes(h.cls)) type='Plate';
  return r.type===type;
}
function statsPair(old,r) {
  const before={...old?.stats}, after={...r.stats};
  // Equipped Blizzard hit ratings and Forever catalog chance values use different units.
  if (before.Hit) before.Hit/=10;
  if (before['Spell Damage'] || after['Spell Damage'] || before['Spell Healing'] || after['Spell Healing']) {
    for (const stats of [before,after]) {
      if (stats['Spell Healing'] && stats['Spell Damage']===undefined) stats['Spell Damage']=Math.round(stats['Spell Healing']/3);
      if (stats['Spell Power']) {
        for (const key of ['Spell Damage','Spell Healing']) stats[key]=(stats[key]||0)+stats['Spell Power'];
        delete stats['Spell Power'];
      }
    }
  }
  return [before,after];
}

const spellSchools = {Mage:['Fire','Frost','Arcane'],Warlock:['Fire','Shadow'],Priest:['Holy','Shadow'],
  Druid:['Nature','Arcane'],Shaman:['Nature','Fire','Frost'],Paladin:['Holy']};
// Each scenario compares the direction of all its action metrics. Do not add AP, crit and mana together.
function actionProfiles(h,r) {
  const t=h.talents.trees, learned=h.talents.learned, profiles=[];
  const add=(label,axes)=>profiles.push({label,axes});
  if (!Object.keys(learned).length) return profiles;
  if (h.cls==='Hunter' && h.gear.ranged) add('Для дальних атак',['ranged','physicalCrit','hit','weapon']);
  if (r.type==='Wand') add('Для стрельбы жезлом',['weapon','hit','wandCrit']);
  if (h.cls==='Druid' && t['Feral Combat']) add('Для ударов в облике кошки',['cat','physicalCrit','hit']);
  if (['Warrior','Rogue'].includes(h.cls) || t.Enhancement || t.Retribution)
    add('Для ближних ударов',['melee','physicalCrit','hit']);
  if (spellSchools[h.cls] && (['Mage','Priest','Warlock'].includes(h.cls) || t.Elemental || t.Balance || t.Holy))
    add('Для урона заклинаниями',[...spellSchools[h.cls],'spellCrit','hit']);
  if (t.Holy || t.Restoration || learned.Meditation)
    add('Для долгого лечения',['healing','mana','mp5','spirit','spellCrit']);
  if (h.gear.offhand?.type==='Shield' && (t.Protection || learned['Shield Specialization']))
    add('Для защиты со щитом',['hp','armor','defense','block','blockValue','parry','avoidance']);
  // Overlapping roles stay separate. Prefer the role suggested by the current investment.
  const relevance = {
    'Для долгого лечения':Math.max(t.Holy||0,t.Restoration||0,learned.Meditation ? t.Discipline||0 : 0),
    'Для ближних ударов':Math.max(t.Enhancement||0,t.Arms||0,t.Fury||0,t.Retribution||0,t.Combat||0,t.Assassination||0),
    'Для защиты со щитом':t.Protection||0, 'Для ударов в облике кошки':t['Feral Combat']||0,
    'Для урона заклинаниями':Math.max(t.Elemental||0,t.Shadow||0,t.Fire||0,t.Frost||0,t.Arcane||0,t.Destruction||0,t.Affliction||0,t.Balance||0),
    'Для стрельбы жезлом':learned['Wand Specialization']||0,
    'Для дальних атак':Math.max(t.Marksmanship||0,t['Beast Mastery']||0,t.Survival||0)
  };
  return profiles.sort((a,b)=>relevance[b.label]-relevance[a.label]);
}
function talentContext(h,r,raw) {
  const learned=h.talents.learned;
  if (r.type==='Wand' && learned['Wand Specialization'] && raw.DPS)
    return 'Wand Specialization '+learned['Wand Specialization']+' · урон жезла +'+Math.round((h.modifiers.wand-1)*100)+'% во время стрельбы.';
  if (raw.Intellect && learned['Mental Dexterity'])
    return 'Mental Dexterity '+learned['Mental Dexterity']+' · '+Math.round(h.modifiers.apFromInt*100)+'% итогового Intellect переходит в силу атаки.';
  if (raw.Spirit && learned.Meditation)
    return 'Meditation '+learned.Meditation+' · во время каста сохраняется '+Math.round(h.modifiers.meditation*100)+'% регенерации маны.';
  if (raw.Spirit && learned['Spirit Tap']) return 'Spirit Tap '+learned['Spirit Tap']+' · дополнительная отдача от Spirit зависит от убийств.';
  if (raw.Intellect && learned['Fel Vitality']) return 'Fel Vitality '+learned['Fel Vitality']+' · учтён бонус к запасу маны.';
  if (raw.Hit && learned.Precision) return 'Precision '+learned.Precision+' уже действует. Остаток до порога зависит от цели и вида атаки.';
  if ((raw.Intellect || raw['Critical Strike']) && learned['Elemental Devastation'])
    return 'Elemental Devastation '+learned['Elemental Devastation']+' · дополнительный эффект зависит от ближних ударов после крита заклинанием.';
  return '';
}
function missingContext(raw,h) {
  if (raw.DPS) return 'Нужна доля боя, которую герой проводит за стрельбой.';
  if (raw.Spirit && h.talents.learned.Meditation) return 'Знак зависит от длительности лечения и времени между пулами.';
  if (raw.Spirit) return 'Знак зависит от того, как часто герой останавливается для восстановления.';
  if (raw.Intellect && raw['Spell Power']) return 'Знак зависит от используемых заклинаний и от того, заканчивается ли мана.';
  return 'Итог зависит от длительности боя и доли атак или заклинаний.';
}
function compare(h,r,scale) {
  const old=h.gear[r.slot], [before,after]=statsPair(old,r);
  const changes=[];
  let score=0,gross=0;
  for (const stat of new Set([...Object.keys(before),...Object.keys(after)])) {
    const diff=(after[stat]||0)-(before[stat]||0);
    if (Math.abs(diff)<1e-8) continue;
    const key=stat==='DPS'?(r.slot==='ranged'?'Ranged DPS':'Melee DPS'):stat;
    const value=diff*(scale[key]||0)*(stat==='Hit'?10:1);
    score+=value; gross+=Math.abs(value); changes.push({stat,diff});
  }
  if (!changes.some(c=>c.diff>0)) return null;
  const raw=Object.fromEntries(changes.map(c=>[c.stat,c.diff]));
  const {values:p,effects}=project(h,r,changes);
  p.avoidance=raw.Agility||0; // Direction of the Agility component of dodge; no invented percentage.
  p.wandCrit=raw['Critical Strike']||0;
  const positive=v=>Number.isFinite(v) && v>1e-8;
  const contexts=actionProfiles(h,r);
  const good=contexts.find(role=>{
    const values=role.axes.map(k=>p[k]);
    return values.every(v=>Number.isFinite(v) && v>=0) && role.axes.some(k=>k!=='hit' && positive(p[k]));
  });
  const direct=changes.every(c=>c.diff>0);
  const useful=positive(p.hp) || positive(p.armor) || positive(p.mana) || positive(p.mp5) ||
    positive(p.hp5) || positive(p.spirit) || positive(p.weapon) ||
    contexts.some(role=>role.axes.some(k=>k!=='hit' && positive(p[k]))) ||
    (!contexts.length && (positive(p.melee) || positive(p.damage) || positive(p.healing) || positive(p.physicalCrit)));
  const warnings=[...(old?.flags||[])];
  if (raw['Attack Power Vs Beasts']) warnings.push('нужно знать, какая часть боёв проходит против зверей');
  if (raw.Hit && !(direct && useful)) warnings.push('нужны уровень цели и остаток до порога меткости для этой атаки');
  if (raw.Parry && p.parry===null) warnings.push('нет исходного шанса парирования');
  if ([old,r].some(item=>item?.stats['Spell Healing'] && item.stats['Spell Damage']===undefined))
    warnings.push('бонус к урону от лечения оценён как треть, точное значение отсутствует');
  if (raw.Block) warnings.push('неизвестен перевод рейтинга блока в шанс для этого уровня');
  if ((p.hp===null && raw.Stamina) || (p.mana===null && raw.Intellect))
    warnings.push('в оружейной не хватает исходных характеристик для расчёта ресурсов');
  if (!direct && !Object.keys(h.talents.learned).length) warnings.push('в оружейной отсутствуют изученные таланты');
  const candidateSchool=['PHYSICAL','HOLY','FIRE','NATURE','FROST','SHADOW','ARCANE'][r.damage?.school];
  const differentSchool=old && r.type==='Wand' && candidateSchool!==old.school;
  if (differentSchool) warnings.push('нужно знать сопротивление цели школам двух жезлов');
  if (!useful && !(raw.Hit>0 || score>0)) return null;
  if (!direct && !good && score<=0) return null;
  const note=talentContext(h,r,raw);
  let kind,label,why;
  if (warnings.length) {
    kind='unknown';label='Нужны данные';why=warnings.join(' · ').replace(/^./,c=>c.toUpperCase())+'.';
  } else if (direct && useful) {
    kind='direct';label='Уверенная замена';why='Есть полезный прирост, потерь по сравниваемым характеристикам нет.';
  } else if (good) {
    kind='role';label=good.label;
    why=({ 'Для ближних ударов':'Сравнены сила атаки, крит и меткость вблизи.',
      'Для дальних атак':'Сравнены сила дальних атак, крит, меткость и урон оружия.',
      'Для стрельбы жезлом':'Сравнение для непрерывной стрельбы при равном сопротивлении цели.',
      'Для ударов в облике кошки':'Сравнены сила атаки кошки, крит и меткость.',
      'Для урона заклинаниями':'Сравнены бонусы урона по школам класса, крит и меткость.',
      'Для долгого лечения':'Сравнены сила лечения, крит, запас маны и восстановление.',
      'Для защиты со щитом':'Сравнены здоровье, броня, защита и блок с текущим щитом.' })[label];
  } else {
    if (score<=0) return null;
    const narrow=gross>0 && score/gross<=0.15;
    kind='marginal';label=narrow?'Малый перевес':'Зависит от боя';
    why=(narrow?'По весам веток выигрыш близок к потерям. ':'Ориентир по весам веток. ')+missingContext(raw,h);
  }
  return {old,changes,effects,score,kind,label,why,note,scope:good?.label,
    roleOrder:good ? contexts.indexOf(good) : Infinity,
    actionValues:good ? good.axes.map(key=>p[key]) : []};
}
function chooseForSlot(options) {
  const priority={direct:3,role:2,marginal:1,unknown:0};
  const ordered=options.sort((a,b)=>priority[b.kind]-priority[a.kind] || a.roleOrder-b.roleOrder ||
    b.score-a.score || b.r.ilvl-a.r.ilvl || a.r.id-b.r.id);
  // Discard a weaker choice for the same action before using generic stat weights.
  return ordered.find(candidate=>!ordered.some(other=>
    candidate.kind==='role' && other.kind==='role' && candidate.scope===other.scope &&
    other.actionValues.every((value,i)=>value>=candidate.actionValues[i]) &&
    other.actionValues.some((value,i)=>value>candidate.actionValues[i])));

}
function recommend(entries,known) {
  const heroes=entries.map(armoryHero).filter(Boolean);
  const options=new Map();
  for (const h of heroes) {
    const scale=fallbackWeights(h);
    for (const r of catalog) {
      if (!['BoE','unbound'].includes(r.bind) || !wearable(h,r)) continue;
      const old=h.gear[r.slot];
      if (old?.id===r.id || (r.slot==='ranged' && old && old.type!==r.type)) continue;
      const makers=heroes.filter(p=>p.owner!==h.owner && known[p.key]?.[r.profession]?.includes(r.id));
      if (!makers.length) continue;
      const comparison=compare(h,r,scale);
      if (!comparison) continue;
      const key=h.key+'/'+r.slot;
      if (!options.has(key)) options.set(key,[]);
      options.get(key).push({id:h.key+'/'+r.id,h,r,makers,...comparison});
    }
  }
  return [...options.values()].map(chooseForSlot);
}

module.exports = recommend;
