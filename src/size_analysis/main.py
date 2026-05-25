#!/usr/bin/env python3
"""
Eyeglass Frame Size Analysis — EU27 Population
===============================================
Data hypothesis layer and AsciiDoc report generator.
The mathematical optimisation is in size_analysis.optimizer.

Run:  python3 -m size_analysis.main

SOURCES
-------
[S1]  Eurostat demo_pjan — Population on 1 January by age, EU27_2020, 2023.
      DOI: https://doi.org/10.2908/DEMO_PJAN

[S8]  Optica Kenya — Eyeglasses Frame Size Chart.
      https://optica.africa/blogs/news/know-your-eyeglass-frame-size-chart-to-get-a-frame-that-suits-your-face

[S9]  Banton Frameworks — How are glasses measured?
      https://www.bantonframeworks.co.uk/blogs/eye-care/frame-dimensions

[S10] Fesharaki H et al. "Normal Interpupillary Distance Values in an Iranian Population."
      J Ophthalmic Vis Res. 2012;7(3):231-234. PMC3520592.
      https://pmc.ncbi.nlm.nih.gov/articles/PMC3520592/

[S11] Dodgson NA, Woods AJ, Merritt JO, Benton SA, Bolas MT.
      "Variation and extrema of human interpupillary distance."
      Proc. SPIE 5291; 2004:36–46.  DOI: https://doi.org/10.1117/12.529999

[S12] Kevin Paisley Optometrists — Frame Size Guide.
      https://kevinpaisley.com.au/frame-size-guide/

TERMINOLOGY
-----------
"Lens width" = horizontal width of one lens in the boxing system (ISO 8624).
First number in standard frame notation, e.g. 51-18-140 = lens 51 mm,
bridge 18 mm, temple 140 mm.
"""

import os
import dataclasses

import json

from size_analysis.eu_population import MODEL as POPULATION_MODEL
from size_analysis.frame_model import FrameSpec
from size_analysis.constraint import SizeConstraint
from size_analysis.ipd_model import MODEL as IPD_MODEL, IPDModel, Normal
from size_analysis.categories import Category
from size_analysis.population_model import PopulationModel
from size_analysis.optimizer import (
    union_coverage_group,
    Model, pop_of, exact_coverage, pop_covered_by_set, total_modelled,
    SearchSpace, objective,
    solve, RankedSolution, fit_error,
)


# ============================================================================
# SIZE HYPOTHESIS (labels + constrained-optimisation parameters)
# ============================================================================

@dataclasses.dataclass(frozen=True)
class SizeHypothesis:
    """Display labels and constrained-optimisation parameters for a size set.

    labels           -- ordered size labels, e.g. ('XS', 'S', 'M', 'L').
    n_children_sizes -- how many of the smallest labels are children-only sizes
                        pinned to the exhaustive-pair solution before optimising
                        the remaining adult sizes.
    """
    labels: tuple[str, ...]
    n_children_sizes: int = 2

    def __len__(self) -> int:
        return len(self.labels)


def _is_child_group(cat: Category) -> bool:
    # Only the 5-7 and 8-10 Fledelius bands.
    # Ages 11-17 are covered incidentally by the adult sizes.
    # Ages 0-4 have no IPD data; a future XXS size is planned for that group.
    if isinstance(cat.age, int):
        return 5 <= cat.age <= 10
    if isinstance(cat.age, tuple):
        return cat.age[0] <= 10 and cat.age[1] >= 5
    return False


def rank(result: list[RankedSolution], top_n: int = 1, how: str = "pareto") -> list[RankedSolution]:
    if how == "pareto":
        # Pareto rank by coverage (descending) and fit error (ascending).
        # This is the default for all results in the report.
        ranked = sorted(result, key=lambda r: (-r.coverage, r.fit_error))
    elif how == "sort":
        # Sort by coverage (descending) and fit error (ascending), but ignore Pareto dominance.
        ranked = sorted(result, key=lambda r: -r.coverage)
    else:
        raise ValueError(f"Unknown ranking method: {how}")
    return ranked[:top_n]


# ============================================================================
# NAMED SOLUTIONS
# ============================================================================

def children_2size(model: Model, space: SearchSpace) -> list[RankedSolution]:
    """Rank the top 10 2-frame sets by child population coverage."""
    result = solve(
        SearchSpace(n_sizes=2, candidates=space.candidates),
        model,
        group_filter=_is_child_group,
    )

    return rank(result, top_n=10, how="sort")


