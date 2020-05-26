import tailhead
import time
import json
from ..log_processing import AbstractLogProcessor


class LogFluentdProcessor(AbstractLogProcessor):
    def __init__(self, metric_updaters, path, *args, **kwargs):
        super().__init__(metric_updaters, *args, **kwargs)
        self.path = path
        self.should_exit = False

    def run(self):
        for line in tailhead.follow_path(self.path):
            if line is None:
                time.sleep(0.1)
                if self.should_exit:
                    return
                continue
            payload = json.loads(line)['Payload']
            self.update_metrics(payload)
