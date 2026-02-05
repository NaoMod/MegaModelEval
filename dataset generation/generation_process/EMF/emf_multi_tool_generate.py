
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
from emf_pipeline import generate_emf_multi_tool_instructions, validate_emf_dataset

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

    remainder_needed = TARGET - generated_count
    if remainder_needed <= 0:
        print("No remainder needed.")
        return
    print(f"Generating remainder: {remainder_needed} instructions to reach {TARGET}")

    # Discover EMF tools
    registry = MegamodelRegistry()
    await populate_registry(registry)
    
    emf_tools = registry.tools_by_server.get("emf_server", [])
    all_tools = emf_tools
    
    tools_dicts = [
        {"name": getattr(t, "name", ""), "description": getattr(t, "description", "")}
        for t in all_tools if getattr(t, "name", "")
    ]
    tool_names = [t["name"] for t in tools_dicts]
    print(f"Discovered {len(tool_names)} EMF tools:")
    for tt in tool_names:
        print(f"- {tt}")

    # Build workflows
    workflows = build_two_step_workflows(tool_names)
    if not workflows:
        print("No workflows built. Exiting.")
        return
    
    print(f"Total: {len(workflows)} candidate two-step workflows")

    # Generate with LLM, save incrementally
    print(f"\nGenerating with LLM and saving incrementally...\n")
    
    llm_calls = 0
    max_calls = remainder_needed * 2
    
    for i in range(remainder_needed):
        if llm_calls >= max_calls:
            print(f"Reached max LLM calls ({max_calls})")
            break
        
        workflow = workflows[i % len(workflows)]
        
        print(f"[{i+1}/{remainder_needed}] Generating for workflow: {workflow}")
        
        multi_items = generate_emf_multi_tool_instructions(
            per_item=1,
            llm_max_calls=1,
            registry=registry,
            workflows=[workflow]
        )
        
        print(f"  LLM generated {len(multi_items)} items")
        
        validated = validate_emf_dataset(multi_items)
        
        print(f"  After validation: {len(validated)} valid items")
        
        if validated:
            for item in validated:
                if item not in all_instructions:
                    all_instructions.append(item)
                    generated_count += 1
                    llm_calls += 1
                    
                    # Save after each instruction
                    save_progress()
                    
                    instr_text = item.get("instruction", "")[:60].replace("\n", " ")
                    pct = (generated_count / TARGET) * 100
                    print(f"✓ [{generated_count}/{TARGET}] ({pct:.1f}%) - {instr_text}...")
                    
                    if generated_count >= TARGET:
                        break
        else:
            llm_calls += 1
            print(f"  ✗ No valid items generated")
        
        if generated_count >= TARGET:
            break
        
        await asyncio.sleep(0.3)
    
    print(f"\nDone. Generated {generated_count} EMF multi-tool instructions")
    return


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
