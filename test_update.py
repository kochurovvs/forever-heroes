import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('update', Path(__file__).with_name('update.py'))
update = importlib.util.module_from_spec(spec)
spec.loader.exec_module(update)


class PublicationTests(unittest.TestCase):
    def run_case(self, failed, quest_failure=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'roster.json').write_text(json.dumps({'region': 'eu', 'owners': {'Owner': ['Test Hero']}}))
            (root / 'cache.json').write_text('{"fetchedAt":"old-time","heroes":[]}')
            (root / 'icons.json').write_text('{}')
            (root / 'dungeons').mkdir()
            (root / 'dungeons/catalog.json').write_text('[]')
            (root / 'template.html').write_text('<style></style><main><header></header><h1>Heroes</h1>__DATA__ __ICONS__</main><div id="hover-tip"></div>')
            (root / 'index.html').write_text('previous working site')
            def collect(pair, region, cache, offline):
                return {'name': pair[1], 'owner': pair[0], 'url': 'https://example.test',
                        'status': 'HTTP 500' if failed else 'ok',
                        'character': None if failed else {'level': 18}}
            original = (root / 'cache.json').read_bytes()
            with patch.object(update, 'ROOT', root), patch.object(update, 'collect', collect), \
                 patch.object(update.quests, 'collect', return_value={'heroes':{}}, side_effect=RuntimeError('API unavailable') if quest_failure else None), \
                 patch.object(update, 'update_icons', lambda heroes, icons: icons), patch.object(sys, 'argv', ['update.py']):
                if failed or quest_failure:
                    with self.assertRaises(SystemExit):
                        update.main()
                    self.assertEqual((root / 'index.html').read_text(), 'previous working site')
                    self.assertEqual((root / 'cache.json').read_bytes(), original)
                else:
                    update.main()
                    data = json.loads((root / 'cache.json').read_text())
                    self.assertTrue(data['complete'])
                    self.assertNotEqual(data['fetchedAt'], 'old-time')
                    self.assertIn('Test Hero', (root / 'index.html').read_text())

    def test_failure_keeps_html_and_timestamp(self):
        self.run_case(True)

    def test_quest_failure_keeps_previous_dashboard(self):
        self.run_case(False, quest_failure=True)

    def test_success_publishes_new_snapshot(self):
        self.run_case(False)

    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            update.validate({'region': 'eu', 'owners': {'A': ['Test Hero'], 'B': ['test hero']}})


    def test_roster_uses_kill_count_and_rank_from_the_armory(self):
        hero = {'name': 'Test Hero', 'owner': 'Owner', 'character': {}}
        for pvp, expected in [
            ({'honorableKills': {'tier': 3, 'value': 12450}, 'rank': {'value': 4}}, ['12\xa0450', '4']),
            ({'honorableKills': {'value': 0}, 'rank': {'value': 0}}, ['0', '0']),
            ({'rank': {'value': 1}}, ['—', '1']),
            (None, ['—', '—']),
        ]:
            with self.subTest(pvp=pvp):
                hero['character']['pvp'] = pvp
                identity, _, _ = update.snapshot_row(hero)
                cells = [part.split('</td>')[0] for part in identity.split('<td class="profile-v pvp-value">')[1:]]
                self.assertEqual(cells, expected)

    def test_comparison_is_rendered_from_the_current_snapshot(self):
        hero = {'name': 'A & B', 'owner': '<Player>', 'character': {
            'level': 17, 'stats': {'overview': [{'enum': 'MANA', 'value': {'type': 'WHOLE', 'value': 0}}]},
            'professions': {'primaries': [{'name': 'Mining', 'tiers': [{'skillPoints': 12, 'maxSkillPoints': 75}]}]},
        }}
        data = {'heroes': [hero], 'complete': True, 'fetchedAt': '2026-11-16T11:45:00+00:00'}
        template = ('<table class="paper"><thead><tr><th data-key="MANA"></th><th data-key="Mining"></th>'
                    '<th data-key="ENERGY"></th></tr></thead><tbody>__SNAPSHOT_ROWS__</tbody></table>__DISPLAY_TIME__')
        result = update.render_dashboard(template, data, {})
        self.assertIn('A &amp; B', result)
        self.assertIn('&lt;Player&gt;', result)
        self.assertIn('>0</td>', result)
        self.assertIn('>12/75</td>', result)
        self.assertIn('>—</td>', result)
        self.assertIn('>17</span>', result)
        self.assertIn('16.11.2026, 14:45 МСК', result)


if __name__ == '__main__':
    unittest.main()
