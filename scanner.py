"""Coin Radar: Binance geçmiş verisiyle kısa vadede ±%10 hareket olasılığını tahmin eder.
Çıktı: docs/data.json (web arayüzü bunu okur)."""
import os, json, time
from datetime import datetime, timezone
import numpy as np, pandas as pd, requests, lightgbm as lgb
from sklearn.metrics import roc_auc_score

BASE = os.getenv("BINANCE_BASE", "https://data-api.binance.vision")  # ABD IP'lerinde de çalışır
TOP_N = int(os.getenv("TOP_N", 80))                 # hacme göre ilk N coin
MIN_VOL = float(os.getenv("MIN_VOLUME_USDT", 5e6))  # 24s min hacim
PAGES = int(os.getenv("PAGES", 3))                  # 1 sayfa = 1000 saatlik mum
H = int(os.getenv("HORIZON_H", 24))                 # tahmin ufku (saat)
TH = float(os.getenv("THRESHOLD", 0.10))            # hedef hareket (%10)
OUT = os.getenv("OUT", "docs/data.json")
SKIP = {"USDC", "FDUSD", "TUSD", "USDP", "DAI", "EUR", "TRY", "USD1", "XUSD", "AEUR", "PAXG", "WBTC", "WBETH"}
PARAMS = dict(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=100,
              subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=5, verbose=-1)


def get(path, **p):
    for i in range(3):
        try:
            r = requests.get(BASE + path, params=p, timeout=20)
            r.raise_for_status()
            return r.json()
        except Exception:
            if i == 2:
                raise
            time.sleep(1.5)


def universe():
    rows = [x for x in get("/api/v3/ticker/24hr")
            if x["symbol"].endswith("USDT") and x["symbol"][:-4] not in SKIP and float(x["quoteVolume"]) >= MIN_VOL]
    rows.sort(key=lambda x: -float(x["quoteVolume"]))
    return rows[:TOP_N]


def klines(sym):
    out, end = [], None
    for _ in range(PAGES):
        p = dict(symbol=sym, interval="1h", limit=1000)
        if end:
            p["endTime"] = end
        k = get("/api/v3/klines", **p)
        if not k:
            break
        out = k + out
        end = k[0][0] - 1
        time.sleep(0.05)
    df = pd.DataFrame(out).iloc[:, :6]
    df.columns = ["t", "o", "h", "l", "c", "v"]
    df = df.astype(float)
    df["t"] = pd.to_datetime(df["t"], unit="ms")
    return df.drop_duplicates("t").set_index("t")


def feats(df):
    c, r = df.c, df.c.pct_change()
    f = pd.DataFrame(index=df.index)
    for n in (1, 3, 6, 12, 24, 48, 120):
        f[f"ret{n}"] = c.pct_change(n)
    f["vol24"], f["vol72"] = r.rolling(24).std(), r.rolling(72).std()
    f["vol_ratio"] = f.vol24 / f.vol72
    f["range24"] = (df.h.rolling(24).max() - df.l.rolling(24).min()) / c
    f["atr14"] = ((df.h - df.l) / c).rolling(14).mean()
    f["to_hi24"] = c / df.h.rolling(24).max() - 1
    f["to_lo24"] = c / df.l.rolling(24).min() - 1
    f["to_hi120"] = c / df.h.rolling(120).max() - 1
    f["to_lo120"] = c / df.l.rolling(120).min() - 1
    f["volx"] = df.v / df.v.rolling(24).mean()
    f["volx3"] = df.v.rolling(3).mean() / df.v.rolling(72).mean()
    d = c.diff()
    g, l = d.clip(lower=0).rolling(14).mean(), (-d.clip(upper=0)).rolling(14).mean()
    f["rsi"] = 100 - 100 / (1 + g / (l + 1e-12))
    f["ema_gap"] = c.ewm(span=12).mean() / c.ewm(span=48).mean() - 1
    return f.replace([np.inf, -np.inf], np.nan)


def labels(df):
    hi = df.h[::-1].rolling(H).max()[::-1].shift(-1)  # sonraki H saatin en yükseği
    lo = df.l[::-1].rolling(H).min()[::-1].shift(-1)
    ux, dx = hi / df.c - 1 >= TH, lo / df.c - 1 <= -TH
    up = (ux & ~dx).astype(float).where(hi.notna())
    dn = (dx & ~ux).astype(float).where(lo.notna())
    return pd.DataFrame({"y_up": up, "y_dn": dn})


def fit_eval(X, y, ts):
    cut = np.sort(ts)[int(len(ts) * 0.8)]
    tr, te = ts < cut - np.timedelta64(H, "h"), ts >= cut  # eğitim/test arasında H saat boşluk
    p = lgb.LGBMClassifier(**PARAMS).fit(X[tr], y[tr]).predict_proba(X[te])[:, 1]
    yt = y[te].values
    k = max(1, int(len(p) * 0.02))
    m = dict(auc=round(float(roc_auc_score(yt, p)), 3) if len(set(yt)) > 1 else None,
             precision_top2=round(float(yt[np.argsort(-p)[:k]].mean()), 4),
             base_rate=round(float(yt.mean()), 4), test_rows=int(len(p)))
    return lgb.LGBMClassifier(**PARAMS).fit(X, y), m


def main():
    uni = universe()
    print(len(uni), "coin taranıyor...")
    frames, last = [], {}
    for x in uni:
        s = x["symbol"]
        try:
            df = klines(s).iloc[:-1]  # son (kapanmamış) mumu at
        except Exception as e:
            print("atlandı", s, e)
            continue
        if len(df) < 500:
            continue
        f = feats(df)
        d = f.join(labels(df))
        d["sym"] = s
        frames.append(d)
        last[s] = (f.iloc[-1], float(df.c.iloc[-1]), x)
    data = pd.concat(frames)
    cols = [c for c in data.columns if c not in ("y_up", "y_dn", "sym")]
    tr = data.dropna(subset=cols + ["y_up", "y_dn"])
    X, ts = tr[cols], tr.index.values
    syms = list(last)
    Xl = pd.DataFrame([last[s][0] for s in syms])[cols]
    res, metrics = {}, {}
    for name in ("up", "dn"):
        model, metrics[name] = fit_eval(X, tr[f"y_{name}"].astype(int), ts)
        res[name] = model.predict_proba(Xl)[:, 1]
        print(name, metrics[name])
    coins = [dict(symbol=s[:-4], price=last[s][1], chg24=float(last[s][2]["priceChangePercent"]),
                  volume=float(last[s][2]["quoteVolume"]), p_up=round(float(res["up"][i]), 4),
                  p_dn=round(float(res["dn"][i]), 4)) for i, s in enumerate(syms)]
    os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as fh:
        json.dump(dict(generated=datetime.now(timezone.utc).isoformat(), horizon=H, threshold=TH,
                       metrics=metrics, coins=coins), fh, ensure_ascii=False)
    print("yazıldı:", OUT)


if __name__ == "__main__":
    main()
