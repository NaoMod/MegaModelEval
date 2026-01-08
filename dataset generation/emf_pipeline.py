from pathlib import Path
from typing import Any, Dict, List, Tuple
import sys
import json
import os
import random

WORKDIR = Path(__file__).resolve().parents[1]
if str(WORKDIR) not in sys.path:
    sys.path.insert(0, str(WORKDIR))

from collections import Counter
ROOT = Path(__file__).resolve().parent
OUT = ROOT / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

from dotenv import load_dotenv
load_dotenv()

from langchain_openai import ChatOpenAI

SRC_DIR = WORKDIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from src.core.megamodel import MegamodelRegistry

# EMF-specific seed imports
from seeds.model_management_seeds.single_tool_seeds import SingleToolSeeds as EMFSingleToolSeeds
from seeds.model_management_seeds.multi_tool_seeds import MultiToolSeeds as EMFMultiToolSeeds


# EMF Tool Categorization
def _derive_emf_pattern(tool_name: str) -> Tuple[str, str]:
    """Derive the pattern and operation type for EMF tools.
    
    Returns: (tool_id, pattern_type)
    Patterns:
    - create: create_object, start_metamodel_session_stateless
    - update: update_feature, clear_feature
    - inspect: inspect_instance, list_features
    - delete: delete_object
    """
    if tool_name == "start_metamodel_session_stateless":
        return "session_start", "start_session"
    elif tool_name == "create_object":
        return "object_create", "create"
    elif tool_name in ["update_feature", "clear_feature"]:
        return "object_modify", "update"
    elif tool_name in ["inspect_instance", "list_features"]:
        return "object_inspect", "inspect"
    elif tool_name == "delete_object":
        return "object_delete", "delete"
    else:
        return tool_name, "unknown"


def build_emf_workflows(tool_names: List[str]) -> List[List[str]]:
    """Generate valid 2-tool workflow chains for EMF tools.
    Workflow categories:
    1. session_start → create: Initialize session and create object
    2. create → inspect: Create object and inspect it
    3. create → update: Create object and modify it
    4. inspect → update: Inspect and then update
    5. update → inspect: Update and verify with inspection
    6. create → delete: Create and delete (cleanup)
    
    Returns:
        List of valid [tool1, tool2] pairs
    """
    workflows: List[List[str]] = []
    
    session_tools = [t for t in tool_names if "start_metamodel" in t]
    create_tools = [t for t in tool_names if "create" in t]
    inspect_tools = [t for t in tool_names if "inspect" in t or "list_features" in t]
    update_tools = [t for t in tool_names if "update" in t or "clear" in t]
    delete_tools = [t for t in tool_names if "delete" in t]
    
    def pairwise(a, b, limit=100):
        pairs = []
        for x in a:
            for y in b:
                if x != y:  # Avoid same tool twice
                    pairs.append([x, y])
                    if len(pairs) >= limit:
                        return pairs
        return pairs
    
    # Build workflow combinations
    workflows += pairwise(session_tools, create_tools, limit=50)      # session → create
    workflows += pairwise(create_tools, inspect_tools, limit=100)     # create → inspect
    workflows += pairwise(create_tools, update_tools, limit=100)      # create → update
    workflows += pairwise(inspect_tools, update_tools, limit=100)     # inspect → update
    workflows += pairwise(update_tools, inspect_tools, limit=100)     # update → inspect
    workflows += pairwise(create_tools, delete_tools, limit=50)       # create → delete
    
    random.shuffle(workflows)
    return workflows


def _get_tool_arguments_template(tool_name: str) -> Dict[str, str]:
    """Get argument template for each tool type."""
    templates = {
        "start_metamodel_session_stateless": {"metamodel_file_path": "e.g., './ecore/Family.ecore'"},
        "create_object": {"session_id": "abc123", "class_name": "e.g., Package"},
        "update_feature": {"session_id": "abc123", "class_name": "e.g., Class", "object_id": "1", "feature_name": "e.g., visibility", "value": "e.g., public"},
        "inspect_instance": {"session_id": "abc123", "class_name": "e.g., Package", "object_id": "1"},
        "list_features": {"session_id": "abc123", "class_name": "e.g., Class"},
        "clear_feature": {"session_id": "abc123", "class_name": "e.g., Package", "object_id": "1", "feature_name": "e.g., version"},
        "delete_object": {"session_id": "abc123", "class_name": "e.g., Class", "object_id": "1"},
    }
    return templates.get(tool_name, {})


