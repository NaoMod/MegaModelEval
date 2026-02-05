#!/usr/bin/env python3
"""
Visualization script for agent accuracy progression
Discovers outputs named agent_execution_results_agentX_*.json (X in 1..7),
computes accuracy per agent, labels each agent by its commit code declared
as the first line docstring of evaluation/agent_versions/agentX.py, and draws a
line chart ordered by agent index.
"""

import json
import re
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple

# Reuse the evaluator that understands how to score execution results
try:
    from evaluate_accuracy import evaluate_file
except Exception:
    # Fallback if relative import fails when run differently
    import importlib.util as _ilu
    _eval_path = Path(__file__).parent / "evaluate_accuracy.py"
    _spec = _ilu.spec_from_file_location("evaluate_accuracy", str(_eval_path))
    if _spec and _spec.loader:
        _mod = _ilu.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)
        evaluate_file = getattr(_mod, "evaluate_file")
    else:
        raise RuntimeError("Cannot import evaluate_accuracy.evaluate_file")

def find_latest_agent_files() -> List[Tuple[int, Path]]:
    """Find the latest result file for each agent1..agent7.
    Returns a list of (agent_index, path) tuples ordered by agent index.
    """
    base_dir = Path(__file__).parent
    results: List[Tuple[int, Path]] = []
    for i in range(1, 8):
        # Look in version-specific subdirectory
        version_dir = base_dir / f"version_{i}"
        if not version_dir.exists():
            continue
            
        # pattern like agent_execution_results_seeds_agent3_*.json
        pattern = f"agent_execution_results_seeds_agent{i}_*.json"
        matches = sorted(version_dir.glob(pattern))
        if not matches:
            # Try without timestamp fallback: agent_execution_results_agent{i}.json
            fallback = version_dir / f"agent_execution_results_agent{i}.json"
            if fallback.exists():
                matches = [fallback]
        if matches:
            # Pick the latest lexicographically (timestamped names are sortable)
            latest = matches[-1]
            results.append((i, latest))
        else:
            # Still include placeholder with None path? We'll skip missing ones
            pass
    return results

def get_agent_code_label(agent_index: int) -> str:
    """Extract the commit code from the first line of the agent file.
    Falls back to f"agent{index}" if not found.
    """
    agent_path = Path(__file__).parent.parent / "evaluation" / "agent_versions" / f"agent{agent_index}.py"
    try:
        with open(agent_path, 'r') as f:
            first_line = f.readline().strip().strip('"').strip("'")
        # Expect something like: code: abcdef1 ...
        m = re.search(r"code:\s*([0-9a-fA-F]+)", first_line)
        if m:
            return m.group(1)
    except Exception:
        pass
    return f"agent{agent_index}"

def compute_agent_accuracies() -> List[Tuple[str, float, int]]:
    """Compute accuracies for latest agent1..agent7 result files.
    Returns a list of (label, accuracy, agent_index) ordered by agent index.
    """
    found = find_latest_agent_files()
    results: List[Tuple[str, float, int]] = []
    for idx, path in found:
        label = get_agent_code_label(idx)
        acc, _details = evaluate_file(path)
        results.append((label, acc, idx))
    return results

def create_accuracy_plot():
    """Create a line chart showing agent index vs accuracy."""
    pairs = compute_agent_accuracies()
    if not pairs:
        raise RuntimeError("No matching agent_execution_results_agentX files found in version_*/ subdirectories")

    # Maintain the natural ordering by agent index (1 .. 7)
    pairs.sort(key=lambda x: x[2])

    labels, accuracies, _indices = zip(*pairs)
    accuracies_pct = [a * 100 for a in accuracies]

    plt.figure(figsize=(12, 6))
    x = np.arange(len(labels))
    plt.plot(x, accuracies_pct, marker='o', linestyle='-', color='#1f77b4', linewidth=2)
    for xi, yi in zip(x, accuracies_pct):
        plt.text(xi, yi + 1, f"{yi:.1f}%", ha='center', va='bottom', fontsize=9, fontweight='bold')

    plt.title('Agent Accuracy by Version (Seeds Dataset)', fontsize=12, fontweight='bold', pad=12)
    plt.xlabel('Agent Version', fontsize=11)
    plt.ylabel('Accuracy (%)', fontsize=11)
    plt.ylim(0, 100)
    plt.grid(axis='y', alpha=0.3, linestyle='--')
    plt.xticks(x, labels, rotation=0)
    plt.tight_layout()

    plots_dir = Path(__file__).parent.parent / "plots"
    plots_dir.mkdir(exist_ok=True)
    output_file = plots_dir / "agent_accuracy_progression_seeds.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Plot saved to: {output_file}")
    plt.close()
    return list(labels), accuracies_pct

def print_accuracy_table():
    """Print a formatted table of results for latest agent files."""
    pairs = compute_agent_accuracies()
    if not pairs:
        print("No matching agent_execution_results_agentX files found.")
        return
    # Keep order by agent index
    pairs.sort(key=lambda x: x[2])

    print("\n=== Agent Accuracy (Latest results per agent) ===")
    print(f"{'Commit':<12} {'Accuracy':<10} {'Delta vs prev'}")
    print("-" * 40)
    prev = None
    for label, acc, _idx in pairs:
        delta = (acc - prev) * 100 if prev is not None else 0.0
        print(f"{label:<12} {acc*100:>6.1f}%    {delta:+6.1f}%")
        prev = acc
    print("-" * 40)

if __name__ == "__main__":
    print("Creating agent accuracy visualization...")
    
    try:
        # Print table
        print_accuracy_table()
        
        # Create plot
        agents, accuracies = create_accuracy_plot()
        
        print(f"\nVisualization complete!")
        print(f"Agents in order: {' → '.join(agents)}")
        print(f"Accuracies: {' → '.join([f'{acc:.1f}%' for acc in accuracies])}")
        
    except Exception as e:
        print(f"Error creating visualization: {e}")