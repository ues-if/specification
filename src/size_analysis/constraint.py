import dataclasses

from size_analysis.frame_model import FrameSpec


@dataclasses.dataclass(frozen=True)
class SizeConstraint:
    """Constraints for a single frame size, used in constrained optimisation."""
    lens_range: tuple[int, int]
    bridge_range: tuple[int, int]
    bridge_ratio_range: tuple[float, float]

    @property
    def candidates(self) -> tuple[FrameSpec, ...]:
        return tuple(self._candidates())

    def _candidates(self):
        for lens in range(self.lens_range[0], self.lens_range[1] + 1):  # inclusive range
            for bridge in range(self.bridge_range[0], self.bridge_range[1] + 1):  # inclusive range
                ratio = lens / bridge
                if self.bridge_ratio_range[0] <= ratio <= self.bridge_ratio_range[1]:
                    yield FrameSpec(lens=lens, bridge=bridge)