def all_ages_4size(model: Model, space: SearchSpace) -> list[FrameSpec]:
    """Unconstrained: maximise f(S) over all age groups for |S| = space.n_sizes."""
    result = solve(space, model)
    return rank(result, top_n=1)[0].specs


def constrained_all_ages(model: Model, space: SearchSpace, hyp: SizeHypothesis) -> dict[str, FrameSpec]:
    """Constrained: pin the best children pair, then maximise f(S) for the rest.

    The first hyp.n_children_sizes slots are fixed to the exhaustive-pair optimum
    for children.  The remaining (space.n_sizes - hyp.n_children_sizes) sizes are
    found by maximising f(S) over all age groups with the children sizes pinned.
    """
    pairs = children_2size(model, space)
    children = pairs[0].specs
    n_free = space.n_sizes - hyp.n_children_sizes
    free_space = SearchSpace(n_sizes=n_free, candidates=space.candidates)
    result = solve(free_space, model, pinned=children)
    free = rank(result, top_n=1)[0].specs
    all_specs = children + sorted(free, key=lambda f: f.lens + f.bridge)
    return dict(zip(hyp.labels, all_specs))

# ============================================================================
# 8.  PRINT ALL TABLES
# ============================================================================
# 8.  ADOC OUTPUT
# ============================================================================

_ADOC_PATH = os.path.join(os.getcwd(), "docs", "sizes-rationale.adoc")


def adoc_table(
    headers: list,
    rows: list,
    cols: str = "",
    title: str = "",
) -> str:
    """Return an AsciiDoc table string.

    headers  -- list of header cell strings
    rows     -- list of lists (or list of pre-formatted '| a | b' strings)
    cols     -- AsciiDoc cols attribute value, e.g. '>s,^,<'; auto-generated if empty
    title    -- optional table title (printed as `.title` above the block)
    """
    if not cols:
        cols = ",".join(["<"] * len(headers))
    lines = []
    if title:
        lines.append(f".{title}")
    lines.append(f'[cols="{cols}",options="header"]')
    lines.append("|===")
    lines.append("| " + " | ".join(headers))
    for row in rows:
        if isinstance(row, str):
            lines.append(row)
        else:
            lines.append("| " + " | ".join(str(c) for c in row))
    lines.append("|===")
    return "\n".join(lines)


def _adoc_table8(model: Model, space: SearchSpace, hyp: SizeHypothesis) -> str:
    pairs = children_2size(model, space)
    p = pairs[0]
    child_cats = [cat for cat in model.groups if _is_child_group(cat)]
    total_child = sum(model.groups[cat] for cat in child_cats)
    fp_a, fp_b = p.specs[0].lens + p.specs[0].bridge, p.specs[1].lens + p.specs[1].bridge
    pop_a = sum(
        model.groups[cat] * union_coverage_group([fp_a], model.ipd_groups[cat], model.tolerance)
        for cat in child_cats
    )
    pop_b = sum(
        model.groups[cat] * union_coverage_group([fp_b], model.ipd_groups[cat], model.tolerance)
        for cat in child_cats
    )

    ranking_rows = [
        [rk, str(pair.specs[0]), str(pair.specs[1]),
         f"{pair.coverage:,.0f}", f"{100 * pair.coverage / total_child:.1f} %" + (" \u2605" if rk == 1 else ""),
         f"{pair.fit_error:,.0f}"]
        for rk, pair in enumerate(pairs, 1)
    ]
    summary_rows = [
        ["XS", str(p.specs[0]), f"{pop_a:,.0f}", f"{100 * pop_a / total_child:.1f} %", ""],
        ["S",  str(p.specs[1]), f"{pop_b:,.0f}", f"{100 * pop_b / total_child:.1f} %", ""],
        ["*Union*", "", f"*{p.coverage:,.0f}*", f"*{100 * p.coverage / total_child:.1f} %*", f"*{p.fit_error:,.0f}*"],
    ]

    lines = [
        "=== 2-Size Solution: Children (ages 5\u201310)",
        "",
        f"Top {len(pairs)} frame pairs ranked by coverage of ages 5\u201310",
        f"(total population ages 5\u201310 modelled: {total_child:,}).",
        "",
        adoc_table(
            headers=["Rank", "Spec XS", "Spec S", "Pop. covered", "Coverage", "Fit error"],
            rows=ranking_rows,
            cols=">s,^,^,>,>,>",
            title=f"Top {len(pairs)} pairs by child coverage",
        ),
        "",
        adoc_table(
            headers=["Size", "Spec", "Pop. covered", "Share of children", "Fit error"],
            rows=summary_rows,
            cols="^s,^,>,>,>",
            title=f"Recommended pair \u2014 {p.specs[0]} + {p.specs[1]}",
        ),
        "",
    ]
    return "\n".join(lines)


