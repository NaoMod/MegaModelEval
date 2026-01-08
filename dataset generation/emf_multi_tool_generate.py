
import sys
import json
import asyncio
import random
from pathlib import Path
from typing import List

WORKDIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(WORKDIR))
sys.path.insert(0, str(WORKDIR / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.core.megamodel import MegamodelRegistry
from scripts.run_agent_versions import populate_registry
from pipeline import generate_dataset_for_regression_testing, build_workflows, _infer_capabilities_from_registry, _build_type_graph

TARGET = 250  # Generate 250 multi-tool instructions
OUTPUT_FILE = Path(__file__).parent / "outputs" / "emf_multi_250_dataset.json"
REMAINDER_FILE = Path(__file__).parent / "outputs" / "emf_multi_250_remainder.json"

all_instructions: List[dict] = []
generated_count = 0


def load_existing_progress() -> bool:
    global all_instructions, generated_count
    if OUTPUT_FILE.exists():
        try:
            with open(OUTPUT_FILE, "r") as f:
                all_instructions = json.load(f)
            generated_count = len(all_instructions)
            print(f"Resuming from {generated_count} existing multi-tool instructions")
            return True
        except Exception as e:
            print(f"Could not load previous progress: {e}")
    return False


def save_progress() -> None:
    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    with open(OUTPUT_FILE, "w") as f:
        json.dump(all_instructions, f, indent=2)
    pct = (generated_count / TARGET) * 100 if TARGET else 0
    print(f"\nProgress saved: {generated_count}/{TARGET} ({pct:.1f}%) -> {OUTPUT_FILE}")

def save_remainder(remainder_instructions: List[dict]) -> None:
    REMAINDER_FILE.parent.mkdir(exist_ok=True)
    with open(REMAINDER_FILE, "w") as f:
        json.dump(remainder_instructions, f, indent=2)
    print(f"\nRemainder saved: {len(remainder_instructions)} -> {REMAINDER_FILE}")


def build_two_step_workflows(tool_names: List[str]) -> List[List[str]]:
    """Create 4 categories of two-step workflows for EMF tools.
    EMF tools are categorized as:
    - create_object, update_feature, delete_object, clear_feature (modification)
    - list_features, inspect_instance (inspection)
    - start_metamodel_session_stateless (session)
    """
    session_tools = []
    modify_tools = []
    inspect_tools = []
    
    for name in tool_names:
        if "start_metamodel" in name or "session" in name.lower():
            session_tools.append(name)
        elif "create" in name or "update" in name or "delete" in name or "clear" in name:
            modify_tools.append(name)
        elif "list" in name or "inspect" in name:
            inspect_tools.append(name)

    workflows: List[List[str]] = []
    
    def pairwise(a, b, limit=150):
        pairs = []
        for x in a:
            for y in b:
                pairs.append([x, y])
                if len(pairs) >= limit:
                    return pairs
        return pairs

    # Create workflow combinations
    workflows += pairwise(modify_tools, modify_tools, limit=120)      # modify -> modify
    workflows += pairwise(modify_tools, inspect_tools, limit=120)     # modify -> inspect
    workflows += pairwise(inspect_tools, modify_tools, limit=120)     # inspect -> modify
    workflows += pairwise(inspect_tools, inspect_tools, limit=120)    # inspect -> inspect

    random.shuffle(workflows)
    return workflows


async def main():
    global generated_count, all_instructions

    print(f"Generating {TARGET} multi-tool instructions (2-step) for EMF stateless server...")
    load_existing_progress()
    if generated_count >= TARGET:
        print("Target already satisfied.")
        return

    # Only generate the remainder if previous instructions exist
    remainder_needed = TARGET - generated_count
    if remainder_needed <= 0:
        print("No remainder needed.")
        return
    print(f"Generating remainder: {remainder_needed} instructions to reach {TARGET}")

    # Discover EMF stateless tools
    registry = MegamodelRegistry()
    await populate_registry(registry)
    
    emf_tools = registry.tools_by_server.get("emf_stateless", [])
    all_tools = emf_tools
    
    tools_dicts = [
        {"name": getattr(t, "name", ""), "description": getattr(t, "description", "")}
        for t in all_tools if getattr(t, "name", "")
    ]
    tool_names = [t["name"] for t in tools_dicts]
    print(f"Discovered {len(tool_names)} EMF stateless tools:")

    for tt in tool_names:
        print(f"- {tt}")

    # Build workflows
    capabilities = _infer_capabilities_from_registry(registry, tools_dicts)
    type_graph = _build_type_graph(capabilities)
    workflows = build_workflows(type_graph)
    
    if not workflows:
        print("No workflows built. Exiting.")
        return
    
    # Categorize for display
    modify_modify = [w for w in workflows if ("create" in w[0] or "update" in w[0] or "delete" in w[0]) and 
                                             ("create" in w[1] or "update" in w[1] or "delete" in w[1])]
    modify_inspect = [w for w in workflows if ("create" in w[0] or "update" in w[0] or "delete" in w[0]) and 
                                              ("list" in w[1] or "inspect" in w[1])]
    inspect_modify = [w for w in workflows if ("list" in w[0] or "inspect" in w[0]) and 
                                              ("create" in w[1] or "update" in w[1] or "delete" in w[1])]
    inspect_inspect = [w for w in workflows if ("list" in w[0] or "inspect" in w[0]) and 
                                               ("list" in w[1] or "inspect" in w[1])]
    
    print(f"\nWorkflow Breakdown:")
    print(f"  modify → modify: {len(modify_modify)}")
    print(f"  modify → inspect: {len(modify_inspect)}")
    print(f"  inspect → modify: {len(inspect_modify)}")
    print(f"  inspect → inspect: {len(inspect_inspect)}")
    print(f"  Total: {len(workflows)} candidate two-step workflows")

    # Track usage for each tool
    tool_counts = {name: 0 for name in tool_names}
    
    # Shuffle each category independently for variety
    random.shuffle(modify_modify)
    random.shuffle(modify_inspect)
    random.shuffle(inspect_modify)
    random.shuffle(inspect_inspect)
    
    # Calculate how many of each pattern we need for equal distribution
    per_pattern = remainder_needed // 4
    extra = remainder_needed % 4
    
    print(f"\nBalanced generation: {per_pattern} per pattern (+{extra} extra distributed)")

    # Load existing remainder progress if available
    remainder_instructions = []
    import os
    if os.path.exists(str(REMAINDER_FILE)):
        try:
            with open(REMAINDER_FILE, "r") as f:
                remainder_instructions = json.load(f)
            print(f"Loaded {len(remainder_instructions)} existing remainder instructions from {REMAINDER_FILE}")
        except Exception as e:
            print(f"Could not load previous remainder progress: {e}")

    # Count existing patterns in remainder
    pattern_counts = {"modify>modify": 0, "modify>inspect": 0, "inspect>modify": 0, "inspect>inspect": 0}
    for item in remainder_instructions:
        p = item.get("pattern", "")
        if p in pattern_counts:
            pattern_counts[p] += 1
    
    print(f"Existing pattern distribution: {pattern_counts}")

    # Create pattern queues with their workflows
    pattern_queues = {
        "modify>modify": {"workflows": modify_modify, "idx": 0},
        "modify>inspect": {"workflows": modify_inspect, "idx": 0},
        "inspect>modify": {"workflows": inspect_modify, "idx": 0},
        "inspect>inspect": {"workflows": inspect_inspect, "idx": 0},
    }
    
    # Round-robin through patterns to ensure equal distribution
    pattern_order = ["modify>modify", "modify>inspect", "inspect>modify", "inspect>inspect"]
    pattern_idx = 0
    
    while len(remainder_instructions) < remainder_needed:
        # Pick the pattern with the least count (to balance)
        current_pattern = min(pattern_order, key=lambda p: pattern_counts[p])
        queue = pattern_queues[current_pattern]
        
        if not queue["workflows"]:
            print(f"Warning: No workflows available for pattern {current_pattern}")
            pattern_order.remove(current_pattern)
            if not pattern_order:
                break
            continue
        
        # Get next workflow from this pattern (cycling through)
        workflow = queue["workflows"][queue["idx"] % len(queue["workflows"])]
        queue["idx"] += 1
        
        try:
            result = generate_dataset_for_regression_testing(
                tools=[],
                workflows=[workflow],
                per_api=0,
                per_workflow=1,
                registry=registry,
            )
            if result:
                for item in result:
                    instr_text = item.get("instruction", "")
                    if not instr_text:
                        continue
                    if any(existing.get("instruction") == instr_text for existing in all_instructions):
                        continue
                    if any(existing.get("instruction") == instr_text for existing in remainder_instructions):
                        continue
                    # Add pattern info and append
                    item["pattern"] = current_pattern
                    remainder_instructions.append(item)
                    pattern_counts[current_pattern] += 1
                    for t in workflow:
                        if t in tool_counts:
                            tool_counts[t] += 1
                    pct = ((generated_count + len(remainder_instructions)) / TARGET) * 100
                    preview = instr_text[:60].replace("\n", " ")
                    print(f"{generated_count + len(remainder_instructions)}/{TARGET} ({pct:.1f}%) [{current_pattern}] - {preview}...")
                    break
                if (generated_count + len(remainder_instructions)) % 10 == 0:
                    save_remainder(remainder_instructions)
                    print(f"  Pattern dist: {pattern_counts}")
            await asyncio.sleep(0.4)
        except Exception as e:
            print(f"Error processing workflow {workflow}: {e}")
            await asyncio.sleep(1.5)
        
        pattern_idx = (pattern_idx + 1) % len(pattern_order)

    save_remainder(remainder_instructions)
    print(f"\nDone. Generated {len(remainder_instructions)} EMF multi-tool instructions.")
    return


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