def generate_emf_single_tool_instructions(
    selected_apis: List[Dict[str, Any]],
    per_api: int = 1,
    llm_max_calls: int = 5,
    prompt: str | None = None,
    registry: MegamodelRegistry | None = None,
) -> List[Dict[str, Any]]:
    """Generate single-tool instructions with structured arguments.
    
    Args:
        selected_apis: List of tool dictionaries with 'name' and 'description'
        per_api: Number of instructions per tool
        llm_max_calls: Maximum LLM API calls
        prompt: Custom prompt template
        registry: MegamodelRegistry instance
    
    Returns:
        List of instruction dictionaries with instruction and relevant_apis (with arguments)
    """
    model_name = os.getenv("OPENAI_MODEL", "gpt-5-nano-2025-08-07")
    llm = ChatOpenAI(model=model_name, temperature=0.1, max_retries=2) if (ChatOpenAI and os.getenv("OPENAI_API_KEY")) else None
    items: List[Dict[str, Any]] = []
    
    if not selected_apis:
        return items
    
    llm_calls = 0
    n = max(1, int(per_api))
    
    for tool in selected_apis:
        name, desc = tool.get("name", ""), tool.get("description", "")
        tool_id, pattern_type = _derive_emf_pattern(name)
        
        for _ in range(n):
            if llm is None or llm_calls >= llm_max_calls:
                continue
            
            # Get argument template for this tool
            arg_template = _get_tool_arguments_template(name)
            arg_desc = json.dumps(arg_template, indent=2)
            
            # Get seeds matching this specific tool
            all_seeds = EMFSingleToolSeeds.get_seeds()
            tool_seeds = [s for s in all_seeds if name in s.pattern]
            
            if not tool_seeds:
                tool_seeds = random.sample(all_seeds, min(3, len(all_seeds)))
            
            selected_seeds = random.sample(tool_seeds, min(3, len(tool_seeds)))
            
            # Build seed examples with diverse values
            seed_examples = "\n".join([f"- {s.instruction}" for s in selected_seeds])
            
            p = prompt or (
                f"Generate an INSTRUCTION for this EMF tool.\n\n"
                f"Tool: {name}\n"
                f"Description: {desc}\n\n"
                f"Example instructions:\n{seed_examples}\n\n"
                f"Required Arguments (provide as JSON):\n{arg_desc}\n\n"
                f"RULE: Use different values for class names, session IDs, and object IDs. Do not repeat the same values.\n\n"
                f"OUTPUT FORMAT - Return ONLY valid JSON (no extra text, no trailing commas, no garbage after the closing brace):\n"
                f'{{"instruction": "your instruction here", "arguments": {{"arg1": "value1", "arg2": "value2"}}}}\n\n'
                f"IMPORTANT: Output ONLY the JSON object. No explanation, no extra text before or after.\n\n"
                f"Generate one instruction:"
            )
            
            try:
                msg = llm.invoke(p)
                response_text = getattr(msg, "content", str(msg)).strip()
                
                # Try to parse JSON from response
                try:
                    parsed = json.loads(response_text)
                    instruction = parsed.get("instruction", "").strip()
                    arguments = parsed.get("arguments", {})
                except json.JSONDecodeError:
                    # Fallback: extract first line as instruction
                    instruction = response_text.split("\n")[0]
                    arguments = {}
                
                # Handle case where arguments is a string (LLM returned JSON-as-string)
                if isinstance(arguments, str):
                    # Clean up: remove trailing commas, spaces, and extra text
                    cleaned_args = arguments.strip()
                    # Remove anything after the closing brace if it's JSON
                    if cleaned_args.startswith('{'):
                        # Find the last closing brace
                        last_brace = cleaned_args.rfind('}')
                        if last_brace != -1:
                            cleaned_args = cleaned_args[:last_brace + 1]
                    try:
                        arguments = json.loads(cleaned_args)
                    except (json.JSONDecodeError, ValueError):
                        arguments = {}
                
                llm_calls += 1
                
                if instruction:
                    # Extract arguments: only accept dict type
                    args_list = []
                    if isinstance(arguments, dict):
                        args_list = [str(v) for v in arguments.values()]
                    
                    # If arguments weren't properly parsed as dict, use template
                    if not args_list:
                        args_list = [str(v) for v in arg_template.values()]
                    
                    arguments_str = ", ".join(args_list)
                    
                    items.append({
                        "instruction": instruction,
                        "relevant_apis": [{
                            "api_name": name,
                            "arguments": arguments_str
                        }],
                    })
            except Exception as e:
                continue
    
    return items
    
    return items


