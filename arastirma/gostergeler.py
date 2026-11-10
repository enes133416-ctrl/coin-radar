"""Gösterge ailesi analizi: hangi göstergeler bağımsız bilgi taşıyor?

Bu modül üretim kodu değil, ARAŞTIRMA kodudur. Amacı şu soruyu ölçmek:
"15 gösterge eklemek, 5 temel boyuttan fazlasını veriyor mu?"

Kullanım:
    python arastirma/ablasyon.py            # sentetik piyasa (ağ gerekmez)
    python arastirma/ablasyon.py --real     # Binance'ten gerçek mumlar (ağ gerekir)
"""
import sys
import numpy as np
import pandas as pd


# ---------------------------------------------------------------- göstergeler
def rma(s, n):
    """Wilder yumuşatması (RSI/ATR/ADX'in standardı)."""
    return s.ewm(alpha=1 / n, adjust=False, min_periods=n).mean()


def ema(s, n):
    return s.ewm(span=n, adjust=False, min_periods=n).mean()


def true_range(df):
    pc = df.c.shift()
    return pd.concat([df.h - df.l, (df.h - pc).abs(), (df.l - pc).abs()], axis=1).max(axis=1)


def atr(df, n=14):
    return rma(true_range(df), n)


def rsi(df, n=14):
    d = df.c.diff()
    up = rma(d.clip(lower=0), n)
    dn = rma((-d).clip(lower=0), n)
    return 100 - 100 / (1 + up / (dn + 1e-12))


def stoch(df, n=14):
    lo = df.l.rolling(n).min()
    hi = df.h.rolling(n).max()
    return 100 * (df.c - lo) / (hi - lo + 1e-12)


def stochrsi(df, n=14):
    r = rsi(df, n)
    lo, hi = r.rolling(n).min(), r.rolling(n).max()
    return 100 * (r - lo) / (hi - lo + 1e-12)


def kdj(df, n=9):
    k = stoch(df, n).ewm(alpha=1 / 3, adjust=False).mean()
    d = k.ewm(alpha=1 / 3, adjust=False).mean()
    return k, d, 3 * k - 2 * d


def williams_r(df, n=14):
    hi, lo = df.h.rolling(n).max(), df.l.rolling(n).min()
    return -100 * (hi - df.c) / (hi - lo + 1e-12)


def cci(df, n=20):
    tp = (df.h + df.l + df.c) / 3
    ma = tp.rolling(n).mean()
    md = (tp - ma).abs().rolling(n).mean()
    return (tp - ma) / (0.015 * md + 1e-12)


def macd(df, fast=12, slow=26, sig=9):
    line = ema(df.c, fast) - ema(df.c, slow)
    return line, ema(line, sig), line - ema(line, sig)


def bollinger(df, n=20, k=2):
    ma = df.c.rolling(n).mean()
    sd = df.c.rolling(n).std()
    upper, lower = ma + k * sd, ma - k * sd
    width = (upper - lower) / ma
    pos = (df.c - lower) / (upper - lower + 1e-12)
    return ma, width, pos


def parabolic_sar(df, step=0.02, mx=0.2):
    """Klasik Wilder PSAR. Yön: +1 yukarı trend, -1 aşağı."""
    h, l = df.h.to_numpy().copy(), df.l.to_numpy().copy()
    n = len(df)
    sar = np.full(n, np.nan)
    trend = np.ones(n)
    if n < 3:
        return pd.Series(sar, index=df.index), pd.Series(trend, index=df.index)
    af, ep, s = step, h[0], l[0]
    up = True
    for i in range(1, n):
        s = s + af * (ep - s)
        if up:
            if l[i] < s:
                up = False
                s, ep, af = ep, l[i], step
            elif h[i] > ep:
                ep, af = h[i], min(af + step, mx)
        else:
            if h[i] > s:
                up = True
                s, ep, af = ep, h[i], step
            elif l[i] < ep:
                ep, af = l[i], min(af + step, mx)
        sar[i] = s
        trend[i] = 1.0 if up else -1.0
    return pd.Series(sar, index=df.index), pd.Series(trend, index=df.index)


