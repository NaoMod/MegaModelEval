import json
from langsmith import Client
from dotenv import load_dotenv
load_dotenv()

client = Client()

# Fetch the complete trace
parent_runs = list(client.list_runs(project_name="pr-blank-sticker-58", limit=1))

if not parent_runs:
    print("No runs found!")
    exit()

parent_run = parent_runs[0]
trace_id = parent_run.trace_id if hasattr(parent_run, 'trace_id') else parent_run.id

# Get all runs in the trace
all_runs = list(client.list_runs(
    project_name="pr-blank-sticker-58",
    trace_id=trace_id
))

print(f"Found {len(all_runs)} runs in trace {trace_id}")

# Save complete trace for reference
with open("complete_trace_final.txt", "w", encoding="utf-8") as f:
    for i, run in enumerate(all_runs):
        f.write(f"\n{'='*80}\n")
        f.write(f"RUN {i+1}: {run.name} ({run.run_type})\n")
        f.write(f"{'='*80}\n")
        f.write(str(run))
        f.write("\n")

structured_data = {
    "execution_traces": [],
    "workflows": [],
    "agents": [],
    "tools": [],
    "models": []
}

agents_map = {}
tools_map = {}
workflows_map = {}

print("\n" + "="*80)
print("PROCESSING TRACE")
print("="*80)

# Find the LLM run with tool definitions in invocation_params
llm_run = None
for run in all_runs:
    if run.run_type == "llm" and hasattr(run, 'extra'):
        if 'invocation_params' in run.extra and 'tools' in run.extra['invocation_params']:
            llm_run = run
            print(f"Found LLM run with tool definitions: {run.name}")
            break

if not llm_run:
    print("WARNING: No LLM run with tool definitions found!")
    exit()

# Extract model name and agent prompt
model_name = None
agent_prompt = ""
user_instruction = ""

# Get model name from invocation_params
if 'invocation_params' in llm_run.extra:
    model_name = llm_run.extra['invocation_params'].get('model_name')

# Get messages from inputs
if hasattr(llm_run, 'inputs') and 'messages' in llm_run.inputs:
    messages = llm_run.inputs['messages']
    if messages and len(messages) > 0:
        # Messages are in LangChain format with nested structure
        for msg_list in messages:
            if isinstance(msg_list, list):
                for msg in msg_list:
                    if isinstance(msg, dict):
                        msg_type = msg.get('kwargs', {}).get('type')
                        msg_content = msg.get('kwargs', {}).get('content', '')
                        
                        if msg_type == 'system':
                            agent_prompt = msg_content
                            print(f"  Found agent prompt: {len(msg_content)} chars")
                        elif msg_type == 'human':
                            user_instruction = msg_content
                            print(f"  Found user instruction: {user_instruction}")

print(f"  Model: {model_name}")

# Extract tools from invocation_params
tools_from_schema = {}
if 'invocation_params' in llm_run.extra and 'tools' in llm_run.extra['invocation_params']:
    tool_list = llm_run.extra['invocation_params']['tools']
    print(f"  Found {len(tool_list)} tool schemas in invocation_params")
    
    for tool_def in tool_list:
        if 'function' in tool_def:
            func = tool_def['function']
            tool_name = func.get('name')
            if tool_name:
                tools_from_schema[tool_name] = {
                    "name": tool_name,
                    "description": func.get('description', ''),
                    "parameters": func.get('parameters', {}),
                    "server_name": None  # Not in the schema
                }

print(f"  Extracted {len(tools_from_schema)} tool schemas")

# Create agent (without tool_refs)
agent_id = None
if model_name:
    agent_id = f"agent_{model_name.replace('/', '_').replace('-', '_')}"
    agent = {
        "id": agent_id,
        "model": model_name,
        "prompt": agent_prompt
    }
    agents_map[agent_id] = agent
    structured_data["agents"].append(agent)
    print(f"  Created agent: {agent_id}")

# Create tools (without id, just name)
for tool_name, tool_info in tools_from_schema.items():
    tool = {
        "name": tool_name,
        "description": tool_info["description"],
        "parameters": tool_info["parameters"],
        "server_name": tool_info["server_name"]
    }
    tools_map[tool_name] = tool
    structured_data["tools"].append(tool)

print(f"  Created {len(structured_data['tools'])} tools")