def _adoc_coverage_section(heading: str, frames: dict[str, FrameSpec], model: Model, pop: PopulationModel, hyp: SizeHypothesis, extra: str = "") -> str:
    cov = pop_covered_by_set(list(frames.values()), model)
    total = total_modelled(model.groups)
    pct = 100 * cov / total
    uncov = total - cov

    cov_rows = []
    prev_specs: list[FrameSpec] = []
    for lbl, f in frames.items():
        prev_fps = [s.lens + s.bridge for s in prev_specs]
        fp = f.lens + f.bridge
        marginal = {
            cat: union_coverage_group(prev_fps + [fp], dist, model.tolerance) -
                 union_coverage_group(prev_fps,         dist, model.tolerance)
            for cat, dist in model.ipd_groups.items()
        }
        unique = pop_of(model.groups, marginal)
        cov_with = exact_coverage(prev_specs + [f], model)
        groups_g = [
            str(cat) if cov_with[cat] > 0.999
            else f"{cat} ({100*marginal[cat]:.0f}%)"
            for cat in model.groups
            if marginal[cat] > 0.01
        ]
        fe = fit_error([f], model)
        cov_rows.append([
            lbl, str(f), f"{unique:,.0f}",
            f"{100*unique/total:.1f} %",
            f"{fe:,.0f}",
            ', '.join(groups_g) or '\u2014',
        ])
        prev_specs.append(f)

    final_covs = exact_coverage(list(frames.values()), model)
    partial = [
        f"{cat}: {100*final_covs[cat]:.0f}%"
        for cat in model.groups
        if final_covs[cat] < 0.999
    ]
    partial_str = (", ".join(partial[:10]) + ("\u2026" if len(partial) > 10 else "")) or "none"

    lines = [
        heading,
        "",
        f"Population modelled: {total:,} \u2014 coverage: *{cov:,.0f}* ({pct:.1f} %).",
    ]
    if extra:
        lines += ["", extra]
    lines += [
        "",
        adoc_table(
            headers=["Label", "Spec", "Unique pop", "% of total", "Fit error", "Groups covered"],
            rows=cov_rows,
            cols="^s,^,>,>,>,<",
        ),
        "",
        f"Partial coverage ({uncov/1e6:.1f} M, {100*uncov/total:.1f} % uncovered): {partial_str}",
        "",
    ]
    return "\n".join(lines)

def _adoc_cv_section(heading: str, cross_val: dict[str, dict], hyp: SizeHypothesis, extra: str = "") -> str:
    rows = []
    for model_name, data in cross_val.items():
        total = data['total_population']
        for label, ld in data['per_label'].items():
            rows.append([
                model_name,
                label,
                str(ld['spec']),
                f"{ld['unique_population']:,.0f}",
                f"{ld['unique_pct']:.1f} %",
                f"{ld['fit_error']:,.0f}",
            ])
        rows.append([
            f"*{model_name} total*", "", "",
            f"*{data['coverage']:,.0f}*",
            f"*{data['coverage_pct']:.1f} %*",
            f"*{data['fit_error']:,.0f}*",
        ])

    lines = [
        heading,
        "",
        extra,
        "",
        adoc_table(
            headers=["Model", "Label", "Spec", "Unique pop", "% of total", "Fit error"],
            rows=rows,
            cols="<,^s,^,>,>,>",
        ),
        "",
    ]
    return "\n".join(lines)

