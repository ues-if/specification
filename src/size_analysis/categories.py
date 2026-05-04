import dataclasses
import enum


class AgeGroup(enum.Enum):
    CHILD = "child"
    ADULT = "adult"


class Sex(enum.Enum):
    FEMALE = "F"
    MALE = "M"


@dataclasses.dataclass(frozen=True)
class Category:
    age: int | AgeGroup | None = None
    sex: Sex | None = None

    def matches(self, other: "Category") -> bool:
        if self.sex is not None and other.sex != self.sex:
            return False
        if self.age is None:
            return True
        if isinstance(self.age, AgeGroup):
            if self.age == AgeGroup.ADULT:
                return isinstance(other.age, int) and other.age >= 18
            if self.age == AgeGroup.CHILD:
                return isinstance(other.age, int) and other.age < 18
        return other.age == self.age

    def __str__(self) -> str:
        prefix = self.sex.value if self.sex is not None else "T"
        if self.age is None:
            return prefix
        suffix = str(self.age) if isinstance(self.age, int) else self.age.value
        return f"{prefix}-{suffix}"
