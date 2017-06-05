class DummyTracer(object):
    def __init__(self, with_subtracer=False):
        super(DummyTracer, self).__init__()
        if with_subtracer:
            self._tracer = object()
        self.spans = []

    def clear(self):
        self.spans = []

    def start_span(self, operation_name, child_of=None):
        span = DummySpan(operation_name, child_of=child_of)
        self.spans.append(span)
        return span

class DummySpan(object):
    def __init__(self, operation_name='span', child_of=None):
        super(DummySpan, self).__init__()
        self.operation_name = operation_name
        self.child_of = child_of
        self.tags = {}
        self.is_finished = False

    def set_tag(self, name, value):
        self.tags[name] = value

    def finish(self):
        self.is_finished = True
