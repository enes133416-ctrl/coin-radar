"""Ölçüm 2: Ablasyon — hangi gösterge ailesi gerçekten tahmin gücü katıyor?

Kurulum (üretim kodundaki ilkelere sadık):
  · Etiket: ilk-temas, ATR tabanlı asimetrik bariyer (3×ATR yukarı / 1×ATR aşağı, 24 saat)
  · Zaman sıralı bölme: eğitim → kalibrasyon (24s boşluk) → test (%20)
  · Örnek seyreltme: 24 saat (örtüşen etiket yok)
  · Değerlendirme: AUC, Brier, BSS (iklimsele karşı), top-10 isabet, top-10 EV

Kullanım: python arastirma/ablasyon.py [--real]
"""
import sys
import json
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import roc_auc_score, brier_score_loss
from gostergeler import feature_frame, triple_barrier, synthetic_market, FAMILIES, atr

REAL = '--real' in sys.argv

BASE = ['atr_pct', 'vol_z', 'ret_1', 'ret_24', 'pos168', 'pos720',
        'btc_ret24', 'btc_vol24', 'btc_corr', 'beta']

SETS = [
    ('0 · taban (volatilite+konum)', BASE),
    ('1 · + trend (MA/EMA/SAR/ST/MACD)', BASE + FAMILIES['trend']),
    ('2 · + momentum (RSI/KDJ/WR/StochRSI/CCI)', BASE + FAMILIES['momentum']),
    ('3 · + bant (BOLL/squeeze)', BASE + ['bb_width', 'bb_pos', 'squeeze']),
    ('4 · + hacim (OBV/VWAP/MFI/CMF/rel-vol)', BASE + FAMILIES['flow']),
    ('5 · + emir akışı (taker buy, bilet)', BASE + ['taker_buy', 'taker_buy_z', 'avg_ticket_z']),
    ('6 · + ADX', BASE + ['adx']),
    ('7 · HER ŞEY (35 gösterge)', None),
    ('8 · SADECE momentum (ana model)', FAMILIES['momentum']),
    ('9 · SADECE emir akışı', ['taker_buy', 'taker_buy_z', 'avg_ticket_z', 'cmf', 'obv_slope']),
    ('10 · SADECE trend', FAMILIES['trend']),
]


def load():
    if REAL:
        from radar.data import Binance
        cfg = json.load(open('config.json'))
        api = Binance(cfg)
        syms = ['BTCUSDT', 'ETHUSDT', 'SOLUSDT', 'BNBUSDT', 'XRPUSDT', 'DOGEUSDT',
                'ADAUSDT', 'AVAXUSDT', 'LINKUSDT', 'SUIUSDT', 'LTCUSDT', 'DOTUSDT']
        btc = api.klines('BTCUSDT')
        frames = {}
        for s in syms:
            df = btc if s == 'BTCUSDT' else api.klines(s)
            if len(df) > 800:
                frames[s] = df
        return frames, btc
    m = synthetic_market(planted=True)
    return m, m['A00']


def build(frames, btc):
    rows = []
    for s, df in frames.items():
        f = feature_frame(df, btc)
        f['y'] = triple_barrier(df)
        f['sym'] = s
        f['bar'] = np.arange(len(df))
        rows.append(f)
    data = pd.concat(rows).replace([np.inf, -np.inf], np.nan)
    # 24 saatlik seyreltme (örtüşen etiket yok) + ilk 720 saat ısınma dışı
    data = data[data.bar >= 720]
    data = data[data.bar % 24 == 0]
    return data.dropna(subset=['y'])


