"""Features are indexed by candle open time, and available at its close."""
import numpy as np
import pandas as pd


def features(df, btc, cfg):
    c = df.c
    r = c.pct_change()
    f = pd.DataFrame(index=df.index)
    for n in (1, 3, 6, 12, 24, 48, 120):
        f[f'ret{n}'] = c.pct_change(n)
    f['vol24'], f['vol72'] = r.rolling(24).std(), r.rolling(72).std()
    f['vol_ratio'] = f.vol24 / f.vol72
    f['vol_zscore'] = (f.vol24 - f.vol24.rolling(168, min_periods=72).mean()) / f.vol24.rolling(168, min_periods=72).std()
    f['range24'] = (df.h.rolling(24).max() - df.l.rolling(24).min()) / c
    true_range = pd.concat([df.h-df.l, (df.h-c.shift()).abs(), (df.l-c.shift()).abs()], axis=1).max(axis=1)
    f['atr14'] = true_range.rolling(14).mean() / c
    mean = c.rolling(20).mean()
    std = c.rolling(20).std()
    f['bb_width'] = 4 * std / mean
    f['squeeze'] = (f.bb_width / f.bb_width.rolling(168, min_periods=72).mean())
    for n in (168, 720):
        # Newly listed coins can still be scored using their available history.
        f[f'to_hi{n}'] = c / df.h.rolling(n, min_periods=min(n, 168)).max() - 1
        f[f'to_lo{n}'] = c / df.l.rolling(n, min_periods=min(n, 168)).min() - 1
    f['volx'] = df.v / df.v.rolling(24).mean()
    f['volx3'] = df.v.rolling(3).mean() / df.v.rolling(72).mean()
    d = c.diff()
    g, loss = d.clip(lower=0).rolling(14).mean(), (-d.clip(upper=0)).rolling(14).mean()
    f['rsi'] = 100 - 100 / (1 + g / (loss + 1e-12))
    f['ema_gap'] = c.ewm(span=12, adjust=False).mean() / c.ewm(span=48, adjust=False).mean() - 1
    bc = btc.c.reindex(df.index)
    br = bc.pct_change(fill_method=None)
    for n in (1, 4, 24):
        f[f'btc_ret{n}'] = bc.pct_change(n, fill_method=None)
    f['btc_vol24'] = br.rolling(24).std()
    f['btc_corr168'] = r.rolling(168).corr(br)
    f['btc_beta168'] = r.rolling(168).cov(br) / br.rolling(168).var()
    close_time = df.index + pd.Timedelta(hours=1)
    f['utc_hour'] = close_time.hour
    f['utc_weekday'] = close_time.day_of_week
    f['hours_to_funding'] = cfg['funding_interval_hours'] - close_time.hour % cfg['funding_interval_hours']
    return f.replace([np.inf, -np.inf], np.nan)


def add_futures(f, history):
    """As-of join; exchange statistics timestamp may describe start of interval,
    so delay hourly ratio/OI by one hour conservatively. No backward fill."""
    close = f.index + pd.Timedelta(hours=1)
    def align(name, time_key, value_key, delay=0):
        rows = history.get(name, [])
        if not rows:
            return pd.Series(np.nan, index=f.index)
        try:
            s = pd.Series([float(x[value_key]) for x in rows], index=pd.to_datetime([x[time_key] for x in rows], unit='ms') + pd.Timedelta(hours=delay)).sort_index()
            s = s[~s.index.duplicated(keep='last')]
            aligned = s.reindex(close, method='ffill', tolerance=pd.Timedelta(hours=24 if name == 'funding' else 2))
            return pd.Series(aligned.to_numpy(), index=f.index)
        except (KeyError, ValueError, TypeError):
            return pd.Series(np.nan, index=f.index)
    funding = align('funding', 'fundingTime', 'fundingRate')
    f['funding_rate'] = funding
    f['funding_mean24'] = funding.rolling(24, min_periods=24).mean()
    f['funding_change24'] = funding - funding.shift(24)
    oi = align('oi', 'timestamp', 'sumOpenInterest', 1)
    f['open_interest'] = oi
    for n in (1, 4, 24):
        f[f'oi_change{n}'] = oi.pct_change(n, fill_method=None)
    f['global_ls'] = align('global_ls', 'timestamp', 'longShortRatio', 1)
    f['top_ls'] = align('top_ls', 'timestamp', 'longShortRatio', 1)
    return f.replace([np.inf, -np.inf], np.nan)


def labels(df, thresholds, horizon):
    """First barrier wins. Both barriers in the same hourly candle are unknowable."""
    threshold = np.broadcast_to(np.asarray(thresholds, dtype=float), len(df))
    hi, lo, close = df.h.to_numpy(), df.l.to_numpy(), df.c.to_numpy()
    up = np.full(len(df), np.nan); dn = up.copy()
    for i in range(len(df) - horizon):
        if not np.isfinite(threshold[i]) or threshold[i] <= 0:
            continue
        u = np.flatnonzero(hi[i+1:i+1+horizon] >= close[i]*(1+threshold[i]))
        d = np.flatnonzero(lo[i+1:i+1+horizon] <= close[i]*(1-threshold[i]))
        if len(u) and len(d) and u[0] == d[0]:
            continue
        up[i] = float(len(u) > 0 and (len(d) == 0 or u[0] < d[0]))
        dn[i] = float(len(d) > 0 and (len(u) == 0 or d[0] < u[0]))
    return pd.DataFrame({'y_up': up, 'y_dn': dn}, index=df.index)
