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
    def run_case(self, failed):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'roster.json').write_text(json.dumps({'region': 'eu', 'owners': {'Owner': ['Test Hero']}}))
            (root / 'cache.json').write_text('{"fetchedAt":"old-time","heroes":[]}')
            (root / 'icons.json').write_text('{}')
            (root / 'template.html').write_text('__DATA__ __ICONS__')
            (root / 'index.html').write_text('previous working site')
            def collect(pair, region, cache, offline):
                return {'name': pair[1], 'owner': pair[0], 'url': 'https://example.test',
                        'status': 'HTTP 500' if failed else 'ok',
                        'character': None if failed else {'level': 18}}
            original = (root / 'cache.json').read_bytes()
            with patch.object(update, 'ROOT', root), patch.object(update, 'collect', collect), \
                 patch.object(update, 'update_icons', lambda heroes, icons: icons), patch.object(sys, 'argv', ['update.py']):
                if failed:
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

    def test_success_publishes_new_snapshot(self):
        self.run_case(False)

    def test_duplicate_rejected(self):
        with self.assertRaises(ValueError):
            update.validate({'region': 'eu', 'owners': {'A': ['Test Hero'], 'B': ['test hero']}})


if __name__ == '__main__':
    unittest.main()
