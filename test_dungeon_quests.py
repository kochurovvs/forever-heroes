import contextlib
import io
import json
from pathlib import Path
import unittest
from urllib.parse import urlsplit
from unittest.mock import patch

from dungeons import quests
from dungeons.view import add_dungeons, member


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
        for label in ['Не взяты · 1','В журнале · 2','Сданы · 1','Внутри данжа','Quest 5']:
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

    def test_all_dungeons_have_levels_and_working_tabs(self):
        catalog = json.loads((Path(__file__).parent/'dungeons/catalog.json').read_text())
        self.assertEqual({d['id'] for d in catalog if d['planned']}, {'rol','wc'})
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
