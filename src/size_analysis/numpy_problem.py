"""SciPy MILP formulation of the multi-objective frame sizing problem.

The solver uses a grid maximum-coverage decision vector:

    q = [x_0 ... x_C-1, u_0 ... u_B-1]

where x_c selects candidate frame category c and u_b marks IPD grid cell b as
covered by at least one selected frame.

Frame candidate search bounds are fixed from external frame-size evidence,
not derived from IPD alone:

* lens width: 38-62 mm
* bridge width: 10-24 mm
* lens/bridge ratio: 2.5-3.0


Evidence:

* lens width: 40-60 mm
* bridge width: 14-24 mm
* lens/bridge ratio: 2.5-2.9


* All About Vision reports most eyeglass frame lens widths as 40-60 mm and
  bridge widths as 14-24 mm:
  https://www.allaboutvision.com/eyewear/eyeglasses/styles/glasses-frame-size/
* Dresden Vision's published XS-L frame table has lens/bridge ratios from about
  2.49 to 2.89:
  https://dresden.vision/our-glasses/frame-sizes
* Speksy lists small/medium/large frame ranges spanning lens widths 40-60 mm
  and bridge widths 14-24 mm:
  https://www.speksy.com/blog/how-to-check-glasses-size/
* Ophthalmic Anthropometry Versus Spectacle Frame Measurements - Is Spectacle Fit in Children Compromised?
  https://journals.lww.com/ajpr/fulltext/2022/14010/ophthalmic_anthropometry_versus_spectacle_frame.8.aspx

The wider fixed bounds keep plausible edge candidates in the search while the
ratio filter rejects geometrically odd lens/bridge splits. IPD data can only
constrain lens + bridge, not the lens/bridge split.
"""

import dataclasses
import json
import math
import statistics
from pathlib import Path
from typing import Any

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp

from size_analysis.categories import Category, Sex
from size_analysis.constraint import SizeConstraint
from size_analysis.frame_model import FrameSpec
from size_analysis.ipd_model import IPDModel
from size_analysis.population_model import PopulationModel

STANDARD_AGE_BRACKETS: tuple[tuple[int, int], ...] = (
    (5, 7),
    (8, 10),
    (11, 13),
    (14, 17),
    (18, 99),
)


def build_problem(
    combined_model: dict[str, Any],
    candidates: tuple[FrameSpec, ...],
    tolerance: float,
    grid_step: float = 0.25,
) -> dict[str, Any]:
    """Build the NumPy arrays needed by the SciPy maximum-coverage MILP.

    Parameters
    ----------
    combined_model
        Output of build_gaussian_population_model. It contains EU population
        already grouped into explicit age ranges, plus each range's Gaussian
        IPD parameters.
    candidates
        Candidate manufacturable frame categories. Each candidate contributes one
        binary x variable.
    tolerance
        Maximum allowed absolute distance, in millimeters, between group IPD
        and frame PD for a person to be covered.
    grid_step
        IPD grid spacing, in millimeters, used by the SciPy MILP optimizer to
        approximate continuous Gaussian maximum coverage.

    Returns
    -------
    dict[str, Any]
        A dictionary containing metadata plus NumPy arrays. Important shapes:
        population is (G,); gaussian_ipd is (G, 2); frame_pd is (C,);
        ipd_grid and ipd_grid_weight are (B,); grid_coverage_matrix is (B, C).
    """
    categories = combined_model["categories"]
    population = combined_model["population"]
    gaussian_ipd = combined_model["gaussian_ipd"]
    mean_ipd = gaussian_ipd[:, 0]
    standard_deviation_ipd = gaussian_ipd[:, 1]

    # frame_pd is a NumPy array with one entry per candidate frame category.
    frame_pd = np.array([candidate.pd for candidate in candidates], dtype=float)

    # ipd_grid and ipd_grid_weight are NumPy arrays with one entry per grid cell.
    # ipd_grid contains the center value of each cell. 
    # ipd_grid_weight contains the population-weighted probability mass of each cell, normalized by total population.
    ipd_grid, ipd_grid_weight = _build_ipd_grid(
        mean_ipd=mean_ipd,
        standard_deviation_ipd=standard_deviation_ipd,
        population=population,
        tolerance=tolerance,
        grid_step=grid_step,
    )
    grid_coverage_matrix = (
        np.abs(ipd_grid[:, np.newaxis] - frame_pd[np.newaxis, :]) <= tolerance
    ).astype(float)
    n_groups = len(categories)
    n_candidates = len(candidates)
    n_grid = len(ipd_grid)

    assert population.shape == (n_groups,)
    assert mean_ipd.shape == (n_groups,)
    assert standard_deviation_ipd.shape == (n_groups,)
    assert frame_pd.shape == (n_candidates,)
    assert ipd_grid.shape == (n_grid,)
    assert ipd_grid_weight.shape == (n_grid,)
    assert grid_coverage_matrix.shape == (n_grid, n_candidates)

    return {
        "categories": categories,
        "candidates": candidates,
        "tolerance": tolerance,
        "grid_step": grid_step,
        "n_groups": n_groups,
        "n_candidates": n_candidates,
        "population": population,
        "gaussian_ipd": gaussian_ipd,
        "frame_pd": frame_pd,
        "ipd_grid": ipd_grid,
        "ipd_grid_weight": ipd_grid_weight,
        "grid_coverage_matrix": grid_coverage_matrix,
        "variable_layout": "q = [x_0..x_C-1, u_0..u_B-1]",
    }


