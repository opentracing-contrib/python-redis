from opentracing.mocktracer import MockTracer
from mock import patch
import unittest

import redis
import redis_opentracing


class TestPipeline(unittest.TestCase):
    def setUp(self):
        self.tracer = MockTracer()
        self.client = redis.StrictRedis()

    def test_trace_pipeline(self):
        pipe = self.client.pipeline()
        with patch.object(pipe, 'execute') as execute:
            execute.__name__ = 'execute'

            redis_opentracing.init_tracing(self.tracer,
                                           trace_all_classes=False)
            redis_opentracing.trace_pipeline(pipe)
            pipe.lpush('my:keys', 1, 3)
            pipe.lpush('my:keys', 5, 7)
            pipe.execute()

            self.assertEqual(execute.call_count, 1)
            self.assertEqual(len(self.tracer.finished_spans()), 1)
            self.assertEqual(self.tracer.finished_spans()[0].operation_name, 'MULTI')
            self.assertEqual(self.tracer.finished_spans()[0].tags, {
                'component': 'redis-py',
                'db.type': 'redis',
                'db.statement': 'LPUSH my:keys 1 3;LPUSH my:keys 5 7',
                'span.kind': 'client',
            })

    def test_trace_pipeline_start_span_cb(self):
        def start_span_cb(span):
            span.set_operation_name('Test')

        pipe = self.client.pipeline()
        with patch.object(pipe, 'execute') as execute:
            execute.__name__ = 'execute'

            redis_opentracing.init_tracing(self.tracer,
                                           trace_all_classes=False,
                                           start_span_cb=start_span_cb)
            redis_opentracing.trace_pipeline(pipe)
            pipe.lpush('my:keys', 1, 3)
            pipe.execute()

            spans = self.tracer.finished_spans()
            self.assertEqual(len(spans), 1)
            self.assertEqual(spans[0].operation_name, 'Test')

    def test_trace_pipeline_empty(self):
        pipe = self.client.pipeline()
        with patch.object(pipe, 'execute') as execute:
            execute.__name__ = 'execute'

            redis_opentracing.init_tracing(self.tracer,
                                           trace_all_classes=False)

            # No commands at all.
            redis_opentracing.trace_pipeline(pipe)
            pipe.execute()

            self.assertEqual(execute.call_count, 1)
            self.assertEqual(len(self.tracer.finished_spans()), 0)

    def test_trace_pipeline_immediate(self):
        pipe = self.client.pipeline()
        with patch.object(pipe, 'immediate_execute_command') as iexecute:
            iexecute.__name__ = 'immediate_execute_command'
            redis_opentracing.init_tracing(self.tracer,
                                           trace_all_classes=False)

            redis_opentracing.trace_pipeline(pipe)
            pipe.immediate_execute_command('WATCH', 'my:key')
            self.assertEqual(iexecute.call_count, 1)
            self.assertEqual(len(self.tracer.finished_spans()), 1)
            span = self.tracer.finished_spans()[0]
            self.assertEqual(span.operation_name, 'WATCH')
            self.assertEqual(span.tags, {
                'component': 'redis-py',
                'db.type': 'redis',
                'db.statement': 'WATCH my:key',
                'span.kind': 'client',
            })

    def test_trace_pipeline_error(self):
        pipe = self.client.pipeline()
        with patch.object(pipe, 'execute', side_effect=ValueError) as execute:
            execute.__name__ = 'execute'

            redis_opentracing.init_tracing(self.tracer,
                                           trace_all_classes=False)
            redis_opentracing.trace_pipeline(pipe)
            pipe.lpush('my:keys', 1, 3)
            pipe.lpush('my:keys', 5, 7)

            call_exc = None
            try:
                pipe.execute()
            except ValueError as exc:
                call_exc = exc

            self.assertEqual(execute.call_count, 1)
            self.assertEqual(len(self.tracer.finished_spans()), 1)
            span = self.tracer.finished_spans()[0]
            self.assertEqual(span.operation_name, 'MULTI')
            self.assertEqual(span.tags, {
                'component': 'redis-py',
                'db.type': 'redis',
                'db.statement': 'LPUSH my:keys 1 3;LPUSH my:keys 5 7',
                'span.kind': 'client',
                'error': True,
            })
            self.assertEqual(len(span.logs), 1)
            self.assertEqual(span.logs[0].key_values.get('event', None),
                             'error')
            self.assertTrue(isinstance(
                span.logs[0].key_values.get('error.object', None), ValueError
            ))
