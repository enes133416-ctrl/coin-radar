"""Persistent, independent price snapshots for the model's rising candidates."""
from datetime import datetime, timedelta, timezone
import math


def utc_now():
    return datetime.now(timezone.utc)


def parse_time(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone(timezone.utc)


def update_record(api, record, now):
    """Update the first 24 hours after a snapshot from complete one-minute candles.

    The partial minute containing the snapshot is omitted: its high/low could have
    occurred before the snapshot. Only publish values after validating continuity.
    """
    if record.get('status') in ('complete', 'unavailable'):
        return record
    result = dict(record)
    try:
        start = parse_time(record['recorded_at'])
        first = start.replace(second=0, microsecond=0)
        if first < start:
            first += timedelta(minutes=1)
        end = min(now, start + timedelta(hours=24)).replace(second=0, microsecond=0)
        if end <= first:
            result.update(status='pending', error=None)
            return result
        first_ms, end_ms = int(first.timestamp() * 1000), int(end.timestamp() * 1000)
        rows, cursor = [], first_ms
        while cursor < end_ms:
            batch = api.spot('/api/v3/klines', symbol=record['symbol'] + 'USDT',
                             interval='1m', startTime=cursor, endTime=end_ms - 1, limit=1000)
            if not isinstance(batch, list) or not batch:
                raise ValueError('Mum verileri eksik')
            for row in batch:
                if int(row[0]) != cursor:
                    raise ValueError('Mum verilerinde boşluk var')
                high, low = float(row[2]), float(row[3])
                if not math.isfinite(high) or not math.isfinite(low) or low <= 0 or high < low:
                    raise ValueError('Geçersiz mum fiyatı')
                rows.append((high, low))
                cursor += 60000
            if cursor > end_ms:
                raise ValueError('Beklenmeyen mum aralığı')
        result.update(high=max(x[0] for x in rows), low=min(x[1] for x in rows),
                      observed_from=first.isoformat(), observed_until=end.isoformat(),
                      status='complete' if now >= start + timedelta(hours=24) else 'pending', error=None)
    except Exception:
        # Keep previously verified values, but make the failed refresh visible.
        result.update(error='Fiyat geçmişi alınamadı; sonraki taramada yeniden denenecek.')
    return result


def update_history(api, previous, coins, top_k, now_fn=utc_now):
    """Refresh outstanding snapshots and take fresh quotes for the current top picks."""
    now = now_fn()
    records = [update_record(api, r, now) for r in previous]
    for coin in sorted(coins, key=lambda c: -c['p_up'])[:top_k]:
        try:
            quote = api.spot('/api/v3/ticker/price', symbol=coin['symbol'] + 'USDT')
            price = float(quote['price'])
            if not math.isfinite(price) or price <= 0:
                raise ValueError('Geçersiz fiyat')
            records.append({'symbol': coin['symbol'], 'recorded_at': now_fn().isoformat(),
                            'price': price, 'probability': coin['p_up'], 'status': 'pending',
                            'high': None, 'low': None, 'error': None})
        except Exception:
            # A stale model price is not a substitute for the requested live quote.
            records.append({'symbol': coin['symbol'], 'recorded_at': now_fn().isoformat(),
                            'price': None, 'probability': coin['p_up'], 'status': 'unavailable',
                            'high': None, 'low': None,
                            'error': 'Kayıt anında fiyat alınamadı; bu kayıt hesaplanamaz.'})
    return records[-400:]