def generate_emf_multi_tool_instructions(
    *,
    per_item: int = 1,
    llm_max_calls: int = 5,
    prompt: str | None = None,
    registry: MegamodelRegistry | None = None,
    workflows: List[List[str]] | None = None
) -> List[Dict[str, Any]]:
    """Generate multi-tool (2-step) instructions for EMF stateless server.
    
    Args:
        per_item: Number of instructions per workflow
        llm_max_calls: Maximum LLM API calls
        prompt: Custom prompt template
        registry: MegamodelRegistry instance
        workflows: List of [tool1, tool2] pairs for 2-step operations
    
    Returns:
        List of instruction dictionaries with pattern and relevant_apis
    """
    model_name = os.getenv("OPENAI_MODEL", "gpt-5-nano-2025-08-07")
    llm = ChatOpenAI(model=model_name, temperature=0.2, max_retries=2) if (ChatOpenAI and os.getenv("OPENAI_API_KEY")) else None
    items: List[Dict[str, Any]] = []
    
    if not workflows or len(workflows) == 0:
        return items
    
    # Get all seeds
    all_seeds = EMFMultiToolSeeds.get_seeds()
    
    llm_calls = 0
    
    # Process each workflow
    for workflow in workflows:
        tool_a, tool_b = workflow[0], workflow[1]
        pattern_a = _derive_emf_pattern(tool_a)[1]
        pattern_b = _derive_emf_pattern(tool_b)[1]
        combined_pattern = f"{pattern_a}→{pattern_b}"
        
        for _ in range(per_item):
            if llm is None or llm_calls >= llm_max_calls:
                continue
            
            # Find relevant seeds with both tools or similar patterns
            relevant_seeds = [s for s in all_seeds if tool_a in s.pattern and tool_b in s.pattern]
            if not relevant_seeds:
                # Fallback: use any 2-action seeds
                relevant_seeds = [s for s in all_seeds if "," in s.pattern]
            
            # Sample seeds to show both instruction and actual function calls
            selected_seeds = random.sample(relevant_seeds, min(2, len(relevant_seeds))) if relevant_seeds else []
            seed_examples = "\n".join([
                f"- Instruction: {s.instruction}\n  Functions: {s.pattern}"
                for s in selected_seeds[:2]
            ])
            
            p = prompt or (
                f"Generate a practical 2-step instruction for EMF model management workflow.\n\n"
                f"Step 1 Tool: {tool_a}\n"
                f"Step 2 Tool: {tool_b}\n"
                f"Workflow Type: {combined_pattern}\n\n"
                f"Guidelines:\n"
                "1. The instruction should logically chain two EMF operations\n"
                "2. Use concrete session IDs and object identifiers\n"
                "3. Make the workflow sequence realistic and practical\n"
                "4. Include relevant class names and property details\n"
                "5. Do not mention tool names\n\n"
                f"Example 2-step workflows:\n{seed_examples}\n\n"
                "Generate one cohesive instruction for this 2-step workflow:"
            )
            
            # Pick a random seed pattern for the actual function calls
            seed_pattern = random.choice(selected_seeds).pattern if selected_seeds else f"{tool_a}(...), {tool_b}(...)"
            
            try:
                msg = llm.invoke(p)
                instruction = getattr(msg, "content", str(msg)).strip()
                llm_calls += 1
            except Exception:
                instruction = f"Use {tool_a} followed by {tool_b}"

            items.append({
                "pattern": seed_pattern,  # Actual function calls with arguments
                "instruction": instruction,
                "relevant_apis": [
                    {"api_name": tool_a, "tool_id": _derive_emf_pattern(tool_a)[0]},
                    {"api_name": tool_b, "tool_id": _derive_emf_pattern(tool_b)[0]}
                ],
                "workflow_type": combined_pattern,
            })
    
    return items


def validate_emf_dataset(examples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Validate EMF dataset examples.
    
    Checks:
    - Non-empty instruction
    - Has relevant_apis with api_name and arguments
    """
    ok: List[Dict[str, Any]] = []
    for e in examples:
        instruction = e.get("instruction", "").strip()
        relevant_apis = e.get("relevant_apis", [])
        
        # Check if instruction exists and has valid apis with arguments
        if instruction and relevant_apis:
            # Validate each API has required fields
            valid_apis = []
            for api in relevant_apis:
                if api.get("api_name") and api.get("arguments"):
                    valid_apis.append(api)
            
            if valid_apis:
                ok.append({
                    "instruction": instruction,
                    "relevant_apis": valid_apis
                })
    
    return ok


def write_emf_dataset(examples: List[Dict[str, Any]], path: Path) -> None:
    """Write EMF dataset to JSON file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(examples, indent=2))


def generate_emf_dataset(
    *,
    tools: List[Dict[str, Any]],
    workflows: List[List[str]] | None = None,
    per_tool: int = 1,
    per_workflow: int = 1,
    registry: MegamodelRegistry | None = None,
) -> List[Dict[str, Any]]:
    """Generate complete EMF dataset with single-tool and multi-tool instructions.
    
    Args:
        tools: List of available EMF tools
        workflows: Pre-built 2-tool workflows
        per_tool: Instructions per tool
        per_workflow: Instructions per workflow
        registry: MegamodelRegistry instance
    
    Returns:
        Combined list of single-tool and multi-tool instructions
    """
    items: List[Dict[str, Any]] = []
    
    # 1) Generate single-tool instructions
    if tools:
        single_items = generate_emf_single_tool_instructions(
            selected_apis=tools,
            per_api=per_tool,
            registry=registry
        )
        items.extend(single_items)
    
    # 2) Generate multi-tool instructions
    if workflows:
        multi_items = generate_emf_multi_tool_instructions(
            per_item=per_workflow,
            registry=registry,
            workflows=workflows
        )
        items.extend(multi_items)
    
    # 3) Validate
    validated_items = validate_emf_dataset(items)
    
    return validated_items
