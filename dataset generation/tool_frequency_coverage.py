e
import argparse
import json
import re
from collections import Counter
from pathlib import Path

# The 10 tools removed in the paper's Table 4 ablation test (Get + Apply per
# transformation = 20 tool names, but we track at the transformation-name level,
# matching the 5 transformations x 2 patterns described in the paper text).
ABLATION_TRANSFORMATIONS = [
    "KM32EMF",
    "MySQL2KM3",
    "Families2Persons",
    "XML2Ant",
    "Make2Ant",
]


def normalize_toolllm_name(api_name: str):
    m = re.match(r'^apply_(.+)_transformation_tool$', api_name)
    if m:
        return m.group(1)
    m = re.match(r'^list_transformation_(.+)_tool$', api_name)
    if m:
        return m.group(1)
    return None


def normalize_megamodel_name(api_name: str):
    if api_name.endswith(".apply"):
        return api_name[: -len(".apply")]
    if api_name.endswith(".get_tool"):
        return api_name[: -len(".get_tool")]
    return None


def count_frequencies(dataset_path: Path, normalizer):

    data = json.loads(dataset_path.read_text())
    counter = Counter()
    total = len(data)
    for entry in data:
        names_in_this_entry = set()
        for api in entry.get("relevant_apis", []):
            norm = normalizer(api.get("api_name", ""))
            if norm and norm != "samples":
                names_in_this_entry.add(norm)
        for name in names_in_this_entry:
            counter[name] += 1
    return counter, total


def pct(count, total):
    return f"{(100.0 * count / total):.1f}%" if total else "n/a"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--toolllm", required=True)
    ap.add_argument("--simple", required=True)
    ap.add_argument("--multi", required=True)
    ap.add_argument("--out-dir", required=True)
    args = ap.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    toolllm_counts, toolllm_total = count_frequencies(Path(args.toolllm), normalize_toolllm_name)
    simple_counts, simple_total = count_frequencies(Path(args.simple), normalize_megamodel_name)
    multi_counts, multi_total = count_frequencies(Path(args.multi), normalize_megamodel_name)

    megamodel_counts = simple_counts + multi_counts
    megamodel_total = simple_total + multi_total

    all_names = sorted(set(toolllm_counts) | set(megamodel_counts))

    print(f"{'Transformation':35s} {'ToolLLM (n='+str(toolllm_total)+')':>18s} {'Megamodel (n='+str(megamodel_total)+')':>20s}")
    print("-" * 80)
    for name in all_names:
        t_count = toolllm_counts.get(name, 0)
        m_count = megamodel_counts.get(name, 0)
        marker = "  <-- ABLATION TOOL" if name in ABLATION_TRANSFORMATIONS else ""
        print(f"{name:35s} {t_count:>6d} ({pct(t_count, toolllm_total):>6s}) {m_count:>6d} ({pct(m_count, megamodel_total):>6s}){marker}")

    print("\n=== ABLATION TOOLS SPECIFICALLY (paper Table 4) ===")
    print(f"{'Transformation':25s} {'ToolLLM count':>15s} {'Megamodel count':>18s}")
    for name in ABLATION_TRANSFORMATIONS:
        t_count = toolllm_counts.get(name, 0)
        m_count = megamodel_counts.get(name, 0)
        print(f"{name:25s} {t_count:>15d} {m_count:>18d}")

    # Distribution stats: min/median/max frequency per dataset, to characterize
    # "thin vs even" coverage at a glance.
    def dist_stats(counts, total_names_pool):
        values = sorted(counts.get(n, 0) for n in total_names_pool)
        n = len(values)
        if n == 0:
            return {}
        median = values[n // 2] if n % 2 == 1 else (values[n // 2 - 1] + values[n // 2]) / 2
        return {
            "min": values[0],
            "median": median,
            "max": values[-1],
            "tools_appearing_once_or_less": sum(1 for v in values if v <= 1),
        }

    toolllm_stats = dist_stats(toolllm_counts, all_names)
    megamodel_stats = dist_stats(megamodel_counts, all_names)

    print("\n=== DISTRIBUTION SUMMARY ===")
    print(f"ToolLLM:   min={toolllm_stats.get('min')} median={toolllm_stats.get('median')} max={toolllm_stats.get('max')} "
          f"tools_with<=1_instruction={toolllm_stats.get('tools_appearing_once_or_less')}")
    print(f"Megamodel: min={megamodel_stats.get('min')} median={megamodel_stats.get('median')} max={megamodel_stats.get('max')} "
          f"tools_with<=1_instruction={megamodel_stats.get('tools_appearing_once_or_less')}")

    summary = {
        "toolllm": {
            "total_entries": toolllm_total,
            "per_transformation_count": dict(toolllm_counts),
            "distribution": toolllm_stats,
        },
        "megamodel_combined": {
            "total_entries": megamodel_total,
            "per_transformation_count": dict(megamodel_counts),
            "distribution": megamodel_stats,
        },
        "ablation_tools_comparison": {
            name: {"toolllm": toolllm_counts.get(name, 0), "megamodel": megamodel_counts.get(name, 0)}
            for name in ABLATION_TRANSFORMATIONS
        },
    }

    out_path = out_dir / "tool_frequency_summary.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"\nWrote full summary to: {out_path}")


if __name__ == "__main__":
    main()