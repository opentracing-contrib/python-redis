#################
Redis Opentracing
#################

This package enables distributed tracing for the Python redis library.

Installation
============

Run the following command:

    $ pip install redis_opentracing

Getting started
===============

Tracing a Redis client requires setting up an OpenTracing-compatible tracer, and calling `init_tracing` to set up the tracing wrappers. See the examples directory for several different approaches.

.. code-block:: python

    import redis
    import redis_opentracing

    redis_opentracing.init_tracing(tracer)

    client = redis.StrictRedis()
    client.set('last_access', datetime.datetime.now())

It's possible to trace only specific Redis clients:

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

When pipeline commands are executed as a transaction, these commands will be grouped under a single 'MULTI' operation. They'll also appear as a single operation in the trace. Outside of a transaction, each command will generate a span.

And it's also possible to trace only specific pubsub objects:

.. code-block:: python

    redis_opentracing.init_tracing(tracer, trace_all_classes=False)

    pubsub = client.pubsub()
    redis_opentracing.trace_pubsub(pubsub)

    pubsub.subscribe('incoming-fruits')
    msg = pubsub.get_message() # This message will appear as a 'SUB' operation.

Incoming messages through `get_message`, `listen` and `run_in_thread` will be traced, and any command executed through the pubsub's `execute_command` method will be traced too.

Further information
===================

If you’re interested in learning more about the OpenTracing standard, please visit `opentracing.io`_ or `join the mailing list`_. If you would like to implement OpenTracing in your project and need help, feel free to send us a note at `community@opentracing.io`_.

.. _opentracing.io: http://opentracing.io/
.. _join the mailing list: http://opentracing.us13.list-manage.com/subscribe?u=180afe03860541dae59e84153&id=19117aa6cd
.. _community@opentracing.io: community@opentracing.io

