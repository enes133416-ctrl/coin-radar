"""Public Binance data access. Snapshot data is never backfilled into history."""
import time
import numpy as np
import pandas as pd
import requests


class Binance:
    def __init__(self, cfg):
        self.cfg = cfg
        self.session = requests.Session()

    def get(self, base, path, **params):
        for i in range(self.cfg['request_retries']):
            try:
                r = self.session.get(base + path, params=params, timeout=self.cfg['request_timeout_seconds'])
                r.raise_for_status()
                return r.json()
            except (requests.RequestException, ValueError) as exc:
                status = getattr(getattr(exc, 'response', None), 'status_code', None)
                if status is not None and 400 <= status < 500 and status != 429:
                    raise
                if i + 1 == self.cfg['request_retries']:
                    raise
                time.sleep(1.5 * (i + 1))

    def spot(self, path, **params):
        return self.get(self.cfg['spot_base'], path, **params)

    def futures(self, path, **params):
        return self.get(self.cfg['futures_base'], path, **params)

    def universe(self):
        info = self.spot('/api/v3/exchangeInfo')
        symbols = {s['symbol']: s for s in info['symbols'] if s.get('status') == 'TRADING'
                   and s.get('quoteAsset') == 'USDT' and s.get('baseAsset') not in self.cfg['skip_assets']}
        rows = [dict(x, exchange_info=symbols[x['symbol']]) for x in self.spot('/api/v3/ticker/24hr')
                if x['symbol'] in symbols and float(x['quoteVolume']) >= self.cfg['min_volume_usdt']]
        rows.sort(key=lambda x: -float(x['quoteVolume']))
        limit = self.cfg.get('top_n')
        return rows if limit is None else rows[:limit]

    def klines(self, symbol):
        out, end = [], None
        for _ in range(self.cfg['kline_pages']):
            p = dict(symbol=symbol, interval='1h', limit=1000)
            if end is not None:
                p['endTime'] = end
            rows = self.spot('/api/v3/klines', **p)
            if not rows:
                break
            out = rows + out
            end = rows[0][0] - 1
            time.sleep(self.cfg['request_delay_seconds'])
        if not out:
            return pd.DataFrame(columns=['o', 'h', 'l', 'c', 'v'])
        df = pd.DataFrame(out).iloc[:, :6]
        df.columns = ['t', 'o', 'h', 'l', 'c', 'v']
        df = df.astype(float)
        df['t'] = pd.to_datetime(df.t, unit='ms')
        # Only fully closed candles; timestamps are open times in UTC.
        df = df.drop_duplicates('t').set_index('t').sort_index()
        return df[df.index + pd.Timedelta(hours=1) <= pd.Timestamp.now(tz='UTC').tz_localize(None)]

    def book(self, symbol):
        d = self.spot('/api/v3/depth', symbol=symbol, limit=self.cfg['order_book_limit'])
        bids, asks = np.array(d['bids'], dtype=float), np.array(d['asks'], dtype=float)
        if not len(bids) or not len(asks):
            raise ValueError('empty order book')
        mid = (bids[0, 0] + asks[0, 0]) / 2
        band = self.cfg['depth_band_pct']
        return {'spread': float((asks[0, 0] - bids[0, 0]) / mid),
                'bid_depth_usdt': float((bids[bids[:, 0] >= mid * (1-band)].prod(axis=1)).sum()),
                'ask_depth_usdt': float((asks[asks[:, 0] <= mid * (1+band)].prod(axis=1)).sum()),
                'depth_truncated': bool((len(bids) == self.cfg['order_book_limit'] and bids[-1, 0] >= mid*(1-band)) or (len(asks) == self.cfg['order_book_limit'] and asks[-1, 0] <= mid*(1+band)))}

    def futures_history(self, symbol):
        """Published history only. Some contracts/endpoints are unavailable or limited to 30 days."""
        result, errors = {}, []
        endpoints = [('funding', '/fapi/v1/fundingRate', {'limit': 1000}),
                     ('oi', '/futures/data/openInterestHist', {'period': '1h', 'limit': 500}),
                     ('global_ls', '/futures/data/globalLongShortAccountRatio', {'period': '1h', 'limit': 500}),
                     ('top_ls', '/futures/data/topLongShortAccountRatio', {'period': '1h', 'limit': 500})]
        for name, path, params in endpoints:
            try:
                rows = self.futures(path, symbol=symbol, **params)
                if not isinstance(rows, list):
                    raise ValueError('unexpected response')
                result[name] = rows
            except (requests.RequestException, ValueError) as exc:
                errors.append(name + ': ' + str(exc))
                result[name] = []
        # Current OI is an explicitly timestamped snapshot, not used as historical data.
        try:
            oi = self.futures('/fapi/v1/openInterest', symbol=symbol)
            result['current_oi'] = {'value': float(oi['openInterest']), 'time': oi['time']}
        except (requests.RequestException, ValueError, KeyError) as exc:
            result['current_oi'] = None
            errors.append('current_oi: ' + str(exc))
        result['errors'] = errors
        return result


def monitoring(info):
    # Spot exchangeInfo does not consistently expose Binance's monitoring/delisting labels.
    # Absence of a tag field is unknown, not proof that a symbol is safe.
    tags = info.get('tags')
    if tags is None:
        return {'status': 'unknown', 'tags': []}
    tags = list(tags) if isinstance(tags, list) else [str(tags)]
    return {'status': 'warning' if any('monitor' in str(x).lower() or 'delist' in str(x).lower() for x in tags) else 'no_warning_reported', 'tags': tags}
