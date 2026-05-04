"""Tests for size_analysis.optimizer using plain pytest functions."""

import pytest

from size_analysis.categories import AgeGroup, Category, Sex
from size_analysis.frame_model import FrameSpec
from size_analysis.ipd_model import IPDModel, Normal
from size_analysis.population_model import PopulationModel
from size_analysis.optimizer import (
    Model,
    RankedSolution,
    SearchSpace,
    _build_coverage,
    _merge_intervals,
    exact_coverage,
    pop_covered_by_set,
    pop_of,
    solve,
    total_modelled,
    union_coverage_group,
)

_ADULT = Category(sex=Sex.FEMALE, age=AgeGroup.ADULT)
_CHILD = Category(sex=Sex.MALE, age=5)


def _candidates_from_ranges(lens_range, bridge_range):
    return tuple(
        FrameSpec(lens=lens, bridge=bridge)
        for lens in range(lens_range[0], lens_range[1] + 1)
        for bridge in range(bridge_range[0], bridge_range[1] + 1)
    )


def _single_group_model(mean, sd, population, X=4.0):
    ipd_model = IPDModel(groups={_ADULT: Normal(mean=mean, standard_deviation=sd)})
    pop = PopulationModel(groups={Category(sex=Sex.FEMALE, age=30): population})
    lens = int(mean) - 5
    bridge = 10
    lens_range = (lens, lens + 10)
    bridge_range = (bridge, bridge + 5)
    candidates = _candidates_from_ranges(lens_range, bridge_range)
    return Model(pop, ipd_model, X, candidates)


def _two_group_model():
    ipd_model = IPDModel(groups={
        Category(sex=Sex.FEMALE, age=AgeGroup.ADULT): Normal(mean=55.0, standard_deviation=0.5),
        Category(sex=Sex.MALE,   age=AgeGroup.ADULT): Normal(mean=65.0, standard_deviation=0.5),
    })
    pop = PopulationModel(groups={
        Category(sex=Sex.FEMALE, age=25): 1000,
        Category(sex=Sex.MALE,   age=25): 1000,
    })
    all_candidates = _candidates_from_ranges((42, 60), (10, 15))
    model = Model(pop, ipd_model, 2.0, all_candidates)
    candidates = tuple(s for s in model.coverage if s.lens / s.bridge >= 2.5)
    space = SearchSpace(n_sizes=2, candidates=candidates)
    return model, space


# --- _merge_intervals ---

@pytest.mark.parametrize("frame_pds,X,expected", [
    ([], 4.0, []),
    ([50], 4.0, [(46.0, 54.0)]),
    ([50, 70], 4.0, [(46.0, 54.0), (66.0, 74.0)]),
    ([50, 58], 4.0, [(46.0, 62.0)]),
    ([50, 52], 4.0, [(46.0, 56.0)]),
    ([50, 52, 70], 4.0, [(46.0, 56.0), (66.0, 74.0)]),
    ([50, 55, 60], 4.0, [(46.0, 64.0)]),
])
def test_merge_intervals(frame_pds, X, expected):
    assert _merge_intervals(frame_pds, X) == pytest.approx(expected)


# --- union_coverage_group ---

def test_union_coverage_zero_frames():
    assert union_coverage_group([], Normal(mean=60.0, standard_deviation=2.0), 4.0) == 0.0


@pytest.mark.parametrize("frame_pds,lo,hi", [
    ([60],  0.999, 1.0),
    ([100], 0.0,   1e-6),
])
def test_union_coverage_tight_distribution(frame_pds, lo, hi):
    c = union_coverage_group(frame_pds, Normal(mean=60.0, standard_deviation=0.1), 4.0)
    assert lo <= c <= hi


@pytest.mark.parametrize("frame_pds", [[55], [55, 65], [50, 60, 70]])
def test_union_coverage_in_unit_interval(frame_pds):
    c = union_coverage_group(frame_pds, Normal(mean=60.0, standard_deviation=3.0), 4.0)
    assert 0.0 <= c <= 1.0