def pareto_sweep(
    problem: dict[str, Any],
    min_k: int = 1,
    max_k: int | None = None,
    top_n_per_k: int = 1,
    excluded_candidates: tuple[FrameSpec, ...] = (),
    retained_candidates: tuple[FrameSpec, ...] = (),
) -> list[dict[str, Any]]:
    """Solve the practical Pareto sweep with SciPy MILP over category count.

    Parameters
    ----------
    problem
        Dictionary returned by build_problem.
    min_k
        Smallest number of frame categories to select.
    max_k
        Largest number of frame categories to select. Defaults to all
        candidates.
    top_n_per_k
        Number of best solutions to keep for each k. Additional solutions are
        found by adding exclusion constraints for already returned selections.
    excluded_candidates
        Existing frame specs to remove from the generation/search space.
    retained_candidates
        Existing frame specs to keep in the final evaluation metrics. This lets
        a previous spec remain the best fit for a group without allowing the
        optimizer to select it again as a new candidate.

    Returns
    -------
    list[dict[str, Any]]
        Evaluation dictionaries returned by evaluate_selection, sorted after
        the full search by descending coverage, then lower excess deviation,
        lower mean deviation, and lower k.

    Notes
    -----
    For each allowed number of selected frame categories k, this finds the
    selected candidate vector x that maximizes weighted Gaussian coverage.
    Ties are ordered by lower weighted excess deviation beyond tolerance.

    The MILP objective maximizes weighted coverage on the IPD grid stored in
    problem["ipd_grid"]. The returned metrics are then recomputed with
    evaluate_selection, which reports exact interval-union Gaussian coverage
    for the selected frame PDs.
    """
    n_candidates = problem["n_candidates"]
    excluded_candidate_indices = _candidate_indices(problem, excluded_candidates)
    retained_candidate_indices = _candidate_indices(problem, retained_candidates)
    n_available_candidates = n_candidates - len(excluded_candidate_indices)
    if max_k is None:
        max_k = n_available_candidates
    if min_k < 0 or max_k > n_available_candidates or min_k > max_k:
        raise ValueError("expected 0 <= min_k <= max_k <= available candidates")

    results: list[dict[str, Any]] = []
    for k in range(min_k, max_k + 1):
        excluded: list[np.ndarray] = []
        seen_pd_sets: set[tuple[float, ...]] = set()
        attempts = 0
        max_attempts = top_n_per_k * n_candidates
        while len(seen_pd_sets) < top_n_per_k and attempts < max_attempts:
            attempts += 1
            result = _solve_milp_for_k(
                problem=problem,
                k=k,
                excluded_selections=excluded,
                excluded_candidate_indices=excluded_candidate_indices,
                retained_candidate_indices=retained_candidate_indices,
                bounds_class=Bounds,
                linear_constraint_class=LinearConstraint,
                milp_function=milp,
            )
            if result is None:
                break
            excluded.append(result["x"])
            pd_set = tuple(sorted(result["selected_frame_pd"]))
            if pd_set not in seen_pd_sets:
                seen_pd_sets.add(pd_set)
                results.append(result)
    results.sort(key=_result_sort_key)
    return results


def optimize(
    problem: dict[str, Any],
    min_k: int = 1,
    max_k: int | None = None,
    top_n_per_k: int = 1,
    excluded_candidates: tuple[FrameSpec, ...] = (),
    retained_candidates: tuple[FrameSpec, ...] = (),
) -> list[dict[str, Any]]:
    """Optimize the frame category problem with SciPy MILP over a Pareto k sweep.

    Parameters
    ----------
    problem
        Dictionary returned by build_problem.
    min_k
        Smallest number of frame categories to select.
    max_k
        Largest number of frame categories to select. Defaults to all
        candidates.
    top_n_per_k
        Number of best solutions to keep for each k.
    excluded_candidates
        Existing frame specs to exclude from the next generated optimization
        set.
    retained_candidates
        Existing frame specs to keep for post-generation evaluation.

    Returns
    -------
    list[dict[str, Any]]
        Pareto-sweep results. Each row contains k, coverage,
        coverage_rate, weighted_mean_deviation, selected candidates, and
        per-group diagnostic arrays.

    Notes
    -----
    This is the main user-facing optimization entry point. It preserves the
    multi-objective structure by solving one binary MILP for each allowed
    category count k, then reporting the coverage and tolerance tradeoff for each k.
    """
    return pareto_sweep(
        problem=problem,
        min_k=min_k,
        max_k=max_k,
        top_n_per_k=top_n_per_k,
        excluded_candidates=excluded_candidates,
        retained_candidates=retained_candidates,
    )


def build_gaussian_population_model(
    population_model: PopulationModel,
    ipd_model: IPDModel,
    region: str = "EU",
) -> dict[str, Any]:
    """Convert EU population rows into age-range rows with Gaussian IPD.

    Parameters
    ----------
    population_model
        EU population model keyed by exact integer ages and sex.
    ipd_model
        IPD model keyed by age bands or symbolic groups.

    Returns
    -------
    dict[str, Any]
        Plain dictionary with one row per IPD category. categories are
        normalized to explicit inclusive age ranges. population contains the
        summed EU population for that row. gaussian_ipd has shape (G, 2), with
        column 0 = mean IPD and column 1 = IPD standard deviation.
    """
    source_categories = tuple(ipd_model.groups)
    categories = tuple(
        dataclasses.replace(_category_as_standard_age_range(category, population_model), region=region)
        for category in source_categories
    )
    population = np.array([
        sum(
            count
            for population_category, count in population_model.groups.items()
            if _category_matches_population_age(category, population_category)
        )
        for category in categories
    ], dtype=float)
    gaussian_ipd = np.array([
        (
            ipd_model.groups[category].mean,
            ipd_model.groups[category].standard_deviation,
        )
        for category in source_categories
    ], dtype=float)

    n_groups = len(categories)
    assert population.shape == (n_groups,)
    assert gaussian_ipd.shape == (n_groups, 2)

    return {
        "categories": categories,
        "population": population,
        "gaussian_ipd": gaussian_ipd,
    }


