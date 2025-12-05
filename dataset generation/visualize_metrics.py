#!/usr/bin/env python3
"""
Dataset Metrics Visualization

This script creates visually appealing graphs from diversity metrics CSV files.
It visualizes the comparison between seed and generated datasets for both
single-tool and multi-tool scenarios (including lexical metrics).
"""

import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path

# --- Style setup ---
plt.style.use('ggplot')
sns.set_palette('viridis')
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 14  
plt.rcParams['axes.titlesize'] = 18 
plt.rcParams['axes.labelsize'] = 16 

# Output directory
OUTPUT_DIR = Path(__file__).resolve().parent / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)


def load_data(dataset_type="all"):
    """Load the CSV data files for specified dataset type"""
    if dataset_type == "uml":
        subdir = OUTPUT_DIR / "uml"
        single_tool_path = subdir / "single_uml_tool_comparison.csv"
        multi_tool_path = subdir / "multi_uml_tool_comparison.csv"
    elif dataset_type == "openrewrite":
        subdir = OUTPUT_DIR / "openRewrite"
        single_tool_path = subdir / "single_openRewrite_tool_comparison.csv"
        multi_tool_path = subdir / "multi_openRewrite_tool_comparison.csv"
    else:  # all tools (atl_tools)
        subdir = OUTPUT_DIR / "atl_tools"
        single_tool_path = subdir / "single_tool_comparison.csv"
        multi_tool_path = subdir / "multi_tool_comparison.csv"
    
    single_df = pd.read_csv(single_tool_path)
    multi_df = pd.read_csv(multi_tool_path)
    
    return single_df, multi_df

def create_full_metric_comparison(single_df, multi_df, dataset_label="ATL Tools"):
    metrics = [
        'Distance', 'Dispersion', 'Isocontour Radius',
        'Affinity', 'Vocabulary Size', 'Unique 3-grams'
    ]

    fig, axs = plt.subplots(2, 3, figsize=(18, 10))
    axs = axs.flatten()
    plt.subplots_adjust(wspace=0.4, hspace=0.4)

    def get_value(df, col, metric):
        val = df.loc[df['Metric'] == metric, col].values
        if len(val) == 0 or val[0] in ['N/A', 'NA']:
            return np.nan
        return float(val[0])

    for i, metric in enumerate(metrics):
        ax = axs[i]

        if metric == 'Affinity':
        # Only two bars
            single_val = get_value(single_df, 'Generated Dataset', metric)
            multi_val = get_value(multi_df, 'Generated Dataset', metric)
            if np.isnan(single_val) or np.isnan(multi_val):
                ax.text(0.5, 0.5, f"No data for {metric}", ha='center', va='center')
                ax.axis('off')
                continue

            values = [single_val, multi_val]
            labels = ['Single Tool', 'Multi Tool']
            colors = ['#4F81BD', '#4F81BD']
            alphas = [0.85, 0.45]
            hatches = ['', '///']

            bars = ax.bar([0, 1], values, color=colors, width=0.5)
            for j, bar in enumerate(bars):
                bar.set_alpha(alphas[j])
                bar.set_hatch(hatches[j])
                # Value labels
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(values)*0.01,
                        f'{values[j]:.2f}', ha='center', va='bottom', fontsize=14, fontweight='bold')  # Increased from 9

            ax.set_xticks([0, 1])
            ax.set_xticklabels(labels, fontsize=16, fontweight='bold')  # Increased from 14 and added bold
            ax.set_ylim(0, max(values) * 1.2)
            ax.set_title(metric, fontsize=16, fontweight='bold')  # Increased from 10
            ax.spines[['top', 'right']].set_visible(False)

        else:
            single_seed = get_value(single_df, 'Seed Dataset', metric)
            single_gen = get_value(single_df, 'Generated Dataset', metric)
            multi_seed = get_value(multi_df, 'Seed Dataset', metric)
            multi_gen = get_value(multi_df, 'Generated Dataset', metric)

            values = [single_seed, single_gen, multi_seed, multi_gen]
            positions = [0, 0.35, 1.0, 1.35]
            colors = ['#4F81BD', '#C0504D', '#4F81BD', '#C0504D']
            alphas = [0.85, 0.85, 0.45, 0.45]
            hatches = ['', '', '///', '///']

            bars = ax.bar(positions, [v if not np.isnan(v) else 0 for v in values],
                          color=colors, alpha=1.0, width=0.35)
            for j, bar in enumerate(bars):
                bar.set_alpha(alphas[j])
                bar.set_hatch(hatches[j])
                # Value labels
                if not np.isnan(values[j]):
                    # Use 3 decimal places for Isocontour Radius, 2 for others
                    format_str = f'{values[j]:.3f}' if metric == 'Isocontour Radius' else f'{values[j]:.2f}'
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(values)*0.01,
                            format_str, ha='center', va='bottom', fontsize=14, fontweight='bold')  # Increased from 9
                else:
                    ax.text(bar.get_x() + bar.get_width()/2, max(values)*0.01,
                            'N/A', ha='center', va='bottom', fontsize=14, color='#cccccc', fontstyle='italic')  # Increased from 9

            ax.set_xticks([0.175, 1.175])
            ax.set_xticklabels(['Single Tool', 'Multi Tool'], fontsize=16, fontweight='bold')  # Increased from 14 and added bold
            ax.set_ylim(0, np.nanmax(values) * 1.2)
            ax.set_title(metric, fontsize=16, fontweight='bold')  # Increased from 10
            ax.spines[['top', 'right']].set_visible(False)

    # Compose a title using the passed dataset label
    dataset_title = f"Metrics for {dataset_label} Single Tool and Multi Tool"
    fig.suptitle(dataset_title, fontsize=20, fontweight='bold', y=1.04)  # Increased from 16
    plt.tight_layout()
    
    # Determine output directory based on dataset label
    tool_type = dataset_label.lower().replace(' ', '_')
    output_dir = Path(__file__).parent / "experimentation_charts" / tool_type
    output_dir.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_dir / f"metric_{dataset_label}_comparison_final.png", dpi=300, bbox_inches='tight')


