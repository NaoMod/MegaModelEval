import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))

import asyncio
import json
import argparse
import random
from pathlib import Path
import datetime
from typing import List
from dotenv import load_dotenv
from scripts.run_agent_versions import populate_registry
from src.agents.workflow import WorkflowPlan
load_dotenv(Path(__file__).parent.parent / '.env')

from src.core.megamodel import MegamodelRegistry
from src.mcp_ext.client import MCPClient
from src.agents.execution import MCPInvocation
from src.agents.agent import MCPAgent

# UNCHANGED from run_agent_reduced_tools.py -- same 10 tools, same ablation.
TOOLS_TO_REMOVE = [
    "list_transformation_KM32EMF_tool",
    "apply_KM32EMF_transformation_tool",
    "list_transformation_MySQL2KM3_tool",
    "apply_MySQL2KM3_transformation_tool",
    "list_transformation_Families2Persons_tool",
    "apply_Families2Persons_transformation_tool",
    "list_transformation_XML2Ant_tool",
    "apply_XML2Ant_transformation_tool",
    "list_transformation_Make2Ant_tool",
    "apply_Make2Ant_transformation_tool"
]


def load_toolllm_dataset_split(file_name: str = "toolllm_1000_dataset.json") -> tuple[List[dict], List[dict]]:

    base_outputs = Path(__file__).parent.parent / "dataset generation" / "outputs"
    fpath = base_outputs / file_name
    try:
        with open(fpath, 'r') as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error loading dataset file {fpath}: {e}")
        return [], []

    if not isinstance(data, list):
        print(f"Warning: dataset at {fpath} is not a list; returning empty lists")
        return [], []

    single_items, multi_items = [], []
    for item in data:
        if not item.get("instruction"):
            continue
        if "," in item.get("pattern", ""):
            multi_items.append(item)
        else:
            single_items.append(item)

    print(f"Loaded {len(data)} total items from {fpath} -> "
          f"{len(single_items)} single-tool, {len(multi_items)} multi-tool")
    return single_items, multi_items


