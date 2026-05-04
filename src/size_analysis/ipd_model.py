import dataclasses

from size_analysis.categories import AgeGroup, Category, Sex


@dataclasses.dataclass(frozen=True)
class Normal:
    mean: float
    standard_deviation: float


@dataclasses.dataclass(frozen=True)
class IPDGroup:
    category: Category
    distribution: Normal


@dataclasses.dataclass(frozen=True)
class IPDModel:
    groups: dict[Category, Normal]  # Category → IPD Normal distribution


# Fledelius & Stubgaard 1986 (digitised from Figure 10 in Dodgson [S11])
# Format: (age_label, female_mean, female_min, female_max, male_mean, male_min, male_max)
_ipd_fledelius = [
    ("5-7",   52, 45, 60,  53, 47, 61),
    ("8-10",  54, 48, 62,  56, 50, 63),
    ("11-13", 56, 50, 64,  58, 52, 65),
    ("14-16", 58, 52, 65,  61, 54, 68),
    ("17-19", 59, 53, 66,  63, 55, 71),
    ("20-24", 59, 53, 67,  64, 57, 72),
    ("25-30", 60, 54, 67,  64, 57, 72),
    ("31-55", 61, 55, 68,  65, 58, 73),
    (">55",   61, 55, 68,  65, 58, 73),
]

MODEL = IPDModel(
    # Fledelius & Stubgaard 1986 (children, ages 5–16)
    groups={
        **{
            Category(sex=Sex.FEMALE, age=int(age.split('-')[0])): Normal(
                mean=mean,
                standard_deviation=(max_val - min_val) / 4,  # Approximately 95% of data within mean ± 2*stddev
            )
            for age, mean, min_val, max_val, _, _, _ in _ipd_fledelius[:4]
        },
        **{
            Category(sex=Sex.MALE, age=int(age.split('-')[0])): Normal(
                mean=mean,
                standard_deviation=(max_val - min_val) / 4,  # Approximately 95% of data within mean ± 2*stddev
            )
            for age, _, _, _, mean, min_val, max_val in _ipd_fledelius[:4]
        },
        # ANSUR 1988
        Category(sex=Sex.FEMALE, age=AgeGroup.ADULT): Normal(mean=62.31, standard_deviation=3.599),
        Category(sex=Sex.MALE, age=AgeGroup.ADULT):   Normal(mean=64.67, standard_deviation=3.708),
    }
)