def create_selected_metrics_comparison(single_df, multi_df, dataset_label="ATL Tools"):
    """Create visualization with only Distance, Affinity, and Unique 3-grams"""
    metrics = ['Distance', 'Affinity', 'Unique 3-grams']

    fig, axs = plt.subplots(1, 3, figsize=(18, 6))
    plt.subplots_adjust(wspace=0.4, hspace=0.4)

    def get_value(df, col, metric):
        val = df.loc[df['Metric'] == metric, col].values
        if len(val) == 0 or val[0] in ['N/A', 'NA']:
            return np.nan
        return float(val[0])

    for i, metric in enumerate(metrics):
        ax = axs[i]

        if metric == 'Affinity':
            # Only two bars
            single_val = get_value(single_df, 'Generated Dataset', metric)
            multi_val = get_value(multi_df, 'Generated Dataset', metric)
            if np.isnan(single_val) or np.isnan(multi_val):
                ax.text(0.5, 0.5, f"No data for {metric}", ha='center', va='center')
                ax.axis('off')
                continue

            values = [single_val, multi_val]
            labels = ['Single Tool', 'Multi Tool']
            colors = ['#4F81BD', '#4F81BD']
            alphas = [0.85, 0.45]
            hatches = ['', '///']

            bars = ax.bar([0, 1], values, color=colors, width=0.5)
            for j, bar in enumerate(bars):
                bar.set_alpha(alphas[j])
                bar.set_hatch(hatches[j])
                # Value labels
                ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(values)*0.01,
                        f'{values[j]:.2f}', ha='center', va='bottom', fontsize=14, fontweight='bold')

            ax.set_xticks([0, 1])
            ax.set_xticklabels(labels, fontsize=16, fontweight='bold')
            ax.set_ylim(0, max(values) * 1.2)
            ax.set_title(metric, fontsize=16, fontweight='bold')
            ax.spines[['top', 'right']].set_visible(False)

        else:
            single_seed = get_value(single_df, 'Seed Dataset', metric)
            single_gen = get_value(single_df, 'Generated Dataset', metric)
            multi_seed = get_value(multi_df, 'Seed Dataset', metric)
            multi_gen = get_value(multi_df, 'Generated Dataset', metric)

            values = [single_seed, single_gen, multi_seed, multi_gen]
            positions = [0, 0.35, 1.0, 1.35]
            colors = ['#4F81BD', '#C0504D', '#4F81BD', '#C0504D']
            alphas = [0.85, 0.85, 0.45, 0.45]
            hatches = ['', '', '///', '///']

            bars = ax.bar(positions, [v if not np.isnan(v) else 0 for v in values],
                          color=colors, alpha=1.0, width=0.35)
            for j, bar in enumerate(bars):
                bar.set_alpha(alphas[j])
                bar.set_hatch(hatches[j])
                # Value labels
                if not np.isnan(values[j]):
                    ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + max(values)*0.01,
                            f'{values[j]:.2f}', ha='center', va='bottom', fontsize=14, fontweight='bold')
                else:
                    ax.text(bar.get_x() + bar.get_width()/2, max(values)*0.01,
                            'N/A', ha='center', va='bottom', fontsize=14, color='#cccccc', fontstyle='italic')

            ax.set_xticks([0.175, 1.175])
            ax.set_xticklabels(['Single Tool', 'Multi Tool'], fontsize=16, fontweight='bold')
            ax.set_ylim(0, np.nanmax(values) * 1.2)
            ax.set_title(metric, fontsize=16, fontweight='bold')
            ax.spines[['top', 'right']].set_visible(False)

    # Compose a title using the passed dataset label
    dataset_title = f"Selected Metrics for {dataset_label} Single Tool and Multi Tool"
    fig.suptitle(dataset_title, fontsize=20, fontweight='bold', y=1.04)
    plt.tight_layout()
    
    # Determine output directory based on dataset label
    tool_type = dataset_label.lower().replace(' ', '_')
    output_dir = Path(__file__).parent / "experimentation_charts" / tool_type
    output_dir.mkdir(parents=True, exist_ok=True)
    plt.savefig(output_dir / f"metric_{dataset_label}_selected_comparison.png", dpi=300, bbox_inches='tight')


def create_summary_dashboard():
    """Generate all visualizations in a single dashboard"""
    
    # Generate graphs for all three dataset types
    datasets = [
        ("all", "ATL Tools"),
        ("uml", "UML"), 
        ("openrewrite", "OpenRewrite")
    ]
    
    for dataset_type, dataset_label in datasets:
        try:
            print(f"Generating full visualization for {dataset_label}...")
            single_df, multi_df = load_data(dataset_type)
            create_full_metric_comparison(single_df, multi_df, dataset_label)
            print(f"{dataset_label} full visualization created successfully!")
            
            print(f"Generating selected metrics visualization for {dataset_label}...")
            create_selected_metrics_comparison(single_df, multi_df, dataset_label)
            print(f"{dataset_label} selected metrics visualization created successfully!")
        except FileNotFoundError as e:
            print(f"Skipping {dataset_label}: {e}")
        except Exception as e:
            print(f"Error creating {dataset_label} visualization: {e}")
    
    print(f"All outputs saved to: {OUTPUT_DIR}")


if __name__ == "__main__":
    create_summary_dashboard()