def build_gaussian_population_model_from_records(records_path: str | Path) -> dict[str, Any]:
    """Build Gaussian IPD groups from normalized JSON records.

    Individual IPD records are preferred: each region/sex/age-band group is
    fitted directly from the sample values. Population records are used as
    weights only when they match the same region/sex/age group; otherwise the
    sample count is used as the group population.
    """
    records = json.loads(Path(records_path).read_text(encoding="utf-8"))
    population_by_group: dict[tuple[str, str, tuple[int | None, int | None]], float] = {}
    samples_by_group: dict[tuple[str, str, tuple[int, int]], list[float]] = {}

    for record in records:
        region = region_for_record(record)
        sex = record.get("sex") or "T"
        age_range = tuple(record["age"]["range"])
        standard_age_range = standard_age_bracket(age_range)
        if record["kind"] == "population":
            if standard_age_range is None:
                continue
            population_by_group[(region, sex, standard_age_range)] = population_by_group.get((region, sex, standard_age_range), 0.0) + float(record["count"])
        elif record["kind"] == "ipd_sample":
            if standard_age_range is None:
                continue
            samples_by_group.setdefault((region, sex, standard_age_range), []).append(float(record["ipd"]["value"]))

    categories: list[Category] = []
    population: list[float] = []
    gaussian_ipd: list[tuple[float, float]] = []
    for (region, sex, age_range), values in sorted(samples_by_group.items()):
        if len(values) < 2:
            continue
        category = Category(region=region, sex=sex_from_code(sex), age=age_range)
        categories.append(category)
        gaussian_ipd.append((statistics.fmean(values), statistics.stdev(values)))
        population.append(population_for_sample_group(population_by_group, region, sex, age_range, len(values)))

    return {
        "categories": tuple(categories),
        "population": np.array(population, dtype=float),
        "gaussian_ipd": np.array(gaussian_ipd, dtype=float),
    }


def combine_gaussian_population_models(*models: dict[str, Any]) -> dict[str, Any]:
    """Concatenate compatible Gaussian population-model dictionaries."""
    usable = [model for model in models if len(model["categories"]) > 0]
    if not usable:
        return {
            "categories": tuple(),
            "population": np.array([], dtype=float),
            "gaussian_ipd": np.empty((0, 2), dtype=float),
        }
    return {
        "categories": tuple(category for model in usable for category in model["categories"]),
        "population": np.concatenate([model["population"] for model in usable]),
        "gaussian_ipd": np.vstack([model["gaussian_ipd"] for model in usable]),
    }


def region_for_record(record: dict[str, Any]) -> str:
    source = record.get("source", "")
    if source.startswith("eurostat"):
        return "EU"
    if source.startswith("taiwan"):
        return "TW"
    if source.startswith("ansur"):
        return "US"
    return str(record.get("region") or "UNK")


def sex_from_code(code: str) -> Sex | None:
    if code == "F":
        return Sex.FEMALE
    if code == "M":
        return Sex.MALE
    return Sex.OTHER


def standard_age_bracket(age_range: tuple[int | None, int | None]) -> tuple[int, int] | None:
    lower, upper = age_range
    if lower is None:
        return None
    if upper is None and lower >= 18:
        return (18, 99)
    upper_value = lower if upper is None else upper
    midpoint = (int(lower) + int(upper_value)) / 2.0
    for bracket in STANDARD_AGE_BRACKETS:
        if bracket[0] <= midpoint <= bracket[1]:
            return bracket
    return None


def population_for_sample_group(
    population_by_group: dict[tuple[str, str, tuple[int | None, int | None]], float],
    region: str,
    sex: str,
    age_range: tuple[int, int],
    sample_count: int,
) -> float:
    exact = population_by_group.get((region, sex, age_range))
    if exact is not None:
        return exact
    matching_population = [
        population
        for (pop_region, pop_sex, pop_age_range), population in population_by_group.items()
        if pop_region == region
        and pop_sex == sex
        and pop_age_range[0] is not None
        and pop_age_range[1] is not None
        and age_range[0] <= int(pop_age_range[0]) <= age_range[1]
        and age_range[0] <= int(pop_age_range[1]) <= age_range[1]
    ]
    if matching_population:
        return float(sum(matching_population))
    return float(sample_count)


def derive_search_parameters(
    gaussian_population_model: dict[str, Any],
    standard_deviation_span: float = 2.0,
    bridge_ratio_range: tuple[float, float] = (2.5, 3.0),
) -> SizeConstraint:
    """Derive SizeConstraint search bounds from the Gaussian IPD population.

    The population model can determine the target frame-PD span because
    ``frame_pd = lens + bridge`` is compared directly to IPD. The lens/bridge
    split is not identifiable from IPD data alone, so ``bridge_ratio_range`` is
    still an explicit design assumption.

    Parameters
    ----------
    gaussian_population_model
        Output of build_gaussian_population_model. It must contain
        ``gaussian_ipd`` with columns ``[mean_ipd, standard_deviation_ipd]``.
    standard_deviation_span
        Number of standard deviations around each group's mean to include. The
        default 2.0 derives bounds from the union of ``mean ± 2*std``.
    bridge_ratio_range
        Allowed ``lens / bridge`` ratio range. This converts the derived PD span
        into lens and bridge ranges.

    Returns
    -------
    SizeConstraint
        Integer lens, bridge, and ratio bounds for candidate generation.
    """
    if standard_deviation_span <= 0:
        raise ValueError("standard_deviation_span must be positive")
    if bridge_ratio_range[0] <= 0 or bridge_ratio_range[1] <= bridge_ratio_range[0]:
        raise ValueError("bridge_ratio_range must be positive and increasing")

    gaussian_ipd = gaussian_population_model["gaussian_ipd"]
    mean_ipd = gaussian_ipd[:, 0]
    standard_deviation_ipd = gaussian_ipd[:, 1]
    min_pd = math.floor(np.min(mean_ipd - standard_deviation_span * standard_deviation_ipd))
    max_pd = math.ceil(np.max(mean_ipd + standard_deviation_span * standard_deviation_ipd))

    min_ratio, max_ratio = bridge_ratio_range
    lens_min = math.floor(min_pd * min_ratio / (min_ratio + 1.0))
    lens_max = math.ceil(max_pd * max_ratio / (max_ratio + 1.0))
    bridge_min = math.floor(min_pd / (max_ratio + 1.0))
    bridge_max = math.ceil(max_pd / (min_ratio + 1.0))

    return SizeConstraint(
        lens_range=(lens_min, lens_max),
        bridge_range=(bridge_min, bridge_max),
        bridge_ratio_range=bridge_ratio_range,
    )


