from opentracing.mocktracer import MockTracer
from mock import patch
import unittest

import redis
import redis_opentracing


class TestClient(unittest.TestCase):
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

    def test_trace_client(self):
        with patch.object(self.client,
                          'execute_command',
                          return_value='1') as exc_command:
            exc_command.__name__ = 'execute_command'

            redis_opentracing.init_tracing(self.tracer,
                                           trace_all_classes=False)
            redis_opentracing.trace_client(self.client)
            res = self.client.get('my.key')

            self.assertEqual(res, '1')
            self.assertEqual(exc_command.call_count, 1)
            self.assertTrue(True, exc_command.call_args == (('my.key',),))
            self.assertEqual(len(self.tracer.finished_spans()), 1)
            span = self.tracer.finished_spans()[0]
            self.assertEqual(span.operation_name, 'GET')
            self.assertEqual(span.tags, {
                'component': 'redis-py',
                'db.type': 'redis',
                'db.statement': 'GET my.key',
                'span.kind': 'client',
            })

    def test_trace_client_error(self):
        with patch.object(self.client,
                          'execute_command',
                          side_effect=ValueError) as exc_command:
            exc_command.__name__ = 'execute_command'

            redis_opentracing.init_tracing(self.tracer,
                                           trace_all_classes=False)
            redis_opentracing.trace_client(self.client)

            call_exc = None
            try:
                self.client.get('my.key')
            except ValueError as exc:
                call_exc = exc

            self.assertEqual(exc_command.call_count, 1)
            self.assertTrue(True, exc_command.call_args == (('my.key',),))
            self.assertEqual(len(self.tracer.finished_spans()), 1)
            span = self.tracer.finished_spans()[0]
            self.assertEqual(span.operation_name, 'GET')
            self.assertEqual(span.tags, {
                'component': 'redis-py',
                'db.type': 'redis',
                'db.statement': 'GET my.key',
                'span.kind': 'client',
                'error': True,
            })
            self.assertEqual(len(span.logs), 1)
            self.assertEqual(span.logs[0].key_values.get('event', None),
                             'error')
            self.assertTrue(isinstance(
                span.logs[0].key_values.get('error.object', None), ValueError
            ))

    def test_trace_client_start_span_cb(self):
        def start_span_cb(span):
            span.set_operation_name('Test')

        with patch.object(self.client,
                          'execute_command',
                          return_value='1') as exc_command:
            exc_command.__name__ = 'execute_command'

            redis_opentracing.init_tracing(self.tracer,
                                           trace_all_classes=False,
                                           start_span_cb=start_span_cb)
            redis_opentracing.trace_client(self.client)
            res = self.client.get('my.key')

            span = self.tracer.finished_spans()[0]
            self.assertEqual(span.operation_name, 'Test')

    def test_trace_client_start_span_cb_exc(self):
        def start_span_cb(span):
            raise RuntimeError('This should not happen')

        with patch.object(self.client,
                          'execute_command',
                          return_value='1') as exc_command:
            exc_command.__name__ = 'execute_command'

            redis_opentracing.init_tracing(self.tracer,
                                           trace_all_classes=False,
                                           start_span_cb=start_span_cb)
            redis_opentracing.trace_client(self.client)
            res = self.client.get('my.key')

            span = self.tracer.finished_spans()[0]
            self.assertEqual(span.operation_name, 'GET')
            self.assertFalse(span.tags.get('error', False))

    def test_trace_client_pipeline(self):
        redis_opentracing.init_tracing(self.tracer,
                                       trace_all_classes=False)
        redis_opentracing.trace_client(self.client)

        pipe = self.client.pipeline()
        pipe.rpush('my:keys', 1, 3)
        pipe.rpush('my:keys', 5, 7)
        pipe.execute()
        self.assertEqual(len(self.tracer.finished_spans()), 1)
        span = self.tracer.finished_spans()[0]
        self.assertEqual(span.operation_name, 'MULTI')
        self.assertEqual(span.tags, {
            'component': 'redis-py',
            'db.type': 'redis',
            'db.statement': 'RPUSH my:keys 1 3;RPUSH my:keys 5 7',
            'span.kind': 'client',
        })

    def test_trace_client_pubsub(self):
        redis_opentracing.init_tracing(self.tracer,
                                       trace_all_classes=False)
        redis_opentracing.trace_client(self.client)

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
