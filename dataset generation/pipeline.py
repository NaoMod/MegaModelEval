import json
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple
import sys
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
import random
# Single-tool instruction seed examples
from seeds.all_tools.single_tool_seeds import SingleToolSeeds
# Multi-tool instruction seed examples
from seeds.all_tools.multi_tool_seeds import MultiToolSeeds
    

# --- 1) Start with a megamodel repository (populate registry) ---
def _norm_transfo_name(name: str) -> str:
    return (name or "").strip().lower()

def _infer_capabilities_from_registry(registry: MegamodelRegistry, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Discovers what models each transformation tool can process by looking up their input/output metamodel types in the registry. 
    Returns a list of dictionaries with tool_name, input_types, and output_types for each tool"""
    # Get transformation name -> (in_uri, out_uri) from registry
    transfo_types = {
        _norm_transfo_name(getattr(e, "name", "")): (
            getattr(getattr(e, "source_metamodel", None), "uri", None),
            getattr(getattr(e, "target_metamodel", None), "uri", None)
        )
        for e in registry.entities.values()
        if hasattr(e, "source_metamodel") or hasattr(e, "target_metamodel")
    }

    def get_tool_types(name: str) -> tuple[list, list]:
        if not name.startswith("apply_") or not name.endswith("_transformation_tool"):
            return [], []  # Non-apply tools (including list_*) have no strict types
        base = _norm_transfo_name(name[len("apply_"):-len("_transformation_tool")])
        in_uri, out_uri = transfo_types.get(base, (None, None))
        return ([in_uri] if in_uri else []), ([out_uri] if out_uri else [])

    return [
        {
            "tool_name": t.get("name", ""),
            "input_types": in_types,
            "output_types": out_types
        }
        for t in tools
        for in_types, out_types in [get_tool_types(t.get("name", ""))]
    ]


def _build_type_graph(capabilities: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build a simple type graph to find possible 2-tool chains. This enables finding valid 2-tool chains where the output of one tool feeds into the next.

    Returns dict with:
      - tool_io: {tool_name: {"in": set, "out": set}}
      - follow_edges: {tool_name: [tool_name,...]} where out intersects next.in
      - precede_edges: inverse of follow_edges

    The _build_type_graph function builds a dependency graph showing which transformation tools can be chained together based on type compatibility (i.e., the output of one tool matches the input of another).
    """
    tool_io: Dict[str, Dict[str, set]] = {}
    for c in capabilities or []:
        name = c.get("tool_name", "")
        ins = set(c.get("input_types", []) or [])
        outs = set(c.get("output_types", []) or [])
        tool_io[name] = {"in": ins, "out": outs}

    follow_edges: Dict[str, List[str]] = {k: [] for k in tool_io.keys()}
    names = list(tool_io.keys())
    for i, a in enumerate(names):
        for b in names:
            if a == b:
                continue
            if tool_io[a]["out"] and tool_io[a]["out"].intersection(tool_io[b]["in"]):
                follow_edges[a].append(b)
    precede_edges: Dict[str, List[str]] = {k: [] for k in tool_io.keys()}
    for a, bs in follow_edges.items():
        for b in bs:
            precede_edges[b].append(a)
    return {"tool_io": tool_io, "follow_edges": follow_edges, "precede_edges": precede_edges}


def build_workflows(type_graph: Dict[str, Any]) -> List[List[str]]:
    """Generate all valid 2-tool workflow chains from the type graph.
    
    Creates four types of workflow chains:
    1. apply → apply: Only type-compatible chains (from follow_edges where output matches input)
    2. apply → get: All combinations of apply tools followed by get tools
    3. get → get: All combinations of get tools (excluding same tool)
    4. get → apply: All combinations of get tools followed by apply tools
    
    Args:
        type_graph: The type graph returned by _build_type_graph containing
                   tool_io, follow_edges and precede_edges.
    
    Returns:
        A list of workflows, where each workflow is a list of 2 tool names
        [tool_A, tool_B] representing a valid chain.
    """
    workflows: List[List[str]] = []
    follow_edges = type_graph.get("follow_edges", {})
    tool_io = type_graph.get("tool_io", {})
    
    # Get all tool names and categorize them
    all_tools = list(tool_io.keys())
    apply_tools = [t for t in all_tools if t.startswith("apply_")]
    get_tools = [t for t in all_tools if t.startswith("get_") or t.startswith("list_")]
    
    # 1. apply -> apply: Only type-compatible chains (from follow_edges)
    for tool_a, followers in follow_edges.items():
        for tool_b in followers:
            if tool_a.startswith("apply_") and tool_b.startswith("apply_"):
                workflows.append([tool_a, tool_b])
    
    # 2. apply -> get: All combinations
    for apply_tool in apply_tools:
        for get_tool in get_tools:
            workflows.append([apply_tool, get_tool])
    
    # 3. get -> get: All combinations (excluding same tool)
    for get_tool_a in get_tools:
        for get_tool_b in get_tools:
            if get_tool_a != get_tool_b:
                workflows.append([get_tool_a, get_tool_b])
    
    # 4. get -> apply: All combinations
    for get_tool in get_tools:
        for apply_tool in apply_tools:
            workflows.append([get_tool, apply_tool])
    
    return workflows


def _serialize_historical_executions(registry: MegamodelRegistry) -> List[Dict[str, Any]]:
    """Extract successfully executed AgentTraces from the registry."""
    executions: List[Dict[str, Any]] = []
    for session_id, session in getattr(registry, "sessions", {}).items():
        traces_payload = []
        for trace in getattr(session, "execution_traces", []) or []:
            invocs = []
            for inv in getattr(trace, "invocations", []) or []:
                invocs.append({
                    "tool_name": getattr(inv, "tool_name", None),
                    "server_name": getattr(inv, "server_name", None),
                    "success": bool(getattr(inv, "success", False)),
                    "timestamp": getattr(getattr(inv, "timestamp", None), "isoformat", lambda: None)(),
                })
            traces_payload.append({
                "trace_id": getattr(trace, "trace_id", ""),
                "invocations": invocs,
            })
        executions.append({
            "session_id": session_id,
            "status": getattr(session, "status", "unknown"),
            "traces": traces_payload,
        })
    return executions


def discover_patterns(components: Dict[str, Any]) -> Dict[str, Any]:
    """Identify historical workflow patterns from successful AgentTraces.

    Returns a list of pattern entries with:
    - pattern: compact token chain (e.g., "get>apply")
    - tools: ordered list of tool names in the chain
    - count: frequency observed across traces
    """
    executions = components.get("executions", []) or []
    pattern_counter: Counter = Counter()
    pattern_examples: Dict[str, List[str]] = {}

    for sess in executions:
        for tr in sess.get("traces", []) or []:
            invocs = [i for i in tr.get("invocations", []) or [] if i.get("success")]
            if not invocs:
                continue
            tool_chain = [i.get("tool_name", "") for i in invocs if i.get("tool_name")]
            if not tool_chain:
                continue
            # Map tool names to coarse pattern tokens
            tokens = [_derive_api(t)[1] for t in tool_chain]
            pattern = ">".join(tokens)
            pattern_counter[pattern] += 1
            pattern_examples.setdefault(pattern, tool_chain)

    common_patterns = [
        {"pattern": pat, "tools": pattern_examples.get(pat, []), "count": cnt}
        for pat, cnt in pattern_counter.most_common()
    ]
    # Build type graph from MCPCapabilities
    type_graph = _build_type_graph(components.get("capabilities", []) or [])
    return {"common_patterns": common_patterns, "type_graph": type_graph}



def sample_apis(components: Dict[str, Any], insights: Dict[str, Any]) -> List[Dict[str, Any]]:
    # Prefer tools seen in historical patterns; add bias from type connectivity; fallback to first N tools.
    tools = components.get("tools", [])
    if not tools:
        return []
    # Pattern frequency
    freq: Dict[str, int] = {}
    for entry in insights.get("common_workflows", []) or []:
        for t in entry.get("tools", []) or []:
            freq[t] = freq.get(t, 0) + entry.get("count", 1)
    # Type connectivity (follow + precede degree)
    graph = insights.get("type_graph", {}) or {}
    follow = graph.get("follow_edges", {})
    precede = graph.get("precede_edges", {})
    degree: Dict[str, int] = {}
    for name in set(list(follow.keys()) + list(precede.keys())):
        degree[name] = len(follow.get(name, []) or []) + len(precede.get(name, []) or [])

    by_name = {t.get("name", ""): t for t in tools}
    def score(name: str) -> tuple:
        return (freq.get(name, 0), degree.get(name, 0))
    ranked_names = sorted(by_name.keys(), key=lambda n: score(n), reverse=True)
    ranked = [by_name[n] for n in ranked_names if n in by_name]
    # Deterministic tail
    fallback = [t for t in tools if t.get("name", "") not in by_name]
    return (ranked + fallback)[:10]


# --- Utilité: Instead of working with long tool names like "apply_Class2Relational_transformation_tool", We get simple patterns like "apply" or "get" 
def _derive_api(tool_name: str) -> Tuple[str, str]:
    if tool_name.startswith("list_transformation_") and tool_name.endswith("_tool"):
        base = tool_name[len("list_transformation_"):-len("_tool")]
        return f"{base}.get_tool", "get"
    if tool_name.startswith("apply_") and tool_name.endswith("_transformation_tool"):
        base = tool_name[len("apply_"):-len("_transformation_tool")]
        return f"{base}.apply", "apply"
    if tool_name.startswith("extract_"):
        # Map extract tools to "get" pattern since they retrieve information
        return f"model.{tool_name}", "get"
    return tool_name, "call"

def generate_single_tool_instructions(
    selected_apis: List[Dict[str, Any]],
    per_api: int = 1,
    llm_max_calls: int = 5,
    prompt: str | None = None,
    registry: MegamodelRegistry | None = None,
) -> List[Dict[str, Any]]:
    model_name = os.getenv("OPENAI_MODEL", "gpt-5-nano-2025-08-07")
    llm = ChatOpenAI(model=model_name, temperature=0.1, max_retries=2) if (ChatOpenAI and os.getenv("OPENAI_API_KEY")) else None
    items: List[Dict[str, Any]] = []
    if not selected_apis:
        return items
    
    # Map transformation name -> first sample source path from registry (if available)
    sample_by_name: Dict[str, str] = {}
    if registry is not None:
        for e in getattr(registry, "entities", {}).values():
            name = getattr(e, "name", None)
            samples = getattr(e, "sample_sources", None)
            if name and samples:
                key = str(name).strip().lower()
                if key not in sample_by_name and isinstance(samples, list) and samples:
                    sample_by_name[key] = samples[0]
    
    llm_calls = 0
    n = max(1, int(per_api))
    for tool in selected_apis:
        name, desc = tool.get("name", ""), tool.get("description", "")
        api_name, pattern = _derive_api(name)
        for _ in range(n):
            if llm is None or llm_calls >= llm_max_calls:
                continue
            
            # Default path
            model_path = "./examples/input.xmi"
            
            # Try to get real path from registry if available
            if pattern == "apply":
                base = api_name.split(".")[0].strip().lower()
                if base in sample_by_name:
                    model_path = sample_by_name[base]
            
            # Get seeds by pattern and select 3 from different levels
            all_seeds = SingleToolSeeds.get_seeds()
            pattern_seeds = [s for s in all_seeds if s.pattern == pattern]
            
            selected_seeds = []
            # Select random seeds from available pattern seeds
            if pattern_seeds:
                # Select up to 3 random seeds
                num_to_select = min(3, len(pattern_seeds))
                selected_seeds = random.sample(pattern_seeds, num_to_select)
            
            # Get instructions from selected seeds to use as examples
            seed_examples = "\n".join([f"- {s.instruction}" for s in selected_seeds])
            
            p = prompt or (
                f"You will be provided with a tool, its description, and expected operation. Your task is to generate a single instruction for using this tool.\n\n"
                f"Tool: {api_name}\n"
                f"Operation: {pattern}\n"
                f"Description: {desc}\n\n"
                f"Rules for {pattern} instructions:\n"
                "1. Use exactly one action verb\n"
                "2. Do not mention tool names\n"
                "3. Keep the instruction concise and focused\n"
                f"4. For 'apply': Include the specific target type and the exact path '{model_path}'\n"
                "5. Make instructions practical and concrete, not vague\n"
                "6. Include details about the source and target model types when relevant\n\n"
                "Example instructions:\n"
                f"{seed_examples}\n\n"
                "Generate your instruction that would make sense to a user who wants to work with these model transformations:"
            )
            
            try:
                msg = llm.invoke(p)
                instruction = getattr(msg, "content", str(msg)).strip()
                llm_calls += 1
            except Exception:
                continue

            items.append({
                "pattern": pattern,
                "instruction": instruction,
                "relevant_apis": [{"api_name": api_name, "arguments": model_path if pattern == "apply" else ""}],
            })
    return items

def generate_multi_tool_instructions(
    *,
    chain_len: int = 2,
    per_item: int = 1,
    llm_max_calls: int = 5,
    prompt: str | None = None,
    registry: MegamodelRegistry | None = None,
    workflows: List[List[str]] | None = None
) -> List[Dict[str, Any]]:
    """Generate instructions for using multiple tools in sequence.
    
    Directly uses provided workflows to create tool combinations.
    """
    model_name = os.getenv("OPENAI_MODEL", "gpt-5-nano-2025-08-07")
    llm = ChatOpenAI(model=model_name, temperature=0.2, max_retries=2) if (ChatOpenAI and os.getenv("OPENAI_API_KEY")) else None
    items: List[Dict[str, Any]] = []
    
    # Check if we have workflows
    if not workflows or len(workflows) == 0:
        return items
    
    # Map transformation name -> first sample source path from registry (if available)
    sample_by_name: Dict[str, str] = {}
    if registry is not None:
        for e in getattr(registry, "entities", {}).values():
            name = getattr(e, "name", None)
            samples = getattr(e, "sample_sources", None)
            if name and samples:
                key = str(name).strip().lower()
                if key not in sample_by_name and isinstance(samples, list) and samples:
                    sample_by_name[key] = samples[0]
    
    # Get all seeds once
    all_seeds = MultiToolSeeds.get_seeds()
    get_get_seeds = [s for s in all_seeds if s.pattern == "get, get"]
    get_apply_seeds = [s for s in all_seeds if s.pattern == "get, apply"]
    apply_get_seeds = [s for s in all_seeds if s.pattern == "apply, get"]
    apply_apply_seeds = [s for s in all_seeds if s.pattern == "apply, apply"]
    
    # Initialize
    llm_calls = 0
    
    # Process each workflow directly
    for workflow in workflows:
        if len(workflow) < chain_len:
            continue
            
        # Process each segment of length chain_len in the workflow
        for i in range(len(workflow) - chain_len + 1):
            tool_combo = workflow[i:i+chain_len]
            
            # Extract API info and patterns directly from tool names
            apis = []
            patterns = []
            model_paths = []
            tool_types = []
            
            for tool_name in tool_combo:
                api, pat = _derive_api(tool_name)
                # Default path
                model_path = "./examples/input.xmi" if pat == "apply" else ""
                
                # Try to get real path from registry if available
                if pat == "apply":
                    base = api.split(".")[0].strip().lower()
                    if base in sample_by_name:
                        model_path = sample_by_name[base]
                
                model_paths.append(model_path)
                apis.append({"api_name": api, "arguments": model_path if pat == "apply" else ""})
                patterns.append(pat)
                
                # Extract tool type info (split on first '2' only to handle names like XML2R2ML)
                if "2" in api:
                    parts = api.split(".")[0].split("2", 1)  # Split only on first '2'
                    if len(parts) == 2:
                        source, target = parts
                        tool_types.append(f"{source} to {target}")
                    else:
                        tool_types.append("model transformation")
                else:
                    tool_types.append("model transformation")
            
            pattern_key = ", ".join(patterns)
            
            # Generate instructions per combination
            for _ in range(max(1, int(per_item))):
                # Pattern mapping
                pattern_seeds_map = {
                    "get, get": get_get_seeds,
                    "get, apply": get_apply_seeds,
                    "apply, get": apply_get_seeds,
                    "apply, apply": apply_apply_seeds
                }
                
                # Select 3 seeds from matching pattern
                selected_seeds = []
                pattern_seeds = pattern_seeds_map.get(pattern_key, [])
                
                # Select random seeds from available pattern seeds
                if pattern_seeds:
                    num_to_select = min(3, len(pattern_seeds))
                    selected_seeds = random.sample(pattern_seeds, num_to_select)
                
                # Fill remaining slots if we don't have 3
                while len(selected_seeds) < 3:
                    other_patterns = [k for k in pattern_seeds_map.keys() if k != pattern_key]
                    for other_pat in other_patterns:
                        if len(selected_seeds) >= 3:
                            break
                        other_seeds = pattern_seeds_map[other_pat]
                        if other_seeds:
                            selected_seeds.append(random.choice(other_seeds))
                    break
                
                # Build the prompt with all three seeds
                seed_examples = "\n".join([f"- {s.instruction}" for s in selected_seeds])
                
                path_instructions = []
                for j, (pat, path) in enumerate(zip(patterns, model_paths)):
                    if pat == "apply":
                        path_instructions.append(f"Step {j+1} ('apply'): Include path '{path}'")
                
                # Update the prompt to include actual paths
                p = prompt or (
                    "You will be provided with a sequence of tools and their operations. Your task is to generate a single instruction that covers using these tools in sequence.\n\n"
                    f"Tool sequence: {' → '.join([api['api_name'] for api in apis])}\n"
                    f"Operations: {' → '.join(patterns)}\n"
                    f"Transformations: {' → '.join(tool_types)}\n\n"
                    "Rules for multi-step instructions:\n"
                    "1. Use exactly one verb for each step (two verbs total)\n"
                    "2. Do not mention tool names\n"
                    "3. Keep steps in the correct logical order\n"
                    f"4. Paths for 'apply' operations:\n   {chr(10).join(path_instructions) if path_instructions else '   No apply operations in this sequence'}\n"
                    "5. For 'get' operations: Focus on retrieving specific configuration information\n"
                    "6.For every 'apply' step explicitly state the TARGET model type produced (source model mention optional)\n"
                    "Three example instructions (various patterns):\n"
                    f"{seed_examples}\n\n"
                    "Generate your instruction that clearly connects the two operations in a meaningful way:"
                )
                
                # Generate the instruction
                instruction = ""
                try:
                    if llm and llm_calls < llm_max_calls:
                        msg = llm.invoke(p)
                        instruction = getattr(msg, "content", str(msg)).strip()
                        llm_calls += 1
                    else:
                        # Fallback instruction if no LLM is available or max calls reached
                        instruction = f"Using {patterns[0]} to process a {tool_types[0]} model, then {patterns[1]} to complete the transformation to {tool_types[1]}"
                except Exception:
                    # Fallback instruction
                    instruction = f"Using {patterns[0]} to process a {tool_types[0]} model, then {patterns[1]} to complete the transformation to {tool_types[1]}"
                
                # Add the instruction
                items.append({
                    "pattern": ">".join(patterns),
                    "instruction": instruction,
                    "relevant_apis": apis,
                })
    
    return items

def validate_dataset(examples: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    ok: List[Dict[str, Any]] = []
    for e in examples:
        if not isinstance(e, dict):
            continue
        instr = e.get("instruction")
        apis = e.get("relevant_apis", [])
        if instr and isinstance(apis, list) and apis and all(isinstance(a, dict) and a.get("api_name") for a in apis):
            ok.append(e)
    return ok

# --- 10) Final dataset ---
def write_final_dataset(examples: List[Dict[str, Any]], path: Path) -> None:
    path.write_text(json.dumps(examples, indent=2))

def create_output_examples(examples: List[Dict[str, Any]], path: Path) -> None:
    path.write_text(json.dumps(examples, indent=2))





def generate_dataset_for_regression_testing(
    *,
    tools: List[Dict[str, Any]],
    workflows: List[List[str]] | None = None,
    per_api: int = 1,
    per_workflow: int = 1,
    registry: MegamodelRegistry | None = None,
) -> List[Dict[str, Any]]:
    # Create a lookup dictionary for tools by name
    by_name = {t.get("name", ""): t for t in (tools or [])}
    
    # Initialize items list for collecting instructions
    items: List[Dict[str, Any]] = []
    
    # 1) First generate single-tool instructions
    if tools:
        # Remove excluded tools
        filtered_tools = tools.copy()
        if "extract_input_metamodel_name" in by_name:
            filtered_tools = [t for t in filtered_tools if t.get("name", "") != "extract_input_metamodel_name"]
        if "list_transformation_samples_tool" in by_name:
            filtered_tools = [t for t in filtered_tools if t.get("name", "") != "list_transformation_samples_tool"]

        single_items = generate_single_tool_instructions(
            selected_apis=filtered_tools,
            per_api=per_api,
            llm_max_calls=100,  # Increased to allow for more calls
            registry=registry,
        )
        
        items.extend(single_items)
    
    # 2) Build workflows from type graph if not provided
    if workflows is None and registry is not None:
        # Infer capabilities from registry and build type graph
        capabilities = _infer_capabilities_from_registry(registry, tools)
        type_graph = _build_type_graph(capabilities)
        workflows = build_workflows(type_graph)
    
    # 3) Generate multi-tool instructions from workflows
    if workflows:
        multi_items = generate_multi_tool_instructions(
            chain_len=2,
            per_item=per_workflow,
            llm_max_calls=100,  # Increased to allow for more calls
            registry=registry,
            workflows=workflows
        )
        
        items.extend(multi_items)

    # 4) Validate but don't limit to just 10 items
    items = validate_dataset(items)
    return items