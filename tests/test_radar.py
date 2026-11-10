import json
import unittest
import numpy as np
import pandas as pd
from radar.data import Binance, monitoring
from radar.features import features, add_futures, labels
from radar.model import split_at, assert_no_leakage, evaluate, thin
from scanner import resolve

with open('config.json', encoding='utf-8') as f:
    CFG = json.load(f)


class RadarTests(unittest.TestCase):
    def test_universe_volume_threshold_and_no_default_count_limit(self):
        symbols = [{'symbol': f'C{i}USDT', 'baseAsset': f'C{i}', 'quoteAsset': 'USDT', 'status': 'TRADING'} for i in range(200)]
        symbols += [{'symbol': 'LOWUSDT', 'baseAsset': 'LOW', 'quoteAsset': 'USDT', 'status': 'TRADING'},
                    {'symbol': 'USDCUSDT', 'baseAsset': 'USDC', 'quoteAsset': 'USDT', 'status': 'TRADING'},
                    {'symbol': 'STOPUSDT', 'baseAsset': 'STOP', 'quoteAsset': 'USDT', 'status': 'BREAK'},
                    {'symbol': 'CEUR', 'baseAsset': 'C', 'quoteAsset': 'EUR', 'status': 'TRADING'}]
        rows = [{'symbol': f'C{i}USDT', 'quoteVolume': str(250000 + i)} for i in range(200)]
        rows += [{'symbol': 'LOWUSDT', 'quoteVolume': '249999.99'},
                 *[{'symbol': x, 'quoteVolume': '1000000'} for x in ['USDCUSDT', 'STOPUSDT', 'CEUR']]]
        api = Binance(CFG)
        api.spot = lambda path: {'symbols': symbols} if path.endswith('exchangeInfo') else rows
        result = api.universe()
        self.assertEqual(CFG['min_volume_usdt'], 250000)
        self.assertIsNone(CFG['top_n'])
        self.assertEqual(len(result), 200)
        self.assertEqual(result[0]['symbol'], 'C199USDT')
        self.assertEqual(result[-1]['symbol'], 'C0USDT')  # threshold is inclusive
        api.cfg = dict(CFG, top_n=10)
        self.assertEqual(len(api.universe()), 10)

    def test_first_touch_and_ambiguous(self):
        idx = pd.date_range('2024-01-01', periods=5, freq='h')
        df = pd.DataFrame({'c': [100]*5, 'h': [100, 111, 100, 100, 100], 'l': [100, 99, 89, 100, 100]}, index=idx)
        y = labels(df, .1, 2)
        self.assertEqual(y.iloc[0].tolist(), [1, 0])
        df.loc[idx[1], 'l'] = 89
        self.assertTrue(y.iloc[-1].isna().all())
        self.assertTrue(labels(df, .1, 2).iloc[0].isna().all())

    def test_future_features_do_not_look_ahead(self):
        idx = pd.date_range('2024-01-01', periods=800, freq='h')
        rng = np.random.default_rng(7)
        c = 100*np.exp(np.cumsum(rng.normal(0, .01, len(idx))))
        df = pd.DataFrame({'c': c, 'o': c, 'h': c*1.01, 'l': c*.99, 'v': rng.uniform(10,20,len(idx))}, index=idx)
        original = features(df, df, CFG)
        changed = df.copy(); changed.iloc[700:] *= 4
        modified = features(changed, changed, CFG)
        pd.testing.assert_frame_equal(original.iloc[:700], modified.iloc[:700])
        hist = {'oi': [{'timestamp': int(idx[5].timestamp()*1000), 'sumOpenInterest': '123'}]}
        joined = add_futures(pd.DataFrame(index=idx), hist)
        self.assertTrue(pd.isna(joined.oi_change1.iloc[4]))
        self.assertTrue(pd.isna(joined.open_interest.iloc[4]))
        self.assertEqual(joined.open_interest.iloc[5], 123)
        self.assertTrue(pd.isna(joined.open_interest.iloc[9]))

    def test_walk_forward_purges_and_fits(self):
        rng = np.random.default_rng(42)
        idx = pd.date_range('2024-01-01', periods=1200, freq='h').repeat(5)
        frame = pd.DataFrame({'x': rng.normal(size=len(idx)), 'x_copy': 0., 'sym': np.tile(list('abcde'), 1200)}, index=idx)
        frame['x_copy'] = frame.x
        frame['y_up_fixed'] = (frame.x + rng.normal(size=len(idx)) > .5).astype(int)
        cfg = dict(CFG, min_class_samples=2, walk_forward_folds=2, min_features=1, model_params={**CFG['model_params'], 'n_estimators': 10, 'min_child_samples': 5})
        a, b, c = split_at(frame, idx[4500], idx[-1]+pd.Timedelta(hours=1), cfg)
        assert_no_leakage(a, b, c, 24)
        with self.assertRaises(AssertionError):
            assert_no_leakage(a, a, c, 24)
        self.assertTrue(all((np.diff(g.index.as_unit('ns').asi8) >= pd.Timedelta(hours=24).value).all() for _, g in thin(a,24).groupby('sym')))
        bundle, m = evaluate(frame, ['x', 'x_copy'], 'y_up_fixed', cfg)
        self.assertEqual(len(m['folds']), 2)
        self.assertIn('x_copy', bundle['dropped'])
        self.assertTrue(0 <= m['brier'] <= 1)
        self.assertGreater(m['top10_rows'], 0)

    def test_monitoring_unknown_and_tracking(self):
        self.assertEqual(monitoring({})['status'], 'unknown')
        self.assertEqual(monitoring({'tags': ['Monitoring']})['status'], 'warning')
        idx = pd.date_range('2024-01-01', periods=24, freq='h')
        df = pd.DataFrame({'h': [111]+[100]*23, 'l': [99, 89]+[100]*22}, index=idx)
        entry = {'t': idx[0].isoformat(), 'sym':'A', 'side':'up', 'price':100, 'threshold':.1}
        done, keep = resolve([entry], {'AUSDT':df}, idx[-1], CFG)
        self.assertTrue(done[0]['hit'])
        df.iloc[0, df.columns.get_loc('l')] = 89
        done, _ = resolve([entry], {'AUSDT':df}, idx[-1], CFG)
        self.assertIsNone(done[0]['hit'])


if __name__ == '__main__':
    unittest.main()
