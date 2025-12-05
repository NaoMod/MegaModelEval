import sys
import os
# Ensure src is on sys.path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'src')))
import asyncio
import json
import subprocess
import argparse
from pathlib import Path
import datetime
import importlib.util
from typing import List
from dotenv import load_dotenv
from agents.workflow import WorkflowPlan
# Load environment variables from .env file
load_dotenv(Path(__file__).parent / '.env')
# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

# Import project modules
from mcp_servers.atl_server.atl_mcp_server import fetch_transformations
from core.megamodel import MegamodelRegistry
from core.am3 import ReferenceModel, TransformationModel
from mcp_ext.integrator import MCPServerIntegrator
from mcp_ext.client import MCPClient
from agents.execution import MCPInvocation

async def populate_registry(registry):
    integrator = MCPServerIntegrator(registry)
    

    # Get server script paths
    atl_server_script = os.path.join(os.path.dirname(__file__), '..', 'mcp_servers', 'atl_server', 'atl_mcp_server.py')
    emf_server_script = os.path.join(os.path.dirname(__file__), '..', 'mcp_servers', 'emf_server', 'stateless_emf_server.py')
    openrewrite_server_script = os.path.join(os.path.dirname(__file__), '..', 'mcp_servers', 'openRewrite_servers', 'openrewrite_server.py')

    # Setup servers with script paths in metadata
    atl_server = integrator.setup_atl_server()
    emf_server = integrator.setup_emf_server()
    # For OpenRewrite, add a generic server registration if needed

    # Setup OpenRewrite server (mimic ATL/EMF pattern)
    from src.mcp_ext.infrastructure import MCPServer, MCPCapability
    openrewrite_server = MCPServer(
        host="localhost",
        port=8089,
        name="openrewrite_server",
        tools_port=8083
    )
    openrewrite_server.add_capability(MCPCapability(
        input_types=["java", "xml", "yml", "properties"],
        output_types=["java", "xml", "yml", "properties"],
        can_execute=True,
        description="OpenRewrite code transformations"
    ))
    integrator.registry.register_mcp_server("openrewrite_server", openrewrite_server)
    openrewrite_server.metadata["script_path"] = openrewrite_server_script
    atl_server.metadata["script_path"] = atl_server_script
    emf_server.metadata["script_path"] = emf_server_script

    # Get ATL tools
    atl_client = MCPClient()
    tools = []
    try:
        await atl_client.connect_to_server(atl_server_script)
        session = await atl_client.get_session()
        response = await session.list_tools()
        tools = response.tools
    finally:
        await atl_client.cleanup()
    atl_tools = tools

    # Discover EMF tools using MCP protocol
    emf_client = MCPClient()
    tools = []
    try:
        await emf_client.connect_to_server(emf_server_script)
        session = await emf_client.get_session()
        response = await session.list_tools()
        tools = response.tools
    finally:
        await emf_client.cleanup()
    emf_tools = tools

    # Discover OpenRewrite tools using MCP protocol
    openrewrite_client = MCPClient()
    tools = []
    try:
        await openrewrite_client.connect_to_server(openrewrite_server_script)
        session = await openrewrite_client.get_session()
        response = await session.list_tools()
        tools = response.tools
    finally:
        await openrewrite_client.cleanup()
    openrewrite_tools = tools

    # Register tools with the megamodel registry
    registry.tools_by_server["atl_server"] = atl_tools
    registry.tools_by_server["emf_server"] = emf_tools
    registry.tools_by_server["openrewrite_server"] = openrewrite_tools

    # Call ATL server to get enabled transformations
    enabled_transformations = fetch_transformations()

    # Register transformation tools for ATL server
    def get_or_register_metamodel(uri, name):
        mm = registry.get_entity(uri)
        if not mm:
            mm = ReferenceModel(uri=uri, name=name)
            registry.register_entity(mm)
        return mm

    # Fetch samples once from ATL server
    try:
        samples_raw = subprocess.run([
            'curl', '-s', '-X', 'GET', 'http://localhost:8080/transformations/samples'
        ], capture_output=True, text=True, check=True)
        samples_data = json.loads(samples_raw.stdout)
        # Map name -> sampleSources
        samples_by_name = {entry.get('name'): entry.get('sampleSources', []) for entry in (samples_data or [])}
    except Exception:
        samples_by_name = {}
    for transfo_data in enabled_transformations:
        transfo_name = transfo_data.get('name')
        # Input metamodels
        input_mms = transfo_data.get('input_metamodels', [])
        source_ref = None
        if input_mms:
            mm = input_mms[0]
            source_ref = get_or_register_metamodel(mm.get('path'), mm.get('name', mm.get('path')))
        # Output metamodels
        output_mms = transfo_data.get('output_metamodels', [])
        target_ref = None
        if output_mms:
            mm = output_mms[0]
            target_ref = get_or_register_metamodel(mm.get('path'), mm.get('name', mm.get('path')))
        # Register transformation with references
        transfo_entity = TransformationModel(
            uri=transfo_data.get('atlFile', transfo_data.get('name', 'unknown')),
            name=transfo_data.get('name', 'unknown'),
            source_metamodel=source_ref,
            target_metamodel=target_ref,
            sample_sources=samples_by_name.get(transfo_name, [])
        )
        registry.register_entity(transfo_entity)


