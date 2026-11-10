"""Offline end-to-end smoke test; no Binance requests or repository outputs."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd
import scanner


class PipelineTest(unittest.TestCase):
    def test_offline_pipeline_and_atr_comparison(self):
        with open('config.json', encoding='utf-8') as f:
            cfg = json.load(f)
        cfg.update(min_class_samples=2, walk_forward_folds=2, min_features=3,
                   atr_target_enabled=True, model_params={**cfg['model_params'], 'n_estimators': 10, 'min_child_samples': 5})
        rng = np.random.default_rng(123)
        end = pd.Timestamp.now(tz='UTC').tz_localize(None).floor('h') - pd.Timedelta(hours=1)
        idx = pd.date_range(end=end, periods=1500, freq='h')
        frames = {}
        for sym in ['BTCUSDT'] + [f'C{i}USDT' for i in range(12)]:
            c = 100 * np.exp(np.cumsum(rng.normal(0, .025, len(idx))))
            frames[sym] = pd.DataFrame({'c': c, 'o': c, 'h': c*1.015, 'l': c*.985,
                                        'v': rng.uniform(100, 1000, len(idx))}, index=idx)

        class FakeBinance:
            def __init__(self, cfg): pass
            def universe(self):
                return [{'symbol': s, 'priceChangePercent': '1', 'quoteVolume': '10000000', 'exchange_info': {}} for s in frames]
            def klines(self, s): return frames[s]
            def spot(self, path, **params):
                assert path == '/api/v3/ticker/price'
                return {'price': '123.45'}
            def book(self, s): return {'spread': .001, 'bid_depth_usdt': 100000., 'ask_depth_usdt': 100000., 'depth_truncated': False}
            def futures_history(self, s): return {'errors': [], 'current_oi': None}

        original = os.getcwd()
        with tempfile.TemporaryDirectory() as temp:
            try:
                os.chdir(temp)
                with open('config.json', 'w', encoding='utf-8') as f:
                    json.dump(cfg, f)
                with patch.object(scanner, 'Binance', FakeBinance):
                    scanner.main()
                with open('docs/data.json', encoding='utf-8') as f:
                    output = json.load(f)
                with open('docs/report.json', encoding='utf-8') as f:
                    report = json.load(f)
                self.assertEqual(len(output['coins']), 13)
                self.assertEqual(len(output['price_history']), cfg['top_k'])
                self.assertTrue(all(e['price'] == 123.45 and e['status'] == 'pending' for e in output['price_history']))
                self.assertEqual(len(output['metrics']['up']['folds']), 2)
                self.assertEqual(set(report['comparison']), {'fixed', 'atr'})
                self.assertTrue(all(e['price'] is None for e in output['pending']))
                self.assertTrue(all(pd.Timestamp(e['t']) > end for e in output['pending']))
            finally:
                os.chdir(original)


if __name__ == '__main__':
    unittest.main()
