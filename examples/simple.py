import datetime
import redis

import redis_opentracing

# Your OpenTracing-compatible tracer here.
tracer = None

if __name__ == '__main__':
    client = redis.StrictRedis()

    # By default, init_tracing() traces all Redis commands.
    redis_opentracing.init_tracing(tracer)

    # Traced as a SET command.
    client.set('last_access', datetime.datetime.now())

    # Traced as a MULTI command with
    # SET key:00 what
    # SET foo:01 bar
    pipe = client.pipeline()
    pipe.set('key:00', 'what')
    pipe.set('foo:01', 'bar')
    print(pipe.execute())
