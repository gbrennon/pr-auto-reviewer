import dataclasses
from dataclasses import dataclass

# ruleid: python-domain-boundary-dataclasses-must-be-frozen
@dataclass
class MutableBoundary:
    value: str


@dataclass(init=False, frozen=True)
class FrozenBoundary:
    value: str


@dataclasses.dataclass(frozen=True, init=False)
class QualifiedFrozenBoundary:
    value: str