def evaluate_selection(
    problem: dict[str, Any],
    x: np.ndarray,
    retained_candidate_indices: tuple[int, ...] = (),
) -> dict[str, Any]:
    """Evaluate one binary frame-selection vector without assignment variables.

    Parameters
    ----------
    problem
        Dictionary returned by build_problem.
    x
        Binary candidate-selection vector with shape (C,). x[c] = 1 means
        candidate c is manufactured.
    retained_candidate_indices
        Candidate indices for previous specs that should remain available for
        final evaluation even if they were excluded from generation.

    Returns
    -------
    dict[str, Any]
        Summary metrics and per-group arrays:
        k, coverage, coverage_rate, weighted_mean_deviation,
        selected_indices, selected_candidates, selected_frame_pd, retained_*,
        evaluation_*, x, group_coverage, group_mean_deviation,
        group_excess_deviation, and group_best_matches.

    Notes
    -----
    Coverage is exact for the Gaussian population model: the selected frame PDs
    are converted into tolerance intervals, overlapping intervals are merged,
    and each group's Normal distribution is integrated over the union.
    """
    x = np.asarray(x, dtype=int)
    if x.shape != (problem["n_candidates"],):
        raise ValueError("x must have shape (n_candidates,)")

    selected_indices = np.flatnonzero(x)
    selected_frame_pd = problem["frame_pd"][selected_indices]
    selected_index_set = set(int(idx) for idx in selected_indices)
    retained_indices = tuple(
        idx for idx in retained_candidate_indices
        if idx not in selected_index_set
    )
    evaluation_indices = tuple(int(idx) for idx in selected_indices) + retained_indices
    evaluation_frame_pd = problem["frame_pd"][list(evaluation_indices)]
    population = problem["population"]
    total_population = population.sum()
    if total_population <= 0:
        raise ValueError("problem must contain at least one modelled person")

    group_coverage = _union_coverage_by_group(
        selected_frame_pd=evaluation_frame_pd,
        mean_ipd=problem["gaussian_ipd"][:, 0],
        standard_deviation_ipd=problem["gaussian_ipd"][:, 1],
        tolerance=problem["tolerance"],
    )
    weighted_coverage = float(population @ group_coverage)
    coverage_rate = weighted_coverage / float(total_population)

    group_mean_deviation = _nearest_mean_deviation(
        selected_frame_pd=evaluation_frame_pd,
        mean_ipd=problem["gaussian_ipd"][:, 0],
    )
    weighted_mean_deviation = float((population @ group_mean_deviation) / total_population)
    group_excess_deviation = _tolerance_excess_deviation(
        selected_frame_pd=evaluation_frame_pd,
        mean_ipd=problem["gaussian_ipd"][:, 0],
        tolerance=problem["tolerance"],
    )
    weighted_excess_deviation = float((population @ group_excess_deviation) / total_population)
    group_best_matches = _group_best_matches(
        problem=problem,
        evaluation_indices=evaluation_indices,
        evaluation_frame_pd=evaluation_frame_pd,
        retained_indices=set(retained_indices),
    )

    return {
        "k": int(x.sum()),
        "coverage": weighted_coverage,
        "coverage_rate": coverage_rate,
        "weighted_mean_deviation": weighted_mean_deviation,
        "weighted_excess_deviation": weighted_excess_deviation,
        "selected_indices": tuple(int(idx) for idx in selected_indices),
        "selected_candidates": tuple(problem["candidates"][idx] for idx in selected_indices),
        "selected_frame_pd": tuple(float(pd) for pd in selected_frame_pd),
        "retained_indices": retained_indices,
        "retained_candidates": tuple(problem["candidates"][idx] for idx in retained_indices),
        "retained_frame_pd": tuple(float(problem["frame_pd"][idx]) for idx in retained_indices),
        "evaluation_indices": evaluation_indices,
        "evaluation_candidates": tuple(problem["candidates"][idx] for idx in evaluation_indices),
        "evaluation_frame_pd": tuple(float(problem["frame_pd"][idx]) for idx in evaluation_indices),
        "x": x,
        "group_coverage": group_coverage,
        "group_mean_deviation": group_mean_deviation,
        "group_excess_deviation": group_excess_deviation,
        "group_best_matches": group_best_matches,
    }


