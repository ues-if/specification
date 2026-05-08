from size_analysis.categories import AgeGroup, Category, Sex


def test_category_string_sorts_by_padded_age_then_sex():
    categories = [
        Category(sex=Sex.MALE, age=(8, 10)),
        Category(sex=Sex.FEMALE, age=(5, 7)),
        Category(sex=Sex.MALE, age=(5, 7)),
        Category(sex=Sex.FEMALE, age=(31, 55)),
    ]

    assert sorted(str(category) for category in categories) == [
        "05-07-F-ALL",
        "05-07-M-ALL",
        "08-10-M-ALL",
        "31-55-F-ALL",
    ]


def test_category_string_handles_single_and_symbolic_ages():
    assert str(Category(sex=Sex.FEMALE, age=5)) == "05-05-F-ALL"
    assert str(Category(sex=Sex.MALE, age=AgeGroup.CHILD)) == "00-17-M-ALL"
    assert str(Category(sex=Sex.FEMALE, age=AgeGroup.ADULT)) == "18-99-F-ALL"
    assert str(Category()) == "00-99-T-ALL"


def test_category_string_includes_region_when_available():
    assert str(Category(region="EU", sex=Sex.FEMALE, age=(5, 7))) == "05-07-F-EU"
