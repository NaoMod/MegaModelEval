
import json
import re
import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import numpy as np
from pathlib import Path

# --- Style setup (unchanged from original) ---
plt.style.use('ggplot')
sns.set_palette('viridis')
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 14
plt.rcParams['axes.titlesize'] = 18
plt.rcParams['axes.labelsize'] = 16

SCRIPT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = SCRIPT_DIR / "outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

THREE_WAY_DIR = OUTPUT_DIR / "three_way_comparison"

DATASET_NAMES = ["Seed Dataset", "Megamodel-Guided Dataset", "ToolLLM Baseline Dataset"]
DATASET_COLORS = ['#4F81BD', '#2E8B57', '#C0504D']  # blue, green, red
DATASET_SHORT = ["Seed", "Megamodel", "ToolLLM"]


# ---------------------------------------------------------------------------
# Load the three-way CSVs
# ---------------------------------------------------------------------------

def load_three_way_data():
    single_path = THREE_WAY_DIR / "atl_single_tool_three_way_diversity.csv"
    multi_path = THREE_WAY_DIR / "atl_multi_tool_three_way_diversity.csv"

    if not single_path.exists() or not multi_path.exists():
        raise FileNotFoundError(
            f"Expected three-way comparison CSVs at {single_path} and {multi_path}. "
            f"Run diversity_compare_toolllm.py first."
        )

    single_df = pd.read_csv(single_path)
    multi_df = pd.read_csv(multi_path)
    return single_df, multi_df



def _count_seed_instructions(seed_file_path: Path) -> int:
    if not seed_file_path.exists():
        return 0
    content = seed_file_path.read_text()
    matches = re.findall(r'instruction="(.*?)",?\n', content, re.DOTALL)
    return len(matches)


def _count_json_instructions(json_path: Path) -> int:
    if not json_path.exists():
        return 0
    data = json.loads(json_path.read_text())
    return len([item for item in data if item.get("instruction")])


def _count_toolllm_split(json_path: Path) -> dict:
    if not json_path.exists():
        return {"single": 0, "multi": 0}
    data = json.loads(json_path.read_text())
    single, multi = 0, 0
    for item in data:
        if not item.get("instruction"):
            continue
        if "," in item.get("pattern", ""):
            multi += 1
        else:
            single += 1
    return {"single": single, "multi": multi}


def get_item_counts():
    """Returns {'single': {'Seed Dataset': N, 'Megamodel-Guided Dataset': N,
    'ToolLLM Baseline Dataset': N}, 'multi': {...}}"""
    single_seed_path = SCRIPT_DIR / "seeds" / "model_transformation_seeds" / "all_tools" / "single_tool_seeds.py"
    multi_seed_path = SCRIPT_DIR / "seeds" / "model_transformation_seeds" / "all_tools" / "multi_tool_seeds.py"
    megamodel_single_path = OUTPUT_DIR / "atl_tools" / "simple_500_dataset.json"
    megamodel_multi_path = OUTPUT_DIR / "atl_tools" / "multi_500_dataset.json"
    toolllm_path = OUTPUT_DIR / "toolllm_1000_dataset.json"

    toolllm_counts = _count_toolllm_split(toolllm_path)

    return {
        "single": {
            "Seed Dataset": _count_seed_instructions(single_seed_path),
            "Megamodel-Guided Dataset": _count_json_instructions(megamodel_single_path),
            "ToolLLM Baseline Dataset": toolllm_counts["single"],
        },
        "multi": {
            "Seed Dataset": _count_seed_instructions(multi_seed_path),
            "Megamodel-Guided Dataset": _count_json_instructions(megamodel_multi_path),
            "ToolLLM Baseline Dataset": toolllm_counts["multi"],
        },
    }


def get_value(df, col, metric):
    val = df.loc[df['Metric'] == metric, col].values
    if len(val) == 0 or str(val[0]) in ['N/A', 'NA', 'nan']:
        return np.nan
    return float(val[0])


