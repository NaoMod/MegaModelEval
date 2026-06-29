#!/usr/bin/env python3
"""
Script to create a unified megamodel by merging:
- ATL megamodel (langsmith_final_output.json)
- EMF megamodel (emf_langsmith_final_output.json)
- 7 Agent version logs (version_1 to version_7)

Only uses the original megamodel structure without adding new attributes.
"""

import json
import os

# Define paths
BASE_PATH = os.path.dirname(os.path.abspath(__file__))
ATL_MEGAMODEL = os.path.join(BASE_PATH, "ATL", "langsmith_final_output.json")
EMF_MEGAMODEL = os.path.join(BASE_PATH, "EMF", "emf_langsmith_final_output.json")
AGENT_LOGS_PATH = os.path.join(os.path.dirname(BASE_PATH), "regression_testing", "agent_version_logs")
OUTPUT_PATH = os.path.join(BASE_PATH, "unified_megamodel.json")

def load_json(file_path):
    """Load JSON file and return data"""
    with open(file_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def find_agent_log_file(version_folder):
    """Find the non-seed JSON file in a version folder"""
    for file in os.listdir(version_folder):
        if file.endswith('.json') and 'seed' not in file.lower():
            return os.path.join(version_folder, file)
    return None

def load_agent_version_logs():
    """Load all 7 agent version logs"""
    agent_logs = []
    for i in range(1, 8):
        version_folder = os.path.join(AGENT_LOGS_PATH, f"version_{i}")
        if os.path.exists(version_folder):
            log_file = find_agent_log_file(version_folder)
            if log_file:
                executions = load_json(log_file)
                agent_logs.append({
                    "version": i,
                    "executions": executions
                })
                print(f"Loaded version_{i}: {len(executions)} executions")
    return agent_logs

def convert_agent_logs_to_traces(agent_logs):
    """Convert agent execution logs to megamodel execution trace format matching original structure"""
    traces = []
    for agent_data in agent_logs:
        version = agent_data["version"]
        for execution in agent_data["executions"]:
            # Build trace_steps from execution_results (matching original format)
            trace_steps = []
            for result in execution.get("execution_results", []):
                trace_steps.append({
                    "tool_ref": result.get("tool_name", ""),
                    "success": result.get("success", False),
                    "invocations": [
                        {
                            "content": json.dumps(result.get("result", {}).get("structuredContent", "")),
                            "is_error": result.get("result", {}).get("isError", False)
                        }
                    ] if result.get("result") else []
                })
            
            # Build workflow_ref from plan_steps tool names
            tool_names = [step.get("tool_name", "") for step in execution.get("plan_steps", [])]
            workflow_ref = "workflow_" + "_".join(tool_names) if tool_names else ""
            
            traces.append({
                "instruction": execution.get("instruction", ""),
                "workflow_ref": workflow_ref,
                "trace_steps": trace_steps
            })
    return traces

def convert_agent_logs_to_workflows(agent_logs):
    """Extract unique workflows from agent logs matching original format"""
    workflows = {}
    for agent_data in agent_logs:
        for execution in agent_data["executions"]:
            tool_names = [step.get("tool_name", "") for step in execution.get("plan_steps", [])]
            if tool_names:
                workflow_id = "workflow_" + "_".join(tool_names)
                if workflow_id not in workflows:
                    workflows[workflow_id] = {
                        "workflow_id": workflow_id,
                        "workflow_steps": [
                            {"tool_ref": tool_name} for tool_name in tool_names
                        ]
                    }
    return list(workflows.values())

def convert_agent_logs_to_agents(agent_logs, atl_agents):
    """Extract agents from version logs matching original format"""
    agents = []
    # Use first ATL agent as template for structure
    template = atl_agents[0] if atl_agents else {}
    
    for agent_data in agent_logs:
        version = agent_data["version"]
        agents.append({
            "agent_id": f"agent_v{version}",
            "model": f"agent{version}"
        })
    return agents

def convert_agent_logs_to_tools(agent_logs, atl_tools):
    """Extract unique tools from agent logs matching original format"""
    tools = {}
    # Use first ATL tool as template for structure
    template = atl_tools[0] if atl_tools else {}
    
    for agent_data in agent_logs:
        for execution in agent_data["executions"]:
            for step in execution.get("plan_steps", []):
                tool_name = step.get("tool_name", "")
                if tool_name and tool_name not in tools:
                    tools[tool_name] = {
                        "tool_id": f"tool_{tool_name}",
                        "name": tool_name,
                        "server_name": step.get("server_name", "atl_server")
                    }
    return list(tools.values())

def create_unified_megamodel():
    """Create the unified megamodel by merging all sources using original structure only"""
    print("Loading ATL megamodel...")
    atl_megamodel = load_json(ATL_MEGAMODEL)
    
    print("Loading EMF megamodel...")
    emf_megamodel = load_json(EMF_MEGAMODEL)
    
    print("Loading agent version logs...")
    agent_logs = load_agent_version_logs()
    
    # Convert agent logs to megamodel format
    agent_traces = convert_agent_logs_to_traces(agent_logs)
    agent_workflows = convert_agent_logs_to_workflows(agent_logs)
    agent_agents = convert_agent_logs_to_agents(agent_logs, atl_megamodel.get("agents", []))
    agent_tools = convert_agent_logs_to_tools(agent_logs, atl_megamodel.get("tools", []))
    
    # Create unified megamodel using ONLY original structure keys
    # ATL has: execution_traces, workflows, agents, tools, models
    # EMF has: execution_traces, agents, tools, objects
    
    unified_megamodel = {
        # Merge all execution_traces into single array
        "execution_traces": (
            atl_megamodel.get("execution_traces", []) +
            emf_megamodel.get("execution_traces", []) +
            agent_traces
        ),
        
        # Merge workflows (ATL + agent logs)
        "workflows": (
            atl_megamodel.get("workflows", []) +
            agent_workflows
        ),
        
        # Merge all agents
        "agents": (
            atl_megamodel.get("agents", []) +
            emf_megamodel.get("agents", []) +
            agent_agents
        ),
        
        # Merge all tools (deduplicate by tool_id)
        "tools": (
            atl_megamodel.get("tools", []) +
            emf_megamodel.get("tools", []) +
            agent_tools
        ),
        
        # Models from ATL
        "models": atl_megamodel.get("models", []),
        
        # Objects from EMF
        "objects": emf_megamodel.get("objects", [])
    }
    
    # Write unified megamodel
    print(f"\nWriting unified megamodel to {OUTPUT_PATH}...")
    with open(OUTPUT_PATH, 'w', encoding='utf-8') as f:
        json.dump(unified_megamodel, f, indent=2, ensure_ascii=False)
    
    # Print summary
    print("\n" + "="*60)
    print("UNIFIED MEGAMODEL CREATED SUCCESSFULLY")
    print("="*60)
    print(f"\nCounts:")
    print(f"  execution_traces: {len(unified_megamodel['execution_traces'])}")
    print(f"  workflows: {len(unified_megamodel['workflows'])}")
    print(f"  agents: {len(unified_megamodel['agents'])}")
    print(f"  tools: {len(unified_megamodel['tools'])}")
    print(f"  models: {len(unified_megamodel['models'])}")
    print(f"  objects: {len(unified_megamodel['objects'])}")
    print(f"\nOutput: {OUTPUT_PATH}")
    
    return unified_megamodel

if __name__ == "__main__":
    create_unified_megamodel()
