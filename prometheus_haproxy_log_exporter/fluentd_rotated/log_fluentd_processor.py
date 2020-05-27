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
        self._processed_files = []
        self.should_exit = False

    def _get_path_by_pattern(self, pattern):
        matched_paths = glob.glob(pattern)
        # if no files match glob, return None and wait for the
        # next iteration - fluentd is probably rotating file right now.
        if len(matched_paths) == 0:
            print("Glob matched no paths. Returning early "
                  "and waiting for the next iteration")
            return None
        print("Glob found {} matched paths:".format(len(matched_paths)))
        # compare all matched paths against the list of paths already processed
        # so that we can avoid tailing "closed" log file that is still waiting
        # for the rotation.
        # XXX: if self._processed_files is empty, we should compare file stat
        # and pick least recently changed one.
        new_path = None
        for path in matched_paths:
            if path in self._processed_files:
                print("\t{} already seen - skipping".format(path))
                continue
            print("\t{} is a new path - tailing it".format(path))
            new_path = path
            break
        # all logs have been processed, so return None and we'll try to match log
        # file in the next iteration.
        if new_path is None:
            print("Glob found no paths that weren't seen before. "
                  "Returning and waiting for the next iteration")
            return None
        # keep paths for the last 24 processed files (24 hours) so that we can
        # reprocessing finished logs that have yet to been rotated.
        self._processed_files = self._processed_files[-23:] + [new_path]
        return new_path

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