def test_union_coverage_monotone_with_more_frames():
    dist = Normal(mean=60.0, standard_deviation=2.0)
    assert union_coverage_group([60, 65], dist, 4.0) >= union_coverage_group([60], dist, 4.0)


def test_union_coverage_duplicate_frames_unchanged():
    dist = Normal(mean=60.0, standard_deviation=2.0)
    assert union_coverage_group([60, 60], dist, 4.0) == pytest.approx(
        union_coverage_group([60], dist, 4.0), rel=1e-9
    )


# --- build_coverage ---

def test_build_coverage_keys_are_frame_specs():
    candidates = _candidates_from_ranges((45, 50), (10, 15))
    coverage = _build_coverage(candidates, {_ADULT: Normal(mean=60.0, standard_deviation=2.0)}, 4.0)
    assert all(isinstance(k, FrameSpec) for k in coverage)


def test_build_coverage_fractions_in_unit_interval():
    candidates = _candidates_from_ranges((45, 55), (10, 15))
    coverage = _build_coverage(candidates, {_ADULT: Normal(mean=60.0, standard_deviation=2.0)}, 4.0)
    assert all(0.0 < frac <= 1.0 for fracs in coverage.values() for frac in fracs.values())


def test_build_coverage_same_frame_pd_same_coverage():
    candidates = _candidates_from_ranges((44, 51), (9, 16))
    coverage = _build_coverage(candidates, {_ADULT: Normal(mean=60.0, standard_deviation=2.0)}, 4.0)
    a, b = FrameSpec(lens=45, bridge=15), FrameSpec(lens=50, bridge=10)
    if a in coverage and b in coverage:
        assert coverage[a] == pytest.approx(coverage[b])


def test_build_coverage_excludes_far_specs():
    candidates = _candidates_from_ranges((35, 40), (10, 12))
    coverage = _build_coverage(candidates, {_ADULT: Normal(mean=60.0, standard_deviation=0.1)}, 4.0)
    assert len(coverage) == 0


# --- pop_of ---

@pytest.mark.parametrize("groups,fracs,expected", [
    ({_ADULT: 1000}, {_ADULT: 1.0}, 1000.0),
    ({_ADULT: 1000}, {_ADULT: 0.5},  500.0),
    ({_ADULT: 1000, _CHILD: 2000}, {_ADULT: 0.5, _CHILD: 0.25}, 1000.0),
    ({_ADULT: 1000}, {}, 0.0),
])
def test_pop_of(groups, fracs, expected):
    assert pop_of(groups, fracs) == pytest.approx(expected)


# --- total_modelled ---

def test_total_modelled():
    assert total_modelled({_ADULT: 1000, _CHILD: 2000}) == 3000


# --- Model ---

def test_model_construction():
    model = _single_group_model(mean=60.0, sd=2.0, population=1000)
    assert model.tolerance == pytest.approx(4.0)
    assert len(model.groups) == 1
    assert len(model.ipd_groups) == 1
    assert len(model.coverage) > 0


def test_model_is_immutable():
    model = _single_group_model(mean=60.0, sd=2.0, population=1000)
    with pytest.raises(AttributeError):
        model.tolerance = 5.0  # type: ignore[misc]


def test_model_aggregates_population_by_category():
    cat = Category(sex=Sex.FEMALE, age=AgeGroup.ADULT)
    ipd_model = IPDModel(groups={cat: Normal(mean=62.0, standard_deviation=3.0)})
    pop = PopulationModel(groups={
        Category(sex=Sex.FEMALE, age=25): 1000,
        Category(sex=Sex.FEMALE, age=35): 2000,
        Category(sex=Sex.MALE,   age=25):  500,
    })
    candidates = _candidates_from_ranges((48, 55), (10, 15))
    model = Model(pop, ipd_model, 4.0, candidates)
    assert model.groups[cat] == 3000


def test_model_cov_respects_ranges():
    model = _single_group_model(mean=60.0, sd=2.0, population=1000)
    for spec in model.coverage:
        assert 55 <= spec.lens <= 65
        assert 10 <= spec.bridge <= 15


