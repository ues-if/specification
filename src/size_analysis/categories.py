import dataclasses
import enum


class AgeGroup(enum.Enum):
    CHILD = "child"
    ADULT = "adult"


class Sex(enum.Enum):
    FEMALE = "F"
    MALE = "M"
    OTHER = "T"


@dataclasses.dataclass(frozen=True)
class Category:
    age: int | tuple[int, int] | AgeGroup | None = None
    sex: Sex | None = None
    region: str | None = None

    def matches(self, other: "Category") -> bool:
        if self.region is not None and other.region is not None and other.region != self.region:
            return False
        if self.sex is not None and other.sex != self.sex:
            return False
        if self.age is None:
            return True
        if isinstance(self.age, AgeGroup):
            if self.age == AgeGroup.ADULT:
                return isinstance(other.age, int) and other.age >= 18
            if self.age == AgeGroup.CHILD:
                return isinstance(other.age, int) and other.age < 18
        if isinstance(self.age, tuple):
            return isinstance(other.age, int) and self.age[0] <= other.age <= self.age[1]
        return other.age == self.age

    def __str__(self) -> str:
        region = self.region or "ALL"
        suffix = self.sex.value if self.sex is not None else "T"
        if self.age is None:
            return f"00-99-{suffix}-{region}"
        if isinstance(self.age, int):
            prefix = f"{self.age:02d}-{self.age:02d}"
        elif isinstance(self.age, tuple):
            prefix = f"{self.age[0]:02d}-{self.age[1]:02d}"
        elif self.age == AgeGroup.CHILD:
            prefix = "00-17"
        else:
            prefix = "18-99"
        return f"{prefix}-{suffix}-{region}"
