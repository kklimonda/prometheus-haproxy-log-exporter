# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import itertools

from prometheus_client import Counter, Histogram

NAMESPACE = 'haproxy_log'

TIMERS = {
    'request_wait_seconds': (
        'time_wait_request',
        "Time spent waiting for the client to send the full HTTP request (TR in HAProxy)",
    ),
    'server_tcp_connection_establish_seconds': (
        'time_connect_server',
        "Time in seconds to connect to the final server (Tc in HAProxy)",
    ),
    'request_queued_seconds': (
        'time_wait_queues',
        "Time that the request spend on HAProxy queues (Tw in HAProxy)",
    ),
    'response_processing_seconds': (
        'time_wait_response',
        "Time waiting the downstream server to send the full HTTP response (Tr in HAProxy)",
    ),
    'session_duration_seconds': (
        'total_time',
        "Time between accepting the HTTP request and sending back the HTTP response (Tt in HAProxy)",
    ),
}

TIMER_ABORT_COUNTERS = {
    'request_wait_seconds': (  # Tq
        'request_abort_total',
        "Count of connections aborted before a complete request was received",
    ),
    'server_tcp_connection_establish_seconds': (  # Tc
        'request_pre_server_connection_abort',
        "Count of connections aborted before a connection to a server was established",
    ),
    'request_queued_seconds': (  # Tw
        'request_pre_queue_abort_total',
        "Count of connections aborted before reaching the queue",
    ),
    'response_processing_seconds': (  # Tr
        'request_response_abort_total',
        "Count of connections for which the last response header from the server was never received",
    ),
}

TIMER_NAMES = TIMERS.keys()

# These are attributes associated with each line processed, which can be used
# as labels on metrics. Labels (matching official haproxy exporter where
# applicable) are converted to attributes from haproxy.line.Line.
REQUEST_LABELS = [
    # (label, attribute)
    ('code', 'status_code'),
    ('frontend', 'frontend_name'),
    ('backend', 'backend_name'),
    ('server', 'server_name'),
    ('http_request_path', 'http_request_path'),
    ('http_request_method', 'http_request_method'),
    ('client_ip', 'client_ip'),
    ('client_port', 'client_port'),
]

# These are the default buckets for the Prometheus python client, adjusted to
# be in milliseconds
DEFAULT_TIMER_BUCKETS = (
    0.005, 0.010, 0.025,
    0.050, 0.075, 0.100, 0.250,
    0.500, 0.750, 1.0, 2.5,
    5.0, 7.5, 10.0, float('inf'),
)


DEFAULT_QUEUE_LENGTH_BUCKETS = tuple(itertools.chain(
    range(0, 10),
    (20, 30, 40, 60, 100, float('inf')),
))


def requests_total(labelnames):
    requests_total = Counter(
        'requests_total',
        "Total processed requests",
        namespace=NAMESPACE,
        labelnames=labelnames,
    )

    if len(labelnames) == 0:
        def observe(line):
            requests_total.inc()
    else:
        def observe(line):
            requests_total.labels(**{
                label: getattr(line, label)
                for label in labelnames
            }).inc()

    return observe


def timer(timer_name, labelnames, buckets):
    attribute, documentation = TIMERS[timer_name]

    labelnames

    label_mappings = [mapping for mapping
                      in REQUEST_LABELS if mapping[0] in labelnames]

    histogram = Histogram(
        timer_name,
        documentation=documentation,
        namespace=NAMESPACE,
        labelnames=tuple(labelnames),
        buckets=buckets,
    )

    if timer_name == 'session_duration_seconds':
        def observe(line):
            raw_value = getattr(line, attribute)
            # not all attributes are set for both HTTP and TCP logs,
            # so ba il out early if value is None
            if raw_value is None:
                return

            label_values = {
                label: getattr(line, attr)
                for (label, attr) in label_mappings
            }

            # strip prefix + if present, and convert from milliseconds to seconds
            if isinstance(raw_value, str) and raw_value.startswith('+'):
                value = float(raw_value[1:]) / 1000
            else:
                value = float(raw_value) / 1000

            histogram.labels(**label_values).observe(value)
    else:
        abort_counter_name, abort_counter_documentation = TIMER_ABORT_COUNTERS[timer_name]

        abort_counter = Counter(
            abort_counter_name,
            abort_counter_documentation,
            namespace=NAMESPACE,
            labelnames=labelnames,
        )

        if len(labelnames) == 0:
            def observe(line):
                value = float(getattr(line, attribute))

                if value == -1:
                    abort_counter.inc()
                else:
                    histogram.observe(value)
        else:
            def observe(line):
                value = getattr(line, attribute)
                # Not all attributes are set for both TCP and HTTP
                # so bail out early if value is None
                if value is None:
                    return
                value = float(value)

                label_values = {
                    label: getattr(line, attr)
                    for label, attr in label_mappings
                }

                if value == -1:
                    abort_counter.labels(**label_values).inc()
                else:
                    histogram.labels(**label_values).observe(value / 1000)

    return observe


def bytes_read_total(labelnames):
    counter = Counter(
        'bytes_read_total',
        "Bytes read total",
        namespace=NAMESPACE,
        labelnames=labelnames,
    )

    label_mappings = [mapping for mapping
                      in REQUEST_LABELS if mapping[0] in labelnames]

    if len(labelnames) == 0:
        def observe(line):
            counter.inc()
    else:
        def observe(line):
            counter.labels(**{
                label: getattr(line, attr)
                for label, attr in label_mappings
            }).inc()

    return observe


def backend_queue_length(labelnames, buckets):
    histogram = Histogram(
        'backend_queue_length',
        "Requests processed before this one in the backend queue",
        namespace=NAMESPACE,
        labelnames=tuple(labelnames),
        buckets=buckets,
    )

    label_mappings = [mapping for mapping
                      in REQUEST_LABELS if mapping[0] in labelnames]

    if len(labelnames) == 0:
        def observe(line):
            histogram.observe(line.queue_backend)
    else:
        def observe(line):
            histogram.labels({
                label: getattr(line, attr)
                for label, attr in label_mappings
            }).observe(line.queue_backend)

    return observe


def server_queue_length(labelnames, buckets):
    histogram = Histogram(
        'server_queue_length',
        "Length of the server queue when the request was received",
        namespace=NAMESPACE,
        labelnames=tuple(labelnames),
        buckets=buckets,
    )

    label_mappings = [mapping for mapping
                      in REQUEST_LABELS if mapping[0] in labelnames]

    if len(labelnames) == 0:
        def observe(line):
            histogram.observe(line.queue_server)
    else:
        def observe(line):
            histogram.labels({
                label: getattr(line, attr)
                for label, attr in label_mappings
            }).observe(line.queue_server)

    return observe