def cross_validate_other_set(fc: dict[str, FrameSpec], other_models: dict[str, tuple[PopulationModel, IPDModel]], tolerance: float = None) -> dict[str, dict]:
    """Given other IPD models, recalculate per-labeled-spec marginal coverage of fc in those models."""
    if tolerance is None:
        tolerance = 4.0

    results = {}
    fc_items = list(fc.items())  # [(label, FrameSpec), ...]
    fc_specs = [f for _, f in fc_items]

    for model_name, (pop_model, ipd_model) in other_models.items():
        model = Model(pop_model, ipd_model, tolerance, fc_specs)
        total_pop = total_modelled(model.groups)

        per_label = {}
        prev_specs: list[FrameSpec] = []
        for label, spec in fc_items:
            prev_fps = [s.lens + s.bridge for s in prev_specs]
            fp = spec.lens + spec.bridge
            marginal = {
                cat: union_coverage_group(prev_fps + [fp], dist, model.tolerance) -
                     union_coverage_group(prev_fps,         dist, model.tolerance)
                for cat, dist in model.ipd_groups.items()
            }
            unique = pop_of(model.groups, marginal)
            fe = fit_error([spec], model)
            per_label[label] = {
                'spec': spec,
                'unique_population': unique,
                'unique_pct': 100 * unique / total_pop if total_pop > 0 else 0.0,
                'fit_error': fe,
            }
            prev_specs.append(spec)

        total_coverage = pop_covered_by_set(fc_specs, model)
        total_fit_error = fit_error(fc_specs, model)
        results[model_name] = {
            'total_population': total_pop,
            'coverage': total_coverage,
            'coverage_pct': 100 * total_coverage / total_pop if total_pop > 0 else 0.0,
            'fit_error': total_fit_error,
            'per_label': per_label,
        }

    return results

def _load_cross_validation_models() -> dict[str, tuple[PopulationModel, IPDModel]]:
    """Load cross-validation models from processed IPD records.

    eurostat_demo_pjan records are pure population counts (no IPD field) and are
    paired with the standard IPD_MODEL (Fledelius + ANSUR) to form the baseline
    EU27 cross-validation entry.  Other sources (e.g. taiwan_plos_s002) carry
    individual IPD samples and are converted to Normal distributions per category.
    """
    
    # Check if the file exists
    ipd_file_path = 'data/processed/ipd_records.json'
    if not os.path.exists(ipd_file_path):
        print(f"Warning: {ipd_file_path} not found. Please run the data fetching script to generate the IPD records.")
        return {}
    
    # Load the processed IPD records
    with open(ipd_file_path, 'r') as f:
        ipd_data = json.load(f)
    
    cv_models = {}
    
    for record in ipd_data:
        # Example record
        # {
        #     "source": "taiwan_plos_s002",
        #     "source_path": "data\\raw\\taiwan_plos\\pone.0188638.s002.xlsx",
        #     "kind": "ipd_sample",
        #     "sex": "F",
        #     "age": {
        #       "value": 21,
        #       "range": [
        #         21,
        #         21
        #       ],
        #       "label": "21"
        #     },
        #     "ipd": {
        #       "value": 60.0,
        #       "unit": "mm",
        #       "label": "Interpupillary breadth"
        #     },
        #     "count": 1
        #   },
        
        # Get the source name for this study
        study_name = record.get('source', 'Unknown')
        
        # Create category from age and sex
        age_val = record.get('age', {}).get('value')
        sex = record.get('sex', 'U')
        count = record.get('count', 1)
        ipd_val = record.get('ipd', {}).get('value')
        
        if age_val is not None and ipd_val is not None:
            category = Category(age=age_val, sex=sex)
            
            # Initialize study data if not exists
            if study_name not in cv_models:
                cv_models[study_name] = {'population_groups': {}, 'ipd_groups': {}}
            
            # Add to population groups
            if category not in cv_models[study_name]['population_groups']:
                cv_models[study_name]['population_groups'][category] = 0
            cv_models[study_name]['population_groups'][category] += count
            
            # Add to IPD groups (collect IPD values for this category)
            if category not in cv_models[study_name]['ipd_groups']:
                cv_models[study_name]['ipd_groups'][category] = []
            cv_models[study_name]['ipd_groups'][category].extend([ipd_val] * count)
    
    # Convert collected data to proper models
    final_cv_models = {}
    for study_name, data in cv_models.items():
        if data['population_groups'] and data['ipd_groups']:
            # Create PopulationModel
            pop_model = PopulationModel(data['population_groups'])
            
            # Create IPDModel - convert lists to distributions
            ipd_distributions = {}
            for category, ipd_values in data['ipd_groups'].items():
                if len(ipd_values) > 0:
                    # Create a simple distribution from the IPD values
                    # For now, use mean and std dev, but this could be more sophisticated
                    import statistics
                    mean_ipd = statistics.mean(ipd_values)
                    if len(ipd_values) > 1:
                        std_ipd = statistics.stdev(ipd_values)
                    else:
                        std_ipd = 2.0  # Default standard deviation for single values
                    
                    # Create a normal distribution representation
                    # This assumes IPDModel can accept mean/std parameters
                    ipd_distributions[category] = Normal(mean=mean_ipd, standard_deviation=std_ipd)
            
            ipd_model = IPDModel(ipd_distributions)
            final_cv_models[study_name] = (pop_model, ipd_model)
    
    cv_models = final_cv_models

    # eurostat_demo_pjan records are population-only; pair with the standard IPD_MODEL.
    cv_models['eurostat_demo_pjan'] = (POPULATION_MODEL, IPD_MODEL)

    return cv_models

