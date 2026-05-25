"""

Abbreviations
-------------
- IPD: Inter-Pupillary Distance
- PD: Pupillary Distance (lens + bridge)
- CDF: Cumulative Distribution Function
- PDF: Probability Density Function
- popᵢ: population count of group i
- μᵢ: mean IPD of group i
- σᵢ: standard deviation of IPD in group i
- X: fitting tolerance (e.g. 5mm)

Coverage-maximisation optimizer for frame PD sets.

Given a population of G groups, each described by a weight (population count)
and an IPD Normal distribution, this module finds a set S of k frame specs
(lens+bridge pairs) that maximises the weighted coverage objective:

    f(S) = Σᵢ popᵢ · P(∃ s ∈ S : |IPDᵢ − pd(s)| ≤ X)

where pd(s) = s.lens + s.bridge and X is the fitting tolerance.

Coverage model
--------------
A frame covers a person when |IPD − pd| ≤ X.  For a group with
Normal(μ, σ) IPD the covered fraction is:

    coverage(pd) = CDF(pd + X) − CDF(pd − X)

Meaning the higher the coverage, the more people in that group are likely to find a good fit with that frame.

For a set S the union coverage is the probability that at least one pd fits,
computed exactly by merging the tolerance windows into disjoint intervals.

Algorithm
---------
f is a non-negative monotone submodular function.  Two solvers are provided:

  solve                  — greedy (1 − 1/e) construction + 1-opt local swap.
  solve_exhaustive_pairs — exact brute-force for k = 2 (used when the
                           candidate set is small enough).
"""
import logging

import dataclasses
import itertools
import statistics
from typing import Callable

from collections import defaultdict

from size_analysis.constraint import SizeConstraint
from size_analysis.categories import Category
from size_analysis.frame_model import FrameSpec
from size_analysis.ipd_model import IPDModel, Normal
from size_analysis.population_model import PopulationModel
from size_analysis.math import absolute_mean_difference


logger = logging.getLogger(__name__)

# ============================================================================
# COVERAGE MODEL
# ============================================================================


def _spec_coverage(spec: FrameSpec, ipd_groups: dict[Category, Normal], tolerance: float) -> dict[Category, float]:
    group_coverages: dict[Category, float] = {}
    for cat, dist_params in ipd_groups.items():
        dist = statistics.NormalDist(dist_params.mean, dist_params.standard_deviation)
        fraction = dist.cdf(spec.pd + tolerance) - dist.cdf(spec.pd - tolerance)
        if fraction > 1e-9:
            group_coverages[cat] = fraction
    return group_coverages


def _build_coverage(
    candidates: tuple[FrameSpec, ...],
    ipd_groups: dict[Category, Normal],
    tolerance: float,
) -> dict[FrameSpec, dict[Category, float]]:
    """Precompute per-spec, per-group coverage fractions.

    Returns a dict mapping each FrameSpec to {category: fraction_covered}.
    Coverage depends only on frame_pd = lens + bridge, so two specs with the
    same sum have identical entries.
    """
    result: dict[FrameSpec, dict[Category, float]] = {}
    for spec in candidates:
        group_coverages = _spec_coverage(spec, ipd_groups, tolerance)
        if group_coverages:
            result[spec] = group_coverages
    return result


def _merge_intervals(frame_pds: list[int], tolerance: float) -> list[tuple[float, float]]:
    """Merge overlapping tolerance windows [fp-tolerance, fp+tolerance] into sorted disjoint intervals."""
    if not frame_pds:
        return []
    intervals = sorted((frame_pd - tolerance, frame_pd + tolerance) for frame_pd in frame_pds)
    merged = [list(intervals[0])]
    for lower, upper in intervals[1:]:
        if lower <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], upper)
        else:
            merged.append([lower, upper])
    return [(lower, upper) for lower, upper in merged]


def union_coverage_group(frame_pds: list[int], dist: Normal, tolerance: float) -> float:
    """Exact P(|IPD - fp| <= tolerance for at least one fp) for a Normal IPD distribution."""
    merged = _merge_intervals(frame_pds, tolerance)
    nd = statistics.NormalDist(dist.mean, dist.standard_deviation)
    return sum(nd.cdf(upper) - nd.cdf(lower) for lower, upper in merged)


# ============================================================================
# POPULATION MODEL
# ============================================================================

class Model:
    """A population model: groups weighted by size and described by IPD distributions.

    Combines a demographic population model with per-group IPD distributions and
    pre-computes the coverage map for all candidate frame specs in the given ranges.
    """

    __slots__ = ('tolerance', 'groups', 'ipd_groups', 'coverage')

    def __init__(
        self,
        pop: PopulationModel,
        ipd_model: IPDModel,
        tolerance: float,
        candidates: tuple[FrameSpec, ...],
    ) -> None:
        ipd_groups: dict[Category, Normal] = dict(ipd_model.groups)
        groups: dict[Category, int] = {
            cat: sum(
                population
                for cat2, population in pop.groups.items()
                if cat.matches(cat2)
            )
            for cat in ipd_groups
        }
        object.__setattr__(self, 'tolerance', tolerance)
        object.__setattr__(self, 'ipd_groups', ipd_groups)
        object.__setattr__(self, 'groups', groups)
        object.__setattr__(self, 'coverage', _build_coverage(candidates, ipd_groups, tolerance))

    def __setattr__(self, name: str, value: object) -> None:
        raise AttributeError("Model is immutable")

    def __delattr__(self, name: str) -> None:
        raise AttributeError("Model is immutable")


