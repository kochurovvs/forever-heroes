import contextlib
import io
import unittest
from urllib.parse import urlsplit
from unittest.mock import patch

from dungeons import quests
from dungeons.view import member


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
