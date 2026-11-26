const fs = require('node:fs');
const recommend = require('./recommend.cjs');

const {heroes, known} = JSON.parse(fs.readFileSync(0, 'utf8'));
const identity = ({key,name}) => ({key,name});
const suggestions = recommend(heroes, known).map(m => ({
  h: identity(m.h),
  r: {id:m.r.id, name:m.r.name, quality:m.r.quality, slot:m.r.slot, recipeUrl:m.r.recipeUrl, icon:m.r.icon},
  makers: m.makers.map(identity),
  old: m.old ? {name:m.old.name, setBonus:m.old.setBonus} : null,
  kind:m.kind, label:m.label, why:m.why, changes:m.changes, effects:m.effects, note:m.note
}));
process.stdout.write(JSON.stringify(suggestions));
