import dataclasses
import time

from typing import Optional, Dict, Any
from polyswarmartifact import ArtifactType


@dataclasses.dataclass
class JobRequest:
    polyswarmd_uri: str
    guid: str
    index: int
    uri: str
    artifact_type: int
    duration: int
    metadata: Optional[Dict[str, Any]]
    chain: str
    ts: int

    @property
    def key(self):
        return f'{self.guid}:{self.index}'

    def is_expired(self, now=None):
        now = now or time.time()
        return self.ts + self.duration < now

    def get_artifact_type(self) -> ArtifactType:
        return ArtifactType(self.artifact_type)

    def asdict(self):
        return dataclasses.asdict(self)


@dataclasses.dataclass
class JobResponse:
    index: int
    bit: bool
    verdict: bool
    confidence: float
    metadata: str

    def asdict(self):
        return dataclasses.asdict(self)
