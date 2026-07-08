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
    # workflow_ref concatenates tool names without separators, e.g.:
    # "workflow_apply_KM32EMF_tool_list_transformation_samples_tool"
    # We use a lookahead to split on known prefixes so each name is extracted
    # individually rather than merged into one non-matching token.
    # Strategy: insert virtual boundaries before each known prefix, then findall.
    prefixes = (
        r'apply_|list_transformation_|inspect_instance|create_object|'
        r'update_feature|delete_object|list_features|start_metamodel_session_'
        r'stateless|extract_input_metamodel_name|list_transformation_samples_'
        r'tool|clear_feature|get_session_info'
    )
    # Split the ref on transitions between known prefixes
    parts = re.split(r'(?=(?:' + prefixes + r'))', workflow_ref)
    tools = []
    for part in parts:
        m = re.match(
            r'((?:apply|list_transformation|inspect_instance|create_object|'
            r'update_feature|delete_object|list_features|start_metamodel_session'
            r'_stateless|extract_input_metamodel_name|list_transformation_'
            r'samples_tool|clear_feature)[a-z0-9_]*_tool)',
            part
        )
        if m:
            tools.append(m.group(1))
    return tools

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
    ("Redundant tool calls (same tool invoked >1x unnecessarily)",
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

print("=" * 65)
print("ERROR CATEGORIZATION — Megamodel Execution Traces (Section 5.3)")
print("=" * 65)
print(f"Total traces analyzed: {total}\n")
for label, count in rows:
    pct = 100 * count / total
    print(f"  {label}")
    print(f"    -> {count:4d} ({pct:.1f}%)")
    print()
print(f"Overall success rate: {100 * len(results['correct']) / total:.1f}%")
print(f"Overall error rate:   {100 * (total - len(results['correct'])) / total:.1f}%")


# ── Extended analysis 1: Single vs multi-tool breakdown ──────────────────────

print("\n" + "=" * 65)
print("SINGLE vs MULTI-TOOL BREAKDOWN")
print("=" * 65)

def all_ok(t):
    steps = t.get("trace_steps", [])
    return bool(steps) and all(s.get("success") for s in steps)

single_traces = [t for t in traces if t.get("workflow_ref", "").count("_tool") == 1]
multi_traces  = [t for t in traces if t.get("workflow_ref", "").count("_tool") > 1]
s_ok = sum(1 for t in single_traces if all_ok(t))
m_ok = sum(1 for t in multi_traces  if all_ok(t))

print(f"  Single-tool traces: {len(single_traces):4d}  "
      f"success: {s_ok}/{len(single_traces)} "
      f"({100*s_ok/max(len(single_traces),1):.1f}%)")
print(f"  Multi-tool traces:  {len(multi_traces):4d}  "
      f"success: {m_ok}/{len(multi_traces)} "
      f"({100*m_ok/max(len(multi_traces),1):.1f}%)")


# ── Extended analysis 2: Per-agent breakdown ─────────────────────────────────

print("\n" + "=" * 65)
print("PER-AGENT BREAKDOWN")
print("=" * 65)

# Handle two workflow schema versions in the same file:
# first entries use {"id": ..., "agent_ref": ...}
# later entries use {"workflow_id": ..., "workflow_steps": ...} with no agent_ref
wf_to_agent = {}
for w in data["workflows"]:
    wid   = w.get("id") or w.get("workflow_id", "")
    agent = w.get("agent_ref", "unknown")
    wf_to_agent[wid] = agent

agent_stats = {}
for t in traces:
    agent = wf_to_agent.get(t.get("workflow_ref", ""), "unknown")
    agent_stats.setdefault(agent, {"total": 0, "ok": 0, "steps": []})
    agent_stats[agent]["total"] += 1
    agent_stats[agent]["steps"].append(len(t.get("trace_steps", [])))
    if all_ok(t):
        agent_stats[agent]["ok"] += 1

for agent, s in agent_stats.items():
    avg = sum(s["steps"]) / len(s["steps"])
    print(f"  {agent}")
    print(f"    Traces: {s['total']}  "
          f"Correct: {s['ok']} ({100*s['ok']/s['total']:.1f}%)  "
          f"Avg steps/trace: {avg:.1f}")


# ── Extended analysis 3: Tool coverage ───────────────────────────────────────

print("\n" + "=" * 65)
print("TOOL COVERAGE")
print("=" * 65)

all_tools  = {t["name"] for t in data["tools"]}
exercised  = {s["tool_ref"]
              for t in traces
              for s in t.get("trace_steps", [])}
never_seen = all_tools - exercised

print(f"  Registered tools:    {len(all_tools)}")
print(f"  Exercised in traces: {len(exercised)}  ({100*len(exercised)/len(all_tools):.1f}%)")
print(f"  Never exercised:     {len(never_seen)}  ({100*len(never_seen)/len(all_tools):.1f}%)")
if never_seen:
    print(f"  Never-exercised tools (first 10):")
    for t_name in sorted(never_seen)[:10]:
        print(f"    {t_name}")


# ── Extended analysis 4: Tool invocation frequency ───────────────────────────

print("\n" + "=" * 65)
print("TOOL INVOCATION FREQUENCY")
print("=" * 65)

tool_freq = Counter(
    s["tool_ref"]
    for t in traces
    for s in t.get("trace_steps", [])
)
print("  Top 10 most invoked:")
for tool, count in tool_freq.most_common(10):
    print(f"    {count:4d}x  {tool}")
print("  Least invoked (bottom 5):")
for tool, count in sorted(tool_freq.items(), key=lambda x: x[1])[:5]:
    print(f"    {count:4d}x  {tool}")


# ── Extended analysis 5: Composition pattern distribution ────────────────────

print("\n" + "=" * 65)
print("COMPOSITION PATTERN DISTRIBUTION")
print("=" * 65)

def ptype(name):
    if name.startswith("apply_"):               return "Apply"
    if name.startswith("list_transformation"):  return "Get"
    return "Other"

patterns = Counter()
for t in traces:
    steps = t.get("trace_steps", [])
    if not steps:
        patterns["(no steps)"] += 1
        continue
    if len(steps) == 1:
        patterns[ptype(steps[0]["tool_ref"])] += 1
    else:
        p = " -> ".join(ptype(s["tool_ref"]) for s in steps[:2])
        patterns[p] += 1

for pat, count in patterns.most_common():
    print(f"  {pat}: {count:4d} ({100*count/total:.1f}%)")


# ── Extended analysis 6: Null-return probe calls ─────────────────────────────

print("\n" + "=" * 65)
print("NULL-RETURN INTERMEDIATE CALLS (is_error=True, step.success=True)")
print("=" * 65)
print(f"  Total: {len(null_return_invocations)}")
print("  These are recoverable agent probe calls (tool returns null,")
print("  agent recovers and continues). NOT counted as execution errors.")

null_tool_freq = Counter(r["tool"] for r in null_return_invocations)
print("  Top tools returning null:")
for tool, count in null_tool_freq.most_common(8):
    print(f"    {count:4d}x  {tool}")


# ── Extended analysis 7: Step count distribution ─────────────────────────────

print("\n" + "=" * 65)
print("STEP COUNT DISTRIBUTION (workflow complexity)")
print("=" * 65)

step_dist = Counter(all_step_counts)
for k in sorted(step_dist):
    bar = "█" * (step_dist[k] // 15)
    print(f"  {k:2d} steps: {step_dist[k]:4d} traces  {bar}")

avg_steps = sum(all_step_counts) / len(all_step_counts)
print(f"\n  Average steps/trace: {avg_steps:.2f}")
print(f"  Max steps in one trace: {max(all_step_counts)}")


# ── Extended analysis 8: Wrong-tool examples (for paper appendix) ────────────

if results["wrong_tool"]:
    print("\n" + "=" * 65)
    print(f"WRONG TOOL EXAMPLES (first 5 of {len(results['wrong_tool'])})")
    print("=" * 65)
    for ex in results["wrong_tool"][:5]:
        print(f"  Instruction: {ex['instruction']}")
        print(f"  Expected:    {ex['expected']}")
        print(f"  Called:      {ex['called']}")
        print()

if results["redundant"]:
    print("\n" + "=" * 65)
    print(f"REDUNDANT CALL EXAMPLES (first 5 of {len(results['redundant'])})")
    print("=" * 65)
    for ex in results["redundant"][:5]:
        print(f"  Instruction: {ex['instruction']}")
        print(f"  Duplicates:  {ex['duplicates']}")
        print()


# ── CSV output (extended) ────────────────────────────────────────────────────

csv_path = SCRIPT_DIR / "error_categorization_results_new.csv"
with open(csv_path, "w", newline="") as f:
    writer = csv.writer(f)

    writer.writerow(["=== ERROR CATEGORIES ==="])
    writer.writerow(["Category", "Count", "Percentage"])
    for label, count in rows:
        writer.writerow([label, count, f"{100 * count / total:.1f}%"])
    writer.writerow(["TOTAL", total, "100.0%"])
    writer.writerow([])

    writer.writerow(["=== SINGLE vs MULTI-TOOL ==="])
    writer.writerow(["Type", "Traces", "Success", "Success %"])
    writer.writerow(["Single-tool", len(single_traces), s_ok,
                     f"{100*s_ok/max(len(single_traces),1):.1f}%"])
    writer.writerow(["Multi-tool", len(multi_traces), m_ok,
                     f"{100*m_ok/max(len(multi_traces),1):.1f}%"])
    writer.writerow([])

    writer.writerow(["=== TOOL COVERAGE ==="])
    writer.writerow(["Metric", "Value"])
    writer.writerow(["Registered tools", len(all_tools)])
    writer.writerow(["Exercised tools", len(exercised)])
    writer.writerow(["Never-exercised tools", len(never_seen)])
    writer.writerow(["Coverage %", f"{100*len(exercised)/len(all_tools):.1f}%"])
    writer.writerow([])

    writer.writerow(["=== COMPOSITION PATTERNS ==="])
    writer.writerow(["Pattern", "Count", "Percentage"])
    for pat, count in patterns.most_common():
        writer.writerow([pat, count, f"{100*count/total:.1f}%"])
    writer.writerow([])

    writer.writerow(["=== STEP COUNT DISTRIBUTION ==="])
    writer.writerow(["Steps", "Traces"])
    for k in sorted(step_dist):
        writer.writerow([k, step_dist[k]])

print(f"\nCSV saved to: {csv_path}")


# ═══════════════════════════════════════════════════════════════════════════
# MODELING ENTITY ANALYSIS
# These sections surface why the megamodel is structurally superior to raw
# logs: the typed artifact graph, metamodel connectivity, chain reduction,
# and which type-compatible chains were actually exercised in real traces.
# None of this is derivable from flat execution logs alone.
# ═══════════════════════════════════════════════════════════════════════════

# ── M1: Build typed artifact graph from tool descriptions ────────────────────

print("\n" + "=" * 65)
print("M1. TYPED ARTIFACT GRAPH (Modeling Entity Analysis)")
print("=" * 65)
print("Source: tool descriptions in the megamodel")
print("(Raw logs record tool names only -- metamodel type links are")
print(" megamodel-specific and not available in flat execution logs.)\n")

apply_tools = [t for t in data["tools"] if t["name"].startswith("apply_")]
tool_pairs = {}
for t in apply_tools:
    desc = t.get("description", "")
    m = re.match(
        r".*?Input metamodel:\s*(\w+).*?Output metamodel:\s*(\w+)", desc
    )
    if m:
        tool_pairs[t["name"]] = {"source": m.group(1), "target": m.group(2)}

sources  = set(v["source"] for v in tool_pairs.values())
targets  = set(v["target"] for v in tool_pairs.values())
all_mms  = sources | targets

print(f"  Apply tools with typed source/target: {len(tool_pairs)} / {len(apply_tools)}")
print(f"  Unique source metamodels:             {len(sources)}")
print(f"  Unique target metamodels:             {len(targets)}")
print(f"  Total unique metamodels referenced:   {len(all_mms)}")
print(f"  Registered model entities:            {len(data['models'])}")


# ── M2: Type-compatible chain reduction ──────────────────────────────────────

print("\n" + "=" * 65)
print("M2. TYPE-COMPATIBLE CHAIN REDUCTION vs CARTESIAN PRODUCT")
print("=" * 65)

type_chains = []
for t1, v1 in tool_pairs.items():
    for t2, v2 in tool_pairs.items():
        if t1 != t2 and v1["target"] == v2["source"]:
            type_chains.append((t1, t2, v1["source"], v1["target"], v2["target"]))

cartesian_size = len(tool_pairs) * (len(tool_pairs) - 1)
reduction_pct  = 100 * (1 - len(type_chains) / max(cartesian_size, 1))

print(f"  Full Cartesian product (apply x apply, no filter): {cartesian_size}")
print(f"  Type-compatible chains (megamodel-filtered):        {len(type_chains)}")
print(f"  Reduction from type filtering:                      {reduction_pct:.1f}%")
print()
print("  This quantifies the megamodel's contribution over a simple Cartesian")
print("  product baseline: {:.0f}% of candidate pairs are semantically invalid".format(reduction_pct))
print("  (type-incompatible) and are excluded only because the megamodel's")
print("  TransformationModel entities carry source/target metamodel links.")
print("  A random-sampling baseline (e.g. ToolLLM-style) would include all")
print(f"  {cartesian_size} pairs, of which only {len(type_chains)} ({100*len(type_chains)/cartesian_size:.1f}%) are type-valid.")


# ── M3: Hub metamodel analysis ───────────────────────────────────────────────

print("\n" + "=" * 65)
print("M3. HUB METAMODEL ANALYSIS")
print("=" * 65)
print("  Metamodels that appear as intermediate type in the most chains")
print("  (high connectivity = high value in the typed artifact graph):\n")

hub_count = Counter()
for t1, t2, src, mid, tgt in type_chains:
    hub_count[mid] += 1

for mm, count in hub_count.most_common(10):
    pct = 100 * count / max(len(type_chains), 1)
    print(f"  {mm:20s}: {count:3d} chains ({pct:.1f}%)")


# ── M4: Which type-compatible chains were exercised in real traces ────────────

print("\n" + "=" * 65)
print("M4. TYPE-COMPATIBLE CHAINS EXERCISED IN REAL TRACES")
print("=" * 65)
print("  Cross-references typed artifact graph with actual execution traces.")
print("  Only possible via the megamodel -- flat logs have no type information.\n")

consecutive_pairs = Counter()
for t in traces:
    steps = [s["tool_ref"] for s in t.get("trace_steps", [])]
    for i in range(len(steps) - 1):
        consecutive_pairs[(steps[i], steps[i + 1])] += 1

exercised_chains = [
    (t1, t2, src, mid, tgt, consecutive_pairs[(t1, t2)])
    for t1, t2, src, mid, tgt in type_chains
    if consecutive_pairs.get((t1, t2), 0) > 0
]
unexercised_chains = [
    (t1, t2, src, mid, tgt)
    for t1, t2, src, mid, tgt in type_chains
    if consecutive_pairs.get((t1, t2), 0) == 0
]

print(f"  Type-compatible chains available:  {len(type_chains)}")
print(f"  Chains exercised in real traces:   {len(exercised_chains)} "
      f"({100*len(exercised_chains)/max(len(type_chains),1):.1f}%)")
print(f"  Chains never exercised (coverage gap): {len(unexercised_chains)} "
      f"({100*len(unexercised_chains)/max(len(type_chains),1):.1f}%)")
print()
print("  Most-exercised type-compatible chains:")
for t1, t2, src, mid, tgt, count in sorted(exercised_chains, key=lambda x: -x[5])[:10]:
    t1_short = t1.replace("apply_", "").replace("_transformation_tool", "")
    t2_short = t2.replace("apply_", "").replace("_transformation_tool", "")
    print(f"    {count:3d}x  {src} -> [{mid}] -> {tgt}  "
          f"({t1_short} -> {t2_short})")

if unexercised_chains:
    print(f"\n  Examples of type-valid but never-exercised chains (benchmark gaps):")
    for t1, t2, src, mid, tgt in unexercised_chains[:5]:
        t1_short = t1.replace("apply_", "").replace("_transformation_tool", "")
        t2_short = t2.replace("apply_", "").replace("_transformation_tool", "")
        print(f"    {src} -> [{mid}] -> {tgt}  ({t1_short} -> {t2_short})")
    print(f"  (These represent unexplored but semantically valid workflows --")
    print(f"   identifiable only via the megamodel's typed artifact graph.)")


# ── M5: Cross-query: which instructions cover which metamodels ───────────────

print("\n" + "=" * 65)
print("M5. METAMODEL COVERAGE ACROSS INSTRUCTIONS")
print("=" * 65)
print("  For each metamodel, how many execution traces involve a tool")
print("  that takes it as input or produces it as output.\n")

mm_coverage = Counter()
for t in traces:
    covered_mms = set()
    for s in t.get("trace_steps", []):
        tp = tool_pairs.get(s["tool_ref"], {})
        if tp.get("source"):
            covered_mms.add(tp["source"])
        if tp.get("target"):
            covered_mms.add(tp["target"])
    for mm in covered_mms:
        mm_coverage[mm] += 1

print(f"  Metamodels covered by at least 1 trace: "
      f"{sum(1 for v in mm_coverage.values() if v > 0)} / {len(all_mms)}")
print()
print("  Top 10 metamodels by trace coverage:")
for mm, count in mm_coverage.most_common(10):
    print(f"    {mm:20s}: {count:4d} traces")

uncovered = all_mms - set(mm_coverage.keys())
if uncovered:
    print(f"\n  Metamodels never touched by any trace: {sorted(uncovered)}")


# ── Append modeling entity data to CSV ───────────────────────────────────────

with open(csv_path, "a", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([])
    writer.writerow(["=== TYPED ARTIFACT GRAPH ==="])
    writer.writerow(["Metric", "Value"])
    writer.writerow(["Apply tools with typed source/target", len(tool_pairs)])
    writer.writerow(["Unique metamodels referenced", len(all_mms)])
    writer.writerow(["Full Cartesian product (apply x apply)", cartesian_size])
    writer.writerow(["Type-compatible chains", len(type_chains)])
    writer.writerow(["Reduction from type filtering", f"{reduction_pct:.1f}%"])
    writer.writerow(["Chains exercised in real traces", len(exercised_chains)])
    writer.writerow(["Chain coverage", f"{100*len(exercised_chains)/max(len(type_chains),1):.1f}%"])
    writer.writerow([])
    writer.writerow(["=== HUB METAMODELS ==="])
    writer.writerow(["Metamodel", "Chains through it", "% of all chains"])
    for mm, count in hub_count.most_common():
        writer.writerow([mm, count, f"{100*count/max(len(type_chains),1):.1f}%"])

print(f"\nModeling entity data appended to: {csv_path}")
print("\nDone.")