def _solve_milp_for_k(
    problem: dict[str, Any],
    k: int,
    excluded_selections: list[np.ndarray],
    excluded_candidate_indices: tuple[int, ...],
    retained_candidate_indices: tuple[int, ...],
    bounds_class: Any,
    linear_constraint_class: Any,
    milp_function: Any,
) -> dict[str, Any] | None:
    """Solve one fixed-k grid maximum-coverage binary MILP with SciPy.

    Parameters
    ----------
    problem
        Dictionary returned by build_problem.
    k
        Exact number of frame categories to select.
    excluded_selections
        Previously returned x vectors for this k. Each is excluded from the
        feasible region so repeated solves can produce top_n_per_k alternatives.
    excluded_candidate_indices
        Candidate x indices that must be fixed to 0 during generation.
    retained_candidate_indices
        Candidate indices to include in final evaluation metrics.
    bounds_class
        scipy.optimize.Bounds, injected to keep the SciPy import localized.
    linear_constraint_class
        scipy.optimize.LinearConstraint, injected to keep the SciPy import
        localized.
    milp_function
        scipy.optimize.milp, injected to keep the SciPy import localized.

    Returns
    -------
    dict[str, Any] | None
        Evaluation dictionary for the selected x vector, or None if SciPy
        reports no feasible or optimal solution.
    """
    n_candidates = problem["n_candidates"]
    objective = _milp_objective(problem)
    constraint_matrix, lower_bound, upper_bound = _milp_constraints_for_k(
        problem=problem,
        k=k,
        excluded_selections=excluded_selections,
    )

    lower_bounds = np.zeros(len(objective))
    upper_bounds = np.ones(len(objective))
    upper_bounds[list(excluded_candidate_indices)] = 0.0

    result = milp_function(
        c=objective,
        integrality=np.ones(len(objective), dtype=int),
        bounds=bounds_class(lower_bounds, upper_bounds),
        constraints=linear_constraint_class(constraint_matrix, lower_bound, upper_bound),
    )
    if not result.success or result.x is None:
        return None

    q = np.rint(result.x).astype(int)
    x = q[:n_candidates]
    evaluated = evaluate_selection(problem, x, retained_candidate_indices=retained_candidate_indices)
    evaluated["solver"] = "scipy.optimize.milp"
    evaluated["solver_success"] = bool(result.success)
    evaluated["solver_message"] = result.message
    evaluated["solver_objective"] = float(result.fun)
    evaluated["q"] = q
    evaluated["grid_coverage_rate"] = float(problem["ipd_grid_weight"] @ q[n_candidates:])
    return evaluated


def _milp_objective(problem: dict[str, Any]) -> np.ndarray:
    """Build the scalar SciPy MILP objective for grid maximum coverage.

    Parameters
    ----------
    problem
        Dictionary returned by build_problem.

    Returns
    -------
    np.ndarray
        Cost vector with shape (C + B,), where B is the number of IPD grid
        points. SciPy minimizes this vector dotted with q = [x, u]. The u terms
        maximize weighted covered population mass. A tiny x cost discourages
        arbitrary duplicate-PD choices when coverage is tied.
    """
    n_candidates = problem["n_candidates"]
    grid_weight = problem["ipd_grid_weight"]
    objective = np.zeros(n_candidates + len(grid_weight), dtype=float)
    objective[:n_candidates] = 1e-12
    objective[n_candidates:] = -grid_weight
    return objective


def _candidate_indices(problem: dict[str, Any], candidates: tuple[FrameSpec, ...]) -> tuple[int, ...]:
    """Return stable problem indices for candidate specs.

    The lookup is by exact FrameSpec, not by frame PD, so a previous 45-15 spec
    does not automatically exclude a different 50-10 spec with the same PD.
    """
    candidate_to_index = {
        candidate: index
        for index, candidate in enumerate(problem["candidates"])
    }
    missing = [candidate for candidate in candidates if candidate not in candidate_to_index]
    if missing:
        missing_str = ", ".join(str(candidate) for candidate in missing)
        raise ValueError(f"candidate(s) not present in problem: {missing_str}")
    return tuple(candidate_to_index[candidate] for candidate in candidates)


def _result_sort_key(row: dict[str, Any]) -> tuple[float, float, float, int, tuple[float, ...]]:
    """Sort completed optimizer rows with best overall result first."""
    return (
        -float(row["coverage_rate"]),
        float(row["weighted_excess_deviation"]),
        float(row["weighted_mean_deviation"]),
        int(row["k"]),
        tuple(float(pd) for pd in row["selected_frame_pd"]),
    )


