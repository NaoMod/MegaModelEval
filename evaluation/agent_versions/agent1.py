
"""code: 31b71b9 feat: agent queryig the megamodel repository """
import os
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from core.megamodel import MegamodelRegistry
from agents.workflow import WorkflowExecutor
from agents.planning import WorkflowPlan, PlanStep, AgentGoal
import json

load_dotenv()
BASE_URL = os.getenv("BASE_URL")
API_USER = os.getenv("API_USER")
API_PASSWORD = os.getenv("API_PASSWORD")

# Ollama's Configuration
OLLAMA_MODEL = "llama3.2"
OLLAMA_TEMPERATURE = 0.1
OLLAMA_MAX_RETRIES = 2

class MCPAgent:
    """Agent powered by a local LLM (Ollama) for MDE orchestration"""
    def __init__(self, registry: MegamodelRegistry):
        self.registry = registry
        self.executor = WorkflowExecutor(registry)
        client_kwargs = {
            "auth": (API_USER, API_PASSWORD)
        }
        self.model = ChatOllama(
            model="llama3.2",
            temperature=0.1,
            max_retries=2
        )
        self.tool_registry = {}

    def plan_workflow(self, user_goal: str) -> WorkflowPlan:
        """Use LLM to reason and generate a workflow plan for the user goal (filtered context)"""
        goal = AgentGoal(
            description=user_goal,
            success_criteria={"completed": True}
        )
        plan = WorkflowPlan(goal=goal)

        # Filter relevant tools by goal keywords (simple heuristic)
        keywords = [w.lower() for w in user_goal.split()]
        all_tools = self.registry.discover_tools()
        relevant_tools = []
        for tool in all_tools:
            name = getattr(tool, "name", str(tool)).lower()
            desc = getattr(tool, "description", "").lower()
            if any(k in name or k in desc for k in keywords):
                relevant_tools.append(tool)
        # If no relevant tools found, fallback to first 5
        if not relevant_tools:
            relevant_tools = all_tools[:5]

        # Filter relevant models by goal keywords
        all_models = self.registry.find_entities_by_type(self.registry.entities.get("Model", type(None)))
        relevant_models = []
        for model in all_models:
            name = getattr(model, "name", str(model)).lower()
            if any(k in name for k in keywords):
                relevant_models.append(model)
        # If no relevant models found, fallback to first 5
        if not relevant_models:
            relevant_models = all_models[:5]

        # Limit to top 10 relevant tools/models and only include names
        tool_names = [getattr(tool, "name", str(tool)) for tool in relevant_tools[:10]]
        model_names = [getattr(model, "name", str(model)) for model in relevant_models[:10]]
        # Expose available server names
        available_servers = list(self.registry.tools_by_server.keys())
        prompt = (
            f"You are an MDE agent. Your goal is: {user_goal}\n"
            f"Relevant tools: {tool_names}\n"
            f"Relevant models: {model_names}\n"
            f"Available server names: {available_servers}\n"
            "Generate a workflow plan as a JSON list of steps. Each step must be a JSON object with keys: tool_name, server_name, parameters, description. Output ONLY the JSON list, no extra text. Example: [ {\"tool_name\": ..., \"server_name\": ..., \"parameters\": {...}, \"description\": ...}, ... ]"
        )

        print("\n--- LLM Prompt ---")
        print(prompt)
        print("--- End LLM Prompt ---\n")

        # Query the LLM for workflow steps
        llm_response = self.model.invoke(prompt)
        # Extract content if response is an AIMessage object
        response_text = getattr(llm_response, "content", llm_response)

        print("\n--- LLM Raw Response ---")
        print(response_text)
        print("--- End LLM Raw Response ---\n")

        # Parse LLM response into workflow steps

        steps = []
        try:
            # Try strict JSON parsing first
            steps = json.loads(response_text)
        except Exception as e:
            print(f"LLM response JSON parsing error: {e}")
            # Fallback: try to extract JSON list from response
            import re
            match = re.search(r'(\[.*\])', response_text, re.DOTALL)
            if match:
                try:
                    steps = json.loads(match.group(1))
                except Exception as e2:
                    print(f"Fallback JSON extraction error: {e2}")
            # Fallback: try line-by-line extraction for dicts
            if not steps:
                import ast
                for line in response_text.splitlines():
                    if line.strip().startswith("{"):
                        try:
                            steps.append(ast.literal_eval(line.strip()))
                        except Exception as e2:
                            print(f"Line parsing error: {e2} | Line: {line.strip()}")
                            continue

        for step in steps:
            if isinstance(step, dict):
                # Default to atl_server if server_name is missing or empty
                server_name = step.get("server_name")
                if not server_name:
                    server_name = available_servers[0] if available_servers else "atl_server"
                plan.add_step(PlanStep(
                    tool_name=step.get("tool_name"),
                    server_name=step.get("server_name"),
                    parameters=step.get("parameters", {}),
                    description=step.get("description", "")
                ))
        return plan

    def run(self, user_goal: str):
        """End-to-end agent orchestration: plan and execute workflow"""
        plan = self.plan_workflow(user_goal)
        result = self.executor.execute_workflow(plan)
        return result