# --- exact_coverage ---

def test_exact_coverage_perfect_frame():
    model = _single_group_model(mean=60.0, sd=0.1, population=1000)
    assert exact_coverage([FrameSpec(lens=50, bridge=10)], model)[_ADULT] > 0.999


def test_exact_coverage_keys_match_groups():
    model = _single_group_model(mean=60.0, sd=2.0, population=1000)
    assert set(exact_coverage([FrameSpec(lens=50, bridge=10)], model).keys()) == set(model.groups)


def test_exact_coverage_monotone_with_more_frames():
    model = _single_group_model(mean=60.0, sd=2.0, population=1000)
    s1, s2 = FrameSpec(lens=50, bridge=10), FrameSpec(lens=53, bridge=10)
    assert exact_coverage([s1, s2], model)[_ADULT] >= exact_coverage([s1], model)[_ADULT]


# --- pop_covered_by_set ---

def test_pop_covered_by_set_perfect_frame():
    model = Model(
        PopulationModel(groups={Category(sex=Sex.FEMALE, age=30): 1000}),
        IPDModel(groups={_ADULT: Normal(mean=65.0, standard_deviation=0.1)}),
        4.0, _candidates_from_ranges((55, 60), (10, 10)),
    )
    assert pop_covered_by_set([FrameSpec(lens=55, bridge=10)], model) > 999.0


def test_pop_covered_by_set_never_exceeds_total():
    model = _single_group_model(mean=60.0, sd=2.0, population=1000)
    assert pop_covered_by_set([FrameSpec(lens=55, bridge=10)], model) <= 1000.0


# --- solve ---

def test_solve_returns_ranked_solutions():
    model, space = _two_group_model()
    results = solve(space, model, top_n=3)
    assert isinstance(results, list)
    assert all(isinstance(r, RankedSolution) for r in results)


@pytest.mark.parametrize("top_n", [1, 3, 5])
def test_solve_top_n_respected(top_n):
    model, space = _two_group_model()
    assert len(solve(space, model, top_n=top_n)) <= top_n


def test_solve_sorted_by_coverage_descending():
    model, space = _two_group_model()
    coverages = [r.coverage for r in solve(space, model, top_n=5)]
    assert coverages == sorted(coverages, reverse=True)


def test_solve_specs_sorted_by_frame_pd():
    model, space = _two_group_model()
    for result in solve(space, model, top_n=3):
        pds = [s.lens + s.bridge for s in result.specs]
        assert pds == sorted(pds)


def test_solve_each_solution_has_correct_n_specs():
    model, space = _two_group_model()
    for result in solve(space, model, top_n=3):
        assert len(result.specs) == space.n_sizes


def test_solve_optimal_covers_both_groups():
    model, space = _two_group_model()
    best = solve(space, model)[0]
    assert best.coverage / total_modelled(model.groups) > 0.95


def test_solve_coverage_never_exceeds_total():
    model, space = _two_group_model()
    total = total_modelled(model.groups)
    for result in solve(space, model, top_n=5):
        assert result.coverage <= total + 1


def test_solve_group_filter_restricts_candidates():
    model, space = _two_group_model()
    results = solve(space, model, group_filter=lambda cat: cat.sex == Sex.FEMALE, top_n=1)
    assert len(results) == 1


def test_solve_group_filter_coverage_below_unfiltered():
    model, space = _two_group_model()
    female_only = lambda cat: cat.sex == Sex.FEMALE
    assert solve(space, model, group_filter=female_only)[0].coverage <= solve(space, model)[0].coverage


def test_solve_pinned_frames_add_to_coverage():
    model, space_2 = _two_group_model()
    space_1 = SearchSpace(n_sizes=1, candidates=space_2.candidates)
    pin = FrameSpec(lens=45, bridge=10)
    with_pin    = solve(space_1, model, pinned=[pin])[0].coverage
    without_pin = solve(space_1, model)[0].coverage
    assert with_pin >= without_pin - 1
