
import sys
import json
from pathlib import Path
from dataclasses import asdict

# Adjust these two lines if your actual project layout differs from what's been shown so far.
PROJECT_ROOT = Path(__file__).resolve().parents[1]  # adjust if needed
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

OUT_DIR = Path(__file__).parent / "outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

from mcp_servers.atl_server.atl_mcp_server import (
    fetch_transformations,
    create_transformation_description,
    generate_get_tool_description,
)
from seeds.model_transformation_seeds.all_tools.single_tool_seeds import SingleToolSeeds
from seeds.model_transformation_seeds.all_tools.multi_tool_seeds import MultiToolSeeds


def build_tools_list():
    transformations = fetch_transformations()
    tools = []
    for t in transformations:
        name = t["name"]

        tools.append({
            "name": f"apply_{name}_transformation_tool",
            "description": create_transformation_description(name),
            "pattern": "apply",
            "arguments": ["file_path"],
        })

        tools.append({
            "name": f"list_transformation_{name}_tool",
            "description": generate_get_tool_description(name),
            "pattern": "get",
            "arguments": [],
        })

    return tools


def build_seed_list(seed_cls):
    """Seed dataclasses -> plain dicts. Keeps the real `level` field too (unused by
    toolllm_baseline.py but harmless and useful for inspection)."""
    return [asdict(s) for s in seed_cls.get_seeds()]


def main():
    print("Fetching real ATL transformations from the running ATL server...")
    tools = build_tools_list()
    print(f"  -> {len(tools)} tools derived ({len(tools)//2} apply + {len(tools)//2} get)")

    single_seeds = build_seed_list(SingleToolSeeds)
    multi_seeds = build_seed_list(MultiToolSeeds)
    print(f"  -> {len(single_seeds)} single-tool seeds, {len(multi_seeds)} multi-tool seeds")

    tools_path = OUT_DIR / "tools.json"
    single_path = OUT_DIR / "single_seeds.json"
    multi_path = OUT_DIR / "multi_seeds.json"

    tools_path.write_text(json.dumps(tools, indent=2))
    single_path.write_text(json.dumps(single_seeds, indent=2))
    multi_path.write_text(json.dumps(multi_seeds, indent=2))

    print(f"\nWrote:\n  {tools_path}\n  {single_path}\n  {multi_path}")
    print(
        f"\nNext: run toolllm_baseline.py with:\n"
        f"  python toolllm_baseline.py "
        f"--tools-file {tools_path} "
        f"--single-seeds-file {single_path} "
        f"--multi-seeds-file {multi_path} "
        f"--n-single-per-tool 1 --n-multi 2 --llm-max-calls 10 "
        f"--out outputs/smoke_test.json"
    )


if __name__ == "__main__":
    main()