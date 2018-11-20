from functools import wraps

import opentracing
from opentracing.ext import tags
import redis

_g_tracer = None
_g_trace_all_classes = None
_g_start_span_cb = None


def init_tracing(tracer=None, trace_all_classes=True, start_span_cb=None):
    """
    Set our tracer for Redis. Tracer objects from the
    OpenTracing django/flask/pyramid libraries can be passed as well.

    :param tracer: the tracer object.
    :param trace_all_classes: If True, Redis clients and pipelines
        are automatically traced. Else, explicit tracing on them
        is required.
    """
    if start_span_cb is not None and not callable(start_span_cb):
        raise ValueError('start_span_cb is not callable')

    global _g_tracer, _g_trace_all_classes, _g_start_span_cb
    if hasattr(tracer, '_tracer'):
        tracer = tracer._tracer

    _g_tracer = tracer
    _g_trace_all_classes = trace_all_classes
    _g_start_span_cb = start_span_cb

    if _g_trace_all_classes:
        _patch_redis_classes()


def trace_client(client):
    """
    Marks a client to be traced. All commands and pipelines executed
    through this client will be traced.

    :param client: the Redis client object.
    """
    _patch_client(client)


def trace_pipeline(pipe):
    """
    Marks a pipeline to be traced.

    :param client: the Redis pipeline object to be traced.
    If executed as a transaction, the commands will appear
    under a single 'MULTI' operation.
    """
    _patch_pipe_execute(pipe)


def trace_pubsub(pubsub):
    """
    Marks a pubsub object to be traced.

    :param pubsub: the Redis pubsub object to be traced.
    Incoming messages through get_message(), listen() and
    run_in_thread() will appear with an operation named 'SUB'.
    Commands executed on this object through execute_command()
    will be traced too with their respective command name.
    """
    _patch_pubsub(pubsub)


def _reset_tracing():
    global _g_tracer, _g_trace_all_classes, _g_start_span_cb
    _g_tracer = _g_trace_all_classes = _g_start_span_cb = None


def _get_tracer():
    return opentracing.tracer if _g_tracer is None else _g_tracer


def _normalize_stmt(args):
    return ' '.join([str(arg) for arg in args])


def _normalize_stmts(command_stack):
    commands = [_normalize_stmt(command[0]) for command in command_stack]
    return ';'.join(commands)


def _set_base_span_tags(span, stmt):
    span.set_tag(tags.COMPONENT, 'redis-py')
    span.set_tag(tags.SPAN_KIND, tags.SPAN_KIND_RPC_CLIENT)
    span.set_tag(tags.DATABASE_TYPE, 'redis')
    span.set_tag(tags.DATABASE_STATEMENT, stmt)


def _patch_redis_classes():
    # Patch the outgoing commands.
    _patch_obj_execute_command(redis.StrictRedis, True)

    # Patch the created pipelines.
    pipeline_method = redis.StrictRedis.pipeline

    @wraps(pipeline_method)
    def tracing_pipeline(self, transaction=True, shard_hint=None):
        pipe = pipeline_method(self, transaction, shard_hint)
        _patch_pipe_execute(pipe)
        return pipe

    redis.StrictRedis.pipeline = tracing_pipeline

    # Patch the created pubsubs.
    pubsub_method = redis.StrictRedis.pubsub

    @wraps(pubsub_method)
    def tracing_pubsub(self, **kwargs):
        pubsub = pubsub_method(self, **kwargs)
        _patch_pubsub(pubsub)
        return pubsub

    redis.StrictRedis.pubsub = tracing_pubsub


def _patch_client(client):
    # Patch the outgoing commands.
    _patch_obj_execute_command(client)

    # Patch the created pipelines.
    pipeline_method = client.pipeline

    @wraps(pipeline_method)
    def tracing_pipeline(transaction=True, shard_hint=None):
        pipe = pipeline_method(transaction, shard_hint)
        _patch_pipe_execute(pipe)
        return pipe

    client.pipeline = tracing_pipeline

    # Patch the created pubsubs.
    pubsub_method = client.pubsub

    @wraps(pubsub_method)
    def tracing_pubsub(**kwargs):
        pubsub = pubsub_method(**kwargs)
        _patch_pubsub(pubsub)
        return pubsub

    client.pubsub = tracing_pubsub


def _patch_pipe_execute(pipe):
    tracer = _get_tracer()

    # Patch the execute() method.
    execute_method = pipe.execute

    @wraps(execute_method)
    def tracing_execute(raise_on_error=True):
        if not pipe.command_stack:
            # Nothing to process/handle.
            return execute_method(raise_on_error=raise_on_error)

        with tracer.start_active_span('MULTI') as scope:
            span = scope.span
            _set_base_span_tags(span, _normalize_stmts(pipe.command_stack))

            _call_start_span_cb(span)

            try:
                res = execute_method(raise_on_error=raise_on_error)
            except Exception as exc:
                span.set_tag(tags.ERROR, True)
                span.log_kv({
                    'event': tags.ERROR,
                    'error.object': exc,
                })
                raise

        return res

    pipe.execute = tracing_execute

    # Patch the immediate_execute_command() method.
    immediate_execute_method = pipe.immediate_execute_command

    @wraps(immediate_execute_method)
    def tracing_immediate_execute_command(*args, **options):
        command = args[0]
        with tracer.start_active_span(command) as scope:
            span = scope.span
            _set_base_span_tags(span, _normalize_stmt(args))

            _call_start_span_cb(span)

            try:
                immediate_execute_method(*args, **options)
            except Exception as exc:
                span.set_tag(tags.ERROR, True)
                span.log_kv({
                    'event': tags.ERROR,
                    'error.object': exc,
                })

    pipe.immediate_execute_command = tracing_immediate_execute_command


def _patch_pubsub(pubsub):
    _patch_pubsub_parse_response(pubsub)
    _patch_obj_execute_command(pubsub)


def _patch_pubsub_parse_response(pubsub):
    tracer = _get_tracer()

    # Patch the parse_response() method.
    parse_response_method = pubsub.parse_response

    @wraps(parse_response_method)
    def tracing_parse_response(block=True, timeout=0):
        with tracer.start_active_span('SUB') as scope:
            span = scope.span
            _set_base_span_tags(span, '')

            _call_start_span_cb(span)

            try:
                rv = parse_response_method(block=block, timeout=timeout)
            except Exception as exc:
                span.set_tag(tags.ERROR, True)
                span.log_kv({
                    'event': tags.ERROR,
                    'error.object': exc,
                })
                raise

        return rv

    pubsub.parse_response = tracing_parse_response


def _patch_obj_execute_command(redis_obj, is_klass=False):
    tracer = _get_tracer()

    execute_command_method = redis_obj.execute_command

    @wraps(execute_command_method)
    def tracing_execute_command(*args, **kwargs):
        if is_klass:
            # Unbound method, we will get 'self' in args.
            reported_args = args[1:]
        else:
            reported_args = args

        command = reported_args[0]

        with tracer.start_active_span(command) as scope:
            span = scope.span
            _set_base_span_tags(span, _normalize_stmt(reported_args))

            _call_start_span_cb(span)

            try:
                rv = execute_command_method(*args, **kwargs)
            except Exception as exc:
                span.set_tag(tags.ERROR, True)
                span.log_kv({
                    'event': tags.ERROR,
                    'error.object': exc,
                })
                raise

        return rv

    redis_obj.execute_command = tracing_execute_command


def _call_start_span_cb(span):
    if _g_start_span_cb is None:
        return

    try:
        _g_start_span_cb(span)
    except Exception:
        pass
