import base64
import json
import mimetypes
import re
from collections import defaultdict
from pathlib import Path
from argparse import ArgumentParser
from html import escape, unescape
from datetime import datetime
from zoneinfo import ZoneInfo

parser = ArgumentParser(description='Build an offline Dungeons preview from a generated Forever Heroes Pages folder.')
parser.add_argument('site', type=Path, help='Folder containing index.html and its assets/')
parser.add_argument('statistics', type=Path, help='Snapshot written by preview_dungeon_statistics.py')
parser.add_argument('output', type=Path, help='New standalone HTML path, outside the published site')
parser.add_argument('--portraits', type=Path, help='Optional directory of <character-slug>.webp avatars')
args = parser.parse_args()
work = args.site.resolve()
parts = Path(__file__).resolve().parent
assets = work / 'assets'
if work in args.output.resolve().parents:
    parser.error('Write the preview outside the published site directory.')
def data_uri(path):
    mime=mimetypes.guess_type(path.name)[0] or 'application/octet-stream'
    return 'data:'+mime+';base64,'+base64.b64encode(path.read_bytes()).decode('ascii')

def dump(value):
    return json.dumps(value,ensure_ascii=False,separators=(',',':')).replace('<','\\u003c')

cur=(work/'index.html').read_text()
stats=json.loads(args.statistics.read_text())
main=next(p for p in assets.glob('*.js') if 'const DATA=' in p.read_text())
source=main.read_text()
def assignment(key):
    return json.JSONDecoder().raw_decode(source.split(key,1)[1])[0]
roster=assignment('const DATA=')['heroes']
icons=assignment(', ICONS=')
groups=defaultdict(set)
fields={}
heroes={}
translations={'Total 5-player dungeons entered':'Входы в подземелья на 5 игроков','Total deaths in 5-player dungeons':'Смерти в подземельях на 5 игроков','Total raid and dungeon deaths':'Смерти в рейдах и подземельях'}
for entry in roster:
    name=entry['name'];profile=entry['character'];cls=profile['class']['name']
    avatar=(args.portraits/(profile['slug']+'.webp')) if args.portraits else None
    raw=stats['heroes'].get(name,{'status':'unavailable'})
    fallback_icon = icons.get('class:'+cls, '')
    if fallback_icon.startswith('assets/'):
        fallback_icon = data_uri(work/fallback_icon)
    hero={'owner':entry['owner'],'cls':cls,'portrait':data_uri(avatar) if avatar and avatar.exists() else fallback_icon,'status':raw['status'],'bosses':[],'counters':[]}
    heroes[name]=hero
    for stat in raw.get('stats',[]):
        label=stat['name']
        match=re.fullmatch(r'(.+?) kills? \((.+)\)',label,re.I)
        amount=stat.get('quantity')
        if not isinstance(amount,(int,float)):continue
        timestamp=stat.get('last_updated_timestamp')
        record={'timestamp':timestamp,'quantity':int(amount)}
        if not match:
            hero['counters'].append(dict(record,label=translations.get(label,label)))
            continue
        boss,dungeon=match.groups()
        hero['bosses'].append(dict(record,boss=boss,dungeon=dungeon))
        if timestamp and amount>0:
            key=(stat['id'],timestamp); groups[key].add(name);fields[key]=(boss,dungeon)
events=[]
for (sid,ts),group in sorted(groups.items(), key=lambda kv:-kv[0][1]):
    if not 2<=len(group)<=5 or len({heroes[n]['owner'] for n in group})!=len(group):continue
    boss,dungeon=fields[(sid,ts)]
    events.append({'id':sid,'timestamp':ts,'dungeon':dungeon,'boss':boss,'heroes':sorted(group)})
catalogDungeons=[unescape(v) for v in re.findall(r'data-report="[^"]+" aria-label="([^"]+)"',cur)]
data={'heroes':heroes,'events':events,'asOf':stats['asOf'],'catalogDungeons':catalogDungeons}
section=(parts/'section.html').read_text().replace('__CATALOG__',(parts/'catalog.html').read_text())
# Render the initial evidence even in viewers that restrict JavaScript.
first = 'Dargor Springhill' if 'Dargor Springhill' in heroes else next(iter(heroes))
initial_events = [e for e in events if first in e['heroes']]
fallback = []
for event in initial_events:
    stamp = datetime.fromtimestamp(event['timestamp'] / 1000, ZoneInfo('Asia/Jerusalem')).strftime('%d.%m · %H:%M:%S')
    party = ', '.join(escape(n) for n in event['heroes'])
    fallback.append(f'<article class="cc-event"><div class="cc-kicker">{escape(event["dungeon"])} · {stamp}</div>'
                    f'<div class="cc-boss">{escape(event["boss"])}</div><p>{party}</p></article>')
section = section.replace('<div id="cc-events" aria-live="polite"></div>',
                          '<div id="cc-events" aria-live="polite">' + ''.join(fallback) + '</div>')
section = section.replace('aria-label="Герой для журнала"></select>', 'aria-label="Герой для журнала"><option>' + escape(first) + '</option></select>')
section = section.replace('aria-label="Фильтр по подземелью"></select>', 'aria-label="Фильтр по подземелью"><option>Все подземелья</option></select>')
asof='<p class="cc-stamp" id="cc-asof"></p>'
section=section.replace('<details class="cc-method">',asof+'<details class="cc-method">')
cur=cur.replace('<div class="dg-layout">',section+'<div class="dg-layout">',1)
cur=cur.replace('<title>Side Quest Company · Heroes &amp; Dungeons</title>','<title>С кем ходили · Side Quest Company · Тестовая версия</title>')
asset_pattern=re.compile(r'assets/[a-f0-9]{20}\.(?:webp|png|jpg|jpeg|gif|svg|woff2?)')
uris={}
def inline_resource(m):
    path=m[0]
    if path not in uris: uris[path]=data_uri(work/path)
    return uris[path]
def script_tag(m):
    content=asset_pattern.sub(inline_resource,(work/m[1]).read_text())
    return '<script>'+content.replace('</script','<\\/script')+'</script>'
cur=re.sub(r'<script src="(assets/[^"]+\.js)"></script>',script_tag,cur)
cur=re.sub(r'<link rel="stylesheet" href="(assets/[^"]+\.css)">',lambda m:'<style>'+(work/m[1]).read_text()+'</style>',cur)
cur=asset_pattern.sub(inline_resource,cur)
css=(parts/'companions.css').read_text(); js=(parts/'companions.js').read_text()
cur=cur.replace('</style><main>', '</style><style>'+css+'</style><main>',1)
cur=cur.replace('</html>','<script type="application/json" id="cc-data">'+dump(data)+'</script><script>'+js+'</script></html>')
out=args.output
out.write_text(cur)
print(out,out.stat().st_size,'heroes',len(heroes),'events',len(events),'dependencies',len(uris))
