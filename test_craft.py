import json
from unittest import TestCase
from unittest.mock import patch

from armory.craft import collect as craft


class GuildCraftTests(TestCase):
    def test_recipe_id_is_resolved_to_output_for_the_current_maker_only(self):
        def hero(slug, maker=False):
            skills = [{'name': 'Tailoring'}] if maker else []
            return {'owner': slug, 'name': slug, 'status': 'ok', 'character': {
                'slug': slug, 'level': 20, 'class': {'name': 'Mage'}, 'professions': {'primaries': skills}}}

        # A new Blizzard recipe ID for the existing Linen Cloak item.
        rid = 987654321
        def api(req):
            if '/professions?' in req.full_url:
                return {'primaries': [{'profession': {'name': 'Tailoring'},
                                       'tiers': [{'known_recipes': [{'id': rid}]}]}]}
            self.assertIn('/recipe/' + str(rid) + '?', req.full_url)
            return {'crafted_item': {'id': 2570}}

        with patch.object(craft, 'access_token', return_value='test'), patch.object(craft, 'request_json', api):
            rows = craft.collect('eu', [hero('мастер', True), hero('recipient')])
            self.assertEqual([(m['r']['id'], m['h']['key'], [v['key'] for v in m['makers']]) for m in rows],
                             [(2570, 'recipient', ['мастер'])])
            self.assertNotIn(str(rid), json.dumps(rows))
            self.assertEqual(craft.collect('eu', [hero('alone')]), [])

    def test_inaccessible_book_confers_no_recipes(self):
        profile = {'primaries': [{'profession': {'name': 'Leatherworking'}, 'tiers': [{'skill_points': 300}]}]}
        self.assertEqual(craft.recipe_ids(profile, {'Leatherworking'}), {'Leatherworking': set()})
