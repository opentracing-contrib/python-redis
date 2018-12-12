.. :changelog:

History
-------

1.0.0 (2018-12-12)
------------------

- Adopt the OpenTracing 2.0 API.
- Default to the global tracer when no tracer was provided.
- Better tags & logs. (#9)
- Remove the prefix parameter for init_tracing().
- Implement a start span callback.
- Code cleanup (#12)
- Use Python 3.6 for Travis (3.4 is EOL).
- Use the OT 2.0 API for in our examples.
