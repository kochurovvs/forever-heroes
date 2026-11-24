"""Package maps and the current profile media for the roster dashboard."""
import base64
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import BytesIO
from pathlib import Path
import re
from urllib.request import Request, urlopen
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[1]


def asset_url(content, extension, directory):
    if directory is None:
        mime = {'webp': 'image/webp'}[extension]
        return f'data:{mime};base64,' + base64.b64encode(content).decode('ascii')
    filename = sha256(content).hexdigest()[:20] + '.' + extension
    directory.mkdir(parents=True, exist_ok=True)
    (directory / filename).write_bytes(content)
    return directory.name + '/' + filename


def profile_media(heroes):
    urls = {}
    for hero in heroes:
        c = hero.get('character') or {}
        render = c.get('render') or {}
        photo = (render.get('foreground') or (c.get('media') or {}).get('main-raw') or {}).get('url')
        background = (render.get('background') or {}).get('url')
        if photo:
            urls[photo] = 'heroes'
        if background:
            urls[background] = 'backgrounds'
        for item in (c.get('gear') or {}).values():
            assets = ((item.get('media') or {}).get('content') or {}).get('assets') or []
            for image in assets:
                if image.get('key') == 'icon' and image.get('value'):
                    urls[image['value']] = 'icons'
    return urls


def dashboard_assets(heroes, directory, online, craft_icons=()):
    result = {'heroes': {}, 'backgrounds': {}, 'icons': {}, 'slots': {}, 'maps': {}}
    for group, folder in [('slots', ROOT/'armory/slots'), ('maps', ROOT/'dungeons/maps')]:
        for file in sorted(folder.glob('*.webp')):
            result[group][file.stem] = asset_url(file.read_bytes(), 'webp', directory)

    media = profile_media(heroes)
    media.update({url: 'icons' for url in craft_icons
                  if url.startswith('https://wow.zamimg.com/images/wow/icons/large/')})
    # Standalone and offline builds keep original image links. Live Pages takes a
    # local copy so visiting players don't depend on an extra cross-origin request.
    for url, group in media.items():
        result[group][url] = url
    if directory is None or not online:
        return result

    from PIL import Image

    def fetch(entry):
        url, group = entry
        if not url.startswith(('https://render.worldofwarcraft.com/', 'https://wow.zamimg.com/images/wow/icons/large/')):
            return
        try:
            request = Request(url, headers={'User-Agent': 'ForeverRoster/1.0'})
            with urlopen(request, timeout=10) as response:
                body = response.read()
            with Image.open(BytesIO(body)) as original:
                image = original.convert('RGBA' if group == 'heroes' else 'RGB')
                if group == 'heroes':
                    bounds = image.getchannel('A').getbbox()
                    if bounds:
                        image = image.crop(bounds)
                size = {'heroes': (700, 660), 'backgrounds': (960, 660), 'icons': (56, 56)}[group]
                image.thumbnail(size, Image.Resampling.LANCZOS)
                stream = BytesIO()
                image.save(stream, 'WEBP', quality=88, method=4)
            return url, group, asset_url(stream.getvalue(), 'webp', directory)
        except (OSError, ValueError, URLError) as exc:
            print(f'Изображение {url}: {exc}. Используем адрес оружейной.', flush=True)
            return
    with ThreadPoolExecutor(max_workers=8) as pool:
        for item in pool.map(fetch, media.items()):
            if item:
                url, group, local = item
                result[group][url] = local
    return result


def split_resources(page, directory):
    def write(match):
        element, body = match.groups()
        if element == 'style':
            url = asset_url(body.encode(), 'css', directory)
            return f'<link rel="stylesheet" href="{url}">'
        url = asset_url(body.encode(), 'js', directory)
        return f'<script src="{url}"></script>'
    return re.sub(r'<(style|script)>(.*?)</\1>', write, page, flags=re.S)