def sample_dataset(single_dataset: List[dict], multi_dataset: List[dict],
                   single_count: int = 100, multi_count: int = 100,
                   seed: int = 42) -> List[dict]:
    """UNCHANGED from run_agent_reduced_tools.py (this function already existed there but
    was never called in __main__ -- it is now actually used, see main() below)."""
    random.seed(seed)

    if len(single_dataset) >= single_count:
        sampled_single = random.sample(single_dataset, single_count)
    else:
        print(f"Warning: Only {len(single_dataset)} single-tool items available, using all")
        sampled_single = single_dataset

    if len(multi_dataset) >= multi_count:
        sampled_multi = random.sample(multi_dataset, multi_count)
    else:
        print(f"Warning: Only {len(multi_dataset)} multi-tool items available, using all")
        sampled_multi = multi_dataset

    return sampled_single + sampled_multi


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run agent evaluation with reduced tools on the ToolLLM-baseline dataset")
    parser.add_argument("--agent", type=str, default="agent2", help="Agent version to evaluate (e.g., agent2, agent3)")
    parser.add_argument("--single-count", type=int, default=100)
    parser.add_argument("--multi-count", type=int, default=100)
    parser.add_argument("--sample-seed", type=int, default=42,
                         help="IMPORTANT: confirm this matches the seed used when sampling "
                              "the seeds/megamodel ablation runs, or the three results are not "
                              "a controlled comparison.")
    args = parser.parse_args()

    async def main():
        registry = MegamodelRegistry()
        await populate_registry(registry)

        atl_server = registry.get_mcp_server("atl_server")
        if not atl_server or not atl_server.metadata.get("script_path"):
            print("ERROR: ATL server not properly configured. Check script path in registry.")
            return
        script_path = atl_server.metadata.get("script_path")

        print(f"\n=== Evaluating MCPAgent (reduced tools) on ToolLLM-baseline dataset ===\n")
        agent_name = "MCPAgent"
        all_execution_results: List[dict] = []
        agent = None
        try:
            agent = MCPAgent(registry)
            client = MCPClient()
            await client.connect_to_server(script_path)
            agent.executor.mcp_clients["atl_server"] = client

            # Same removal logic as run_agent_reduced_tools.py, unchanged.
            atl_tools = registry.tools_by_server.get("atl_server", [])
            original_atl_count = len(atl_tools)
            atl_tools = [tool for tool in atl_tools if getattr(tool, 'name', '') not in TOOLS_TO_REMOVE]
            removed_count = original_atl_count - len(atl_tools)
            registry.tools_by_server["atl_server"] = atl_tools
            print(f"Original ATL tools: {original_atl_count}")
            print(f"Removed tools: {removed_count}")
            print(f"Remaining ATL tools: {len(atl_tools)}")
            print(f"Tools removed: {TOOLS_TO_REMOVE}")
            print("=" * 50 + "\n")

            # CHANGED: load and sample the ToolLLM-baseline dataset instead of seedsdataset.json
            single_items, multi_items = load_toolllm_dataset_split("toolllm_1000_dataset.json")
            if not single_items and not multi_items:
                print("ERROR: No entries found in ToolLLM-baseline dataset, nothing to run.")
                return

            sampled_dataset = sample_dataset(
                single_items, multi_items,
                single_count=args.single_count, multi_count=args.multi_count,
                seed=args.sample_seed
            )
            print(f"Sampled {len(sampled_dataset)} instructions "
                  f"({args.single_count} single-tool + {args.multi_count} multi-tool target, "
                  f"seed={args.sample_seed})")

            print(f"\n-- Running {len(sampled_dataset)} sampled instructions from ToolLLM-baseline dataset --")
            for i, item in enumerate(sampled_dataset):
                instruction = item.get("instruction", "")
                pattern = item.get("pattern", "")
                apis = item.get("relevant_apis", [])
                api_names = [api.get("api_name", "") for api in apis]

                print(f"\n[{i+1}/{len(sampled_dataset)}] Running instruction: {instruction}")
                print(f"  Expected APIs: {api_names}")

                try:
                    plan = await asyncio.to_thread(agent.plan_workflow, instruction)
                    for step in plan.steps:
                        name = getattr(step, 'tool_name', '') or ''
                        if name.startswith(('apply_', 'list_transformation_')):
                            step.server_name = 'atl_server'
                except (asyncio.TimeoutError, Exception) as e:
                    print(f"\n\nWARNING: Planning timed out or failed for instruction {i+1}: {e}")
                    plan = WorkflowPlan(instruction)
                    plan.status = "planning_failed"

                try:
                    plan.start_execution()
                    session = agent.executor.registry.create_session()
                    session.start()
                    trace = session.create_new_trace()

                    results = []
                    for step in plan.steps:
                        step.status = "ready"
                        result = await agent.executor.execute_step_async(step)
                        results.append(result)
                        invocation = MCPInvocation(
                            tool_name=step.tool_name,
                            server_name=step.server_name,
                            arguments=step.parameters,
                            result=result.get("result", {}),
                            success=result.get("success", False)
                        )
                        trace.add_invocation(invocation)

                    plan.status = "completed"
                    session.end()

                    execution_result = {
                        "instruction": instruction,
                        "pattern": pattern,
                        "expected_apis": api_names,
                        "plan_steps": [
                            {
                                "tool_name": step.tool_name,
                                "server_name": step.server_name,
                                "parameters": step.parameters
                            } for step in plan.steps
                        ],
                        "execution_results": [],
                        "status": plan.status
                    }

                    timeout_occurred = plan.status == "timeout"

                    for idx, (step, result) in enumerate(zip(plan.steps, results)):
                        if timeout_occurred and idx == len(plan.steps):
                            continue

                        success = result.get('success', False)
                        result_data = result.get('result', {})
                        serialized_result = {
                            "tool_name": step.tool_name,
                            "success": success,
                            "error": result.get('error', '') if not success else ''
                        }
                        if success:
                            if hasattr(result_data, 'to_dict'):
                                serialized_result["result"] = result_data.to_dict()
                            elif hasattr(result_data, '__dict__'):
                                try:
                                    result_dict = result_data.__dict__
                                    if 'text' in result_dict:
                                        serialized_result["result"] = {"text": result_dict['text']}
                                    else:
                                        clean_dict = {}
                                        for k, v in result_dict.items():
                                            if isinstance(v, (str, int, float, bool, type(None))):
                                                clean_dict[k] = v
                                            else:
                                                clean_dict[k] = str(v)
                                        serialized_result["result"] = clean_dict
                                except Exception:
                                    serialized_result["result"] = str(result_data)
                            else:
                                serialized_result["result"] = str(result_data)
                        execution_result["execution_results"].append(serialized_result)

                    if timeout_occurred and len(results) > len(plan.steps):
                        timeout_result = results[-1]
                        execution_result["execution_results"].append({
                            "tool_name": "execution_timeout",
                            "success": False,
                            "error": timeout_result.get('error', 'Execution timed out')
                        })

                    all_execution_results.append(execution_result)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    print(f"Error during plan execution: {e}")
                    import traceback
                    traceback.print_exc()

                print("--- End Execution ---")

            if all_execution_results:
                outputs_dir = Path(__file__).parent.parent / "dataset generation" / "ablation_test"
                outputs_dir.mkdir(parents=True, exist_ok=True)
                try:
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                    output_filename = f"agent_execution_results_{agent_name}_toolllm_reduced_{timestamp}.json"
                    output_path = outputs_dir / output_filename
                    with open(output_path, 'w') as f:
                        json_str = json.dumps(all_execution_results, indent=2, default=lambda o: list(o) if isinstance(o, set) else str(o))
                        f.write(json_str)
                    print(f"\n{'='*60}")
                    print(f"Execution results saved to: {output_path}")
                    print(f"Agent: {agent_name}")
                    print(f"Tools removed: {len(TOOLS_TO_REMOVE)}")
                    print(f"Instructions evaluated: {len(all_execution_results)}")
                    print(f"{'='*60}\n")
                except Exception as e:
                    print(f"Error saving results for {agent_name}: {e}")
                    import traceback
                    traceback.print_exc()
        except BaseException as e:
            print(f"Error setting up or running {agent_name}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            try:
                for server_name, cli in getattr(agent, 'executor', object()).mcp_clients.items():
                    try:
                        if hasattr(cli, 'exit_stack'):
                            try:
                                await cli.exit_stack.aclose()
                            except BaseException:
                                pass
                    except BaseException:
                        pass
            except BaseException:
                pass
            try:
                await asyncio.sleep(0.2)
            except BaseException:
                pass

    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")