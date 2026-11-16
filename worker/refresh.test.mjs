import assert from 'node:assert/strict';
import test from 'node:test';
import worker, { RefreshGate } from './index.mjs';

const site = 'https://kochurovvs.github.io';
const request = () => new Request('https://worker.example/refresh', { method: 'POST', headers: { Origin: site } });

function setup(t, { age = 16, complete = true, runs = [], dispatchStatus = 200 } = {}) {
  const values = new Map();
  const storage = {
    get: async key => values.get(key),
    put: async (key, value) => values.set(key, value)
  };
  const gate = () => new RefreshGate({ storage }, { GITHUB_TOKEN: 'test-token' });
  let dispatches = 0;
  t.mock.method(globalThis, 'fetch', async (url, options) => {
    if (String(url).startsWith(site + '/forever-heroes/snapshot.json?')) {
      return Response.json({ complete, fetchedAt: new Date(Date.now() - age * 60_000).toISOString() });
    }
    assert.equal(options.headers.Authorization, 'Bearer test-token');
    if (String(url).includes('/runs?')) return Response.json({ workflow_runs: runs });
    assert.equal(String(url), 'https://api.github.com/repos/kochurovvs/forever-heroes/actions/workflows/update-heroes.yml/dispatches');
    assert.equal(options.method, 'POST');
    assert.deepEqual(JSON.parse(options.body), { ref: 'main' });
    dispatches++;
    return new Response(null, { status: dispatchStatus });
  });
  return { gate, dispatches: () => dispatches };
}

for (const [name, opts, expected] of [
  ['recent full snapshot', { age: 14 }, 'fresh'],
  ['incomplete snapshot', { complete: false }, 'unavailable'],
  ['scheduled collection running', { runs: [{ status: 'in_progress' }] }, 'pending']
]) {
  test(name, async t => {
    const state = setup(t, opts);
    assert.equal((await (await state.gate().fetch()).json()).state, expected);
    assert.equal(state.dispatches(), 0);
  });
}

test('at fifteen minutes concurrent visitors share a single durable reservation', async t => {
  const state = setup(t, { age: 15 });
  const gate = state.gate();
  const responses = await Promise.all(Array.from({ length: 20 }, () => gate.fetch()));
  for (const response of responses) assert.equal((await response.json()).state, 'pending');
  assert.equal((await (await state.gate().fetch()).json()).state, 'pending');
  assert.equal(state.dispatches(), 1);
});

test('rejected dispatch is not reported as running or immediately retried', async t => {
  const state = setup(t, { dispatchStatus: 403 });
  for (let i = 0; i < 2; i++) assert.equal((await state.gate().fetch()).status, 503);
  assert.equal(state.dispatches(), 1);
});

test('public entry point accepts only site POSTs and fails closed without credentials', async () => {
  assert.equal((await worker.fetch(new Request('https://worker.example/refresh'), {})).status, 405);
  assert.equal((await worker.fetch(new Request('https://worker.example/refresh', { method: 'POST' }), {})).status, 403);
  assert.equal((await worker.fetch(request(), {})).status, 503);
});