def write_adoc(
    model: Model,
    pop: PopulationModel,
    space: SearchSpace,
    hyp: SizeHypothesis,
    cv_models=dict[str, tuple[PopulationModel, IPDModel]],
    path: str = _ADOC_PATH,
) -> None:
    f4 = all_ages_4size(model, space)
    f4_labeled: dict[str, FrameSpec] = dict(zip(hyp.labels, f4))
    fc = constrained_all_ages(model, space, hyp)
    cov4   = pop_covered_by_set(list(f4_labeled.values()), model)
    cov_fc = pop_covered_by_set(list(fc.values()), model)
    cross_val = cross_validate_other_set(fc, other_models=cv_models, tolerance=model.tolerance)
    delta = cov_fc - cov4
    sign = "+" if delta >= 0 else ""
    n_free = space.n_sizes - hyp.n_children_sizes

    sections = [
        "= Eyeglass Frame Size Optimisation",
        ":description: Statistical analysis deriving optimal standardised frame sizes",
        ":toc:",
        ":numbered:",
        "",
        "include::sizes-rationale-hypothesis.adoc[]",
        "",
        "== Results",
        "",
        _adoc_table8(model, space, hyp),
        _adoc_coverage_section(
            "=== Unconstrained 5-Size Solution (XS\u2013XL) \u2014 All EU27 Ages",
            f4_labeled, model, pop, hyp,
        ),
        _adoc_coverage_section(
            "=== Constrained Solution \u2014 Children Sizes Fixed, Rest Optimised",
            fc, model, pop, hyp,
            extra=(
                f"First {hyp.n_children_sizes} sizes locked to the best children's pair; "
                f"remaining {n_free} sizes re-optimised across all groups. "
                f"Coverage vs unconstrained: {sign}{delta / 1e6:.1f} M "
                f"({sign}{100 * delta / total_modelled(model.groups):.2f} %)."
            ),
        ),
        "include::sizes-rationale-sources.adoc[]",
        "",
        _adoc_cv_section(
            "=== Cross-Validation of Constrained Solution in Other Models",
            cross_val, hyp,
            extra=(
                "Coverage of the constrained solution recalculated in other population/IPD models "
                "derived from processed IPD records. Results vary by model, but the constrained solution "
                "generally retains high coverage across different populations and IPD assumptions."
            ),
        ),
    ]

    content = "\n".join(sections)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    print(f"Written: {path}")


def _distinct_by_pd(candidates: tuple[FrameSpec, ...], ideal_ratio: float) -> tuple[FrameSpec, ...]:
    _by_pd: dict[int, FrameSpec] = {}
    for c in candidates:
        if (c.pd not in _by_pd
                or abs(c.lens / c.bridge - ideal_ratio) < abs(_by_pd[c.pd].lens / _by_pd[c.pd].bridge - ideal_ratio)):
            _by_pd[c.pd] = c
    return tuple(sorted(_by_pd.values(), key=lambda f: f.pd))


def main() -> None:
    tolerance: float = 4.0
    size_constraint = SizeConstraint(
        lens_range=(38, 62),
        bridge_range=(10, 24),
        bridge_ratio_range=(2.5, 3.0),
    )
    hypothesis = SizeHypothesis(labels=('XS', 'S', 'M', 'L'))

    cv_models = _load_cross_validation_models()

    ideal_ratio = (size_constraint.bridge_ratio_range[0] + size_constraint.bridge_ratio_range[1]) / 2
    candidates = _distinct_by_pd(size_constraint.candidates, ideal_ratio)

    model = Model(POPULATION_MODEL, IPD_MODEL, tolerance, candidates)
    space = SearchSpace(n_sizes=4, candidates=candidates)
    write_adoc(model, POPULATION_MODEL, space, hypothesis, cv_models)


if __name__ == '__main__':
    main()
