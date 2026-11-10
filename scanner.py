"""Build Coin Radar predictions and a reproducible walk-forward report."""
import json
import os
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from radar.data import Binance, monitoring
from radar.features import features, add_futures, labels
from radar.model import evaluate
from radar.price_history import update_history


def num(x):
    try:
        return round(float(x), 6) if np.isfinite(float(x)) else None
    except (TypeError, ValueError):
        return None


def resolve(pending, dfs, now, cfg):
    done, keep = [], []
    h = cfg['horizon_hours']
    for e in pending:
        t0, df = pd.Timestamp(e['t']), dfs.get(e['sym'] + 'USDT')
        if df is None or df.index.max() < t0 + pd.Timedelta(hours=h-1):
            if now - t0 < pd.Timedelta(hours=h*3):
                keep.append(e)
            continue
        w = df.reindex(pd.date_range(t0, periods=h, freq='h'))
        if w[['h', 'l']].isna().any().any():
            continue
        threshold = e.get('threshold', cfg['threshold'])
        price = e.get('price')
        if price is None:
            if 'o' not in w or pd.isna(w.o.iloc[0]):
                continue
            price = float(w.o.iloc[0])
        u = np.flatnonzero(w.h.to_numpy() >= price*(1+threshold))
        d = np.flatnonzero(w.l.to_numpy() <= price*(1-threshold))
        result = 'belirsiz' if len(u) and len(d) and u[0] == d[0] else 'yukari' if len(u) and (not len(d) or u[0] < d[0]) else 'asagi' if len(d) else 'yok'
        done.append({**e, 'price': price, 'max_up': num(w.h.max()/price-1), 'max_dn': num(w.l.min()/price-1), 'result': result,
                     'hit': None if result == 'belirsiz' else result == ('yukari' if e['side'] == 'up' else 'asagi')})
    return done, keep


