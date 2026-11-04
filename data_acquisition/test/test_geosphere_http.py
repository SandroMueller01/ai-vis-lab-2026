"""Offline checks for GeoSphere quota handling and HTTP retries."""

import contextlib
import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import requests

# Support discovery and direct execution from any working directory.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from geosphere_http import GeoSphereClient


class GeoSphereClientTests(unittest.TestCase):
    def setUp(self):
        self.now = 100.0
        self.sleeps = []
        self.stack = contextlib.ExitStack()
        self.addCleanup(self.stack.close)
        self.stack.enter_context(patch('geosphere_http.time.monotonic', side_effect=lambda: self.now))
        self.stack.enter_context(patch('geosphere_http.time.sleep', side_effect=self.sleep))
        self.stack.enter_context(contextlib.redirect_stdout(io.StringIO()))
        self.client = GeoSphereClient()
        self.client.session.get = Mock()
        self.addCleanup(self.client.session.close)

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds

    @staticmethod
    def response(status=200, headers=None):
        return SimpleNamespace(status_code=status, headers=requests.structures.CaseInsensitiveDict(headers or {}),
                               url='https://example.test', text='test')

    def test_header_pacing_and_fallbacks(self):
        cases = [
            ({}, 0.3),
            ({'X-RateLimit-Limit-Second': '5'}, 0.21),
            ({'x-ratelimit-remaining-second': '0'}, 1.01),
            ({'x-ratelimit-remaining-hour': '0', 'ratelimit-reset': '12.5'}, 14.5),
            ({'x-ratelimit-remaining-hour': '0', 'ratelimit-reset': '0'}, 2),
            ({'x-ratelimit-limit-second': '0'}, 0.3),
            ({'x-ratelimit-limit-second': '-5'}, 0.3),
            ({'x-ratelimit-limit-second': 'nan'}, 0.3),
            ({'x-ratelimit-remaining-hour': '0', 'ratelimit-reset': 'inf'}, 62),
            ({'x-ratelimit-remaining-hour': '0', 'ratelimit-reset': 'invalid'}, 62),
        ]
        for headers, expected in cases:
            with self.subTest(headers=headers):
                limiter = self.client.rate_limiter
                limiter.next_request_at = 0
                limiter.update(self.response(headers=headers))
                self.assertAlmostEqual(limiter.next_request_at - self.now, expected)
                limiter.wait()
                self.assertAlmostEqual(self.sleeps[-1], expected)

    def test_quota_is_shared_across_calls_and_wait_is_deferred(self):
        first = self.response(headers={'x-ratelimit-remaining-hour': '0', 'ratelimit-reset': '10'})
        self.client.session.get.side_effect = [first, self.response()]
        self.assertIs(self.client.get('stations', {}), first)
        self.assertEqual(self.sleeps, [])
        self.now += 5  # Processing time consumes part of the pending quota wait.
        self.client.get('grid', {})
        self.assertEqual(self.sleeps, [7])

    def test_429_uses_reset_and_retries(self):
        self.client.session.get.side_effect = [self.response(429, {'ratelimit-reset': '2.5'}), self.response()]
        self.client.get('grid', {})
        self.assertEqual(self.sleeps, [4.5])
        self.assertEqual(self.client.session.get.call_count, 2)

    def test_second_limit_does_not_wait_for_hourly_reset(self):
        headers = {'x-ratelimit-remaining-second': '0', 'x-ratelimit-remaining-hour': '100',
                   'ratelimit-reset': '3600'}
        self.client.session.get.side_effect = [self.response(429, headers), self.response()]
        self.client.get('grid', {})
        self.assertAlmostEqual(self.sleeps[0], 1.01)

    def test_hour_limit_takes_priority_over_second_limit(self):
        headers = {'x-ratelimit-remaining-second': '0', 'x-ratelimit-remaining-hour': '0',
                   'ratelimit-reset': '3600'}
        self.client.session.get.side_effect = [self.response(429, headers), self.response()]
        self.client.get('grid', {})
        self.assertEqual(self.sleeps, [3602])

    def test_network_and_server_errors_retry(self):
        for failure in [requests.ConnectionError('offline'), self.response(503)]:
            with self.subTest(failure=failure):
                self.client.rate_limiter.next_request_at = 0
                self.sleeps.clear()
                self.client.session.get.side_effect = [failure, self.response()]
                self.client.get('grid', {})
                self.assertEqual(self.sleeps, [10])

    def test_other_http_errors_fail_without_retrying(self):
        self.client.session.get.return_value = self.response(400)
        with self.assertRaisesRegex(RuntimeError, 'HTTP 400'):
            self.client.get('grid', {})
        self.assertEqual(self.client.session.get.call_count, 1)
        self.assertEqual(self.sleeps, [])

    def test_configured_retry_count_and_per_call_override(self):
        self.client.retries = 2
        self.client.session.get.return_value = self.response(429)
        with self.assertRaisesRegex(RuntimeError, 'giving up'):
            self.client.get('grid', {})
        self.assertEqual(self.client.session.get.call_count, 2)
        self.client.session.get.reset_mock()
        with self.assertRaisesRegex(RuntimeError, 'giving up'):
            self.client.get('grid', {}, retries=1)
        self.assertEqual(self.client.session.get.call_count, 1)


if __name__ == '__main__':
    unittest.main()