def _plot_three_bar_group(ax, single_vals, multi_vals, title, value_fmt='{:.2f}'):
    """Plots 3 bars for single-tool + 3 bars for multi-tool, grouped, for one metric.
    single_vals / multi_vals: lists of 3 floats in DATASET_NAMES order (may contain nan)."""
    positions_single = [0, 0.3, 0.6]
    positions_multi = [1.3, 1.6, 1.9]

    all_positions = positions_single + positions_multi
    all_values = single_vals + multi_vals
    all_colors = DATASET_COLORS + DATASET_COLORS
    all_hatches = ['', '', ''] + ['///', '///', '///']

    plot_values = [v if not np.isnan(v) else 0 for v in all_values]
    bars = ax.bar(all_positions, plot_values, color=all_colors, width=0.28)

    finite_vals = [v for v in all_values if not np.isnan(v)]
    max_val = max(finite_vals) if finite_vals else 1.0

    for j, bar in enumerate(bars):
        bar.set_hatch(all_hatches[j])
        if not np.isnan(all_values[j]):
            ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max_val * 0.02,
                    value_fmt.format(all_values[j]), ha='center', va='bottom',
                    fontsize=10, fontweight='bold', rotation=0)
        else:
            ax.text(bar.get_x() + bar.get_width() / 2, max_val * 0.02,
                    'N/A', ha='center', va='bottom', fontsize=10, color='#999999', fontstyle='italic')

    ax.set_xticks([0.3, 1.6])
    ax.set_xticklabels(['Single Tool', 'Multi Tool'], fontsize=14, fontweight='bold')
    ax.set_ylim(0, max_val * 1.25 if max_val > 0 else 1)
    ax.set_title(title, fontsize=15, fontweight='bold')
    ax.spines[['top', 'right']].set_visible(False)


def _legend_handles():
    return [plt.Rectangle((0, 0), 1, 1, color=DATASET_COLORS[i], label=DATASET_NAMES[i])
            for i in range(3)]



def create_full_metric_comparison(single_df, multi_df, dataset_label="ATL Tools (Three-Way)"):
    metrics = ['Distance', 'Dispersion', 'Isocontour Radius',
               'Affinity (vs. Seeds)', 'Vocabulary Size', 'Unique 3-grams']

    fig, axs = plt.subplots(2, 3, figsize=(20, 11))
    axs = axs.flatten()
    plt.subplots_adjust(wspace=0.4, hspace=0.45)

    for i, metric in enumerate(metrics):
        ax = axs[i]

        if metric == 'Affinity (vs. Seeds)':
            # Only Megamodel-Guided and ToolLLM-Baseline have affinity values (Seed is N/A
            # by construction -- affinity is measured relative to the seed dataset itself).
            single_mm = get_value(single_df, 'Megamodel-Guided Dataset', metric)
            single_tl = get_value(single_df, 'ToolLLM Baseline Dataset', metric)
            multi_mm = get_value(multi_df, 'Megamodel-Guided Dataset', metric)
            multi_tl = get_value(multi_df, 'ToolLLM Baseline Dataset', metric)

            positions = [0, 0.3, 1.3, 1.6]
            values = [single_mm, single_tl, multi_mm, multi_tl]
            colors = [DATASET_COLORS[1], DATASET_COLORS[2], DATASET_COLORS[1], DATASET_COLORS[2]]
            hatches = ['', '', '///', '///']

            plot_values = [v if not np.isnan(v) else 0 for v in values]
            bars = ax.bar(positions, plot_values, color=colors, width=0.28)
            finite = [v for v in values if not np.isnan(v)]
            max_val = max(finite) if finite else 1.0
            for j, bar in enumerate(bars):
                bar.set_hatch(hatches[j])
                if not np.isnan(values[j]):
                    ax.text(bar.get_x() + bar.get_width() / 2, bar.get_height() + max_val * 0.02,
                            f'{values[j]:.3f}', ha='center', va='bottom', fontsize=10, fontweight='bold')
            ax.set_xticks([0.15, 1.45])
            ax.set_xticklabels(['Single Tool', 'Multi Tool'], fontsize=14, fontweight='bold')
            ax.set_ylim(0, max_val * 1.25 if max_val > 0 else 1)
            ax.set_title(metric, fontsize=15, fontweight='bold')
            ax.spines[['top', 'right']].set_visible(False)
            continue

        single_vals = [get_value(single_df, name, metric) for name in DATASET_NAMES]
        multi_vals = [get_value(multi_df, name, metric) for name in DATASET_NAMES]

        if metric in ('Vocabulary Size', 'Unique 3-grams'):
            _plot_three_bar_group(ax, single_vals, multi_vals, metric, value_fmt='{:.0f}')
        elif metric == 'Isocontour Radius':
            _plot_three_bar_group(ax, single_vals, multi_vals, metric, value_fmt='{:.4f}')
        else:
            _plot_three_bar_group(ax, single_vals, multi_vals, metric, value_fmt='{:.3f}')

    fig.legend(handles=_legend_handles(), loc='upper center', ncol=3,
               bbox_to_anchor=(0.5, 1.06), fontsize=13, frameon=False)
    fig.suptitle(f"Metrics for {dataset_label}", fontsize=20, fontweight='bold', y=1.10)
    plt.tight_layout()

    output_dir = SCRIPT_DIR / "experimentation_charts" / "three_way_comparison"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "metric_three_way_comparison_raw.png"
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved: {out_path}")


