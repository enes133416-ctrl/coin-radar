"""Ölçüm 4: Gösterge SAYISI arttıkça test performansı ne oluyor?

Kontrollü deney: sinyal YOK, sadece rastgele gürültü özellikleri.
Beklenti: eğitim AUC'si yükselir, test AUC'si 0,50'de kalır → "aşırı uyum".
Bu, "15 gösterge ekleyelim" kararının neden tehlikeli olduğunun kanıtıdır.

Kullanım: python gurultu_testi.py
"""
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import roc_auc_score
from gostergeler import feature_frame, synthetic_market

rng = np.random.default_rng(0)
m = synthetic_market(n_assets=25, n_bars=4000, planted=False)
rows = []
for s, df in m.items():
    f = feature_frame(df, df)
    f['y'] = (df.c.pct_change().shift(-1) > 0).astype(float)
    f['sym'] = s
    rows.append(f)
data = pd.concat(rows).replace([np.inf, -np.inf], np.nan).dropna(subset=['y'])
data = data.sort_index(kind='stable').iloc[720:]
times = np.sort(data.index.unique())
cut = times[int(len(times) * 0.8)]
tr, te = data[data.index < cut], data[data.index >= cut]
real = [c for c in ['atr_pct', 'vol_z', 'ret_1', 'ret_24', 'pos168', 'rsi', 'adx', 'bb_width']
        if c in data.columns]
params = dict(n_estimators=300, learning_rate=0.05, num_leaves=31, min_child_samples=20,
              verbose=-1, n_jobs=2, random_state=2)

print("\nSinyal YOK (saf gürültü hedefi). Eğitim vs test AUC:")
print(f"{'özellik sayısı':>14} {'eğitim AUC':>11} {'test AUC':>9} {'aşırı uyum farkı':>17}")
print('-' * 56)
for k in [5, 10, 20, 35, 60]:
    cols = list(real) + [f'noise{i}' for i in range(max(0, k - len(real)))]
    Xtr, Xte = tr[list(real)].copy(), te[list(real)].copy()
    for c in cols:
        if c.startswith('noise'):
            Xtr[c] = rng.normal(size=len(Xtr))
            Xte[c] = rng.normal(size=len(Xte))
    mdl = lgb.LGBMClassifier(**params).fit(Xtr[cols], tr.y.astype(int))
    a_tr = roc_auc_score(tr.y.astype(int), mdl.predict_proba(Xtr[cols])[:, 1])
    a_te = roc_auc_score(te.y.astype(int), mdl.predict_proba(Xte[cols])[:, 1])
    print(f"{k:>14} {a_tr:>11.3f} {a_te:>9.3f} {a_tr-a_te:>17.3f}")
print("\nYorum: eğitim AUC'si gösterge sayısıyla şişerken test AUC'si 0,50 civarında kalıyor.")
print("Sitede 'eğitim doğruluğu' veya 'backtest isabeti' gösterilirse tam olarak bu tuzak sergilenir.")
