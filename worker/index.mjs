const SITE = 'https://kochurovvs.github.io';
const PAGES = SITE + '/forever-heroes/';
const WORKFLOW = 'https://api.github.com/repos/kochurovvs/forever-heroes/actions/workflows/update-heroes.yml';
const FIFTEEN_MINUTES = 15 * 60_000;

function reply(state, status = 200) {
  return Response.json({ state }, {
    status,
    headers: { 'Cache-Control': 'no-store', 'Access-Control-Allow-Origin': SITE, 'Vary': 'Origin' }
  });
}

export default {
  async fetch(request, env) {
    const { pathname } = new URL(request.url);
    if (pathname !== '/refresh') return new Response(null, { status: 404 });
    if (request.method !== 'POST') return new Response(null, { status: 405, headers: { Allow: 'POST' } });
    if (request.headers.get('Origin') !== SITE) return new Response(null, { status: 403 });
    if (!env.GITHUB_TOKEN) return reply('unavailable', 503);
    const id = env.REFRESH_GATE.idFromName('forever-heroes-main');
    return env.REFRESH_GATE.get(id).fetch(request);
  }
};

export class RefreshGate {
  constructor(ctx, env) {
    this.storage = ctx.storage;
    this.token = env.GITHUB_TOKEN;
    this.pending = null;
  }

  async fetch() {
    // Join concurrent visitors, including while the upstream requests are waiting.
    if (!this.pending) {
      this.pending = this.check().finally(() => { this.pending = null; });
    }
    try {
      const state = await this.pending;
      return reply(state, state === 'unavailable' ? 503 : 200);
    } catch {
      return reply('unavailable', 503);
    }
  }

  github(url, options = {}) {
    return fetch(url, {
      ...options,
      signal: AbortSignal.timeout(8000),
      redirect: 'manual',
      headers: {
        'Authorization': 'Bearer ' + this.token,
        'User-Agent': 'ForeverHeroesRefresh',
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2026-03-10',
        'Content-Type': 'application/json'
      }
    });
  }

  async check() {
    const marker = new URL('snapshot.json', PAGES);
    marker.searchParams.set('v', String(Math.floor(Date.now() / 1000)));
    const response = await fetch(marker, { cache: 'no-store', signal: AbortSignal.timeout(8000) });
    if (!response.ok) return 'unavailable';
    const snapshot = await response.json();
    const collected = Date.parse(snapshot.fetchedAt);
    if (!snapshot.complete || !Number.isFinite(collected)) return 'unavailable';
    if (Date.now() - collected < FIFTEEN_MINUTES) return 'fresh';

    const hold = await this.storage.get('hold');
    if (hold && Date.now() < hold.until) return hold.state;

    const runs = await this.github(WORKFLOW + '/runs?branch=main&per_page=20');
    if (!runs.ok) return 'unavailable';
    const { workflow_runs } = await runs.json();
    if (workflow_runs.some(run => run.status !== 'completed')) return 'pending';

    // Persist the reservation before POST, even if the Worker restarts or GitHub's response is lost.
    await this.storage.put('hold', { until: Date.now() + FIFTEEN_MINUTES, state: 'pending' });
    const dispatch = await this.github(WORKFLOW + '/dispatches', {
      method: 'POST', body: JSON.stringify({ ref: 'main' })
    });
    if (dispatch.ok) return 'pending';
    if (dispatch.status >= 400 && dispatch.status < 500) {
      await this.storage.put('hold', { until: Date.now() + 60_000, state: 'unavailable' });
    }
    return 'unavailable';
  }
}
