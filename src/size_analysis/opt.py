#!/usr/bin/env python3
"""
Optimal Number of Size Categories
===================================
Sweep across different numbers of sizes to find the coverage curve.
Find the elbow point where marginal gains diminish.

Uses fast NumPy/SciPy optimizer instead of exhaustive search.
"""

from size_analysis.eu_population import MODEL as POPULATION_MODEL
from size_analysis.ipd_model import MODEL as IPD_MODEL
from size_analysis.constraint import SizeConstraint
from size_analysis.optimizer import Model
from size_analysis.numpy_optimizer import sweep_sizes, print_results


if __name__ == '__main__':
    tolerance = 4.0
    size_constraint = SizeConstraint(
        lens_range=(38, 62),
        bridge_range=(10, 24),
        bridge_ratio_range=(2.5, 3.0),
    )
    
    candidates = size_constraint.candidates
    model = Model(POPULATION_MODEL, IPD_MODEL, tolerance, candidates)
    
    results = sweep_sizes(model, min_n=2, max_n=8)
    print_results(results)
