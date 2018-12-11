from opentracing.mocktracer import MockTracer
from mock import patch
import unittest

import redis
import redis_opentracing


class TestTracing(unittest.TestCase):
    def setUp(self):
        self.tracer = MockTracer()
        self.client = redis.StrictRedis()

        # Stash away the original methods for
        # after-test restoration.
        self._execute_command = redis.StrictRedis.execute_command
        self._pipeline = redis.StrictRedis.pipeline

    def tearDown(self):
        redis.StrictRedis.execute_command = self._execute_command
        redis.StrictRedis.pipeline = self._pipeline

    def test_trace_nothing(self):
        with patch.object(self.client,
                          'execute_command') as exc_command:
            exc_command.__name__ = 'execute_command'

            redis_opentracing.init_tracing(self.tracer,
                                           trace_all_classes=False)

            self.client.get('my.key')
            self.assertEqual(exc_command.call_count, 1)
            self.assertEqual(len(self.tracer.finished_spans()), 0)

    def test_trace_all_client(self):
        with patch('redis.StrictRedis.execute_command') as execute_command:
            execute_command.__name__ = 'execute_command'
            redis_opentracing.init_tracing(self.tracer)

            self.client.get('my.key')
            self.assertEqual(execute_command.call_count, 1)
            self.assertTrue(True, execute_command.call_args == (('my.key',),))
            self.assertEqual(len(self.tracer.finished_spans()), 1)
            span = self.tracer.finished_spans()[0]
            self.assertEqual(span.operation_name, 'GET')
            self.assertEqual(span.tags, {
                'component': 'redis-py',
                'db.type': 'redis',
                'db.statement': 'GET my.key',
                'span.kind': 'client',
            })

    def test_trace_all_pipeline(self):
        redis_opentracing.init_tracing(self.tracer)
        pipe = self.client.pipeline()
        pipe.lpush('my:keys', 1, 3)
        pipe.rpush('my:keys', 5, 7)
        pipe.execute()

        self.assertEqual(len(self.tracer.finished_spans()), 1)
        span = self.tracer.finished_spans()[0]
        self.assertEqual(span.operation_name, 'MULTI')
        self.assertEqual(span.tags, {
            'component': 'redis-py',
            'db.type': 'redis',
            'db.statement': 'LPUSH my:keys 1 3;RPUSH my:keys 5 7',
            'span.kind': 'client',
        })

    def test_trace_all_pubsub(self):
        redis_opentracing.init_tracing(self.tracer)
        pubsub = self.client.pubsub()
        pubsub.subscribe('test')

        # Subscribing can cause more than a SUBSCRIBE call.
        self.assertTrue(len(self.tracer.finished_spans()) >= 1)
        span = self.tracer.finished_spans()[0]
        self.assertEqual(span.operation_name, 'SUBSCRIBE')
        self.assertEqual(span.tags, {
            'component': 'redis-py',
            'db.type': 'redis',
            'db.statement': 'SUBSCRIBE test',
            'span.kind': 'client',
        })
