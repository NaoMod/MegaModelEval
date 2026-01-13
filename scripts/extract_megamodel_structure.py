import json
import re
from langsmith import Client
from dotenv import load_dotenv
load_dotenv()

client = Client()

runs = list(client.list_runs(project_name="pr-blank-sticker-58"))

structured_data = {
    "execution_traces": [],
    "agents": [],
    "models": []
}

# Track unique agents and tools to avoid duplicates
agents_map = {}
execution_traces_set = set()

# Process each run
for run in runs:
    messages = run.inputs.get("messages", [])
    model_name = None
    prompt_text = ""
    
    # Extract model name from outputs
    if hasattr(run, 'outputs') and run.outputs:
        llm_output = run.outputs.get('llm_output')
        if llm_output and isinstance(llm_output, dict):
            model_name = llm_output.get('model_name')
    if not model_name and hasattr(run, 'outputs') and run.outputs:
        model_name = run.outputs.get('model_name')
    if not model_name and hasattr(run, 'outputs') and run.outputs:
        try:
            generations = run.outputs.get('generations')
            if generations:
                model_name = generations[0][0]['message']['response_metadata'].get('model_name')
        except Exception:
            pass
    
    # Extract prompt (instructions)
    prompt_text = ""
    if messages and len(messages) > 0:
        # Handle both list of messages and message objects
        first_msg = messages[0]
        if isinstance(first_msg, list) and len(first_msg) > 0:
            prompt_text = first_msg[0].get("kwargs", {}).get("content", "")
        elif hasattr(first_msg, 'content'):
            prompt_text = first_msg.content
        elif isinstance(first_msg, dict) and "content" in first_msg:
            prompt_text = first_msg["content"]
    
    # Extract tool names dynamically from inputs
    tool_names = run.inputs.get("tool_names", [])
    
    # Create agent entry (skip if model is unknown)
    if model_name and model_name != "unknown":
        agent_key = model_name
        if agent_key not in agents_map:
            agent = {
                "model": model_name,
                "prompt": prompt_text[:500] if prompt_text else "",
                "tools": [],
                "_tool_names_set": set()  # Track tool names to avoid duplicates
            }
            agents_map[agent_key] = agent
            structured_data["agents"].append(agent)
    
    # Extract tool map with descriptions (if available)
    tool_map = run.inputs.get("tool_map", {})
    
    # Add tool entries directly to agent
    if tool_names and model_name and model_name != "unknown":
        agent_key = model_name
        for tool_name in tool_names:
            if tool_name not in agents_map[agent_key]["_tool_names_set"]:
                # Get description from tool_map if available, otherwise leave empty
                tool_description = ""
                if tool_name in tool_map and isinstance(tool_map[tool_name], dict):
                    tool_description = tool_map[tool_name].get("description", "")
                
                tool = {
                    "name": tool_name,
                    "description": tool_description,
                    "parameters": {},
                    "server_name": None
                }
                agents_map[agent_key]["tools"].append(tool)
                agents_map[agent_key]["_tool_names_set"].add(tool_name)
    
    # Extract execution trace steps from the run
    trace_steps = []
    if hasattr(run, 'child_runs') and run.child_runs:
        for child_run in run.child_runs:
            trace_step = {
                "tool_name": child_run.name if hasattr(child_run, 'name') else "unknown",
                "success": child_run.status == "success" if hasattr(child_run, 'status') else False,
                "invocations": [
                    {
                        "content": json.dumps(child_run.inputs) if hasattr(child_run, 'inputs') else "",
                        "is_error": child_run.status == "error" if hasattr(child_run, 'status') else False
                    }
                ]
            }
            trace_steps.append(trace_step)
    
    # Extract output tool calls from response
    if hasattr(run, 'outputs') and run.outputs and 'generations' in run.outputs:
        try:
            generations = run.outputs.get('generations', [])
            if generations and len(generations) > 0 and len(generations[0]) > 0:
                message_content = generations[0][0].get('message', {}).get('kwargs', {}).get('content', '')
                # Try to parse as JSON to extract tool calls
                try:
                    tool_call = json.loads(message_content)
                    if 'tool_name' in tool_call:
                        trace_step = {
                            "tool_name": tool_call['tool_name'],
                            "success": True,
                            "invocations": [
                                {
                                    "content": json.dumps(tool_call.get('parameters', {})),
                                    "is_error": False
                                }
                            ]
                        }
                        trace_steps.append(trace_step)
                except:
                    pass
        except Exception:
            pass
    
    # Create execution trace entry
    if trace_steps:
        # Create unique key to avoid duplicates
        trace_key = f"{len(trace_steps)}"
        if trace_key not in execution_traces_set:
            execution_trace = {
                "trace_steps": trace_steps
            }
            structured_data["execution_traces"].append(execution_trace)
            execution_traces_set.add(trace_key)

# (Metamodels and transformation models removed per user request)

# Clean up temporary tracking sets before writing
for agent in structured_data["agents"]:
    if "_tool_names_set" in agent:
        del agent["_tool_names_set"]

# Write the structured JSON to file
with open("langsmith_uml_structured.json", "w", encoding="utf-8") as f:
    json.dump(structured_data, f, indent=2, ensure_ascii=False)

print("Structured UML JSON generated and written to langsmith_uml_structured.json")
print(f"Total execution traces: {len(structured_data['execution_traces'])}")
print(f"Total agents: {len(structured_data['agents'])}")
total_tools = sum(len(agent['tools']) for agent in structured_data['agents'])
print(f"Total tools across all agents: {total_tools}")
