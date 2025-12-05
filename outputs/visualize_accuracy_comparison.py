#!/usr/bin/env python3
"""
Comparison visualization script for agent accuracy progression
Plots both regular dataset and seeds dataset on the same figure with different colors
"""
import re
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from typing import List, Tuple

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

def find_agent_files(is_seeds: bool = False) -> List[Tuple[int, Path]]:
    """Find the latest result file for each agent1..agent7.
    Args:
        is_seeds: If True, look for seeds dataset files; otherwise regular dataset files
    Returns a list of (agent_index, path) tuples ordered by agent index.
    """
    base_dir = Path(__file__).parent / "agent_version_logs"
    results: List[Tuple[int, Path]] = []
    
    for i in range(1, 8):
        # Look in version-specific subdirectory
        version_dir = base_dir / f"version_{i}"
        if not version_dir.exists():
            continue
            
        if is_seeds:
            # pattern like agent_execution_results_seeds_agent3_*.json
            pattern = f"agent_execution_results_seeds_agent{i}_*.json"
        else:
            # pattern like agent_execution_results_agent3_*.json (not seeds)
            pattern = f"agent_execution_results_agent{i}_*.json"
        
        matches = sorted(version_dir.glob(pattern))
        
        if not matches and not is_seeds:
            # Try without timestamp fallback: agent_execution_results_agent{i}.json
            fallback = version_dir / f"agent_execution_results_agent{i}.json"
            if fallback.exists():
                matches = [fallback]
                
        if matches:
            # Pick the latest lexicographically (timestamped names are sortable)
            latest = matches[-1]
            results.append((i, latest))
    
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

def compute_agent_accuracies(is_seeds: bool = False) -> List[Tuple[str, float, int]]:
    """Compute accuracies for latest agent1..agent7 result files.
    Args:
        is_seeds: If True, use seeds dataset files; otherwise use regular dataset files
    Returns a list of (label, accuracy, agent_index) ordered by agent index.
    """
    found = find_agent_files(is_seeds)
    results: List[Tuple[str, float, int]] = []
    for idx, path in found:
        label = get_agent_code_label(idx)
        acc, _details = evaluate_file(path)
        results.append((label, acc, idx))
    return results

def create_comparison_plot():
    """Create a line chart showing agent index vs accuracy for both datasets."""
    
    # Get data for both datasets
    regular_data = compute_agent_accuracies(is_seeds=False)
    seeds_data = compute_agent_accuracies(is_seeds=True)
    
    if not regular_data and not seeds_data:
        raise RuntimeError("No matching agent execution result files found in outputs/agent_version_logs/version_*/")
    
    # Sort by agent index and convert to separate lists
    regular_data.sort(key=lambda x: x[2])
    seeds_data.sort(key=lambda x: x[2])
    
    # Create the plot with smaller figure size for paper
    plt.figure(figsize=(9, 5))
    
    # Plot regular dataset (if available)
    if regular_data:
        labels, accuracies, _indices = zip(*regular_data)
        accuracies_pct = [a * 100 for a in accuracies]
        x = np.arange(len(labels))
        
        line1 = plt.plot(x, accuracies_pct, marker='o', linestyle='-', 
                        color='#1f77b4', linewidth=2, markersize=5, 
                        label='Augmented Dataset', alpha=0.8)[0]
        
        # Add value labels
        for xi, yi in zip(x, accuracies_pct):
            plt.text(xi, yi + 1.5, f"{yi:.1f}%", ha='center', va='bottom', 
                    fontsize=8, fontweight='bold', color='#1f77b4')
    
    # Plot seeds dataset (if available)
    if seeds_data:
        labels_seeds, accuracies_seeds, _indices_seeds = zip(*seeds_data)
        accuracies_pct_seeds = [a * 100 for a in accuracies_seeds]
        x_seeds = np.arange(len(labels_seeds))
        
        line2 = plt.plot(x_seeds, accuracies_pct_seeds, marker='s', linestyle='-', 
                        color='#ff7f0e', linewidth=2, markersize=5, 
                        label='Seeds Dataset', alpha=0.8)[0]
        
        # Add value labels
        for xi, yi in zip(x_seeds, accuracies_pct_seeds):
            plt.text(xi, yi - 3, f"{yi:.1f}%", ha='center', va='top', 
                    fontsize=8, fontweight='bold', color='#ff7f0e')
    
    # Use the labels from whichever dataset we have (they should be the same)
    if regular_data:
        plt.xticks(x, labels, rotation=0, fontsize=10)
    elif seeds_data:
        plt.xticks(x_seeds, labels_seeds, rotation=0, fontsize=10)
    
    plt.xlabel('Agent Version', fontsize=11)
    plt.ylabel('Accuracy (%)', fontsize=11)
    plt.ylim(0, 100)
    plt.grid(axis='y', alpha=0.3, linestyle='--')
    
    # Add legend at bottom right, more compact
    plt.legend(loc='lower right', fontsize=10, framealpha=0.9)
    
    plt.tight_layout()

    plots_dir = Path(__file__).parent / "plots"
    plots_dir.mkdir(exist_ok=True)
    output_file = plots_dir / "agent_accuracy_comparison.png"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"Comparison plot saved to: {output_file}")
    plt.show()
    
    return regular_data, seeds_data