def supertrend(df, n=10, mult=3.0):
    """Supertrend: ATR bantları + yön. Dönüş: trend değişimi."""
    a = atr(df, n)
    hl2 = (df.h + df.l) / 2
    upper, lower = hl2 + mult * a, hl2 - mult * a
    n_rows = len(df)
    trend = np.ones(n_rows)
    st = np.full(n_rows, np.nan)
    fu, fl = upper.to_numpy().copy(), lower.to_numpy().copy()
    c = df.c.to_numpy()
    for i in range(1, n_rows):
        if np.isnan(fu[i]) or np.isnan(fl[i]):
            continue
        if c[i - 1] <= (fu[i - 1] if i > 1 else fu[i]):
            fu[i] = min(fu[i], fu[i - 1] if i > 1 else fu[i])
        if c[i - 1] >= (fl[i - 1] if i > 1 else fl[i]):
            fl[i] = max(fl[i], fl[i - 1] if i > 1 else fl[i])
        if c[i] > fu[i]:
            trend[i] = 1
        elif c[i] < fl[i]:
            trend[i] = -1
        else:
            trend[i] = trend[i - 1]
        st[i] = fl[i] if trend[i] > 0 else fu[i]
    return pd.Series(st, index=df.index), pd.Series(trend, index=df.index)


def obv(df):
    sign = np.sign(df.c.diff()).fillna(0)
    return (sign * df.v).cumsum()


def vwap(df, n=24):
    tp = (df.h + df.l + df.c) / 3
    return (tp * df.v).rolling(n).sum() / (df.v.rolling(n).sum() + 1e-12)


def mfi(df, n=14):
    tp = (df.h + df.l + df.c) / 3
    flow = tp * df.v
    pos = flow.where(tp.diff() > 0, 0)
    neg = flow.where(tp.diff() < 0, 0)
    return 100 - 100 / (1 + pos.rolling(n).sum() / (neg.rolling(n).sum() + 1e-12))


def adx(df, n=14):
    up = df.h.diff()
    dn = -df.l.diff()
    plus = 100 * (up.where((up > dn) & (up > 0), 0) / atr(df, n))
    minus = 100 * (dn.where((dn > up) & (dn > 0), 0) / atr(df, n))
    dx = 100 * (plus - minus).abs() / (plus + minus + 1e-12)
    return rma(dx, n)


def cmf(df, n=20):
    mfm = ((df.c - df.l) - (df.h - df.c)) / (df.h - df.l + 1e-12)
    return (mfm * df.v).rolling(n).sum() / (df.v.rolling(n).sum() + 1e-12)


