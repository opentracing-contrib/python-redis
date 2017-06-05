import unittest

import redis
import redis_opentracing

from .dummies import *


class TestGlobalCalls(unittest.TestCase):
    def setUp(self):
        # Stash away the original methods for
        # after-test restoration.
        self._execute_command = redis.StrictRedis.execute_command
        self._pipeline = redis.StrictRedis.pipeline

    def tearDown(self):
        redis.StrictRedis.execute_command = self._execute_command
        redis.StrictRedis.pipeline = self._pipeline

    def test_init(self):
        tracer = DummyTracer()
        redis_opentracing.init_tracing(tracer)
        self.assertEqual(tracer, redis_opentracing.g_tracer)
        self.assertEqual(True, redis_opentracing.g_trace_all_classes)
        self.assertEqual('Redis', redis_opentracing.g_trace_prefix)


    def test_init_subtracer(self):
        tracer = DummyTracer(with_subtracer=True)
        redis_opentracing.init_tracing(tracer)
        self.assertEqual(tracer._tracer, redis_opentracing.g_tracer)
        self.assertEqual(True, redis_opentracing.g_trace_all_classes)
        self.assertEqual('Redis', redis_opentracing.g_trace_prefix)


    def test_init_trace_prefix(self):
        redis_opentracing.init_tracing(DummyTracer(), prefix='Prod007')
        self.assertEqual('Prod007', redis_opentracing.g_trace_prefix)

        redis_opentracing.init_tracing(DummyTracer(), prefix='')
        self.assertEqual('', redis_opentracing.g_trace_prefix)
