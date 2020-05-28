import tailhead
import time
import json
from ..file import LogFileProcessor


class LogFluentdProcessor(LogFileProcessor):
    def run(self):
        for line in tailhead.follow_path(self.path):
            if line is None:
                time.sleep(0.1)
                if self.should_exit:
                    return
                continue
            try:
                payload = json.loads(line)['Payload']
            except json.decoder.JSONDecodeError:
                print("Line not parsable as JSON: {}".format(line))
                continue
            self.update_metrics(payload)
