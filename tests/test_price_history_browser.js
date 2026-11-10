const assert = require('node:assert/strict');
const {test} = require('node:test');
const PriceHistory = require('../docs/price-history.js');

test('quote and first 24 hours are read from Binance with closed minutes and pagination', async () => {
  const requests = [];
  global.fetch = async url => {
    requests.push(url);
    if (url.pathname.endsWith('/ticker/price')) return {ok:true, json:async()=>({price:'100'})};
    const start = Number(url.searchParams.get('startTime'));
    const end = Number(url.searchParams.get('endTime'));
    const rows = [];
    for (let t=start;t<=end && rows.length<1000;t+=60000) rows.push([t, '100', '120', '80']);
    return {ok:true,json:async()=>rows};
  };
  assert.equal(await PriceHistory.quote('BTC'), 100);
  const start = Date.parse('2026-01-01T12:00:30Z');
  const record = {symbol:'BTC',recorded_at:new Date(start).toISOString(),price:100,status:'pending'};
  const partial = await PriceHistory.refresh(record, start+2*3600000);
  assert.equal(partial.status,'pending');
  assert.equal(partial.observed_from,'2026-01-01T12:01:00.000Z');
  assert.equal(partial.high,120); assert.equal(partial.low,80);
  const done = await PriceHistory.refresh(partial,start+3*86400000);
  assert.equal(done.status,'complete');
  assert.equal(done.observed_until,'2026-01-02T12:00:00.000Z');
  assert.equal(requests.length,4);
  await PriceHistory.refresh(done,start+4*86400000);
  assert.equal(requests.length,4);
});

test('missing candles throw without fabricating high and low', async () => {
  global.fetch = async () => ({ok:true,json:async()=>[]});
  const start = Date.parse('2026-01-01T12:00:30Z');
  const record = {symbol:'BTC',recorded_at:new Date(start).toISOString(),status:'pending',high:110,low:90};
  await assert.rejects(PriceHistory.refresh(record,start+3600000),/eksik/);
  assert.equal(record.high,110); assert.equal(record.low,90);
});
