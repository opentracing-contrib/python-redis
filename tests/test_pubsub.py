from opentracing.mocktracer import MockTracer
from mock import patch
import unittest

import redis
import redis_opentracing


class TestPubSub(unittest.TestCase):
    def setUp(self):
        self.tracer = MockTracer()
        self.client = redis.StrictRedis()

    def test_trace_pubsub(self):
        pubsub = self.client.pubsub()
        return_value = [ # Simulate a real message
            'pmessage',
            'pattern1',
            'channel1',
            'hello',
        ]

        with patch.object(pubsub, 'parse_response',
                          return_value=return_value) as parse_response:
            parse_response.__name__ = 'parse_response'

            redis_opentracing.init_tracing(self.tracer,
                                           trace_all_classes=False)
            redis_opentracing.trace_pubsub(pubsub)
            res = pubsub.get_message()

            self.assertEqual(res, {
                'type': 'pmessage',
                'pattern': 'pattern1',
                'channel': 'channel1',
                'data': 'hello',
            })
            self.assertEqual(parse_response.call_count, 1)
            self.assertEqual(len(self.tracer.finished_spans()), 1)
            self.assertEqual(self.tracer.finished_spans()[0].operation_name, 'SUB')
            self.assertEqual(self.tracer.finished_spans()[0].tags, {
                'component': 'redis-py',
                'db.type': 'redis',
                'db.statement': '',
                'span.kind': 'client',
            })

    def test_trace_pubsub_start_span_cb(self):
        def start_span_cb(span):
            span.set_operation_name('Test')

        pubsub = self.client.pubsub()
        return_value = [ # Simulate a real message
            'pmessage',
            'pattern1',
            'channel1',
            'hello',
        ]

        with patch.object(pubsub, 'parse_response',
                          return_value=return_value) as parse_response:
            parse_response.__name__ = 'parse_response'

            redis_opentracing.init_tracing(self.tracer,
                                           trace_all_classes=False,
                                           start_span_cb=start_span_cb)
            redis_opentracing.trace_pubsub(pubsub)
            res = pubsub.get_message()

            spans = self.tracer.finished_spans()
            self.assertEqual(len(spans), 1)
            self.assertEqual(spans[0].operation_name, 'Test')

    def test_trace_pubsub_execute_command(self):
        pubsub = self.client.pubsub()

        with patch.object(pubsub, 'execute_command',
                          return_value='hello') as execute_command:
            execute_command.__name__ = 'parse_response'

            redis_opentracing.init_tracing(self.tracer,
                                           trace_all_classes=False)
            redis_opentracing.trace_pubsub(pubsub)
            res = pubsub.execute_command('GET', 'foo')

            self.assertEqual(res, 'hello')
            self.assertEqual(execute_command.call_count, 1)
            self.assertEqual(len(self.tracer.finished_spans()), 1)
            self.assertEqual(self.tracer.finished_spans()[0].operation_name, 'GET')
            self.assertEqual(self.tracer.finished_spans()[0].tags, {
                'component': 'redis-py',
                'db.type': 'redis',
                'db.statement': 'GET foo',
                'span.kind': 'client',
            })

    def test_trace_pubsub_error(self):
        pubsub = self.client.pubsub()

        with patch.object(pubsub, 'parse_response',
                          side_effect=ValueError) as parse_response:
            parse_response.__name__ = 'parse_response'

            redis_opentracing.init_tracing(self.tracer,
                                           trace_all_classes=False)
            redis_opentracing.trace_pubsub(pubsub)

            call_exc = None
            try:
                pubsub.get_message()
            except ValueError as exc:
                call_exc = exc

            self.assertEqual(parse_response.call_count, 1)
            self.assertEqual(len(self.tracer.finished_spans()), 1)
            span = self.tracer.finished_spans()[0]
            self.assertEqual(span.operation_name, 'SUB')
            self.assertEqual(span.tags, {
                'component': 'redis-py',
                'db.type': 'redis',
                'db.statement': '',
                'span.kind': 'client',
                'error': True,
            })
            self.assertEqual(len(span.logs), 1)
            self.assertEqual(span.logs[0].key_values.get('event', None),
                             'error')
            self.assertTrue(isinstance(
                span.logs[0].key_values.get('error.object', None), ValueError
            ))
