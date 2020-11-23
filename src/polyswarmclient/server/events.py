import datetime
import dataclasses
import math
import time

from typing import List, Dict


@dataclasses.dataclass
class Bounty:
    guid: str
    artifact_type: str
    artifact_url: str
    sha256: str
    mimetype: str
    expiration: str
    phase: str
    response_url: str
    rules: List[str]
    duration: int = dataclasses.field(init=False)

    def __post_init__(self):
        self.duration = int(math.floor(datetime.datetime.fromisoformat(self.expiration).timestamp())) - int(math.floor(time.time()))
