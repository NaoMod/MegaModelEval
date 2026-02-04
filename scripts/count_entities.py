import json

# Load ATL output
with open('langsmith_final_output.json', 'r') as f:
    atl_data = json.load(f)

# Count trace steps and invocations
atl_trace_steps = 0
atl_invocations = 0
for trace in atl_data.get('execution_traces', []):
    steps = trace.get('trace_steps', [])
    atl_trace_steps += len(steps)
    for step in steps:
        atl_invocations += len(step.get('invocations', []))

print('=== ATL MEGAMODEL ENTITIES ===')
print(f'Execution Traces: {len(atl_data.get("execution_traces", []))}')
print(f'Trace Steps: {atl_trace_steps}')
print(f'Tool Invocations: {atl_invocations}')
print(f'Workflows: {len(atl_data.get("workflows", []))}')
print(f'Agents: {len(atl_data.get("agents", []))}')
print(f'Tools: {len(atl_data.get("tools", []))}')
print(f'Models: {len(atl_data.get("models", []))}')

# Tool names
print('\n--- Tool Names ---')
for t in atl_data.get('tools', []):
    print(f'  - {t["name"]}')

# Model names  
print('\n--- Model Names ---')
for m in atl_data.get('models', []):
    print(f'  - {m.get("name", m)}')

# Agent info
print('\n--- Agent ---')
for a in atl_data.get('agents', []):
    print(f'  - {a["id"]} (model: {a["model"]})')

print()
# Load EMF output
with open('emf_langsmith_final_output.json', 'r') as f:
    emf_data = json.load(f)

# Count trace steps and invocations
emf_trace_steps = 0
emf_invocations = 0
for trace in emf_data.get('execution_traces', []):
    steps = trace.get('trace_steps', [])
    emf_trace_steps += len(steps)
    for step in steps:
        emf_invocations += len(step.get('invocations', []))

print('=== EMF MEGAMODEL ENTITIES ===')
print(f'Execution Traces: {len(emf_data.get("execution_traces", []))}')
print(f'Trace Steps: {emf_trace_steps}')
print(f'Tool Invocations: {emf_invocations}')
print(f'Workflows: {len(emf_data.get("workflows", []))}')
print(f'Agents: {len(emf_data.get("agents", []))}')
print(f'Tools: {len(emf_data.get("tools", []))}')
print(f'Objects: {len(emf_data.get("objects", []))}')

# Tool names
print('\n--- Tool Names ---')
for t in emf_data.get('tools', []):
    print(f'  - {t["name"]}')

# Objects
print('\n--- Objects ---')
for o in emf_data.get('objects', []):
    print(f'  - class: {o["class"]}, id: {o["id"]}')

# TOTALS
print()
print('=== GRAND TOTAL ===')
total_traces = len(atl_data.get('execution_traces', [])) + len(emf_data.get('execution_traces', []))
total_steps = atl_trace_steps + emf_trace_steps
total_invocations = atl_invocations + emf_invocations
total_workflows = len(atl_data.get('workflows', [])) + len(emf_data.get('workflows', []))
total_agents = len(atl_data.get('agents', [])) + len(emf_data.get('agents', []))
total_tools = len(atl_data.get('tools', [])) + len(emf_data.get('tools', []))
total_models = len(atl_data.get('models', []))
total_objects = len(emf_data.get('objects', []))

print(f'Total Execution Traces: {total_traces}')
print(f'Total Trace Steps: {total_steps}')
print(f'Total Tool Invocations: {total_invocations}')
print(f'Total Workflows: {total_workflows}')
print(f'Total Agents: {total_agents}')
print(f'Total Tools: {total_tools}')
print(f'Total Models (ATL): {total_models}')
print(f'Total Objects (EMF): {total_objects}')
total_entities = total_traces + total_steps + total_workflows + total_agents + total_tools + total_models + total_objects
print(f'\nGRAND TOTAL ENTITIES: {total_entities}')