def create_normalized_lexical_comparison(single_df, multi_df, dataset_label="ATL Tools (Three-Way)"):
    counts = get_item_counts()

    metrics = ['Vocabulary Size', 'Unique 3-grams']
    fig, axs = plt.subplots(1, 2, figsize=(14, 6))
    plt.subplots_adjust(wspace=0.35)

    for i, metric in enumerate(metrics):
        ax = axs[i]

        single_raw = [get_value(single_df, name, metric) for name in DATASET_NAMES]
        multi_raw = [get_value(multi_df, name, metric) for name in DATASET_NAMES]

        single_norm = [
            (v / counts["single"][name]) if (not np.isnan(v) and counts["single"][name] > 0) else np.nan
            for v, name in zip(single_raw, DATASET_NAMES)
        ]
        multi_norm = [
            (v / counts["multi"][name]) if (not np.isnan(v) and counts["multi"][name] > 0) else np.nan
            for v, name in zip(multi_raw, DATASET_NAMES)
        ]

        _plot_three_bar_group(ax, single_norm, multi_norm, f"{metric}\n(per instruction)",
                               value_fmt='{:.2f}')

    fig.legend(handles=_legend_handles(), loc='upper center', ncol=3,
               bbox_to_anchor=(0.5, 1.1), fontsize=13, frameon=False)
    fig.suptitle(
        f"Lexical Diversity Normalized by Dataset Size -- {dataset_label}\n"
        f"(raw counts in the other chart scale with dataset size and are NOT directly "
        f"comparable across conditions; this view divides by item count)",
        fontsize=14, fontweight='bold', y=1.18
    )
    plt.tight_layout()

    output_dir = SCRIPT_DIR / "experimentation_charts" / "three_way_comparison"
    output_dir.mkdir(parents=True, exist_ok=True)
    out_path = output_dir / "metric_three_way_comparison_normalized_lexical.png"
    plt.savefig(out_path, dpi=300, bbox_inches='tight')
    plt.close(fig)
    print(f"Saved: {out_path}")

    # Also print the actual counts used, so the normalization is auditable, not opaque
    print("\nItem counts used for normalization:")
    print(f"  Single-tool: {counts['single']}")
    print(f"  Multi-tool:  {counts['multi']}")


def main():
    print("Loading three-way comparison data...")
    single_df, multi_df = load_three_way_data()

    print("Creating raw-metrics comparison (6 panels, 3 bars per group)...")
    create_full_metric_comparison(single_df, multi_df)

    print("Creating normalized lexical-diversity comparison (accounts for dataset size)...")
    create_normalized_lexical_comparison(single_df, multi_df)

    print(f"\nAll outputs saved to: {SCRIPT_DIR / 'experimentation_charts' / 'three_way_comparison'}")


if __name__ == "__main__":
    main()