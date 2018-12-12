import datetime
import redis

import opentracing
import redis_opentracing

# Your OpenTracing-compatible tracer here.
tracer = opentracing.Tracer()

if __name__ == '__main__':
    client = redis.StrictRedis()
    redis_opentracing.init_tracing(tracer,
                                   trace_all_classes=False)

    with tracer.start_active_span('main_span'):

        # Not traced.
        client.set('last_access', datetime.datetime.now())

        # Everthing from this point on client gets traced,
        # with main_span as implicit parent.
        redis_opentracing.trace_client(client)

        # Traced.
        client.set('last_update', datetime.datetime.now())

        # Traced as a MULTI command with
        # LPUSH fruits lemon watermelon
        pipe = client.pipeline()
        pipe.lpush('fruits', 'lemon', 'watermelon')
        print(pipe.execute())
