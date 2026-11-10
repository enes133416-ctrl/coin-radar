import unittest
from datetime import datetime, timedelta, timezone
from radar.price_history import update_record, update_history


class FakeAPI:
    def __init__(self, missing=False):
        self.calls = []
        self.missing = missing

    def spot(self, path, **params):
        self.calls.append((path, params))
        if 'ticker' in path:
            return {'price': '100'}
        start, end = params['startTime'], params['endTime']
        times = list(range(start, end + 1, 60000))[:params['limit']]
        if self.missing and times:
            times.pop(0)
        return [[t, '100', '120', '80', '110'] for t in times]


class PriceHistoryTest(unittest.TestCase):
    def setUp(self):
        self.start = datetime(2026, 1, 1, 12, 0, 30, tzinfo=timezone.utc)
        self.record = {'symbol': 'BTC', 'recorded_at': self.start.isoformat(), 'price': 100, 'status': 'pending', 'high': None, 'low': None}

    def test_partial_and_completed_period_with_pagination(self):
        api = FakeAPI()
        partial = update_record(api, self.record, self.start + timedelta(hours=2))
        self.assertEqual((partial['high'], partial['low'], partial['status']), (120, 80, 'pending'))
        self.assertEqual(partial['observed_from'], '2026-01-01T12:01:00+00:00')
        result = update_record(api, partial, self.start + timedelta(days=3))
        self.assertEqual(result['status'], 'complete')
        self.assertEqual(result['observed_until'], '2026-01-02T12:00:00+00:00')
        self.assertEqual(len(api.calls), 3)  # partial + two pages
        self.assertEqual(update_record(api, result, self.start + timedelta(days=4)), result)

    def test_missing_candles_keep_verified_results(self):
        old = dict(self.record, high=110, low=90, observed_until='2026-01-01T13:00:00+00:00')
        result = update_record(FakeAPI(missing=True), old, self.start + timedelta(hours=3))
        self.assertEqual((result['high'], result['low']), (110, 90))
        self.assertIsNotNone(result['error'])
        self.assertEqual(result['status'], 'pending')

    def test_new_records_are_live_quotes_in_probability_order(self):
        coins = [{'symbol': 'A', 'p_up': .1}, {'symbol': 'BTC', 'p_up': .9}]
        records = update_history(FakeAPI(), [], coins, 1, now_fn=lambda: self.start)
        self.assertEqual(records[0]['symbol'], 'BTC')
        self.assertEqual(records[0]['price'], 100)
        self.assertEqual(records[0]['recorded_at'], self.start.isoformat())

    def test_quote_failure_does_not_use_stale_model_price(self):
        class Broken:
            def spot(self, *args, **kwargs): raise OSError('offline')
        result = update_history(Broken(), [], [{'symbol': 'BTC', 'p_up': .9, 'price': 42}], 1, now_fn=lambda: self.start)[0]
        self.assertIsNone(result['price'])
        self.assertEqual(result['status'], 'unavailable')
        self.assertIsNone(update_record(Broken(), result, self.start + timedelta(days=2))['price'])


if __name__ == '__main__':
    unittest.main()