def _milp_constraints_for_k(
    problem: dict[str, Any],
    k: int,
    excluded_selections: list[np.ndarray],
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Build SciPy lower/upper bounded grid-coverage constraints for fixed k.

    Parameters
    ----------
    problem
        Dictionary returned by build_problem.
    k
        Exact number of frame categories to select.
    excluded_selections
        Previously returned x vectors to exclude.

    Returns
    -------
    tuple[np.ndarray, np.ndarray, np.ndarray]
        constraint_matrix, lower_bound, and upper_bound suitable for
        scipy.optimize.LinearConstraint. The q vector is [x, u], where u[b] is
        1 when IPD grid point b is covered. Rows encode
        u_b <= sum_c grid_coverage_matrix[b, c] * x_c, sum(x) = k, and optional
        exclusion constraints for previous x selections.
    """
    n_candidates = problem["n_candidates"]
    n_grid = len(problem["ipd_grid"])
    n_variables = n_candidates + n_grid

    coverage_constraints = np.zeros((n_grid, n_variables), dtype=float)
    coverage_constraints[:, :n_candidates] = -problem["grid_coverage_matrix"]
    coverage_constraints[:, n_candidates:] = np.eye(n_grid)
    rows = [coverage_constraints]
    lower_bounds = [np.full(n_grid, -np.inf)]
    upper_bounds = [np.zeros(n_grid)]

    k_row = np.zeros((1, n_variables), dtype=float)
    k_row[0, :n_candidates] = 1.0
    rows.append(k_row)
    lower_bounds.append(np.array([float(k)]))
    upper_bounds.append(np.array([float(k)]))

    for x in excluded_selections:
        rows.append(_exclude_selection_row(x, n_variables))
        lower_bounds.append(np.array([1.0 - float(x.sum())]))
        upper_bounds.append(np.array([np.inf]))

    return (
        np.vstack(rows),
        np.concatenate(lower_bounds),
        np.concatenate(upper_bounds),
    )


def _exclude_selection_row(x: np.ndarray, n_variables: int) -> np.ndarray:
    """Build one linear row that excludes an already returned x selection.

    Parameters
    ----------
    x
        Binary selected-candidate vector with shape (C,).
    n_variables
        Total length of the full z vector.

    Returns
    -------
    np.ndarray
        Row with shape (1, n_variables). With lower bound 1 - sum(x), it
        enforces sum_unselected x_i - sum_selected x_i >= 1 - sum(selected),
        which means the next solution must differ in at least one x bit.
    """
    row = np.zeros((1, n_variables), dtype=float)
    row[0, :len(x)] = np.where(x == 1, -1.0, 1.0)
    return row


def _build_ipd_grid(
    mean_ipd: np.ndarray,
    standard_deviation_ipd: np.ndarray,
    population: np.ndarray,
    tolerance: float,
    grid_step: float,
) -> tuple[np.ndarray, np.ndarray]:
    """Build a weighted IPD grid for the SciPy maximum-coverage MILP.

    Parameters
    ----------
    mean_ipd
        Group mean IPD values with shape (G,).
    standard_deviation_ipd
        Group IPD standard deviations with shape (G,).
    population
        Group population counts with shape (G,).
    tolerance
        Fitting tolerance in millimeters. The grid range is padded by this
        value so edge frame candidates can still cover tail mass.
    grid_step
        Grid spacing in millimeters.

    Returns
    -------
    tuple[np.ndarray, np.ndarray]
        ipd_grid has shape (B,) and contains grid cell centers. ipd_grid_weight
        has shape (B,) and contains the population-weighted probability mass in
        each grid cell, normalized by total population.
    """
    if grid_step <= 0:
        raise ValueError("grid_step must be positive")
    total_population = population.sum()
    if total_population <= 0:
        raise ValueError("population_model must contain at least one modelled person")

    lower = float(np.min(mean_ipd - 5.0 * standard_deviation_ipd - tolerance))
    upper = float(np.max(mean_ipd + 5.0 * standard_deviation_ipd + tolerance))
    edges = np.arange(lower, upper + grid_step, grid_step)
    if len(edges) < 2:
        edges = np.array([lower, lower + grid_step])
    grid = (edges[:-1] + edges[1:]) / 2.0

    group_weights = population / total_population
    cell_probability_by_group = _normal_interval_probability(
        mean=mean_ipd[:, np.newaxis],
        standard_deviation=standard_deviation_ipd[:, np.newaxis],
        lower=edges[:-1][np.newaxis, :],
        upper=edges[1:][np.newaxis, :],
    )
    grid_weight = group_weights @ cell_probability_by_group
    return grid, grid_weight


def _category_as_standard_age_range(category: Category, population_model: PopulationModel) -> Category:
    """Convert a category to one of the standard inclusive age brackets.

    Parameters
    ----------
    category
        Source category from the IPD model. It may use a single age, an existing
        age range, or a symbolic AgeGroup such as ADULT.
    population_model
        EU population model containing concrete integer ages. Its available age
        range is used to expand symbolic groups.

    Returns
    -------
    Category
        Equivalent category with age represented as an inclusive
        ``(lower_age, upper_age)`` tuple when age is known.
    """
    if category.age is None:
        return category
    if isinstance(category.age, tuple):
        bracket = standard_age_bracket(category.age)
        if bracket is None:
            raise ValueError(f"no standard age bracket matches {category}")
        return dataclasses.replace(category, age=bracket)
    if isinstance(category.age, int):
        bracket = standard_age_bracket((category.age, category.age))
        if bracket is None:
            raise ValueError(f"no standard age bracket matches {category}")
        return Category(region=category.region, sex=category.sex, age=bracket)

    ages = sorted(
        pop_category.age
        for pop_category in population_model.groups
        if isinstance(pop_category.age, int) and category.matches(pop_category)
    )
    if not ages:
        raise ValueError(f"no EU population ages match {category}")
    bracket = standard_age_bracket((ages[0], ages[-1]))
    if bracket is None:
        raise ValueError(f"no standard age bracket matches {category}")
    return Category(region=category.region, sex=category.sex, age=bracket)


def _category_matches_population_age(category: Category, population_category: Category) -> bool:
    if category.sex is not None and population_category.sex != category.sex:
        return False
    if not isinstance(category.age, tuple) or not isinstance(population_category.age, int):
        return category.matches(population_category)
    return category.age[0] <= population_category.age <= category.age[1]


def _normal_interval_probability(
    mean: np.ndarray,
    standard_deviation: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
) -> np.ndarray:
    """Compute Normal probabilities over [lower, upper] with broadcasting.

    Parameters
    ----------
    mean
        Mean values of the Normal distributions.
    standard_deviation
        Standard deviations of the Normal distributions.
    lower
        Lower integration bound.
    upper
        Upper integration bound.

    Returns
    -------
    np.ndarray
        Broadcasted probability mass CDF(upper) - CDF(lower).
    """
    return _normal_cdf(upper, mean, standard_deviation) - _normal_cdf(lower, mean, standard_deviation)


def _normal_cdf(x: np.ndarray, mean: np.ndarray, standard_deviation: np.ndarray) -> np.ndarray:
    """Evaluate the Normal cumulative distribution function.

    Parameters
    ----------
    x
        Values at which to evaluate the CDF.
    mean
        Mean values of the Normal distributions.
    standard_deviation
        Standard deviations of the Normal distributions.

    Returns
    -------
    np.ndarray
        Broadcasted CDF values.
    """
    z = (x - mean) / (standard_deviation * np.sqrt(2.0))
    return 0.5 * (1.0 + np.vectorize(math.erf, otypes=[float])(z))


def _union_coverage_by_group(
    selected_frame_pd: np.ndarray,
    mean_ipd: np.ndarray,
    standard_deviation_ipd: np.ndarray,
    tolerance: float,
) -> np.ndarray:
    """Compute exact per-group coverage for a selected set of frame PDs.

    Parameters
    ----------
    selected_frame_pd
        Selected frame PD values with shape (K,).
    mean_ipd
        Group mean IPD values with shape (G,).
    standard_deviation_ipd
        Group IPD standard deviations with shape (G,).
    tolerance
        Fitting tolerance in millimeters.

    Returns
    -------
    np.ndarray
        Per-group coverage fractions with shape (G,). Coverage is the
        probability that IPD lies within tolerance of at least one selected
        frame PD.
    """
    if len(selected_frame_pd) == 0:
        return np.zeros_like(mean_ipd, dtype=float)

    intervals = _merge_intervals(selected_frame_pd, tolerance)
    coverage = np.zeros_like(mean_ipd, dtype=float)
    for lower, upper in intervals:
        coverage += _normal_interval_probability(
            mean=mean_ipd,
            standard_deviation=standard_deviation_ipd,
            lower=lower,
            upper=upper,
        )
    return coverage


def _nearest_mean_deviation(
    selected_frame_pd: np.ndarray,
    mean_ipd: np.ndarray,
) -> np.ndarray:
    """Compute raw nearest-frame distance from each group mean IPD.

    Parameters
    ----------
    selected_frame_pd
        Selected frame PD values with shape (K,).
    mean_ipd
        Group mean IPD values with shape (G,).

    Returns
    -------
    np.ndarray
        Per-group non-negative distances with shape (G,).
    """
    if len(selected_frame_pd) == 0:
        return np.full_like(mean_ipd, np.inf, dtype=float)
    return np.min(np.abs(mean_ipd[:, np.newaxis] - selected_frame_pd[np.newaxis, :]), axis=1)


def _tolerance_excess_deviation(
    selected_frame_pd: np.ndarray,
    mean_ipd: np.ndarray,
    tolerance: float,
) -> np.ndarray:
    """Compute nearest-frame distance beyond tolerance for each group mean IPD.

    Parameters
    ----------
    selected_frame_pd
        Selected frame PD values with shape (K,).
    mean_ipd
        Group mean IPD values with shape (G,).
    tolerance
        Fitting tolerance in millimeters.

    Returns
    -------
    np.ndarray
        Per-group non-negative excess distances with shape (G,). A value of 0
        means the nearest selected frame PD is within tolerance of the group
        mean.
    """
    return np.maximum(_nearest_mean_deviation(selected_frame_pd, mean_ipd) - tolerance, 0.0)


def _group_best_matches(
    problem: dict[str, Any],
    evaluation_indices: tuple[int, ...],
    evaluation_frame_pd: np.ndarray,
    retained_indices: set[int],
) -> tuple[dict[str, Any], ...]:
    """Find the nearest evaluated frame for every population group."""
    mean_ipd = problem["gaussian_ipd"][:, 0]
    if len(evaluation_frame_pd) == 0:
        return tuple(
            {
                "category": category,
                "population": float(population),
                "candidate_index": None,
                "candidate": None,
                "frame_pd": None,
                "mean_deviation": math.inf,
                "excess_deviation": math.inf,
                "source": None,
            }
            for category, population in zip(problem["categories"], problem["population"])
        )

    evaluation_index_array = np.array(evaluation_indices, dtype=int)
    nearest_positions = np.argmin(
        np.abs(mean_ipd[:, np.newaxis] - evaluation_frame_pd[np.newaxis, :]),
        axis=1,
    )
    matches = []
    for group_idx, position in enumerate(nearest_positions):
        candidate_index = int(evaluation_index_array[position])
        frame_pd = float(evaluation_frame_pd[position])
        mean_deviation = abs(float(mean_ipd[group_idx]) - frame_pd)
        matches.append({
            "category": problem["categories"][group_idx],
            "population": float(problem["population"][group_idx]),
            "mean_ipd": float(mean_ipd[group_idx]),
            "candidate_index": candidate_index,
            "candidate": problem["candidates"][candidate_index],
            "frame_pd": frame_pd,
            "mean_deviation": mean_deviation,
            "excess_deviation": max(mean_deviation - float(problem["tolerance"]), 0.0),
            "source": "retained" if candidate_index in retained_indices else "selected",
        })
    return tuple(sorted(matches, key=lambda match: str(match["category"])))


def _merge_intervals(frame_pd: np.ndarray, tolerance: float) -> list[tuple[float, float]]:
    """Merge overlapping frame tolerance intervals.

    Parameters
    ----------
    frame_pd
        Frame PD values. Each value creates [pd - tolerance, pd + tolerance].
    tolerance
        Half-width of each interval.

    Returns
    -------
    list[tuple[float, float]]
        Sorted, disjoint intervals covering the same union as the input
        tolerance windows.
    """
    intervals = sorted((float(pd - tolerance), float(pd + tolerance)) for pd in frame_pd)
    merged = [intervals[0]]
    for lower, upper in intervals[1:]:
        previous_lower, previous_upper = merged[-1]
        if lower <= previous_upper:
            merged[-1] = (previous_lower, max(previous_upper, upper))
        else:
            merged.append((lower, upper))
    return merged


def _format_solution(row: dict[str, Any]) -> str:
    """Format one optimizer result as a compact console table row.

    Parameters
    ----------
    row
        Result dictionary returned by evaluate_selection and augmented by the
        SciPy solver path.

    Returns
    -------
    str
        Human-readable table row with k, exact covered population, exact
        coverage rate, weighted mean deviation, weighted excess deviation,
        selected frame specs, and selected PDs.
    """
    specs = ", ".join(str(spec) for spec in row["selected_candidates"])
    pds = ", ".join(f"{pd:g}" for pd in row["selected_frame_pd"])
    if row.get("retained_candidates"):
        retained_specs = ", ".join(str(spec) for spec in row["retained_candidates"])
        specs = f"{specs} (+prev {retained_specs})"
    return (
        f"{row['k']:>2}  "
        f"{_format_population(row['coverage']):>10}  "
        f"{100.0 * row['coverage_rate']:>8.2f}%  "
        f"{row['weighted_mean_deviation']:>8.3f} mm  "
        f"{row['weighted_excess_deviation']:>8.3f} mm  "
        f"{specs:<33}  "
        f"{pds}"
    )


def _frame_labels(row: dict[str, Any]) -> dict[int, str]:
    """Assign XS/S/M/L labels to selected frame indices in ascending PD order.

    Parameters
    ----------
    row
        Optimizer result dictionary.

    Returns
    -------
    dict[int, str]
        Mapping from candidate index to display label.
    """
    labels = ("XS", "S", "M", "L", "XL", "XXL")
    idx_to_pd = dict(zip(row["selected_indices"], (c.pd for c in row["selected_candidates"])))
    ordered = sorted(row["selected_indices"], key=lambda idx: idx_to_pd[idx])
    labels_by_index = {
        idx: labels[position] if position < len(labels) else f"Size {position + 1}"
        for position, idx in enumerate(ordered)
    }
    for idx in row.get("retained_indices", ()):
        labels_by_index[idx] = "Prev"
    return labels_by_index


def _format_population(value: float) -> str:
    return f"{value:.3e}"


def _print_group_fit_table(problem: dict[str, Any], row: dict[str, Any]) -> None:
    """Print each population group's nearest selected frame and deviation.

    Parameters
    ----------
    problem
        Dictionary returned by build_problem.
    row
        Optimizer result dictionary. The selected frames are labelled by size in
        ascending frame PD order.
    """
    labels_by_index = _frame_labels(row)

    print()
    print("Group fit for selected frame set:")
    print("group         population    mean IPD  best  frame   frame PD  mean dev  excess")
    print("------------  ------------  --------  ----  ------  --------  --------  ------")
    for match in row["group_best_matches"]:
        candidate_idx = match["candidate_index"]
        label = labels_by_index[candidate_idx] if candidate_idx is not None else "-"
        mean_ipd = match["mean_ipd"]
        frame_pd = "-" if match["frame_pd"] is None else f"{match['frame_pd']:>2.0f}"
        mean_deviation = match["mean_deviation"]
        excess_deviation = match["excess_deviation"]
        print(
            f"{str(match['category']):<12}  "
            f"{_format_population(match['population']):>12}  "
            f"{mean_ipd:>8.2f}    "
            f"{label:<4}  "
            f"{str(match['candidate']):<3}   "
            f"{frame_pd}    "
            f"{mean_deviation:>8.2f}  "
            f"{excess_deviation:>6.2f}"
        )


def main() -> None:
    """Run the default SciPy MILP Pareto sweep from the command line.

    The default candidate set mirrors the existing size-analysis script:
    lens sizes 38..62 mm, bridges 10..24 mm, and lens/bridge ratio 2.5..3.0.
    It prints one best solution for each k from 1 through 4.
    """
    from size_analysis.eu_population import MODEL as POPULATION_MODEL
    from size_analysis.ipd_model import MODEL as IPD_MODEL

    combined_model = build_gaussian_population_model(
        population_model=POPULATION_MODEL,
        ipd_model=IPD_MODEL,
        region="EU",
    )
    records_path = Path("data/processed/ipd_records.json")
    if records_path.exists():
        combined_model = combine_gaussian_population_models(
            combined_model,
            build_gaussian_population_model_from_records(records_path),
        )
    tolerance = 4.0 / 2
    size_constraint = SizeConstraint(
        lens_range=(40, 62),
        bridge_range=(14, 24),
        bridge_ratio_range=(2.5, 2.9),
    )

    problem = build_problem(
        combined_model=combined_model,
        candidates=size_constraint.candidates,
        tolerance=tolerance,
    )
    results = optimize(problem, min_k=1, max_k=7, top_n_per_k=2)

    total_population = float(problem["population"].sum())
    print("Population model: EU27_2020, Eurostat 2023, sex and age groups")
    print(f"Modelled weighted population: {_format_population(total_population)}")
    print("EU population grouped into IPD age ranges:")
    for category, population in zip(combined_model["categories"], combined_model["population"]):
        print(f"  {category}: {_format_population(population)}")
    print(f"Candidates: {problem['n_candidates']}")
    print(
        "Search parameters: "
        f"lens {size_constraint.lens_range[0]}-{size_constraint.lens_range[1]} mm, "
        f"bridge {size_constraint.bridge_range[0]}-{size_constraint.bridge_range[1]} mm, "
        f"lens/bridge {size_constraint.bridge_ratio_range[0]}-{size_constraint.bridge_ratio_range[1]}"
    )
    print(f"IPD grid cells: {len(problem['ipd_grid'])}")
    print(f"Tolerance: {problem['tolerance']} mm")
    print()
    print(" k  covered     coverage   mean dev   excess     frame specs                            PDs")
    print("--  ----------  ---------  ---------  ---------  -------------------------------------  --------")
    for row in results:
        print(_format_solution(row))
    if results:
        _print_group_fit_table(problem, results[0])


if __name__ == "__main__":
    main()
