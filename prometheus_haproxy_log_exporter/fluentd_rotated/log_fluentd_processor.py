import os
import tailhead
import time
import json
import glob
from ..log_processing import AbstractLogProcessor


class LogFluentdProcessor(AbstractLogProcessor):
    def __init__(self, metric_updaters, path, *args, **kwargs):
        super().__init__(metric_updaters, *args, **kwargs)
        self.path = path
        self.should_exit = False

    def _get_path_by_pattern(self, pattern):
        files = glob.glob(pattern)
        if len(files) > 1:
            raise RuntimeError("Too many files matching provided glob")
        elif len(files) == 0:
            return None
        print("Matched file by pattern: {}".format(files[0]))
        return files[0]

    def follow_rotated_fluentd_path(self, pattern):
        while True:
            path = self._get_path_by_pattern(pattern)
            if path is None:
                time.sleep(0.1)
                continue
            for line in tailhead.follow_path(path):
                if line is not None:
                    yield line
                if not os.path.exists(path):
                    break
                yield None

    def run(self):
        for line in self.follow_rotated_fluentd_path(self.path):
            if line is None:
                time.sleep(0.1)
                if self.should_exit:
                    return
                continue
            payload = json.loads(line)['Payload']
            self.update_metrics(payload)
