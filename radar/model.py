"""Time-ordered training, purged calibration and walk-forward evaluation."""
import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, roc_auc_score


def split_at(data, start, end, cfg):
    t = data.index
    gap = pd.Timedelta(hours=cfg['horizon_hours'])
    cal_end = start - gap
    unique = np.sort(t[t < cal_end].unique())
    ncal = max(1, int(len(unique) * cfg['calibration_fraction']))
    if len(unique) <= ncal:
        raise ValueError('Kalibrasyon için yeterli geçmiş yok')
    cal_start = pd.Timestamp(unique[-ncal])
    train = data[t < cal_start - gap]
    cal = data[(t >= cal_start) & (t < cal_end)]
    test = data[(t >= start) & (t < end)]
    assert_no_leakage(train, cal, test, cfg['horizon_hours'])
    return train, cal, test


def assert_no_leakage(train, cal, test, horizon):
    gap = pd.Timedelta(hours=horizon)
    if min(len(train), len(cal), len(test)) == 0:
        raise ValueError('Zaman bölmesinde boş eğitim, kalibrasyon veya test kümesi')
    if not (train.index.max() + gap < cal.index.min() and cal.index.max() + gap < test.index.min()):
        raise AssertionError('Etiket ufku eğitim/kalibrasyon/test dönemleriyle örtüşüyor')


def thin(frame, stride):
    # Fixed UTC phase per symbol: no overlapping labels within one coin.
    hours = frame.index.as_unit('ns').asi8 // (3600 * 10**9)
    return frame[hours % stride == 0]


def select_features(train, cols, target, cfg):
    corr = train[cols].corr().abs()
    selected, dropped = [], {}
    for c in cols:
        if train[c].notna().sum() == 0 or train[c].nunique(dropna=True) < 2:
            dropped[c] = 'sabit veya eksik'
            continue
        match = next((s for s in selected if pd.notna(corr.loc[c, s]) and corr.loc[c, s] > cfg['correlation_threshold']), None)
        if match:
            dropped[c] = 'korelasyon: ' + match
        else:
            selected.append(c)
    if not selected:
        raise ValueError('Kullanılabilir özellik yok')
    preliminary = lgb.LGBMClassifier(**cfg['model_params']).fit(train[selected], train[target].astype(int))
    gain = preliminary.booster_.feature_importance(importance_type='gain')
    pct = gain / gain.sum() * 100 if gain.sum() else np.zeros(len(gain))
    ranked = np.argsort(-pct)
    keep = set(ranked[:cfg['min_features']]) | {i for i, v in enumerate(pct) if v >= cfg['min_importance_pct']}
    for i, c in enumerate(selected):
        if i not in keep:
            dropped[c] = 'düşük önem'
    selected = [c for i, c in enumerate(selected) if i in keep]
    return selected, dropped, corr


def train_model(train, cal, cols, target, cfg):
    train, cal = thin(train, cfg['sample_stride_hours']), thin(cal, cfg['sample_stride_hours'])
    for name, frame in [('eğitim', train), ('kalibrasyon', cal)]:
        counts = frame[target].value_counts()
        if len(counts) < 2 or counts.min() < cfg['min_class_samples']:
            raise ValueError(f'{name} için her sınıfta en az {cfg["min_class_samples"]} örnek gerekli: {counts.to_dict()}')
    selected, dropped, corr = select_features(train, cols, target, cfg)
    model = lgb.LGBMClassifier(**cfg['model_params']).fit(train[selected], train[target].astype(int))
    raw = model.predict_proba(cal[selected])[:, 1]
    iso = IsotonicRegression(out_of_bounds='clip').fit(raw, cal[target].astype(int))
    gain = model.booster_.feature_importance(importance_type='gain')
    pct = gain / gain.sum() * 100 if gain.sum() else np.zeros(len(gain))
    importance = [{'f': selected[i], 'w': round(float(pct[i]), 2)} for i in np.argsort(-pct)]
    return {'model': model, 'calibrator': iso, 'features': selected, 'dropped': dropped,
            'correlation': corr, 'importance': importance, 'cal_rows': len(cal),
            'cal_events': int(cal[target].sum())}


def predict(bundle, frame):
    return bundle['calibrator'].predict(bundle['model'].predict_proba(frame[bundle['features']])[:, 1])


def metrics(test, probs, target, cfg):
    y = test[target].astype(int).to_numpy()
    work = pd.DataFrame({'p': probs, 'y': y}, index=test.index)
    top = work.sort_values('p', ascending=False).groupby(level=0, sort=False).head(cfg['top_k'])
    bins = []
    for i in range(cfg['calibration_bins']):
        mask = (probs >= i / cfg['calibration_bins']) & ((probs < (i+1) / cfg['calibration_bins']) if i+1 < cfg['calibration_bins'] else (probs <= 1))
        if mask.any():
            bins.append({'mean_probability': float(probs[mask].mean()), 'event_rate': float(y[mask].mean()), 'count': int(mask.sum())})
    return {'auc': float(roc_auc_score(y, probs)) if len(np.unique(y)) > 1 else None,
            'brier': float(brier_score_loss(y, probs)), 'base_rate': float(y.mean()),
            'precision_top10': float(top.y.mean()), 'hit_rate': float(top.y.mean()),
            'top10_rows': len(top), 'test_rows': len(y), 'calibration_curve': bins}


def evaluate(data, cols, target, cfg):
    times = np.sort(data.index.unique())
    block = max(1, int(len(times) * cfg['test_fraction']))
    if len(times) <= block * cfg['walk_forward_folds']:
        raise ValueError('Walk-forward için yeterli zaman aralığı yok')
    predictions, folds = [], []
    for i in range(cfg['walk_forward_folds']):
        start_idx = len(times) - block * (cfg['walk_forward_folds'] - i)
        end_idx = min(len(times), start_idx + block)
        start = pd.Timestamp(times[start_idx])
        end = pd.Timestamp(times[end_idx]) if end_idx < len(times) else pd.Timestamp(times[-1]) + pd.Timedelta(hours=1)
        train, cal, test = split_at(data, start, end, cfg)
        bundle = train_model(train, cal, cols, target, cfg)
        p = predict(bundle, test)
        folds.append({'train_end': train.index.max().isoformat(), 'cal_start': cal.index.min().isoformat(),
                      'cal_end': cal.index.max().isoformat(), 'test_start': test.index.min().isoformat(),
                      'test_end': test.index.max().isoformat(), 'metrics': metrics(test, p, target, cfg)})
        predictions.append((test, p))
    test = pd.concat([x[0] for x in predictions])
    probs = np.concatenate([x[1] for x in predictions])
    result = metrics(test, probs, target, cfg)
    result['folds'] = folds
    # Final model retains a separate recent calibration period; never train it on calibration labels.
    end = pd.Timestamp(times[-1]) + pd.Timedelta(hours=cfg['horizon_hours']+1)
    start = end + pd.Timedelta(hours=cfg['horizon_hours']+1)
    # Use a synthetic sentinel only to enforce the same strict purge checks.
    sentinel = data.iloc[[-1]].copy(); sentinel.index = pd.DatetimeIndex([start])
    train, cal, _ = split_at(pd.concat([data, sentinel]).sort_index(), start, start + pd.Timedelta(hours=1), cfg)
    bundle = train_model(train, cal, cols, target, cfg)
    return bundle, result
