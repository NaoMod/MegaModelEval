"""This script generates a multi-tool dataset by creating
two-step workflows using various tools. It ensures balanced usage
of each tool across the generated instructions. The dataset is saved incrementally
to allow resumption in case of interruptions."""
import sys
import json
import asyncio
import random
from pathlib import Path
from typing import List

DATASET_GEN_DIR = Path(__file__).resolve().parents[2]  # dataset generation/
PROJECT_ROOT = Path(__file__).resolve().parents[3]  # project root
sys.path.insert(0, str(DATASET_GEN_DIR))
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.core.megamodel import MegamodelRegistry
from scripts.run_agent_versions import populate_registry
from pipeline import generate_dataset_for_regression_testing, _derive_api, build_workflows, _infer_capabilities_from_registry, _build_type_graph

TARGET = 500 # Generate 500 multi-tool instructions
OUTPUT_FILE = Path(__file__).parent / "outputs" / "atl_multi_500_dataset.json"
REMAINDER_FILE = Path(__file__).parent / "outputs" / "atl_multi_remainder.json"

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
    """Create 4 categories of two-step workflows: get->get, get->apply, apply->get, apply->apply.
    We first classify tool names by derived pattern from _derive_api.
    """
    recipe_apps = []
    recipe_infos = []
    for name in tool_names:
        api, pat = _derive_api(name)
        if pat == "recipe_application":
            recipe_apps.append(name)
        elif pat == "recipe_info":
            recipe_infos.append(name)

    workflows: List[List[str]] = []
    # Helper to sample pairs (limit size to avoid explosion)
    def pairwise(a, b, limit=150):
        pairs = []
        for x in a:
            for y in b:
                pairs.append([x, y])
                if len(pairs) >= limit:
                    return pairs
        return pairs

    workflows += pairwise(recipe_apps, recipe_apps, limit=120)       # recipe_application, recipe_application
    workflows += pairwise(recipe_apps, recipe_infos, limit=120)      # recipe_application, recipe_info
    workflows += pairwise(recipe_infos, recipe_apps, limit=120)      # recipe_info, recipe_application
    workflows += pairwise(recipe_infos, recipe_infos, limit=120)     # recipe_info, recipe_info

    random.shuffle(workflows)
    return workflows


async def main():
    global generated_count, all_instructions

    print(f"Generating {TARGET} multi-tool instructions (2-step)...")
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


    # Discover ATL tools only (exclude EMF tools like list_features, get_session_info)
    registry = MegamodelRegistry()
    await populate_registry(registry)
    
    atl_tools = registry.tools_by_server.get("atl_server", [])
    all_tools = atl_tools  # Only ATL tools, no EMF
    
    tools_dicts = [
        {"name": getattr(t, "name", ""), "description": getattr(t, "description", "")}
        for t in all_tools if getattr(t, "name", "")
    ]
    tool_names = [t["name"] for t in tools_dicts]
    print(f"Discovered {len(tool_names)} tools (ATL + EMF) usable for workflows:")

    for tt in tool_names:
        print(f"- {tt}")

    # Build workflows using the type graph (apply->apply type-compatible, all other combos)
    capabilities = _infer_capabilities_from_registry(registry, tools_dicts)
    type_graph = _build_type_graph(capabilities)
    workflows = build_workflows(type_graph)
    
    if not workflows:
        print("No workflows built. Exiting.")
        return
    
    # Categorize for display
    apply_apply = [w for w in workflows if w[0].startswith("apply_") and w[1].startswith("apply_")]
    apply_get = [w for w in workflows if w[0].startswith("apply_") and (w[1].startswith("get_") or w[1].startswith("list_"))]
    get_get = [w for w in workflows if (w[0].startswith("get_") or w[0].startswith("list_")) and (w[1].startswith("get_") or w[1].startswith("list_"))]
    get_apply = [w for w in workflows if (w[0].startswith("get_") or w[0].startswith("list_")) and w[1].startswith("apply_")]
    
    print(f"\nWorkflow Breakdown:")
    print(f"  apply → apply (type-compatible): {len(apply_apply)}")
    print(f"  apply → get (all combinations):  {len(apply_get)}")
    print(f"  get → get (excluding same tool): {len(get_get)}")
    print(f"  get → apply (all combinations):  {len(get_apply)}")
    print(f"  Total: {len(workflows)} candidate two-step workflows")

    # Track usage for each tool
    tool_counts = {name: 0 for name in tool_names}
    
    # Shuffle each category independently for variety
    random.shuffle(apply_apply)
    random.shuffle(apply_get)
    random.shuffle(get_get)
    random.shuffle(get_apply)
    
    # Calculate how many of each pattern we need for equal distribution
    per_pattern = remainder_needed // 4
    extra = remainder_needed % 4  # Handle remainder
    
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
    pattern_counts = {"apply>apply": 0, "apply>get": 0, "get>get": 0, "get>apply": 0}
    for item in remainder_instructions:
        p = item.get("pattern", "")
        if p in pattern_counts:
            pattern_counts[p] += 1
    
    print(f"Existing pattern distribution: {pattern_counts}")

    # Create pattern queues with their workflows
    pattern_queues = {
        "apply>apply": {"workflows": apply_apply, "idx": 0},
        "apply>get": {"workflows": apply_get, "idx": 0},
        "get>get": {"workflows": get_get, "idx": 0},
        "get>apply": {"workflows": get_apply, "idx": 0},
    }
    
    # Round-robin through patterns to ensure equal distribution
    pattern_order = ["apply>apply", "apply>get", "get>get", "get>apply"]
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
    print(f"\nDone. Generated {len(remainder_instructions)} Table multi-tool instructions.")
    return


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