def main():
    with open('config.json', encoding='utf-8') as fh:
        cfg = json.load(fh)
    h = cfg['horizon_hours']
    if cfg['sample_stride_hours'] < h:
        raise ValueError('Örnek seyreltme aralığı en az hedef ufku kadar olmalı')
    api = Binance(cfg)
    uni = api.universe()
    btc = api.klines('BTCUSDT')
    if len(btc) < cfg['min_history_hours']:
        raise ValueError('BTC geçmişi yetersiz')
    frames, last, dfs, skipped = [], {}, {}, []
    print(len(uni), 'coin taranıyor...', flush=True)
    for x in uni:
        s = x['symbol']
        try:
            df = btc if s == 'BTCUSDT' else api.klines(s)
            # Require a continuous recent history, and prevent labels spanning missing hours.
            if len(df) < cfg['min_history_hours'] or (df.index[-1] - df.index[-cfg['min_history_hours']]) != pd.Timedelta(hours=cfg['min_history_hours']-1):
                raise ValueError('30 günlük kesintisiz geçmiş yok')
            book = api.book(s)
            if book['spread'] > cfg['max_spread_pct'] or min(book['bid_depth_usdt'], book['ask_depth_usdt']) < cfg['min_depth_usdt_per_side']:
                raise ValueError('spread/derinlik filtresi')
            # Exclude older disconnected segments to keep rolling windows and labels valid.
            gaps = np.flatnonzero(np.diff(df.index.as_unit('ns').asi8) != pd.Timedelta(hours=1).value)
            if len(gaps):
                df = df.iloc[gaps[-1]+1:]
            hist = api.futures_history(s)
            f = add_futures(features(df, btc, cfg), hist)
            y = labels(df, cfg['threshold'], h).rename(columns=lambda c: c + '_fixed')
            if cfg['atr_target_enabled']:
                th = (f.atr14 * cfg['atr_multiplier']).clip(cfg['atr_min_threshold'], cfg['atr_max_threshold'])
                y = y.join(labels(df, th, h).rename(columns=lambda c: c + '_atr'))
            frame = f.join(y)
            frame['sym'] = s
            frames.append(frame)
            dfs[s] = df
            last[s] = {'features': f.iloc[-1], 'price': float(df.c.iloc[-1]), 'ticker': x,
                       'book': book, 'monitoring': monitoring(x['exchange_info']),
                       'futures_errors': hist['errors'], 'current_oi': hist['current_oi']}
            print(s, len(df), 'mum', flush=True)
        except (ValueError, KeyError, IndexError, OSError) as e:
            print('atlandı', s, str(e), flush=True)
            skipped.append({'symbol': s, 'reason': str(e)})
        except Exception as e:
            # Per-symbol API failures are visible in the report, not silently treated as good liquidity.
            print('atlandı', s, str(e), flush=True)
            skipped.append({'symbol': s, 'reason': str(e)})
    if not frames:
        raise ValueError('Filtrelerden geçen coin yok; Binance erişimini ve config eşiklerini kontrol edin')
    data = pd.concat(frames).sort_index()
    cols = list(last[next(iter(last))]['features'].index)
    # Early warm-up observations are excluded; missing futures history stays missing, never filled with snapshots.
    data = data.dropna(subset=['ret120', 'vol_zscore', 'btc_ret24'])
    bundles, metrics, comparisons = {}, {}, {}
    modes = ['fixed'] + (['atr'] if cfg['atr_target_enabled'] else [])
    for mode in modes:
        comparisons[mode] = {}
        for side in ('up', 'dn'):
            target = f'y_{side}_{mode}'
            train = data.dropna(subset=[target])
            bundle, result = evaluate(train, cols, target, cfg)
            comparisons[mode][side] = result
            if mode == 'fixed':
                bundles[side], metrics[side] = bundle, result
            print(mode, side, 'Brier:', result['brier'], 'precision@10:', result['precision_top10'], flush=True)
    syms = list(last)
    latest = pd.DataFrame([last[s]['features'] for s in syms], index=syms)[cols]
    probs, contributions = {}, {}
    for side, b in bundles.items():
        from radar.model import predict
        probs[side] = predict(b, latest)
        contributions[side] = b['model'].predict(latest[b['features']], pred_contrib=True)
    coins = []
    for i, s in enumerate(syms):
        item, row, c = last[s], last[s]['features'], dfs[s].c
        obj = {'symbol': s[:-4], 'price': item['price'], 'chg24': float(item['ticker']['priceChangePercent']),
               'volume': float(item['ticker']['quoteVolume']), 'p_up': num(probs['up'][i]), 'p_dn': num(probs['dn'][i]),
               'vol_zscore': num(row['vol_zscore']), 'book': item['book'], 'monitoring': item['monitoring'],
               'current_oi': item['current_oi'], 'futures_errors': item['futures_errors'],
               'spark': [num(v) for v in (c.tail(72)/c.tail(72).iloc[0])],
               'ind': {k: num(row[k]) for k in cols}}
        for side, b in bundles.items():
            cc = contributions[side][i][:-1]
            obj['why_'+side] = [{'f': b['features'][j], 'v': num(row[b['features'][j]]), 'c': num(cc[j])} for j in np.argsort(-np.abs(cc))[:5]]
            # Qualitative data sufficiency, not a statistical confidence interval.
            missing = latest.loc[s, b['features']].isna().mean()
            obj['confidence_'+side] = 'düşük' if missing > cfg['confidence_max_missing_low'] or b['cal_events'] < cfg['confidence_min_events_low'] else 'orta' if missing > cfg['confidence_max_missing_medium'] or b['cal_events'] < cfg['confidence_min_events_medium'] else 'yüksek'
        coins.append(obj)
    outpath = cfg['output']
    try:
        with open(outpath, encoding='utf-8') as fh:
            prev = json.load(fh)
    except (OSError, ValueError):
        prev = {}
    # Price snapshots have their own schema and do not depend on model label versions.
    price_history = update_history(api, prev.get('price_history', []), coins, cfg['top_k'])
    # Legacy records used a different target, so don't mix them with first-touch scores.
    if prev.get('label_version') != 'first_touch_v1':
        prev = {}
    now = pd.Timestamp.now(tz='UTC').tz_localize(None)
    done, keep = resolve(prev.get('pending', []), dfs, now, cfg)
    track = (done + prev.get('track', []))[:400]
    seen = {(e['t'], e['sym'], e['side']) for e in keep + track}
    for side in ('up', 'dn'):
        for coin in sorted(coins, key=lambda c: -c['p_'+side])[:cfg['top_k']]:
            # Start after publication, never retroactively evaluate part of a candle.
            t0 = now.floor('h') + pd.Timedelta(hours=1)
            e = {'t': t0.isoformat(), 'sym': coin['symbol'], 'side': side, 'p': coin['p_'+side], 'price': None, 'reference_price': coin['price'], 'threshold': cfg['threshold']}
            if (e['t'], e['sym'], side) not in seen:
                keep.append(e)
    report = {'generated': datetime.now(timezone.utc).isoformat(), 'config': cfg, 'comparison': comparisons,
              'feature_selection': {k: {'selected': b['features'], 'dropped': b['dropped'], 'importance': b['importance'],
                                    'correlation': json.loads(b['correlation'].to_json())} for k, b in bundles.items()},
              'skipped': skipped, 'limitations': ['Order book is a current snapshot and excluded from model training.',
                   'Public historical liquidation data is unavailable; liquidation features are not used.',
                   'Monitoring tags may not be exposed by spot exchangeInfo; unknown is not safe.',
                   'Universe and liquidity use current filters, so historical backtests have survivorship/selection bias.']}
    out = {'generated': report['generated'], 'label_version': 'first_touch_v1', 'horizon': h, 'threshold': cfg['threshold'],
           'metrics': metrics, 'importance': {k: b['importance'] for k, b in bundles.items()}, 'coins': coins,
           'pending': keep[-200:], 'track': track, 'price_history': price_history,
           'meta': {'coins': len(coins), 'candles': sum(len(d) for d in dfs.values()), 'train_rows': len(data.dropna(subset=['y_up_fixed'])),
                    'features': len(cols), 'data_from': str(min(d.index[0] for d in dfs.values()))[:16],
                    'data_to': str(max(d.index[-1] for d in dfs.values()) + pd.Timedelta(hours=1))[:16]}}
    for path, value in [(cfg['report_output'], report), (outpath, out)]:
        os.makedirs(os.path.dirname(path) or '.', exist_ok=True)
        with open(path, 'w', encoding='utf-8') as fh:
            json.dump(value, fh, ensure_ascii=False, allow_nan=False)
    print('yazıldı:', outpath, cfg['report_output'], flush=True)


if __name__ == '__main__':
    main()
