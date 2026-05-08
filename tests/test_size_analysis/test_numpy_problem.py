import numpy as np
import pytest

from size_analysis.categories import AgeGroup, Category, Sex
from size_analysis.frame_model import FrameSpec
from size_analysis.numpy_problem import (
    _candidate_indices,
    _result_sort_key,
    _solve_milp_for_k,
    build_problem,
    build_gaussian_population_model_from_records,
    evaluate_selection,
    standard_age_bracket,
)


def _small_problem():
    return build_problem(
        combined_model={
            "categories": (Category(sex=Sex.FEMALE, age=AgeGroup.ADULT),),
            "population": np.array([100.0]),
            "gaussian_ipd": np.array([[60.0, 0.5]]),
        },
        candidates=(
            FrameSpec(lens=45, bridge=10),
            FrameSpec(lens=50, bridge=10),
            FrameSpec(lens=55, bridge=10),
        ),
        tolerance=1.0,
        grid_step=1.0,
    )


def test_group_best_matches_are_sorted_by_padded_category_string():
    problem = build_problem(
        combined_model={
            "categories": (
                Category(sex=Sex.MALE, age=(8, 10)),
                Category(sex=Sex.FEMALE, age=(5, 7)),
            ),
            "population": np.array([100.0, 100.0]),
            "gaussian_ipd": np.array([[60.0, 0.5], [55.0, 0.5]]),
        },
        candidates=(FrameSpec(lens=45, bridge=10), FrameSpec(lens=50, bridge=10)),
        tolerance=1.0,
        grid_step=1.0,
    )

    result = evaluate_selection(problem, np.array([1, 1]))

    assert [str(match["category"]) for match in result["group_best_matches"]] == [
        "05-07-F-ALL",
        "08-10-M-ALL",
    ]


def test_processed_records_model_includes_region_in_category_labels(tmp_path):
    records_path = tmp_path / "ipd_records.json"
    records_path.write_text(
        """
        [
          {
            "source": "taiwan_plos_s002",
            "kind": "ipd_sample",
            "sex": "F",
            "age": {"value": 21, "range": [21, 21], "label": "21"},
            "ipd": {"value": 60.0, "unit": "mm"},
            "count": 1
          },
          {
            "source": "taiwan_plos_s002",
            "kind": "ipd_sample",
            "sex": "F",
            "age": {"value": 21, "range": [21, 21], "label": "21"},
            "ipd": {"value": 62.0, "unit": "mm"},
            "count": 1
          }
        ]
        """,
        encoding="utf-8",
    )

    model = build_gaussian_population_model_from_records(records_path)

    assert [str(category) for category in model["categories"]] == ["18-99-F-TW"]
    assert model["population"].tolist() == [2.0]
    assert model["gaussian_ipd"][0, 0] == pytest.approx(61.0)


@pytest.mark.parametrize("age_range,expected", [
    ((5, 5), (5, 7)),
    ((8, 10), (8, 10)),
    ((12, 12), (11, 13)),
    ((16, 16), (14, 17)),
    ((21, 21), (18, 99)),
    ((100, None), (18, 99)),
    ((100, 100), None),
])
def test_standard_age_bracket(age_range, expected):
    assert standard_age_bracket(age_range) == expected


def test_evaluate_selection_retains_previous_specs_for_group_metrics():
    problem = _small_problem()
    x = np.array([1, 0, 0])

    without_retained = evaluate_selection(problem, x)
    with_retained = evaluate_selection(problem, x, retained_candidate_indices=(1,))

    assert without_retained["selected_candidates"] == (FrameSpec(lens=45, bridge=10),)
    assert with_retained["selected_candidates"] == (FrameSpec(lens=45, bridge=10),)
    assert with_retained["retained_candidates"] == (FrameSpec(lens=50, bridge=10),)
    assert with_retained["evaluation_candidates"] == (
        FrameSpec(lens=45, bridge=10),
        FrameSpec(lens=50, bridge=10),
    )
    assert with_retained["coverage_rate"] > without_retained["coverage_rate"]
    assert with_retained["group_mean_deviation"][0] < without_retained["group_mean_deviation"][0]
    assert with_retained["group_best_matches"][0]["candidate"] == FrameSpec(lens=50, bridge=10)
    assert with_retained["group_best_matches"][0]["source"] == "retained"


def test_candidate_indices_require_exact_specs():
    problem = _small_problem()

    assert _candidate_indices(problem, (FrameSpec(lens=50, bridge=10),)) == (1,)
    with pytest.raises(ValueError, match="candidate\\(s\\) not present"):
        _candidate_indices(problem, (FrameSpec(lens=49, bridge=11),))


def test_result_sort_key_orders_best_completed_results_first():
    rows = [
        {
            "coverage_rate": 0.90,
            "weighted_excess_deviation": 0.0,
            "weighted_mean_deviation": 1.0,
            "k": 2,
            "selected_frame_pd": (55.0, 60.0),
        },
        {
            "coverage_rate": 0.95,
            "weighted_excess_deviation": 1.0,
            "weighted_mean_deviation": 0.5,
            "k": 3,
            "selected_frame_pd": (55.0, 60.0, 65.0),
        },
        {
            "coverage_rate": 0.95,
            "weighted_excess_deviation": 0.0,
            "weighted_mean_deviation": 0.5,
            "k": 2,
            "selected_frame_pd": (55.0, 60.0),
        },
    ]

    sorted_rows = sorted(rows, key=_result_sort_key)

    assert sorted_rows[0]["coverage_rate"] == 0.95
    assert sorted_rows[0]["weighted_excess_deviation"] == 0.0
    assert sorted_rows[-1]["coverage_rate"] == 0.90


def test_solve_milp_fixes_excluded_candidates_to_zero_and_keeps_retained_for_evaluation():
    problem = _small_problem()

    class FakeBounds:
        def __init__(self, lower, upper):
            self.lower = lower
            self.upper = upper

    class FakeLinearConstraint:
        def __init__(self, matrix, lower, upper):
            self.matrix = matrix
            self.lower = lower
            self.upper = upper

    def fake_milp(c, integrality, bounds, constraints):
        assert bounds.upper[1] == pytest.approx(0.0)
        q = np.zeros(len(c))
        q[0] = 1.0

        class Result:
            success = True
            x = q
            message = "fake optimal"
            fun = -1.0

        return Result()

    result = _solve_milp_for_k(
        problem=problem,
        k=1,
        excluded_selections=[],
        excluded_candidate_indices=(1,),
        retained_candidate_indices=(1,),
        bounds_class=FakeBounds,
        linear_constraint_class=FakeLinearConstraint,
        milp_function=fake_milp,
    )

    assert result is not None
    assert result["selected_candidates"] == (FrameSpec(lens=45, bridge=10),)
    assert result["retained_candidates"] == (FrameSpec(lens=50, bridge=10),)
    assert FrameSpec(lens=50, bridge=10) in result["evaluation_candidates"]
