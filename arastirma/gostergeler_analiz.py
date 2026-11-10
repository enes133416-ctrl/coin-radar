"""Ölçüm 1: Göstergelerin korelasyon yapısı ve "bağımsız bilgi" sayısı.

Sorulan: 20 gösterge eklemek, 5 boyuttan fazlasını veriyor mu?
Yöntem: korelasyon kümelemesi + PCA ile etkin boyut + her gösterge için
"ailesinin en iyisi olduktan sonra kalan tek başına bilgi" (incremental).

Kullanım: python arastirma/gostergeler_analiz.py [--real]
"""
import sys
import numpy as np
import pandas as pd
from gostergeler import feature_frame, FAMILIES, synthetic_market

REAL = '--real' in sys.argv


def load():
    if REAL:
        from radar.data import Binance
        import json
        cfg = json.load(open('config.json'))
        api = Binance(cfg)
        syms = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT',
                'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'SUIUSDT']
        btc = api.klines('BTCUSDT')
        frames = {}
        for s in syms:
            df = btc if s == 'BTCUSDT' else api.klines(s)
            if len(df) > 800:
                frames[s] = df
        return frames, btc
    m = synthetic_market()
    return m, m['A00']


def main():
    frames, btc = load()
    rows = []
    for s, df in frames.items():
        f = feature_frame(df, btc)
        f['sym'] = s
        rows.append(f)
    X = pd.concat(rows).replace([np.inf, -np.inf], np.nan)
    cols = [c for c in X.columns if c != 'sym' and X[c].notna().mean() > 0.3]
    X = X[cols].dropna(thresh=int(len(cols) * 0.6))
    print(f"\n{'GERÇEK Binance mumları' if REAL else 'SENTETİK piyasa'} · "
          f"{len(frames)} varlık · {len(X):,} satır · {len(cols)} gösterge\n")

    # 1) |korelasyon| — hangi göstergeler neredeyse aynı şeyi söylüyor?
    corr = X.rank().corr().abs()
    print("En yüksek 12 gösterge çifti (|Spearman|):")
    pairs = [(corr.loc[a, b], a, b) for i, a in enumerate(cols) for b in cols[i + 1:]]
    for v, a, b in sorted(pairs, reverse=True)[:12]:
        flag = '  ← neredeyse aynı' if v > 0.9 else ('  ← güçlü örtüşme' if v > 0.8 else '')
        print(f"  {v:5.2f}  {a:14s} {b}{flag}")

    # 2) Etkin boyut (PCA) — kaç bağımsız bilgi ekseni var?
    Z = X.rank().fillna(X.rank().median())
    Z = (Z - Z.mean()) / (Z.std() + 1e-9)
    ev = np.linalg.svd(Z.to_numpy(), compute_uv=False)
    ev = ev ** 2 / (ev ** 2).sum()
    print(f"\nPCA: ilk 3 eksen toplam varyansın %{ev[:3].sum()*100:.0f}'i, "
          f"ilk 5 eksen %{ev[:5].sum()*100:.0f}'i, ilk 8 eksen %{ev[:8].sum()*100:.0f}'i")
    k80 = int(np.searchsorted(np.cumsum(ev), 0.80) + 1)
    k95 = int(np.searchsorted(np.cumsum(ev), 0.95) + 1)
    print(f"  → %80 bilgi için {k80} boyut, %95 için {k95} boyut yeterli "
          f"(gösterge sayısı {len(cols)})")

    # 3) Aile içi ortalama korelasyon (her aile kendi içinde ne kadar tekrar?)
    print("\nAile içi ortalama |korelasyon| (1'e yakın = aile içinde tekrar var):")
    for fam, members in FAMILIES.items():
        members = [m for m in members if m in cols]
        if len(members) < 2:
            continue
        vals = [corr.loc[a, b] for i, a in enumerate(members) for b in members[i + 1:]]
        print(f"  {fam:11s} {np.mean(vals):.2f}   ({', '.join(members)})")


if __name__ == '__main__':
    main()
