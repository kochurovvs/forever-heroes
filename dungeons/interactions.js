const mapDialog = document.querySelector('#map-dialog');
let lastMapTrigger;
function displayMap(link) {
  const {zone, x, y, place, who, quest} = link.dataset;
  const zoneMap = armoryAssets.maps[link.dataset.map];
  if (!zoneMap || !mapDialog.showModal) return false;
  lastMapTrigger = link;
  mapDialog.querySelector('h2').textContent = who;
  mapDialog.querySelector('.map-heading small').textContent = quest;
  const art = mapDialog.querySelector('img');
  art.src = zoneMap;
  art.alt = 'Карта '+zone+' с отметкой в точке '+x+', '+y;
  const marker = mapDialog.querySelector('.map-marker');
  marker.style.left = x+'%';
  marker.style.top = y+'%';
  mapDialog.querySelector('.map-caption b').textContent = zone+' · '+x+', '+y;
  mapDialog.querySelector('.map-caption span').textContent = place;
  mapDialog.querySelector('.map-atlas').href = link.href;
  if (!mapDialog.open) mapDialog.showModal();
  return true;
}
document.addEventListener('click', event => {
  const link = event.target.closest('.map-point');
  if (link && !event.metaKey && !event.ctrlKey && !event.shiftKey && displayMap(link)) event.preventDefault();
  if (event.target.closest('.metric-help')) event.preventDefault();
});
mapDialog.querySelector('.map-close').addEventListener('click', () => mapDialog.close());
mapDialog.addEventListener('click', event => {
  if (event.target !== mapDialog) return;
  const r = mapDialog.getBoundingClientRect();
  if (event.clientX<r.left || event.clientX>r.right || event.clientY<r.top || event.clientY>r.bottom) mapDialog.close();
});
mapDialog.addEventListener('close', () => lastMapTrigger?.focus({preventScroll:true}));
function selectExample() {
  const slug = location.hash.match(/^#gear-([a-z0-9-]+)$/)?.[1];
  if (!slug) return;
  const index = DATA.heroes.findIndex(h => h.character?.slug === slug);
  if (index < 0) return;
  if (!opened.has(index)) { opened.add(index); render(); }
  requestAnimationFrame(() => matrix.querySelector('[data-hero="'+index+'"]')?.closest('tr').scrollIntoView({block:'start'}));
}
selectExample();
window.addEventListener('hashchange',selectExample);
