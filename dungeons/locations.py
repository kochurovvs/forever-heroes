import re
from html import escape

# Zephras area IDs identify the zone map and its percentage coordinate frame.
ZONES = {
    'Orgrimmar': 1637, 'Thunder Bluff': 1638, 'Undercity': 1497,
    'Tirisfal Glades': 85, 'Silverpine Forest': 130, 'The Barrens': 17,
    'Ashenvale': 331, 'Stonetalon Mountains': 406,
    'Hillsbrad Foothills': 267, 'Alterac Mountains': 36, 'Arathi Highlands': 45,
    'Stormwind City': 1519, 'Ironforge': 1537, 'Westfall': 40, 'Wetlands': 11,
    'Dun Morogh': 1, 'Duskwood': 10, 'Redridge Mountains': 44, 'Feralas': 357,
    'Stranglethorn Vale': 33, 'Thousand Needles': 400, 'Mulgore': 215,
}
COORDINATES = re.compile(r' · (\d+(?:\.\d+)?),\s*(\d+(?:\.\d+)?)$')


def map_link(zone, area, x, y, giver, quest):
    label = f'{x}, {y}'
    if zone not in ZONES or not (0 <= float(x) <= 100 and 0 <= float(y) <= 100):
        return escape(label)
    map_id = ZONES[zone]
    url = f'https://zephras.com/forever/enUS/zone/{map_id}/?x={x}&y={y}&zoom=3'
    fields = dict(zone=zone, map=map_id, place=area, x=x, y=y, who=giver, quest=quest)
    attrs = ' '.join(f'data-{key}="{escape(str(value))}"' for key, value in fields.items())
    description = f'Показать на карте: {giver}, {zone}, {label}'
    return (f'<a class="map-point" {attrs} href="{escape(url)}" target="_blank" rel="noopener noreferrer" '
            f'aria-label="{escape(description)}"><span class="pin-icon" aria-hidden="true"></span>{escape(label)}</a>')


def address(q):
    place = q['place']
    coord = COORDINATES.search(place)
    label = f'<b>{escape(q["giver"])}</b> · '
    if not coord:
        return label + escape(place)
    name = place[:coord.start()]
    zone, _, area = name.partition(' · ')
    return label + escape(name) + ' · ' + map_link(zone, area, *coord.groups(), q['giver'], q['name'])
