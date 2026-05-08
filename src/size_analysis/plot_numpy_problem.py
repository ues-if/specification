"""Plot the Gaussian EU/IPD population model and optimized frame bands."""

import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from size_analysis.constraint import SizeConstraint
from size_analysis.eu_population import MODEL as POPULATION_MODEL
from size_analysis.ipd_model import MODEL as IPD_MODEL
from size_analysis.numpy_problem import build_gaussian_population_model, build_problem, optimize


def normal_pdf(x: np.ndarray, mean: float, standard_deviation: float) -> np.ndarray:
    """Evaluate a Normal probability density function."""
    z = (x - mean) / standard_deviation
    return np.exp(-0.5 * z * z) / (standard_deviation * math.sqrt(2.0 * math.pi))


def main() -> None:
    """Generate a plot of population-weighted IPD distributions and frame fit bands."""
    tolerance = 4.0
    size_constraint = SizeConstraint(
        lens_range=(38, 62),
        bridge_range=(10, 24),
        bridge_ratio_range=(2.5, 3.0),
    )
    combined_model = build_gaussian_population_model(POPULATION_MODEL, IPD_MODEL)
    problem = build_problem(
        combined_model=combined_model,
        candidates=size_constraint.candidates,
        tolerance=tolerance,
    )
    solution = optimize(problem, min_k=4, max_k=4)[0]

    x = np.linspace(40.0, 85.0, 900)
    population = problem["population"]
    total_population = population.sum()
    gaussian_ipd = problem["gaussian_ipd"]
    weights = population / total_population

    group_densities = []
    for category, weight, (mean, standard_deviation) in zip(problem["categories"], weights, gaussian_ipd):
        density = weight * normal_pdf(x, mean, standard_deviation)
        group_densities.append((category, density))

    fig, axes = plt.subplots(2, 1, figsize=(12, 10), sharex=True, sharey=True)
    data_ax, overlay_ax = axes

    for ax in axes:
        for category, density in group_densities:
            ax.plot(x, density, linewidth=1.2, alpha=0.55, label=str(category))
        ax.set_ylabel("Population-weighted probability density")
        ax.grid(True, alpha=0.25)

    labels = ("XS", "S", "M", "L")
    colors = ("#4C78A8", "#59A14F", "#F28E2B", "#E15759")
    ordered = sorted(
        zip(solution["selected_candidates"], solution["selected_frame_pd"]),
        key=lambda item: item[1],
    )
    for label, color, (spec, pd) in zip(labels, colors, ordered):
        overlay_ax.axvspan(pd - tolerance, pd + tolerance, color=color, alpha=0.14)
        overlay_ax.axvline(pd, color=color, linestyle="--", linewidth=1.5)
        overlay_ax.text(
            pd,
            overlay_ax.get_ylim()[1] * 0.96,
            f"{label}\n{spec}\nPD {pd:g}",
            ha="center",
            va="top",
            color=color,
            fontsize=10,
        )

    data_ax.set_title("EU Population-Weighted IPD Distributions")
    overlay_ax.set_title("Optimized XS/S/M/L Frame PD Bands Overlaid")
    overlay_ax.set_xlabel("IPD / frame PD (mm)")
    data_ax.legend(ncol=2, fontsize=8)
    fig.tight_layout()

    output = Path("tmp/size_analysis_ipd_distribution.png")
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180)
    print(output)


if __name__ == "__main__":
    main()