# Extract unique models from tool descriptions
models_set = set()
for tool_name, tool_info in tools_from_schema.items():
    description = tool_info["description"]
    
    # Parse "Input metamodel: X, Output metamodel: Y" pattern
    if "Input metamodel:" in description and "Output metamodel:" in description:
        # Extract input metamodel
        input_part = description.split("Input metamodel:")[1].split(",")[0].strip()
        if input_part and input_part != "":
            models_set.add(input_part)
        
        # Extract output metamodel
        output_part = description.split("Output metamodel:")[1].split(".")[0].strip()
        if output_part and output_part != "":
            models_set.add(output_part)

# Convert to sorted list for consistent output
for model_name in sorted(models_set):
    structured_data["models"].append({"name": model_name})

print(f"  Extracted {len(structured_data['models'])} unique models")

# Extract execution trace from tool runs
tool_runs = [r for r in all_runs if r.run_type == "tool"]
print(f"  Found {len(tool_runs)} tool execution runs")

trace_steps = []
for tool_run in tool_runs:
    tool_name = tool_run.name
    
    # Create invocation from inputs
    invocation = {
        "content": json.dumps(tool_run.inputs) if tool_run.inputs else "",
        "is_error": tool_run.status != "success" if hasattr(tool_run, 'status') else False
    }
    
    trace_step = {
        "tool_ref": tool_name,  # Just the name, not prefixed with "tool_"
        "success": tool_run.status == "success" if hasattr(tool_run, 'status') else False,
        "invocations": [invocation]
    }
    trace_steps.append(trace_step)
    print(f"    {tool_name} - {'SUCCESS' if trace_step['success'] else 'FAILED'}")

# Create workflow
workflow_id = None
if agent_id:
    workflow_id = f"workflow_{agent_id}"
    workflow = {
        "id": workflow_id,
        "instruction": agent_prompt[:300] if agent_prompt else "",
        "agent_ref": agent_id,
        "plan_steps": []
    }
    
    for trace_step in trace_steps:
        step = {
            "tool_ref": trace_step["tool_ref"],
            "server_name": None,
            "parameters": []
        }
        workflow["plan_steps"].append(step)
    
    workflows_map[workflow_id] = workflow
    structured_data["workflows"].append(workflow)
    print(f"  Created workflow with {len(workflow['plan_steps'])} steps")

# Create execution trace
if trace_steps and workflow_id:
    execution_trace = {
        "instruction": user_instruction,
        "workflow_ref": workflow_id,
        "trace_steps": trace_steps
    }
    structured_data["execution_traces"].append(execution_trace)
    print(f"  Created execution trace")

# Write the structured JSON to file
with open("langsmith_final_output.json", "w", encoding="utf-8") as f:
    json.dump(structured_data, f, indent=2, ensure_ascii=False)

print("\n" + "="*80)
print("FINAL RESULTS")
print("="*80)
print(f"JSON written to: langsmith_final_output.json")
print(f"Execution traces: {len(structured_data['execution_traces'])}")
print(f"Workflows: {len(structured_data['workflows'])}")
print(f"Agents: {len(structured_data['agents'])}")
print(f"Tools: {len(structured_data['tools'])}")
print(f"Models: {len(structured_data['models'])}")

# Print sample data
if structured_data['agents']:
    print("\n--- Agent ---")
    agent = structured_data['agents'][0]
    print(f"ID: {agent['id']}")
    print(f"Model: {agent['model']}")
    print(f"Prompt (first 200 chars): {agent['prompt'][:200]}...")

if structured_data['tools']:
    print("\n--- Sample Tools (first 3) ---")
    for tool in structured_data['tools'][:3]:
        print(f"\n{tool['name']}:")
        print(f"  Description: {tool['description'][:80]}...")
        if tool['parameters'] and 'properties' in tool['parameters']:
            print(f"  Parameters: {list(tool['parameters']['properties'].keys())}")

if structured_data['models']:
    print("\n--- Models (first 10) ---")
    for model in structured_data['models'][:10]:
        print(f"  - {model['name']}")
    if len(structured_data['models']) > 10:
        print(f"  ... and {len(structured_data['models']) - 10} more")

if structured_data['workflows']:
    print("\n--- Workflow ---")
    workflow = structured_data['workflows'][0]
    print(f"ID: {workflow['id']}")
    print(f"Agent: {workflow['agent_ref']}")
    print(f"Steps: {len(workflow['plan_steps'])}")

if structured_data['execution_traces']:
    print("\n--- Execution Trace ---")
    trace = structured_data['execution_traces'][0]
    print(f"User instruction: {trace['instruction'][:100]}...")
    print(f"Workflow: {trace['workflow_ref']}")
    print(f"Trace steps: {len(trace['trace_steps'])}")
    for step in trace['trace_steps']:
        print(f"  - {step['tool_ref']} ({' ' if step['success'] else '✗'})")