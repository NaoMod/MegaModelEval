import sys
import random
import asyncio
from pathlib import Path
WORKDIR = Path(__file__).resolve().parents[1]
if str(WORKDIR) not in sys.path:
    sys.path.insert(0, str(WORKDIR))
from pipeline import write_final_dataset
from src.core.megamodel import MegamodelRegistry
from scripts.run_agent_versions import populate_registry
from src.agents.agent import MCPAgent
from pipeline import (
    _serialize_historical_executions,
    _infer_capabilities_from_registry,
    discover_patterns,
    _build_type_graph,
    build_workflows,
    sample_apis,
    generate_single_tool_instructions,
    generate_multi_tool_instructions,
    generate_dataset_for_regression_testing
)


async def main() -> None:
    # 1. Get a populated registry
    registry = MegamodelRegistry()
    await populate_registry(registry)  # Now properly awaited!
    
    # # Then run the agent to generate some execution history
    # print("\nExecuting agent to generate history...")
    # agent = MCPAgent(registry)  # Use same registry instance

    # # # Ask the agent to transform Class to Relational 
    # user_goal = "transform this Class model /Users/zakariahachm/Downloads/llm-agents-mde/src/examples/class.xmi to a Relational model"
    # result = agent.run(user_goal)  # This will create session/traces in our registry
    
    # print("\nAgent execution completed. Now testing pipeline components...")

    # # Test 2: Type graph building
    print("\nTesting _build_type_graph:")
    # # Get tools and capabilities first
    atl_tools = registry.tools_by_server.get("atl_server", [])
    emf_tools = registry.tools_by_server.get("emf_server", [])
    tools = [
        {"name": getattr(t, "name", ""), "description": getattr(t, "description", "")}
        for t in [*atl_tools, *emf_tools]
    ]
    capabilities = _infer_capabilities_from_registry(registry, tools)
    
    type_graph = _build_type_graph(capabilities)
    
    print("\nTool Chains (Follow Edges):")
    for tool_name, followers in type_graph["follow_edges"].items():
        if followers:  # Only show tools that can be followed by others
            print(f"\n{tool_name} can be followed by:")
            for follower in followers:
                print(f"  {follower}")
    
    print("\nTool Dependencies (Precede Edges):")
    for tool_name, predecessors in type_graph["precede_edges"].items():
        if predecessors:  # Only show tools that have predecessors
            print(f"\n{tool_name} can be preceded by:")
            for pred in predecessors:
                print(f"  {pred}")

    # Test: Build all valid workflows from type graph
    print("\n" + "="*60)
    print("Testing build_workflows:")
    print("="*60)
    
    workflows = build_workflows(type_graph)
    print(f"\nTotal valid 2-tool workflows: {len(workflows)}")
    
    # Categorize workflows by type
    apply_apply = [w for w in workflows if w[0].startswith("apply_") and w[1].startswith("apply_")]
    apply_get = [w for w in workflows if w[0].startswith("apply_") and (w[1].startswith("get_") or w[1].startswith("list_"))]
    get_get = [w for w in workflows if (w[0].startswith("get_") or w[0].startswith("list_")) and (w[1].startswith("get_") or w[1].startswith("list_"))]
    get_apply = [w for w in workflows if (w[0].startswith("get_") or w[0].startswith("list_")) and w[1].startswith("apply_")]
    
    print(f"\n--- Workflow Breakdown ---")
    print(f"  apply → apply (type-compatible): {len(apply_apply)}")
    print(f"  apply → get (all combinations):  {len(apply_get)}")
    print(f"  get → get (excluding same tool): {len(get_get)}")
    print(f"  get → apply (all combinations):  {len(get_apply)}")
    
    # Show samples from each category
    print("\n--- Sample apply → apply (type-compatible chains) ---")
    for w in apply_apply[:5]:
        print(f"  {w[0]} -> {w[1]}")
    if len(apply_apply) > 5:
        print(f"  ... and {len(apply_apply) - 5} more")
    
    print("\n--- Sample apply → get ---")
    for w in apply_get[:5]:
        print(f"  {w[0]} -> {w[1]}")
    if len(apply_get) > 5:
        print(f"  ... and {len(apply_get) - 5} more")
    
    print("\n--- Sample get → get ---")
    for w in get_get[:5]:
        print(f"  {w[0]} -> {w[1]}")
    if len(get_get) > 5:
        print(f"  ... and {len(get_get) - 5} more")
    
    print("\n--- Sample get → apply ---")
    for w in get_apply[:5]:
        print(f"  {w[0]} -> {w[1]}")
    if len(get_apply) > 5:
        print(f"  ... and {len(get_apply) - 5} more")
    
    if len(workflows) > 10:
        print(f"  ... and {len(workflows) - 10} more workflows")

#     # # Test 3: Historical executions serialization
#     print("\nTesting _serialize_historical_executions:")
#     executions = _serialize_historical_executions(registry)
    
