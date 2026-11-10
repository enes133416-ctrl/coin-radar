"""Ölçüm 3: Duyarlılık testi — yöntem gerçek bir sinyali yakalayabiliyor mu?

Ablasyonda piyasada bitki sinyal yoktu; tüm aileler AUC ~0,45-0,57 verdi.
Bu, "gösterge sayısı bilgi yaratmaz" bulgusudur ama yöntemin çalıştığını da kanıtlamaz.

Burada kontrollü deney yapıyoruz: sinyali TEK bir kanaldan enjekte edip,
hangi gösterge ailesinin onu yakaladığını ölçüyoruz.
  Senaryo A: sinyal yalnızca emir akışında (taker buy dengesizliği) → 1 saatlik getiriye yansır
  Senaryo B: sinyal yalnızca momentumda (aşırı hareketten geri dönüş) → 1 saatlik getiriye yansır
  Senaryo C: sinyal yok (kontrol) → hiçbir aile AUC 0,5'i anlamlı geçmemeli

Kullanım: python sinyal_testi.py
"""
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import roc_auc_score
from gostergeler import feature_frame, FAMILIES, synthetic_market

BASE = ['atr_pct', 'vol_z', 'ret_1', 'ret_24', 'pos168', 'pos720']
SETS = {
    'trend': FAMILIES['trend'],
    'momentum': FAMILIES['momentum'],
    'bant': ['bb_width', 'bb_pos', 'squeeze'],
    'hacim': FAMILIES['flow'],
    'emir akışı': ['taker_buy', 'taker_buy_z', 'avg_ticket_z', 'cmf'],
}


def scenario(kind, n_assets=25, n_bars=5000, alpha=0.30, seed=11):
    """Sinyal tek kanaldan enjekte edilir; diğer kanallar bağımsız gürültüdür."""
    rng = np.random.default_rng(seed)
    frames = {}
    idx = pd.date_range('2021-01-01', periods=n_bars, freq='h')
    for k in range(n_assets):
        eps_flow = rng.normal(0, 1.0, n_bars)      # emir akışını süren şok
        eps_mom = rng.normal(0, 1.0, n_bars)       # momentumu süren ayrı şok
        r = np.zeros(n_bars)
        for t in range(1, n_bars):
            if kind == 'flow':
                r[t] = alpha * eps_flow[t - 1]     # akış öngörüyor (gözlenebilir)
            elif kind == 'momentum':
                # NEGATİF otokorelasyon = geri dönüş: r[t] kısmen r[t-1]'in tersi.
                # Bu, geçmiş fiyattan GÖZLENEBİLİR ve momentum göstergeleri yakalamalı.
                r[t] = -alpha * r[t - 1] + 0.004 * eps_mom[t]
            else:
                r[t] = 0.0                          # kontrol: sinyal yok
        c = 100 * np.exp(np.cumsum(r + rng.normal(0, 0.004, n_bars)))
        # emir akışı: SADECE flow senaryosunda sinyalle ilişkili
        imb = np.clip((0.55 * eps_flow if kind == 'flow' else np.zeros(n_bars))
                      + rng.normal(0, 0.12, n_bars), -0.95, 0.95)
        v = np.exp(rng.normal(10, 0.6, n_bars))
        tb = v * np.clip(0.5 + 0.5 * imb, 0.02, 0.98)
        # fitiller bağımsız gürültüden: bilgi taşımaz (gerçekçi ama yansız)
        o = np.concatenate([[c[0]], c[:-1]])
        wick = np.abs(rng.normal(0, 0.0035, n_bars))
        h = np.maximum(o, c) * (1 + wick)
        l = np.minimum(o, c) * (1 - wick)
        frames[f'S{k:02d}'] = pd.DataFrame({
            'o': o, 'h': h, 'l': l, 'c': c, 'v': v, 'tb': tb,
            'ntrades': np.exp(rng.normal(7, 0.4, n_bars))}, index=idx)
    return frames


def run(kind):
    frames = scenario(kind)
    rows = []
    for s, df in frames.items():
        f = feature_frame(df, df)
        # etiket: sonraki saat yukarı mı? (bitki sinyal tek adımda)
        f['y'] = (df.c.pct_change().shift(-1) > 0).astype(float)
        f.loc[df.index[-1], 'y'] = np.nan
        f['sym'] = s
        rows.append(f)
    data = pd.concat(rows).replace([np.inf, -np.inf], np.nan).dropna(subset=['y'])
    data = data.iloc[720:]
    # ZAMAN sırasına göre böl (varlık sırasına göre değil!) — sızıntı kontrolü
    data = data.sort_index(kind='stable')
    times = np.sort(data.index.unique())
    cut_time = times[int(len(times) * 0.8)]
    tr, te = data[data.index < cut_time], data[data.index >= cut_time]
    params = dict(n_estimators=200, learning_rate=0.05, num_leaves=15, min_child_samples=80,
                  subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=5,
                  verbose=-1, n_jobs=2, random_state=1)
    out = {}
    for name, cols in SETS.items():
        cols = [c for c in cols if c in data.columns]
        m = lgb.LGBMClassifier(**params).fit(tr[cols], tr.y.astype(int))
        p = m.predict_proba(te[cols])[:, 1]
        out[name] = (roc_auc_score(te.y.astype(int), p), m.feature_importances_)
    return out, len(tr), len(te)


if __name__ == '__main__':
    print("\nEtiket: sonraki 1 saat yukarı mı?  (sinyal gücü α = 0,30)")
    print("Not: Bu, 24 saatlik değil 1 saatlik ufuktur — sinyalin varlığını tespit etmek için.\n")
    for kind, title in [('none', 'KONTROL: sinyal yok'),
                        ('flow', 'A: sinyal SADECE emir akışında'),
                        ('momentum', 'B: sinyal SADECE momentumda (geri dönüş)')]:
        res, ntr, nte = run(kind)
        print(f"{title}   (eğitim {ntr:,} · test {nte:,} satır)")
        line = '  '.join(f"{k}: {v[0]:.3f}" for k, v in res.items())
        print(f"  AUC  {line}")
        best = max(res.items(), key=lambda kv: kv[1][0])
        print(f"  → en iyi aile: {best[0]} ({best[1][0]:.3f})\n")