def print_comparison_table():
    """Print a formatted table comparing both datasets."""
    regular_data = compute_agent_accuracies(is_seeds=False)
    seeds_data = compute_agent_accuracies(is_seeds=True)
    
    # Sort by agent index
    regular_data.sort(key=lambda x: x[2])
    seeds_data.sort(key=lambda x: x[2])
    
    # Create dictionaries for easier lookup
    regular_dict = {idx: (label, acc) for label, acc, idx in regular_data}
    seeds_dict = {idx: (label, acc) for label, acc, idx in seeds_data}
    
    # Get all agent indices
    all_indices = sorted(set(regular_dict.keys()) | set(seeds_dict.keys()))
    
    print("\n=== Agent Accuracy Comparison ===")
    print(f"{'Agent':<12} {'Augmented Dataset':<15} {'Seeds Dataset':<15} {'Difference':<12}")
    print("-" * 60)
    
    for idx in all_indices:
        label = regular_dict.get(idx, ("", 0))[0] or seeds_dict.get(idx, ("", 0))[0] or f"agent{idx}"
        regular_acc = regular_dict.get(idx, (None, None))[1]
        seeds_acc = seeds_dict.get(idx, (None, None))[1]
        
        regular_str = f"{regular_acc*100:6.1f}%" if regular_acc is not None else "N/A"
        seeds_str = f"{seeds_acc*100:6.1f}%" if seeds_acc is not None else "N/A"
        
        if regular_acc is not None and seeds_acc is not None:
            diff = (seeds_acc - regular_acc) * 100
            diff_str = f"{diff:+6.1f}%"
        else:
            diff_str = "N/A"
        
        print(f"{label:<12} {regular_str:<15} {seeds_str:<15} {diff_str:<12}")
    
    print("-" * 60)

if __name__ == "__main__":
    print("Creating agent accuracy comparison visualization...")
    
    try:
        # Print comparison table
        print_comparison_table()
        
        # Create comparison plot
        regular_data, seeds_data = create_comparison_plot()
        
        print(f"\nVisualization complete!")
        
        if regular_data:
            agents, accuracies = zip(*[(label, acc*100) for label, acc, _ in regular_data])
            print(f"Augmented Dataset - Agents: {' → '.join(agents)}")
            print(f"Augmented Dataset - Accuracies: {' → '.join([f'{acc:.1f}%' for acc in accuracies])}")
        
        if seeds_data:
            agents_seeds, accuracies_seeds = zip(*[(label, acc*100) for label, acc, _ in seeds_data])
            print(f"Seeds Dataset - Agents: {' → '.join(agents_seeds)}")
            print(f"Seeds Dataset - Accuracies: {' → '.join([f'{acc:.1f}%' for acc in accuracies_seeds])}")
        
    except Exception as e:
        print(f"Error creating visualization: {e}")
        import traceback
        traceback.print_exc()