#     if not executions:
#         print("No execution history found.")
#     else:
#         print("\nFound execution history:")
#         for execution in executions:
#             print(f"\nSession: {execution['session_id']} (Status: {execution['status']})")
#             for trace in execution['traces']:
#                 print(f"\n  Trace: {trace['trace_id']}")
#                 for inv in trace['invocations']:
#                     success = "success" if inv['success'] else "failed"
#                     print(f"    {success} {inv['tool_name']} ({inv['server_name']}) at {inv['timestamp']}")

#     # # Test 4: Pattern Discovery
#     # print("\nTesting discover_patterns:")
#     # Get tools and capabilities first
#     atl_tools = registry.tools_by_server.get("atl_server", [])
#     emf_tools = registry.tools_by_server.get("emf_server", [])
#     tools = [
#         {"name": getattr(t, "name", ""), "description": getattr(t, "description", "")}
#         for t in [*atl_tools, *emf_tools]
#     ]
#     capabilities = _infer_capabilities_from_registry(registry, tools)
    
#     # Create components dictionary
#     components = {
#         "executions": executions,
#         "capabilities": capabilities,
#         "tools": tools
#     }
    
#     # First get patterns for insights
#     patterns_result = discover_patterns(components)
#     insights = {
#         "common_workflows": patterns_result["common_patterns"],
#         "type_graph": patterns_result["type_graph"]
#     }
    
#     # Test 5: Sample APIs
#     print("\nTesting sample_apis:")
#     sampled_apis = sample_apis(components, insights)
    
#     print("\nTop Ranked Tools (by usage frequency and connectivity):")
#     for i, api in enumerate(sampled_apis, 1):
#         name = api.get("name", "")
#         # Calculate scores for this tool
#         freq_score = sum(1 for pattern in patterns_result["common_patterns"] 
#                         for tool in pattern["tools"] if tool == name)
#         connectivity = len(patterns_result["type_graph"]["follow_edges"].get(name, [])) + \
#                       len(patterns_result["type_graph"]["precede_edges"].get(name, []))
        
#         print(f"\n{i}. {name}")
#         print(f"   Usage Frequency: {freq_score}")
#         print(f"   Connectivity Score: {connectivity}")
    
#     # Test 6: Generate Instructions for Top Tools
#     print("\nTesting generate_single_tool_instructions:")
    
#     instructions = generate_single_tool_instructions(
#         selected_apis=sampled_apis,
#         per_api=1,  # one instruction per tool
#         llm_max_calls=10  # allow up to 10 calls for our 10 tools
#     )
    
#     print("\nGenerated Instructions Dataset:")
#     for i, item in enumerate(instructions, 1):
#         print(f"\nInstruction {i}:")
#         print(f"Pattern: {item['pattern']}")
#         print(f"Instruction: {item['instruction']}")
#         print(f"API: {item['relevant_apis'][0]['api_name']}")
        
#     # Save the single-tool dataset
#     output_path = Path(__file__).parent / "outputs" / "single_tool_instructions.json"
#     write_final_dataset(instructions, output_path)
#     print(f"\nSingle-tool dataset saved to: {output_path}")

#     # Test 7: Generate Multi-Tool Instructions
#     print("\nTesting generate_multi_tool_instructions:")
    
#     multi_instructions = generate_multi_tool_instructions(
#         selected_apis=sampled_apis,
#         chain_len=2,  # two tools in sequence
#         per_item=1,   # one instruction per combination
#         llm_max_calls=5,  # allow up to 5 calls
#         enforce_type_compat=True,   # ensure tools can be chained
#         insights=insights  # pass the insights with graph and historical patterns
#     )
    
#     print("\nGenerated Multi-Tool Instructions Dataset:")
#     for i, item in enumerate(multi_instructions, 1):
#         print(f"\nInstruction {i}:")
#         print(f"Pattern: {item['pattern']}")
#         print(f"Instruction: {item['instruction']}")
#         apis = item['relevant_apis']
#         print(f"APIs: {' -> '.join(api['api_name'] for api in apis)}")
        
#     # Save the multi-tool dataset
#     multi_output_path = Path(__file__).parent / "outputs" / "multi_tool_instructions.json"
#     write_final_dataset(multi_instructions, multi_output_path)
#     print(f"\nMulti-tool dataset saved to: {multi_output_path}")
    
#     # Test 8: Test generate_dataset_for_regression_testing
#     print("\nTesting generate_dataset_for_regression_testing:")
    
#     # Prepare tools for testing - take 25 ATL tools
#     tools_for_testing_dicts = [
#         {"name": getattr(t, "name", ""), "description": getattr(t, "description", "")}
#         for t in atl_tools[:25]  # Take the first 25 ATL tools
#     ]
    
#     print(f"Selected {len(tools_for_testing_dicts)} ATL tools for instruction generation")
    
#     # Generate 25 random workflows for multi-tool instructions
#     # Each workflow consists of a get tool (list_transformation_*) followed by an apply tool
#     get_tools = [t["name"] for t in tools_for_testing_dicts if t["name"].startswith("list_transformation_")]
#     apply_tools = [t["name"] for t in tools_for_testing_dicts if t["name"].startswith("apply_")]
    