# ---------------------------------------------------------------- özellikler
def feature_frame(df, btc=None):
    """Tüm göstergeler tek tabloda; hepsi kapanışta bilinir (sızıntı yok)."""
    f = pd.DataFrame(index=df.index)
    a = atr(df, 14)
    f['atr_pct'] = a / df.c
    f['atr_ratio'] = a / atr(df, 56)          # oynaklık rejimi
    f['vol_z'] = (df.c.pct_change().rolling(24).std() /
                  df.c.pct_change().rolling(168, min_periods=72).std())
    f['ret_1'] = df.c.pct_change()
    f['ret_24'] = df.c.pct_change(24)

    # trend ailesi
    f['ma_slope'] = ema(df.c, 20).pct_change(6) / f['atr_pct']
    f['ema_slope'] = ema(df.c, 50).pct_change(6) / f['atr_pct']
    f['ma_gap'] = (ema(df.c, 12) / ema(df.c, 48) - 1) / f['atr_pct']
    _, f['sar_dir'] = parabolic_sar(df)
    _, f['st_dir'] = supertrend(df)
    f['macd_hist'] = macd(df)[2] / df.c / f['atr_pct']
    f['adx'] = adx(df)

    # momentum ailesi
    f['rsi'] = rsi(df)
    f['kdj_j'] = kdj(df)[2]
    f['wr'] = williams_r(df)
    f['stochrsi'] = stochrsi(df)
    f['cci'] = cci(df)

    # oynaklık / bant ailesi
    _, f['bb_width'], f['bb_pos'] = bollinger(df)
    f['squeeze'] = f['bb_width'] / f['bb_width'].rolling(168, min_periods=72).mean()

    # hacim / akış ailesi
    f['vol_z_raw'] = df.v / df.v.rolling(24).mean()
    f['obv_slope'] = obv(df).diff(6) / (df.v.rolling(24).sum() + 1e-12)
    f['vwap_dev'] = (df.c / vwap(df, 24) - 1) / f['atr_pct']
    f['mfi'] = mfi(df)
    f['cmf'] = cmf(df)
    if 'tb' in df:                            # taker buy hacmi (Binance kline alanı)
        f['taker_buy'] = df.tb / (df.v + 1e-12) - 0.5
        f['taker_buy_z'] = (f.taker_buy - f.taker_buy.rolling(72, min_periods=24).mean()) / \
                           (f.taker_buy.rolling(72, min_periods=24).std() + 1e-12)
    if 'ntrades' in df:
        f['avg_ticket'] = df.v / (df.ntrades + 1e-12)
        f['avg_ticket_z'] = (np.log(f.avg_ticket) - np.log(f.avg_ticket).rolling(72, min_periods=24).mean()) / \
                            (np.log(f.avg_ticket).rolling(72, min_periods=24).std() + 1e-12)

    # konum
    for n in (168, 720):
        f[f'pos{n}'] = (df.c - df.l.rolling(n, min_periods=min(n, 168)).min()) / \
                       (df.h.rolling(n, min_periods=min(n, 168)).max() -
                        df.l.rolling(n, min_periods=min(n, 168)).min() + 1e-12)

    if btc is not None:
        br = btc.c.pct_change()
        f['btc_ret24'] = btc.c.pct_change(24)
        f['btc_vol24'] = br.rolling(24).std()
        f['btc_corr'] = df.c.pct_change().rolling(168).corr(br)
        f['beta'] = df.c.pct_change().rolling(168).cov(br) / (br.rolling(168).var() + 1e-12)
    return f.replace([np.inf, -np.inf], np.nan)


FAMILIES = {
    'trend': ['ma_slope', 'ema_slope', 'ma_gap', 'sar_dir', 'st_dir', 'macd_hist'],
    'momentum': ['rsi', 'kdj_j', 'wr', 'stochrsi', 'cci'],
    'volatility': ['atr_pct', 'atr_ratio', 'vol_z', 'bb_width', 'bb_pos', 'squeeze'],
    'flow': ['vol_z_raw', 'obv_slope', 'vwap_dev', 'mfi', 'cmf'],
    'orderflow': ['taker_buy', 'taker_buy_z', 'avg_ticket_z'],
    'position': ['pos168', 'pos720'],
}


# ---------------------------------------------------------------- etiket
def triple_barrier(df, up_mult=3.0, dn_mult=1.0, horizon=24):
    """İlk-temas etiketi: ATR tabanlı asimetrik bariyer. Aynı mumda ikisi → NaN."""
    a = atr(df, 14).to_numpy()
    c, h, l = df.c.to_numpy(), df.h.to_numpy(), df.l.to_numpy()
    n = len(df)
    y = np.full(n, np.nan)
    for i in range(n - horizon):
        if not np.isfinite(a[i]) or a[i] <= 0:
            continue
        ub = c[i] + up_mult * a[i]
        lb = c[i] - dn_mult * a[i]
        u = np.flatnonzero(h[i + 1:i + 1 + horizon] >= ub)
        d = np.flatnonzero(l[i + 1:i + 1 + horizon] <= lb)
        iu, id_ = (u[0] if len(u) else 10**6), (d[0] if len(d) else 10**6)
        if iu == id_:
            continue
        y[i] = 1.0 if iu < id_ else 0.0
    return pd.Series(y, index=df.index)


