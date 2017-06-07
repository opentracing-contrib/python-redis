#################
Redis Opentracing
#################

This package enables distributed tracing for the Python redis library.

Instalation
===========

Run the following command:

    $ pip install redis_opentracing

Getting started
===============

Please see the examples directory. Overall, usage requires that a tracer gets set and have the Redis client and pipelines functionality get automatically traced:

.. code-block:: python

    import redis
    import redis_opentracing

    redis_opentracing.init_tracing(tracer)

    client = redis.StrictRedis()
    client.set('last_access', datetime.datetime.now())

It's possible to have traced only specific `StrictRedis` client objects:

.. code-block:: python

    redis_opentracing.init_tracing(tracer, trace_all_classes=False)
    redis_opentracing.trace_client(client)

    # Only commands and pipelines executed through this client will
    # be traced.
    res = client.get('last_access')

It's also possible to trace only specific pipelines:

.. code-block:: python

    redis_opentracing.init_tracing(tracer, trace_all_classes=False)

    pipe = client.pipeline()
    redis_opentracing.trace_pipeline(pipe)

    # This pipeline will be executed as a single MULTI command.
    pipe.lpush('fruits', 'lemon', 'watermelon')
    pipe.rpush('fruits', 'pineapple', 'apple')
    pipe.execute()


A thing to notice about pipelines is that when executed as a transaction, the set of commands will be included under a single 'MULTI' operation. Else, specially with commands required to be executed immediately, tracing will happen one-by-one (i.e. the `WATCH` command).

Further information
===================

If you’re interested in learning more about the OpenTracing standard, please visit `opentracing.io`_ or `join the mailing list`_. If you would like to implement OpenTracing in your project and need help, feel free to send us a note at `community@opentracing.io`_.

.. _opentracing.io: http://opentracing.io/
.. _join the mailing list: http://opentracing.us13.list-manage.com/subscribe?u=180afe03860541dae59e84153&id=19117aa6cd
.. _community@opentracing.io: community@opentracing.io