#     # Create 25 random workflows
#     random_workflows = []
#     for _ in range(25):
#         # Choose random get and apply tools
#         get_tool = random.choice(get_tools) if get_tools else None
#         apply_tool = random.choice(apply_tools) if apply_tools else None
        
#         if get_tool and apply_tool:
#             # Create a workflow with both tools
#             workflow = [get_tool, apply_tool]
#             random_workflows.append(workflow)
    
#     print(f"Generated {len(random_workflows)} random workflows for multi-tool instructions")
    
#     # Generate dataset using actual registry
#     regression_dataset = generate_dataset_for_regression_testing(
#         tools=tools_for_testing_dicts,
#         workflows=random_workflows,
#         per_api=2.0,      # Generate 2 instructions per tool (25 tools * 2 = 50 total single-tool instructions)
#         per_workflow=1.0, # Generate 1 instruction per workflow (25 workflows * 1 = 25 total multi-tool instructions)
#         registry=registry
#     )
    
#     print(f"\nGenerated {len(regression_dataset)} regression test examples")
#     # 
#     # Count single-tool and multi-tool instructions
#     single_tool_count = sum(1 for item in regression_dataset if len(item.get('relevant_apis', [])) == 1)
#     multi_tool_count = sum(1 for item in regression_dataset if len(item.get('relevant_apis', [])) > 1)
    
#     # Count apply and get operations for single-tool instructions
#     apply_ops = sum(1 for item in regression_dataset 
#                    if len(item.get('relevant_apis', [])) == 1 and item.get('pattern') == 'apply')
#     get_ops = sum(1 for item in regression_dataset 
#                   if len(item.get('relevant_apis', [])) == 1 and item.get('pattern') == 'get')
    
#     print(f"Single-tool instructions: {single_tool_count} (Apply: {apply_ops}, Get: {get_ops})")
#     print(f"Multi-tool instructions: {multi_tool_count}")
    
#     # Display a few examples of each type
#     if single_tool_count > 0:
#         print("\nSample Single-Tool Instructions (Apply):")
#         for i, item in enumerate(regression_dataset):
#             if item.get('pattern') == 'apply' and len(item.get('relevant_apis', [])) == 1:
#                 print(f"\n{i+1}. {item['instruction']}")
#                 if i >= 2:  # Show at most 3 examples
#                     break
        
#         print("\nSample Single-Tool Instructions (Get):")
#         for i, item in enumerate(regression_dataset):
#             if item.get('pattern') == 'get' and len(item.get('relevant_apis', [])) == 1:
#                 print(f"\n{i+1}. {item['instruction']}")
#                 if i >= 2:  # Show at most 3 examples
#                     break
    
#     if multi_tool_count > 0:
#         print("\nSample Multi-Tool Instructions:")
#         for i, item in enumerate(regression_dataset):
#             if len(item.get('relevant_apis', [])) > 1:
#                 print(f"\n{i+1}. {item['instruction']}")
#                 if i >= 2:  # Show at most 3 examples
#                     break
    
#     # Save the regression testing dataset
#     regression_output_path = Path(__file__).parent / "outputs" / "regression_testing_dataset.json"
#     write_final_dataset(regression_dataset, regression_output_path)
#     print(f"\nRegression testing dataset saved to: {regression_output_path}")
    
    
#     # Test 9: Generate only "get" single-tool instructions
#     print("\nTesting generation of 'get' single-tool instructions only:")
    
#     # Filter only the "get" type tools (list_transformation_* tools)
#     get_tools_only = [t for t in tools_for_testing_dicts if t["name"].startswith("list_transformation_")]
#     get_tools_sample = get_tools_only[:10]  # Take just 10 tools for this test
    
#     print(f"Selected {len(get_tools_sample)} 'get' tools for instruction generation")
    
#     # Generate dataset with only "get" tools
#     get_only_dataset = generate_single_tool_instructions(
#         selected_apis=get_tools_sample,
#         per_api=1,     # Generate 1 instruction per tool
#         llm_max_calls=10,  # Allow up to 10 calls (one per tool)
#         registry=registry,
#     )
    
#     print(f"\nGenerated {len(get_only_dataset)} 'get' tool instructions")
    
#     # Display examples of the generated instructions
#     print("\nSample 'Get' Tool Instructions:")
#     for i, item in enumerate(get_only_dataset):
#         print(f"\n{i+1}. {item['instruction']}")
#         print(f"   API: {item['relevant_apis'][0]['api_name']}")
#         if i >= 2:  # Show at most 3 examples
#             break
    
#     # Save the get-only dataset
#     get_only_output_path = Path(__file__).parent / "outputs" / "get_only_instructions.json"
#     write_final_dataset(get_only_dataset, get_only_output_path)
#     print(f"\n'Get' tool instructions dataset saved to: {get_only_output_path}")

if __name__ == "__main__":
    asyncio.run(main())
