#!/usr/bin/env python3
"""
Plot the Pareto sweep results: number of sizes (k) vs population coverage.
Identifies the elbow point where marginal gains diminish.
"""

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

from size_analysis.constraint import SizeConstraint
from size_analysis.eu_population import MODEL as POPULATION_MODEL
from size_analysis.ipd_model import MODEL as IPD_MODEL
from size_analysis.numpy_problem import (
    build_gaussian_population_model,
    build_problem,
    optimize,
)


def main() -> None:
    """Generate a Pareto sweep plot of coverage vs number of sizes."""
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
    
    # Run Pareto sweep from k=2 to k=8
    print("Running Pareto sweep...")
    solutions = optimize(problem, min_k=2, max_k=8)
    
    # Extract k and coverage_rate from solutions
    k_values = []
    coverage_pcts = []
    marginal_gains = []
    
    for i, sol in enumerate(solutions):
        k = sol['k']
        cov_pct = 100 * sol['coverage_rate']
        
        k_values.append(k)
        coverage_pcts.append(cov_pct)
        
        if i > 0:
            marginal = cov_pct - coverage_pcts[i - 1]
        else:
            marginal = None
        marginal_gains.append(marginal)
    
    # Create the figure with professional styling
    fig, ax = plt.subplots(figsize=(8, 5), tight_layout=True)
    
    # Color palette: professional blue
    color_line = "#3ba1ff"
    color_point = "#0085ff"
    color_annotation = "#333333"
    
    # Plot the coverage curve
    ax.plot(
        k_values, coverage_pcts,
        linewidth=2.5,
        color=color_line,
        marker='o',
        markersize=8,
        markerfacecolor=color_point,
        markeredgecolor='white',
        markeredgewidth=1.5,
        zorder=3,
    )
    
    # Annotate each point with k and coverage %
    for i, (k, cov) in enumerate(zip(k_values, coverage_pcts)):
        ax.text(
            k, cov + 0.8,
            f"{cov:.1f}%",
            ha='center', va='bottom',
            fontsize=10, weight='bold',
            color=color_annotation,
        )
        
        # Add marginal gain annotation if available
        if marginal_gains[i] is not None:
            gain = marginal_gains[i]
            ax.text(
                k, cov - 1.2,
                f"+{gain:.1f}%",
                ha='center', va='top',
                fontsize=9, style='italic',
                color='#666666',
            )
    
    # Find and highlight the elbow point (where marginal gain < 2%)
    elbow_k = None
    for i, gain in enumerate(marginal_gains[1:], 1):
        if gain is not None and gain < 2.0:
            elbow_k = k_values[i]
            break
    
    if elbow_k:
        elbow_idx = k_values.index(elbow_k)
        ax.scatter(
            elbow_k, coverage_pcts[elbow_idx],
            s=200, marker='*', color='#fb8500',
            zorder=4, edgecolor='white', linewidth=2,
            label=f'Elbow point (k={elbow_k})',
        )
    
    # Styling: follow the visualization guide
    ax.set_xlabel("Number of Size Categories (k)", fontsize=12, weight='bold')
    ax.set_ylabel("Population Coverage (%)", fontsize=12, weight='bold')
    ax.set_title("Pareto Sweep: Optimal Number of Frame Sizes", fontsize=14, weight='bold')
    
    # Set limits with padding
    ax.set_xlim(1.5, 8.5)
    ax.set_ylim(90, 102)
    
    # Set integer ticks for k
    ax.set_xticks(k_values)
    ax.set_yticks([90, 92, 94, 96, 98, 100, 102])
    
    # Grid styling
    ax.yaxis.grid(True, which='major', linestyle=':', linewidth=0.8, alpha=0.6, color='#cccccc')
    ax.set_axisbelow(True)
    
    # Spine styling: remove top and right, keep bottom and left
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_linewidth(1.5)
    ax.spines['bottom'].set_linewidth(1.5)
    
    # Tick styling
    ax.tick_params(left=False, bottom=False, labelsize=10)
    
    # Legend
    if elbow_k:
        ax.legend(loc='lower right', frameon=False, fontsize=10)
    
    # Add annotation text box with key findings
    if elbow_k:
        n_free = elbow_k - 2  # Assuming 2 children sizes
        textstr = (
            f'Recommendation: {int(elbow_k)} sizes\n'
            f'(2 children + {int(n_free)} adults)\n'
            f'Coverage: {coverage_pcts[k_values.index(elbow_k)]:.1f}%'
        )
        ax.text(
            0.05, 0.05, textstr,
            transform=ax.transAxes,
            fontsize=10,
            verticalalignment='bottom',
            bbox=dict(boxstyle='round', facecolor='#f0f0f0', alpha=0.8, edgecolor='#cccccc'),
            family='monospace',
        )
    
    # Save as PNG and PDF
    output_dir = Path("tmp")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    png_path = output_dir / "pareto_sweep.png"
    pdf_path = output_dir / "pareto_sweep.pdf"
    
    fig.savefig(png_path, dpi=300, bbox_inches='tight', transparent=True)
    fig.savefig(pdf_path, bbox_inches='tight', transparent=True)
    
    print(f"Saved: {png_path}")
    print(f"Saved: {pdf_path}")
    
    # Print summary table
    print("\n" + "="*60)
    print("PARETO SWEEP SUMMARY")
    print("="*60)
    print(f"{'k':<5} {'Coverage':<15} {'Marginal Gain':<15}")
    print("-"*60)
    for i, (k, cov) in enumerate(zip(k_values, coverage_pcts)):
        if marginal_gains[i] is not None:
            gain_str = f"+{marginal_gains[i]:.2f}%"
        else:
            gain_str = "-"
        print(f"{k:<5} {cov:>6.2f}%{'':<7} {gain_str:<15}")
    print("="*60)
    
    if elbow_k:
        print(f"\n✓ Elbow point identified at k={int(elbow_k)}")
        print(f"  Marginal gain drops below 2% beyond this point.")
    
    plt.show()


if __name__ == "__main__":
    main()
