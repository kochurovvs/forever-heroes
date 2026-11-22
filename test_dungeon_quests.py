import contextlib
import io
import json
from pathlib import Path
import unittest
from urllib.parse import unquote, urlsplit
from unittest.mock import patch

from dungeons import quests
from dungeons.locations import ZONES
from dungeons.view import ORIGINS, add_dungeons, member, quest_card


class DungeonQuestsTest(unittest.TestCase):
    hero = {'name':'Test Hero','owner':'Test','character':{'class':{'name':'Mage','slug':'mage'},'level':18}}
    def setUp(self):
        self.dungeon = {'id':'wc', 'quests':[
            {'id':i, 'name':'Quest '+str(i), 'giver':'Giver','place':'Place','how':'Steps',
             'min':10,'inside':i==3, **({'cls':'Warlock'} if i==4 else {})}
            for i in range(1,6)]}

    def run_collection(self, active, done, allow_partial=False):
        def response(request):
            return {'quests':done} if urlsplit(request.full_url).path.endswith('/completed') else {'in_progress':active}
        with patch.object(quests,'access_token',return_value='test'), patch.object(quests,'request_json',side_effect=response), contextlib.redirect_stdout(io.StringIO()):
            return quests.collect('eu',[self.hero],[self.dungeon],allow_partial)['heroes']

    def test_filters_and_completion_precedence(self):
        result = self.run_collection([{'quest':{'id':i}} for i in (1,2,3,4,111)], [{'id':i} for i in (1,4,222)])
        record = result['test-hero']
        self.assertEqual(record['active'],[2,3])
        self.assertEqual(record['done'],[1])
        score, html = member(self.dungeon,self.hero,record)
        self.assertAlmostEqual(score,2/3)
        self.assertIn('Взять 1',html)
        for label in ['Не готово · 1','В журнале · 2','Сданы · 1','Внутри данжа','Quest 5']:
            self.assertIn(label,html)
        self.assertNotIn('Quest 4',html)

    def test_prerequisites_reported_without_counting_them_as_dungeon_goals(self):
        self.dungeon['quests'][0]['prereqs'] = [
            {'id':51, 'name':'Step One'}, {'id':52, 'name':'Step Two'}]
        self.dungeon['quests'][3]['prereqs'] = [{'id':53,'name':'Other class step'}]
        record = self.run_collection([{'id':52},{'id':53}], [{'id':51}])['test-hero']
        self.assertEqual(record['active'],[52])
        self.assertEqual(record['done'],[51])
        score, html = member(self.dungeon,self.hero,record)
        self.assertEqual(score,0)
        for label in ['0/3', 'Step One</a> <small>Сдан', 'Step Two</a> <small>В журнале',
                      'принять этот квест от группы нельзя', 'dg-blocked']:
            self.assertIn(label, html)
        self.assertNotIn('Other class step', html)
        record['done'] = [51,52]
        self.assertNotIn('dg-blocked', member(self.dungeon,self.hero,record)[1])

    def test_chain_focus_follows_the_hero_journal(self):
        catalog = json.loads((Path(__file__).parent/'dungeons/catalog.json').read_text())
        dungeon = next(d for d in catalog if d['id'] == 'rol')
        quest = next(q for q in dungeon['quests'] if q['id'] == 92422)
        first, second = [s['id'] for s in quest['prereqs']]
        goal = quest['id']
        for active, done, label, current in [
            ([], [], 'Начало цепочки', first),
            ([first], [], 'Цепочка взята · Шаг 1 из 3', first),
            ([second], [first], 'Цепочка взята · Шаг 2 из 3', second),
            ([], [first], 'Цепочка начата · Шаг 2 из 3', second),
            ([], [first, second], 'Цепочка начата · Шаг 3 из 3', goal),
            ([goal], [], 'Цепочка взята · Шаг 3 из 3', goal),
            ([goal], [goal], 'Квест для подземелья сдан.', None),
        ]:
            with self.subTest(active=active, done=done):
                record = {'active': active, 'done': done, 'time': '2026-11-18T07:00:00+00:00'}
                _, page = member({**dungeon, 'quests':[quest]}, self.hero, record)
                focus, route = page.split('<details class="quest-route">')
                self.assertIn(label, focus)
                if current is not None:
                    self.assertIn(f'<h5><a href="https://www.wowhead.com/forever/quest={current}"', focus)
                if active or done:
                    self.assertNotIn('Начало цепочки', focus)
                    self.assertIn('Начало цепочки', route)
                    self.assertIn('data-who="Deathguard Linnea"', route)

    def test_all_dungeons_have_levels_and_working_tabs(self):
        catalog = json.loads((Path(__file__).parent/'dungeons/catalog.json').read_text())
        self.assertEqual({d['id'] for d in catalog if d['planned']}, {'wc','sfk'})
        base = '<style></style><main><header></header><h1>Heroes</h1></main><div id="hover-tip"></div>'
        html = add_dungeons(base,[self.hero],catalog,{})
        self.assertIn('Blackfathom Deeps',html)
        self.assertNotIn('__DG_', html)
        self.assertIn('id="dungeons"', html)
        for d in catalog:
            lo, hi = d['levels']
            self.assertTrue(lo <= d['recommended'] <= hi)
            self.assertIn(f'#pick-{d["id"]}:checked~#dg-report-{d["id"]}', html)
            self.assertIn(f'aria-controls="dg-report-{d["id"]}"',html)
            self.assertIn(f'Для группы · {d["recommended"]} ур.',html)

    def test_routes_start_at_first_prerequisite_and_have_zone_maps(self):
        root = Path(__file__).parent / 'dungeons'
        catalog = json.loads((root / 'catalog.json').read_text())
        for dungeon in catalog:
            for quest in dungeon['quests']:
                if not quest.get('prereqs'):
                    continue
                with self.subTest(dungeon=dungeon['id'], quest=quest['name']):
                    origin = ORIGINS[str(quest['id'])]
                    self.assertEqual(origin['id'], quest['prereqs'][0]['id'])
                    map_id = ZONES[origin['zone']]
                    self.assertTrue((root / 'maps' / f'{map_id}.webp').is_file())
                    card = quest_card(quest)
                    start, route = card.split('<details class="quest-route">')
                    self.assertIn('Начало цепочки', start)
                    self.assertIn(f'data-map="{map_id}"', start)
                    self.assertIn(f'data-x="{origin["x"]}"', start)
                    self.assertIn('Квест для подземелья', route)

    def test_quest_requests_use_armory_slug_but_keep_the_roster_key(self):
        hero = {**self.hero, 'name': 'Имя Героини', 'character': {**self.hero['character'], 'slug':'другое-имя'}}
        with patch.object(quests, 'access_token', return_value='test'), \
             patch.object(quests, 'request_json', side_effect=[{'in_progress':[]}, {'quests':[]}]) as request:
            snapshot = quests.collect('eu', [hero], [self.dungeon])
        self.assertIn('имя-героини', snapshot['heroes'])
        for call in request.call_args_list:
            self.assertIn('/другое-имя/quests', unquote(call.args[0].full_url))

    def test_unavailable_quest_journal_is_unknown_and_only_404_is_optional(self):
        with patch.object(quests, 'access_token', return_value='test'), \
             patch.object(quests, 'request_json', side_effect=quests.JournalNotFound('HTTP 404')) as request:
            with self.assertRaises(RuntimeError):
                quests.collect('eu', [self.hero], [self.dungeon])
            snapshot = quests.collect('eu', [self.hero], [self.dungeon], allow_missing_journals=True)
            self.assertNotIn('test-hero', snapshot['heroes'])
            request.side_effect = RuntimeError('HTTP 503')
            with self.assertRaises(RuntimeError):
                quests.collect('eu', [self.hero], [self.dungeon], allow_missing_journals=True)

    def test_empty_and_unknown_are_different(self):
        record = self.run_collection([],[])['test-hero']
        self.assertEqual(member(self.dungeon,self.hero,record)[0],0)
        self.assertEqual(member(self.dungeon,self.hero,None)[0],-1)
        for payload in (None,[{'quest':{}}]):
            with self.assertRaises(RuntimeError):
                self.run_collection(payload,[])
            self.assertEqual(self.run_collection(payload,[],True),{})

if __name__ == '__main__':
    unittest.main()
