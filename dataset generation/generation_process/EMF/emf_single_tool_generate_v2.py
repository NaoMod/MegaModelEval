#!/usr/bin/env python3
"""
Script to generate single-tool instructions for EMF stateless server
"""

import sys
import json
import asyncio
import random
from pathlib import Path

# Add paths
DATASET_GEN_DIR = Path(__file__).resolve().parents[2]  # dataset generation/
PROJECT_ROOT = Path(__file__).resolve().parents[3]  # project root
sys.path.insert(0, str(DATASET_GEN_DIR))
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(Path(__file__).resolve().parent))

# Add src to path before imports
SRC_DIR = PROJECT_ROOT / "src"
sys.path.insert(0, str(SRC_DIR))

from src.core.megamodel import MegamodelRegistry
from scripts.run_agent_versions import populate_registry
from emf_pipeline import generate_emf_single_tool_instructions, validate_emf_dataset

TARGET = 250  # Generate 250 instructions
OUTPUT_FILE = Path(__file__).parent / "outputs" / "emf_single_250_dataset.json"

# Global variables
all_instructions = []
generated_count = 0

def save_progress():
    """Save current progress"""
    global all_instructions, generated_count
    OUTPUT_FILE.parent.mkdir(exist_ok=True)
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(all_instructions, f, indent=2)
    print(f"Progress saved: {generated_count}/{TARGET} ({generated_count/TARGET*100:.1f}%) to {OUTPUT_FILE}")

async def main():
    global all_instructions, generated_count
    
    print(f"Generating {TARGET} single-tool instructions for EMF...")
    all_instructions = []
    generated_count = 0

    try:
        # Initialize registry
        registry = MegamodelRegistry()
        print("Populating registry...")
        await populate_registry(registry)

        # Get EMF server tools (server name is 'emf_server')
        emf_tools = registry.tools_by_server.get("emf_server", [])
        emf_tools_list = []
        for t in emf_tools:
            tool_name = getattr(t, "name", "")
            if tool_name not in ["get_session_info", "list_session_objects"]:
                emf_tools_list.append({"name": tool_name, "description": getattr(t, "description", "")})
        
        print(f"\nFound {len(emf_tools_list)} EMF server tools:")
        for tool in emf_tools_list:
            print(f"  - {tool['name']}")
        
        if not emf_tools_list:
            print("ERROR: No EMF tools found")
            return
        
        # Distribute equally
        num_tools = len(emf_tools_list)
        per_tool = TARGET // num_tools
        remainder = TARGET % num_tools
        print(f"\nGenerating {per_tool} per tool + {remainder} extra = {TARGET} total\n")

        tool_counts = {tool['name']: 0 for tool in emf_tools_list}
        tool_order = emf_tools_list.copy()
        random.shuffle(tool_order)

        for idx, tool in enumerate(tool_order):
            extra = 1 if idx < remainder else 0
            count = per_tool + extra
            
            for attempt in range(count):
                try:
                    instructions = generate_emf_single_tool_instructions(
                        selected_apis=[tool],
                        per_api=1,
                        llm_max_calls=5,
                        registry=registry
                    )
                    
                    validated = validate_emf_dataset(instructions)
                    if validated:
                        all_instructions.extend(validated)
                        generated_count = len(all_instructions)
                        tool_counts[tool['name']] += 1
                        
                        preview = validated[0].get('instruction', '')[:60].replace('\n', ' ')
                        pct = (generated_count / TARGET) * 100
                        print(f"[{generated_count:2d}/{TARGET}] {pct:5.1f}% | {tool['name']:30s} | {preview}...")
                        
                        save_progress()
                    
                    await asyncio.sleep(0.3)
                    
                except Exception as e:
                    print(f"  Error on {tool.get('name')}: {e}")
                    await asyncio.sleep(1)

        print(f"\n{'='*70}")
        print(f"✓ Generated {generated_count} single-tool instructions")
        print(f"Tool distribution:")
        for name in sorted(tool_counts.keys()):
            count = tool_counts[name]
            pct = (count / generated_count * 100) if generated_count else 0
            print(f"  {name:30s}: {count:2d} ({pct:5.1f}%)")
        print(f"Output: {OUTPUT_FILE}")
        
    except KeyboardInterrupt:
        print(f"\nInterrupted at {generated_count} instructions")
        save_progress()
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
