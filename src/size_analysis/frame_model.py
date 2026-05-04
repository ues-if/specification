import dataclasses


@dataclasses.dataclass(frozen=True)
class FrameSpec:
    lens: int
    bridge: int

    @property
    def pd(self) -> int:
        return self.lens + self.bridge

    def __str__(self) -> str:
        return f"{self.lens}-{self.bridge}"