# ---------------------------------------------------------------- sentetik veri
def synthetic_market(n_assets=25, n_bars=6000, seed=3, planted=True):
    """Ortak piyasa faktörü + oynaklık kümelenmesi + (opsiyonel) GÖZLENEBİLİR sürüklenme.

    planted=True iken getiriye, emir akışından gözlenebilen bir sürüklenme eklenir:
      drift_t = k1 * taker_buy_imbalance_t - k2 * (24 saatlik getiri)  (aşırı hareketten geri dönüş)
    Bu, "gerçekten tahmin edilebilir bir bileşen" senaryosudur ve ablasyonun
    hangi gösterge ailesinin bu bileşeni yakaladığını ölçmesini sağlar.
    Gerçek piyasada bu bileşenin varlığı ve büyüklüğü TARTIŞMALIDIR; burada yalnızca
    yöntemin doğru çalıştığını göstermek için var.
    """
    rng = np.random.default_rng(seed)
    market = np.zeros(n_bars)
    s = np.full(n_bars, 0.010)
    for t in range(1, n_bars):
        s[t] = np.sqrt(0.90 * s[t - 1] ** 2 + 0.10 * (market[t - 1] ** 2 + 1e-6))
        s[t] = min(s[t], 0.05)
        market[t] = rng.normal(0, s[t])
    out = {}
    for k in range(n_assets):
        beta = rng.uniform(0.4, 1.6)
        idio = rng.uniform(0.4, 1.2)
        r = beta * market + rng.normal(0, idio * s, n_bars)
        c = 100 * np.exp(np.cumsum(r))
        # gözlenebilir akış dengesizliği
        imb = np.clip(rng.normal(0, 0.12, n_bars) + 0.35 * np.gradient(np.log(c)), -0.95, 0.95)
        if planted:
            hist = np.zeros(n_bars)
            for t in range(25, n_bars):
                r24 = np.log(c[t] / c[t - 24])
                hist[t] = 0.0009 * imb[t - 1] - 0.04 * r24 / 24
            c = c * np.exp(np.cumsum(hist) - np.cumsum(hist).mean())
            c = c / c[0] * 100
        # DİKKAT: burada nedensellik şart. np.gradient merkezi fark kullanır → gelecek bilgisi
        # sızar. Bu yüzden fitiller ve hacim yalnızca mevcut barın getirisine bağlanır.
        lr = np.concatenate([[0.0], np.diff(np.log(c))])
        spread = np.abs(lr) + 1e-4
        h = c * (1 + spread * rng.uniform(0.2, 1.2, n_bars))
        l = c * (1 - spread * rng.uniform(0.2, 1.2, n_bars))
        v = np.exp(rng.normal(10, 0.7, n_bars)) * (1 + 8 * np.abs(lr))
        tb = v * np.clip(0.5 + imb * 0.5 + rng.normal(0, 0.05, n_bars), 0.02, 0.98)
        idx = pd.date_range('2021-01-01', periods=n_bars, freq='h')
        out[f'A{k:02d}'] = pd.DataFrame({
            'o': np.concatenate([[c[0]], c[:-1]]),
            'h': np.maximum.reduce([h, c, np.concatenate([[c[0]], c[:-1]])]),
            'l': np.minimum.reduce([l, c, np.concatenate([[c[0]], c[:-1]])]),
            'c': c, 'v': v, 'tb': tb,
            'ntrades': np.exp(rng.normal(7, 0.5, n_bars))}, index=idx)
    return out
