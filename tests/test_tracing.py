from mock import patch
import unittest

import redis
import redis_opentracing

from .dummies import *


class TestClient(unittest.TestCase):
    def setUp(self):
        self.tracer = DummyTracer()
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
                                           trace_all_classes=False,
                                           prefix='Test')

            self.client.get('my.key')
            self.assertEqual(exc_command.call_count, 1)
            self.assertEqual(len(self.tracer.spans), 0)

    def test_trace_client(self):
        with patch.object(self.client,
                          'execute_command',
                          return_value='1') as exc_command:
            exc_command.__name__ = 'execute_command'

            redis_opentracing.init_tracing(self.tracer,
                                           trace_all_classes=False,
                                           prefix='Test')
            redis_opentracing.trace_client(self.client)
            res = self.client.get('my.key')

            self.assertEqual(res, '1')
            self.assertEqual(exc_command.call_count, 1)
            self.assertTrue(True, exc_command.call_args == (('my.key',),))
            self.assertEqual(len(self.tracer.spans), 1)
            self.assertEqual(self.tracer.spans[0].operation_name, 'Test/GET')
            self.assertEqual(self.tracer.spans[0].is_finished, True)
            self.assertEqual(self.tracer.spans[0].tags, {
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
                                           trace_all_classes=False,
                                           prefix='Test')
            redis_opentracing.trace_client(self.client)

            call_exc = None
            try:
                self.client.get('my.key')
            except ValueError as exc:
                call_exc = exc

            self.assertEqual(exc_command.call_count, 1)
            self.assertTrue(True, exc_command.call_args == (('my.key',),))
            self.assertEqual(len(self.tracer.spans), 1)
            self.assertEqual(self.tracer.spans[0].operation_name, 'Test/GET')
            self.assertEqual(self.tracer.spans[0].is_finished, True)
            self.assertEqual(self.tracer.spans[0].tags, {
                'component': 'redis-py',
                'db.type': 'redis',
                'db.statement': 'GET my.key',
                'span.kind': 'client',
                'error': 'true',
                'error.object': call_exc,
            })

    def test_trace_client_pipeline(self):
        redis_opentracing.init_tracing(self.tracer,
                                       trace_all_classes=False,
                                       prefix='Test')
        redis_opentracing.trace_client(self.client)

        pipe = self.client.pipeline()
        pipe.rpush('my:keys', 1, 3)
        pipe.rpush('my:keys', 5, 7)
        pipe.execute()
        self.assertEqual(len(self.tracer.spans), 1)
        self.assertEqual(self.tracer.spans[0].operation_name, 'Test/MULTI')
        self.assertEqual(self.tracer.spans[0].is_finished, True)
        self.assertEqual(self.tracer.spans[0].tags, {
            'component': 'redis-py',
            'db.type': 'redis',
            'db.statement': 'RPUSH my:keys 1 3;RPUSH my:keys 5 7',
            'span.kind': 'client',
        })

    def test_trace_pipeline(self):
        pipe = self.client.pipeline()
        with patch.object(pipe, 'execute') as execute:
            execute.__name__ = 'execute'

            redis_opentracing.init_tracing(self.tracer,
                                           trace_all_classes=False,
                                           prefix='Test')
            redis_opentracing.trace_pipeline(pipe)
            pipe.lpush('my:keys', 1, 3)
            pipe.lpush('my:keys', 5, 7)
            pipe.execute()

            self.assertEqual(execute.call_count, 1)
            self.assertEqual(len(self.tracer.spans), 1)
            self.assertEqual(self.tracer.spans[0].operation_name, 'Test/MULTI')
            self.assertEqual(self.tracer.spans[0].is_finished, True)
            self.assertEqual(self.tracer.spans[0].tags, {
                'component': 'redis-py',
                'db.type': 'redis',
                'db.statement': 'LPUSH my:keys 1 3;LPUSH my:keys 5 7',
                'span.kind': 'client',
            })

    def test_trace_pipeline_empty(self):
        pipe = self.client.pipeline()
        with patch.object(pipe, 'execute') as execute:
            execute.__name__ = 'execute'

            redis_opentracing.init_tracing(self.tracer,
                                           trace_all_classes=False,
                                           prefix='Test')

            # No commands at all.
            redis_opentracing.trace_pipeline(pipe)
            pipe.execute()

            self.assertEqual(execute.call_count, 1)
            self.assertEqual(len(self.tracer.spans), 0)

    def test_trace_pipeline_immediate(self):
        pipe = self.client.pipeline()
        with patch.object(pipe, 'immediate_execute_command') as iexecute:
            iexecute.__name__ = 'immediate_execute_command'
            redis_opentracing.init_tracing(self.tracer,
                                           trace_all_classes=False,
                                           prefix='Test')

            redis_opentracing.trace_pipeline(pipe)
            pipe.immediate_execute_command('WATCH', 'my:key')
            self.assertEqual(iexecute.call_count, 1)
            self.assertEqual(len(self.tracer.spans), 1)
            self.assertEqual(self.tracer.spans[0].operation_name, 'Test/WATCH')
            self.assertEqual(self.tracer.spans[0].is_finished, True)
            self.assertEqual(self.tracer.spans[0].tags, {
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
                                           trace_all_classes=False,
                                           prefix='Test')
            redis_opentracing.trace_pipeline(pipe)
            pipe.lpush('my:keys', 1, 3)
            pipe.lpush('my:keys', 5, 7)

            call_exc = None
            try:
                pipe.execute()
            except ValueError as exc:
                call_exc = exc

            self.assertEqual(execute.call_count, 1)
            self.assertEqual(len(self.tracer.spans), 1)
            self.assertEqual(self.tracer.spans[0].operation_name, 'Test/MULTI')
            self.assertEqual(self.tracer.spans[0].is_finished, True)
            self.assertEqual(self.tracer.spans[0].tags, {
                'component': 'redis-py',
                'db.type': 'redis',
                'db.statement': 'LPUSH my:keys 1 3;LPUSH my:keys 5 7',
                'span.kind': 'client',
                'error': 'true',
                'error.object': call_exc,
            })

    def test_trace_all_client(self):
        with patch('redis.StrictRedis.execute_command') as execute_command:
            execute_command.__name__ = 'execute_command'
            redis_opentracing.init_tracing(self.tracer, prefix='Test')

            self.client.get('my.key')
            self.assertEqual(execute_command.call_count, 1)
            self.assertTrue(True, execute_command.call_args == (('my.key',),))
            self.assertEqual(len(self.tracer.spans), 1)
            self.assertEqual(self.tracer.spans[0].operation_name, 'Test/GET')
            self.assertEqual(self.tracer.spans[0].is_finished, True)
            self.assertEqual(self.tracer.spans[0].tags, {
                'component': 'redis-py',
                'db.type': 'redis',
                'db.statement': 'GET my.key',
                'span.kind': 'client',
            })

    def test_trace_all_pipeline(self):
        redis_opentracing.init_tracing(self.tracer, prefix='Test')
        pipe = self.client.pipeline()
        pipe.lpush('my:keys', 1, 3)
        pipe.rpush('my:keys', 5, 7)
        pipe.execute()

        self.assertEqual(len(self.tracer.spans), 1)
        self.assertEqual(self.tracer.spans[0].operation_name, 'Test/MULTI')
        self.assertEqual(self.tracer.spans[0].is_finished, True)
        self.assertEqual(self.tracer.spans[0].tags, {
            'component': 'redis-py',
            'db.type': 'redis',
            'db.statement': 'LPUSH my:keys 1 3;RPUSH my:keys 5 7',
            'span.kind': 'client',
        })