def pop_of(groups: dict[Category, int], coverage: dict[Category, float]) -> float:
    return sum(groups[cat] * fraction for cat, fraction in coverage.items())


def exact_coverage(specs: list[FrameSpec], model: Model) -> dict[Category, float]:
    """Exact union-coverage fraction for each group given a set of FrameSpecs."""
    frame_pds = [spec.lens + spec.bridge for spec in specs]
    return {
        cat: union_coverage_group(frame_pds, dist, model.tolerance)
        for cat, dist in model.ipd_groups.items()
    }


def pop_covered_by_set(specs: list[FrameSpec], model: Model) -> float:
    """Total population covered by a set of FrameSpecs (exact interval-union)."""
    return pop_of(model.groups, exact_coverage(specs, model))


def total_modelled(groups: dict[Category, int]) -> int:
    return sum(groups.values())


# ============================================================================
# OPTIMISATION PROBLEM
# ============================================================================

@dataclasses.dataclass(frozen=True)
class SearchSpace:
    """The space of valid k-frame solutions: how many to pick and from which candidates."""
    n_sizes: int
    candidates: tuple[FrameSpec, ...]


def objective(frames: list[FrameSpec], model: Model) -> float:
    """Objective function: total weighted population covered by the frame set.

    A person in group i with IPD ~ Normal(μᵢ, σᵢ) is covered when at least
    one frame s ∈ S satisfies |IPDᵢ − pd(s)| ≤ X, where pd(s) = s.lens + s.bridge.

        f(S) = Σᵢ popᵢ · P(∃ s ∈ S : |IPDᵢ − pd(s)| ≤ X)
    """
    return pop_covered_by_set(frames, model)


def to_voronoi_intervals(frame_pds: list[FrameSpec]) -> list[tuple[float, float, float]]:
    voronoi_intervals = []
    sorted_pds = sorted(frame_pds)
    for i, pd in enumerate(sorted_pds):
        left_bound = float('-inf') if i == 0 else (sorted_pds[i-1] + pd) / 2
        right_bound = float('inf') if i == len(sorted_pds) - 1 else (pd + sorted_pds[i+1]) / 2
        voronoi_intervals.append((pd, left_bound, right_bound))
    return voronoi_intervals


def fit_error(frames: list[FrameSpec], model: Model, group_cats: list[str]) -> float:
    """Total population-weighted fit error for the selected frame set.

    The fit error is computed as the sum of each group's population multiplied
    by the distance from that group's mean IPD to the nearest frame PD.
    """
    frame_pds = defaultdict(list)
    
    for spec in frames:
        frame_pds[spec.lens + spec.bridge].append(spec)

    total_pop = sum(model.groups.values())

    error = 0.0
    for cat in group_cats:
        pop_size = model.groups[cat]
        dist: statistics.NormalDist = model.ipd_groups[cat]
        voronoi_intervals = to_voronoi_intervals(frame_pds.keys())
        for seed_pd, left_bound, right_bound in voronoi_intervals:
            group_error = pop_size/total_pop * absolute_mean_difference(
                dist.mean, dist.standard_deviation, (left_bound, seed_pd, right_bound)
            )
            error += group_error
        
    return error


@dataclasses.dataclass
class RankedSolution:
    coverage: float
    fit_error: float
    specs: list[FrameSpec]


def solve(
    space: SearchSpace,
    model: Model,
    pinned: list[FrameSpec] | None = None,
    group_filter: Callable[[Category], bool] | None = None,
) -> list[RankedSolution]:
    """Rank the top_n frame sets by exhaustive enumeration of f(S).

    Parameters
    ----------
    space        : defines n_sizes and the candidate set.
    model        : population and IPD data.
    pinned       : fixed background frames excluded from the returned solution.
    group_filter : if given, restrict candidates to specs that cover at least one
                   category where group_filter(category) is True.
    top_n        : number of top-ranked solutions to return.

    Returns top_n RankedSolutions sorted by coverage descending and fit error
    ascending; each solution's specs are sorted by frame_pd ascending.
    """
    pinned = pinned or []
    candidates = list(space.candidates)
    logger.info("Number of candidates before filtering: %d", len(candidates))
    if group_filter is not None:
        candidates = [
            spec for spec in candidates
            if any(group_filter(cat) for cat in model.coverage.get(spec, {}))
        ]
    group_cats = [
        cat for cat in model.groups
        if group_filter is None or group_filter(cat)
    ]
    pinned_frame_pds = [spec.lens + spec.bridge for spec in pinned]
    results: list[RankedSolution] = []
    for combo in itertools.combinations(candidates, space.n_sizes):
        frame_pds = [spec.lens + spec.bridge for spec in combo] + pinned_frame_pds
        coverage = sum(
            model.groups[cat] * union_coverage_group(frame_pds, model.ipd_groups[cat], model.tolerance)
            for cat in group_cats
        )
        error = fit_error(list(combo) + pinned, model, group_cats)
        results.append(RankedSolution(
            coverage=coverage,
            fit_error=error,
            specs=sorted(combo, key=lambda frame: frame.lens + frame.bridge),
        ))
    return results
