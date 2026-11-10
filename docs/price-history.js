/* Browser-side price snapshots for the static GitHub Pages site. */
(function (root) {
  const BASE = 'https://data-api.binance.vision';
  const MINUTE = 60000, DAY = 24 * 60 * MINUTE;
  async function request(path, params) {
    const url = new URL(BASE + path);
    Object.entries(params).forEach(([key, value]) => url.searchParams.set(key, value));
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(url, {signal: controller.signal});
      if (!response.ok) throw new Error('Binance HTTP ' + response.status);
      return await response.json();
    } finally { clearTimeout(timer); }
  }
  async function quote(symbol) {
    const data = await request('/api/v3/ticker/price', {symbol: symbol + 'USDT'});
    const price = Number(data.price);
    if (!Number.isFinite(price) || price <= 0) throw new Error('Geçersiz fiyat');
    return price;
  }
  async function refresh(record, now = Date.now()) {
    if (record.status === 'complete' || record.status === 'unavailable') return record;
    const start = Date.parse(record.recorded_at);
    if (!Number.isFinite(start)) throw new Error('Geçersiz kayıt zamanı');
    const first = Math.ceil(start / MINUTE) * MINUTE;
    const end = Math.floor(Math.min(now, start + DAY) / MINUTE) * MINUTE;
    if (end <= first) return {...record, error: null};
    let cursor = first, high = -Infinity, low = Infinity;
    while (cursor < end) {
      const rows = await request('/api/v3/klines', {
        symbol: record.symbol + 'USDT', interval: '1m', startTime: cursor, endTime: end - 1, limit: 1000
      });
      if (!Array.isArray(rows) || !rows.length) throw new Error('Mum verileri eksik');
      for (const row of rows) {
        const h = Number(row[2]), l = Number(row[3]);
        if (Number(row[0]) !== cursor || !Number.isFinite(h) || !Number.isFinite(l) || l <= 0 || h < l)
          throw new Error('Mum verilerinde boşluk veya geçersiz fiyat var');
        high = Math.max(high, h); low = Math.min(low, l); cursor += MINUTE;
      }
      if (cursor > end) throw new Error('Beklenmeyen mum aralığı');
    }
    return {...record, high, low, observed_from: new Date(first).toISOString(),
      observed_until: new Date(end).toISOString(), status: now >= start + DAY ? 'complete' : 'pending', error: null};
  }
  root.PriceHistory = {quote, refresh};
  if (typeof module !== 'undefined') module.exports = root.PriceHistory;
})(typeof window !== 'undefined' ? window : globalThis);