def evaluate(data, cols, seed=42):
    cols = [c for c in cols if c in data.columns]
    times = np.sort(data.index.unique())
    n = len(times)
    test_start = times[int(n * 0.80)]
    cal_start = times[int(n * 0.70)]
    gap = pd.Timedelta(hours=24)
    tr = data[data.index < cal_start - gap]
    cal = data[(data.index >= cal_start) & (data.index < test_start - gap)]
    te = data[data.index >= test_start]
    if min(len(tr), len(cal), len(te)) < 100:
        return None
    params = dict(n_estimators=250, learning_rate=0.04, num_leaves=15, min_child_samples=60,
                  subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=5,
                  verbose=-1, n_jobs=2, random_state=seed)
    m = lgb.LGBMClassifier(**params).fit(tr[cols], tr.y.astype(int))
    p_cal = m.predict_proba(cal[cols])[:, 1]
    # sadece ölçek düzeltmesi (basit Platt); isotonic değil — küçük kalibrasyon kümesinde güvenli
    from sklearn.linear_model import LogisticRegression
    pl = LogisticRegression().fit(p_cal.reshape(-1, 1), cal.y.astype(int))
    p = pl.predict_proba(m.predict_proba(te[cols])[:, 1].reshape(-1, 1))[:, 1]
    y = te.y.astype(int).to_numpy()
    base = float(y.mean())
    brier = brier_score_loss(y, p)
    ref = base * (1 - base)
    work = pd.DataFrame({'p': p, 'y': y}, index=te.index)
    top = work.sort_values('p', ascending=False).groupby(level=0).head(10)
    # top-10 EV: 3R kazanç, 1R kayıp, %0,1 maliyet (R cinsinden)
    hit = float(top.y.mean())
    ev = hit * (3 - 0.1) - (1 - hit) * (1 + 0.1)
    # test seti rastgele 10 seçilirse (baz oran) EV
    ev_base = base * (3 - 0.1) - (1 - base) * (1 + 0.1)
    return dict(n_feat=len(cols), auc=float(roc_auc_score(y, p)) if len(set(y)) > 1 else None,
                brier=brier, bss=1 - brier / ref if ref else None,
                base=base, top10=hit, ev10=ev, ev_base=ev_base, rows=len(y))


def main():
    frames, btc = load()
    data = build(frames, btc)
    all_cols = [c for c in data.columns if c not in ('y', 'sym', 'bar')]
    print(f"\n{'GERÇEK Binance verisi' if REAL else 'SENTETİK piyasa (gözlenebilir sürüklenme eklenmiş)'}")
    print(f"{len(frames)} varlık · {len(data):,} örnek · baz oran %{data.y.mean()*100:.1f} · "
          f"test dönemi son %20\n")
    print(f"{'özellik seti':46s} {'#':>3} {'AUC':>6} {'Brier':>7} {'BSS':>7} {'top10':>7} {'EV(R)':>7}")
    print('-' * 92)
    results = {}
    for name, cols in SETS:
        use = all_cols if cols is None else cols
        r = evaluate(data, use)
        if not r:
            print(f"{name:46s}  (yetersiz veri)")
            continue
        results[name] = r
        print(f"{name:46s} {r['n_feat']:3d} {r['auc']:6.3f} {r['brier']:7.4f} "
              f"{(r['bss'] or 0):7.2f} {r['top10']*100:6.1f}% {r['ev10']:+7.2f}")
        if 'taban' in name or 'HER ŞEY' in name:
            print(f"{'   (aynı satırda rastgele seçim EV)':46s} {'':3s} {'':6s} {'':7s} {'':7s} "
                  f"{r['base']*100:6.1f}% {r['ev_base']:+7.2f}")

    best = max(results.items(), key=lambda kv: (kv[1]['auc'] or 0))
    allr = results.get('7 · HER ŞEY (35 gösterge)')
    print('-' * 92)
    print(f"En iyi AUC: {best[0]} ({best[1]['auc']:.3f})")
    if allr:
        print(f"35 göstergenin tamamı: AUC {allr['auc']:.3f} · top-10 {allr['top10']*100:.1f}%")
        overfit = best[1]['n_feat'] < 20 and (allr['auc'] or 0) <= best[1]['auc']
        print('YORUM: ' + ('tüm göstergeleri eklemek iyileşme sağlamıyor → sadeleştirme haklı'
                           if overfit else 'en azından bazı aileler katkı sağlıyor'))


if __name__ == '__main__':
    main()
