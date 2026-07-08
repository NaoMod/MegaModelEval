import json
import re
import csv
from pathlib import Path
from collections import Counter

# ── Load ─────────────────────────────────────────────────────────────────────

SCRIPT_DIR = Path(__file__).resolve().parent
JSON_PATH = SCRIPT_DIR / "unified_megamodel.json"

print(f"Loading {JSON_PATH} ...")
with open(JSON_PATH) as f:
    data = json.load(f)

traces = data["execution_traces"]
total = len(traces)
print(f"Loaded {total} execution traces.\n")


# ── Category definitions ──────────────────────────────────────────────────────
#
# For each trace we derive the expected tool set from workflow_ref, then compare
# against what the agent actually called.
#
# Categories (mutually exclusive, applied in priority order):
#   1. Planning failure   -- no steps at all
#   2. Execution failure  -- at least one step has success=False
#   3. Wrong tool         -- no called tool appears in workflow_ref
#   4. Wrong sequence     -- right tools, right count, but wrong order
#   5. Redundant calls    -- same tool called more times than expected
#   6. Correct            -- everything matches

def extract_expected_tools(workflow_ref: str) -> list:
    return re.findall(
        r'(?:apply|list_transformation|inspect_instance|create_object|'
        r'update_feature|delete_object|list_features|start_metamodel_session'
        r'|extract_input_metamodel_name)[a-z0-9_]*_tool',
        workflow_ref
    )

results = {
    "correct": [],
    "redundant": [],
    "wrong_tool": [],
    "wrong_sequence": [],
    "planning_failed": [],
    "execution_failed": [],
}

null_return_invocations = []   # is_error=True but step.success=True, content=null
all_step_counts = []

for t in traces:
    steps     = t.get("trace_steps", [])
    wf_ref    = t.get("workflow_ref", "")
    instr     = t.get("instruction", "")

    all_step_counts.append(len(steps))

    # Collect null-return intermediate calls
    for s in steps:
        for inv in s.get("invocations", []):
            if inv.get("is_error") and inv.get("content") in (None, "null", ""):
                null_return_invocations.append({
                    "instruction": instr[:80],
                    "tool": s["tool_ref"],
                    "step_success": s.get("success"),
                })

    # ── Category 1: Planning failure ──
    if not steps:
        results["planning_failed"].append(t)
        continue

    # ── Category 2: Execution failure ──
    if any(not s.get("success", True) for s in steps):
        results["execution_failed"].append(t)
        continue

    called_tools    = [s["tool_ref"] for s in steps]
    expected_tools  = extract_expected_tools(wf_ref)

    # ── Category 3: Wrong tool ──
    # None of the called tools appear in the expected set at all
    if expected_tools and not set(called_tools).intersection(set(expected_tools)):
        results["wrong_tool"].append({
            "instruction": instr[:80],
            "expected": expected_tools,
            "called": called_tools,
        })
        continue

    # ── Category 4: Wrong sequence ──
    # Same tools, same count, but different order
    if (expected_tools
            and len(called_tools) == len(expected_tools)
            and sorted(called_tools) == sorted(expected_tools)
            and called_tools != expected_tools):
        results["wrong_sequence"].append({
            "instruction": instr[:80],
            "expected": expected_tools,
            "called": called_tools,
        })
        continue

    # ── Category 5: Redundant calls ──
    # Same tool appears more times than expected, and the instruction does not
    # explicitly ask for multiple invocations of the same tool
    call_counts     = Counter(called_tools)
    expected_counts = Counter(expected_tools) if expected_tools else Counter()
    multi_keywords  = ["both", "two", "multiple", "each", "all", "and then again"]

    redundant = any(
        call_counts[tool] > max(expected_counts.get(tool, 1), 1)
        for tool in called_tools
        if not any(kw in instr.lower() for kw in multi_keywords)
    )
    if redundant:
        results["redundant"].append({
            "instruction": instr[:80],
            "tools": called_tools,
            "duplicates": {k: v for k, v in call_counts.items() if v > 1},
        })
        continue

    # ── Category 6: Correct ──
    results["correct"].append(t)


# ── Print report ─────────────────────────────────────────────────────────────

rows = [
    ("Correct (right tool, right sequence, all succeeded)",
     len(results["correct"])),
    ("Redundant tool calls (same tool invoked >1× unnecessarily)",
     len(results["redundant"])),
    ("Planning failure (agent produced no steps)",
     len(results["planning_failed"])),
    ("Execution failure (tool invocation returned error)",
     len(results["execution_failed"])),
    ("Wrong tool selected",
     len(results["wrong_tool"])),
    ("Correct tools, wrong execution sequence",
     len(results["wrong_sequence"])),
]


# ── CSV output ───────────────────────────────────────────────────────────────

csv_path = SCRIPT_DIR / "error_categorization_results.csv"
with open(csv_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["Error Category", "Count", "Percentage"])
    for label, count in rows:
        writer.writerow([label, count, f"{100 * count / total:.1f}%"])
    writer.writerow(["TOTAL", total, "100.0%"])

print(f"\nCSV saved to: {csv_path}")

