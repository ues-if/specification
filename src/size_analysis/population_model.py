import dataclasses

from size_analysis.categories import AgeGroup, Category  # noqa: F401 (Category exported for callers)


@dataclasses.dataclass(frozen=True)
class PopulationGroup:
    category: Category
    population: int


@dataclasses.dataclass(frozen=True)
class PopulationModel:
    groups: dict[Category, int]  # Category → population count

    @property
    def total_modelled(self) -> int:
        return sum(self.groups.values())