def load_agent_class_from_file(file_path: Path):
    """Dynamically load MCPAgent class from a given Python file path.
    Returns the MCPAgent class or None if not found.
    """
    spec = importlib.util.spec_from_file_location("agent_module", str(file_path))
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # type: ignore[attr-defined]
    return getattr(module, "MCPAgent", None)


def load_dataset(file_name: str) -> List[dict]:
    base_outputs = Path(__file__).parent.parent / "dataset generation" / "outputs"
    fpath = base_outputs / file_name
    try:
        with open(fpath, 'r') as f:
            data = json.load(f)
            if isinstance(data, list):
                print(f"Loaded {len(data)} items from {fpath}")
                return data
            else:
                print(f"Warning: dataset at {fpath} is not a list; returning empty list")
                return []
    except Exception as e:
        print(f"Error loading dataset file {fpath}: {e}")
        return []


if __name__ == "__main__":
    # Create an argument parser but don't require phase since we're running both
    parser = argparse.ArgumentParser(description="Run agent2 evaluation with combined datasets")
    parser.add_argument("--phase", choices=["single", "multi"], required=False,
                        help="[Deprecated] Which phase to run (ignored, will run both)")
    args = parser.parse_args()
    
    # Check LangSmith environment variables
    if os.environ.get("LANGSMITH_TRACING") == "true":
        print("LangSmith tracing enabled.")
        print(f"LangSmith project: {os.environ.get('LANGSMITH_PROJECT', 'default')}")
        if not os.environ.get("LANGSMITH_API_KEY"):
            print("WARNING: LANGSMITH_API_KEY not set. Tracing may not work.")
    else:
        print("LangSmith tracing not enabled.")

    # Create a single event loop for the entire script
    async def main():
        # 1. Set up registry and populate tools/transformations
        registry = MegamodelRegistry()
        await populate_registry(registry)
        
        # 2. Get ATL server script path for connections
        atl_server = registry.get_mcp_server("atl_server")
        if not atl_server or not atl_server.metadata.get("script_path"):
            print("ERROR: ATL server not properly configured. Check script path in registry.")
            return
            
        script_path = atl_server.metadata.get("script_path")
        
        agents_dir = Path(__file__).parent.parent / "evaluation" / "agent_versions"
        agent_names = [f"agent{i}" for i in range(7, 8)]
        agent_files = [agents_dir / f"{name}.py" for name in agent_names if (agents_dir / f"{name}.py").is_file()]
        if not agent_files:
            print(f"No agent version files found in {agents_dir}")
            return
        print(f"Only evaluating: {[p.stem for p in agent_files]}")
        
        # 4. Evaluate agent2 for both phases at once
        for agent_path in agent_files:
                agent_name = agent_path.stem  # e.g., agent3, agent4, ...
                print(f"\n==== Evaluating {agent_name} (phase: {args.phase}) ====")
                try:
                    MCPAgentCls = load_agent_class_from_file(agent_path)
                    if MCPAgentCls is None:
                        print(f"Skipping {agent_name}: MCPAgent class not found")
                        continue
                    # Prepare per-agent results
                    all_execution_results: List[dict] = []
                    agent = None
                    try:
                        # Instantiate agent and connect client to ATL server
                        agent = MCPAgentCls(registry)
                        client = MCPClient()
                        await client.connect_to_server(script_path)
                        # Store the client in the executor
                        agent.executor.mcp_clients["atl_server"] = client

                        # Load only the seedsdataset.json
                        seeds_dataset = load_dataset("seedsdataset.json")
                        combined_dataset = seeds_dataset
                        if not combined_dataset:
                            print("No entries found in seedsdataset.json, nothing to run.")
                            continue
                        print(f"\n-- Seeds dataset: Running {len(combined_dataset)} instructions from seedsdataset.json --")
                        for i, item in enumerate(combined_dataset):
                            instruction = item.get("instruction", "")
                            pattern = item.get("pattern", "")
                            apis = item.get("relevant_apis", [])
                            api_names = [api.get("api_name", "") for api in apis]
                            print(f"\n[{i+1}/{len(combined_dataset)}] Running instruction: {instruction}")        
                            # Generate the plan without timeout
                            try:
                                # Call plan generation directly without timeout
                                plan = await asyncio.to_thread(agent.plan_workflow, instruction)
                                # Force ATL server for transformation tools
                                for step in plan.steps:
                                    name = getattr(step, 'tool_name', '') or ''
                                    if name.startswith(('apply_', 'list_transformation_')):
                                        step.server_name = 'atl_server'
                                # proceed to execute the generated plan for this instruction
                            except (asyncio.TimeoutError, Exception) as e:
                                print(f"\n\nWARNING: Planning timed out or failed for instruction {i+1}: {e}")
                                plan = WorkflowPlan(instruction)
                                plan.status = "planning_failed"
                            # Execute the plan with timeout
                            try:
                                plan.start_execution()
                                session = agent.executor.registry.create_session()
                                session.start()
                                trace = session.create_new_trace()
                                results = []
                                # Execute steps without timeout
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
                                # Mark plan as completed after execution
                                plan.status = "completed"
                                session.end()
                                # Create a serializable result for this instruction
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
                                    "status": plan.status  # Include execution status (completed or timeout)
                                }
                                # Process the execution results
                                timeout_occurred = plan.status == "timeout"
                                # Converts result objects to JSON-serializable format
                                for i, (step, result) in enumerate(zip(plan.steps, results)):
                                    # Skip timeout error result which was added artificially
                                    if timeout_occurred and i == len(plan.steps):
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
                                # Add timeout error if it occurred
                                if timeout_occurred and len(results) > len(plan.steps):
                                    timeout_result = results[-1]  # Last result is the timeout error
                                    execution_result["execution_results"].append({
                                        "tool_name": "execution_timeout",
                                        "success": False,
                                        "error": timeout_result.get('error', 'Execution timed out')
                                    })
                                all_execution_results.append(execution_result)
                            except KeyboardInterrupt:
                                # Propagate to outer handler; no partial saves
                                raise
                            except Exception as e:
                                print(f"Error during plan execution: {e}")
                                import traceback
                                traceback.print_exc()
                            print("--- End Execution ---")
                        # Save all results
                        if all_execution_results:
                            # Extract version number from agent name (e.g., agent1 -> version_1)
                            version_num = agent_name.replace('agent', '')
                            outputs_dir = Path(__file__).parent.parent / "outputs" / "agent_version_logs" / f"version_{version_num}"
                            outputs_dir.mkdir(parents=True, exist_ok=True)
                            try:
                                # Save results with a unique prefix for seedsdataset
                                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
                                output_filename = f"agent_execution_results_seeds_{agent_name}_{timestamp}.json"
                                output_path = outputs_dir / output_filename
                                with open(output_path, 'w') as f:
                                    # Convert any sets to lists before serializing
                                    json_str = json.dumps(all_execution_results, indent=2, default=lambda o: list(o) if isinstance(o, set) else str(o))
                                    f.write(json_str)
                                print(f"\nExecution results for {agent_name} (seedsdataset) saved to: {output_path}")
                            except Exception as e:
                                print(f"Error saving results for {agent_name}: {e}")
                                import traceback
                                traceback.print_exc()
                    except BaseException as e:
                        #BaseException catches everything including KeyboardInterrupt, SystemExit, etc.
                        print(f"Error setting up or running {agent_name}: {e}")
                        import traceback
                        traceback.print_exc()
                    finally:
                        # Cleanup per-agent clients
                        try:
                            for server_name, cli in getattr(agent, 'executor', object()).mcp_clients.items():
                                try:
                                    if hasattr(cli, 'exit_stack'):
                                        try:
                                            await cli.exit_stack.aclose()
                                        except BaseException:
                                            # Swallow cancellation/errors on shutdown to avoid aborting the whole run
                                            pass
                                except BaseException:
                                    pass
                        except BaseException:
                            pass
                        # Small delay to allow subprocess cleanup before next agent
                        try:
                            await asyncio.sleep(0.2)
                        except BaseException:
                            # Ignore cancellations occurring at this checkpoint
                            pass
                except Exception as e:
                    print(f"Exception occurred while evaluating {agent_name}: {e}")
                    import traceback
                    traceback.print_exc()
    # Run the async main function with graceful handling of Ctrl+C
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nProgram terminated by user.")
