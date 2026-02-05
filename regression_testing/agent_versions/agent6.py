"""code:e4b027d  Feat: removed rules from the agent prompt & performing the same evaluation"""

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain_community.vectorstores import DocArrayInMemorySearch
from core.megamodel import MegamodelRegistry
from agents.workflow import WorkflowExecutor
from agents.planning import WorkflowPlan, PlanStep, AgentGoal
import json

load_dotenv()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

class MCPAgent:
    """Agent powered by an LLM (OpenAI) for MDE orchestration"""
    def __init__(self, registry: MegamodelRegistry):
        self.registry = registry
        self.executor = WorkflowExecutor(registry)
        # Initialize OpenAI chat model (configure OPENAI_API_KEY in environment)
        openai_model = os.getenv("OPENAI_MODEL", OPENAI_MODEL)
        self.model = ChatOpenAI(
            model=openai_model,
            temperature=0.1,
            max_retries=2
        )
        # Embeddings and vector stores for RAG
        self.embeddings = OpenAIEmbeddings(model=OPENAI_EMBEDDING_MODEL)
        self.tool_index = None
        self.model_index = None
        self.tool_registry = {}

    def _build_indexes(self):
        """Build in-memory vector indexes for tools and models from the registry."""
        # Tools index
        all_tools = self.registry.discover_tools()
        tool_texts = []
        tool_metas = []
        for t in all_tools:
            name = getattr(t, "name", "")
            desc = getattr(t, "description", "")
            server = getattr(t, "server_name", "")
            text = f"tool name: {name}\nserver: {server}\ndescription: {desc}"
            tool_texts.append(text)
            tool_metas.append({"name": name, "server": server})
        if tool_texts:
            self.tool_index = DocArrayInMemorySearch.from_texts(tool_texts, self.embeddings, metadatas=tool_metas)
        else:
            self.tool_index = None

        # Models index
        all_models = self.registry.find_entities_by_type(self.registry.entities.get("Model", type(None)))
        model_texts = []
        model_metas = []
        for m in all_models:
            name = getattr(m, "name", "")
            uri = getattr(m, "uri", "")
            text = f"model name: {name}\nuri: {uri}"
            model_texts.append(text)
            model_metas.append({"name": name, "uri": uri})
        if model_texts:
            self.model_index = DocArrayInMemorySearch.from_texts(model_texts, self.embeddings, metadatas=model_metas)
        else:
            self.model_index = None

    def _retrieve_relevant(self, query: str, k_tools: int = 15, k_models: int = 10):
        """Retrieve relevant tools and models via vector search; fallback to keyword heuristics."""
        # Ensure indexes are built
        if self.tool_index is None or self.model_index is None:
            try:
                self._build_indexes()
            except Exception as e:
                print(f"RAG index build failed, will fallback to keyword matching: {e}")

        # Base data from registry
        all_tools = self.registry.discover_tools()
        tools_by_name = {getattr(t, "name", ""): t for t in all_tools}
        all_models = self.registry.find_entities_by_type(self.registry.entities.get("Model", type(None)))
        models_by_name = {getattr(m, "name", ""): m for m in all_models}

        relevant_tools = []
        relevant_models = []
        try:
            if self.tool_index is not None:
                docs = self.tool_index.similarity_search(query, k=k_tools)
                for d in docs:
                    name = d.metadata.get("name")
                    if name in tools_by_name:
                        relevant_tools.append(tools_by_name[name])
            if self.model_index is not None:
                mdocs = self.model_index.similarity_search(query, k=k_models)
                for d in mdocs:
                    name = d.metadata.get("name")
                    if name in models_by_name:
                        relevant_models.append(models_by_name[name])
        except Exception as e:
            print(f"RAG retrieval failed, falling back to keyword matching: {e}")

        # Fallback to simple keyword method if empty
        if not relevant_tools:
            keywords = [w.lower() for w in query.split()]
            def clean_token(tok: str) -> str:
                return tok.strip("'\".,:;!?()[]{}")
            norm_keywords = [clean_token(k) for k in keywords]
            for tool in all_tools:
                name = getattr(tool, "name", str(tool)).lower()
                desc = getattr(tool, "description", "").lower()
                if any(k and (k in name or k in desc) for k in norm_keywords):
                    relevant_tools.append(tool)
            if not relevant_tools:
                relevant_tools = all_tools[:5]
        if not relevant_models:
            for model in all_models:
                name = getattr(model, "name", str(model)).lower()
                if any(k in name for k in [w.lower() for w in query.split()]):
                    relevant_models.append(model)
            if not relevant_models:
                relevant_models = all_models[:5]
        return relevant_tools, relevant_models

    def plan_workflow(self, user_goal: str) -> WorkflowPlan:
        """Use LLM to reason and generate a workflow plan for the user goal (filtered context)"""
        goal = AgentGoal(
            description=user_goal,
            success_criteria={"completed": True}
        )
        plan = WorkflowPlan(goal=goal)

        # Retrieve relevant tools and models via RAG (with fallback)
        relevant_tools, relevant_models = self._retrieve_relevant(user_goal)

        tool_names = [getattr(tool, "name", str(tool)) for tool in relevant_tools[:10]]
        model_names = [getattr(model, "name", str(model)) for model in relevant_models[:10]]
        available_servers = list(self.registry.tools_by_server.keys())
        
        prompt = (
            f"You are an MDE agent. Your goal is: {user_goal}\n"
            f"Relevant tools: {tool_names}\n"
            f"Relevant models: {model_names}\n"
            f"Available server names: {available_servers}\n"
            "Generate a workflow plan as a JSON list of steps. Each step must be a JSON object with keys: tool_name, server_name, parameters, description.\n"
        #     "Rules: (1) Use list_transformation_*_tool for info-only queries (parameters can be {}).\n"
        #     "(2) If you choose an apply_*_transformation_tool, you MUST include parameters.file_path with the absolute path to the input .xmi file (the executor attaches it as multipart field IN). Without file_path, the call fails.\n"
        #     "(3) Use only the file path that appears in the user goal; do not invent paths.\n"
        #     "Output ONLY the JSON list, no extra text. Example: [{\"tool_name\": ..., \"server_name\": ..., \"parameters\": {...}, \"description\": ...}]"
        # )
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
            steps = json.loads(response_text)
        except Exception as e:
            print(f"LLM response JSON parsing error: {e}")
            import re
            match = re.search(r'(\[.*\])', response_text, re.DOTALL)
            if match:
                try:
                    steps = json.loads(match.group(1))
                except Exception as e2:
                    print(f"Fallback JSON extraction error: {e2}")
            if not steps:
                import ast
                for line in response_text.splitlines():
                    if line.strip().startswith("{"):
                        try:
                            steps.append(ast.literal_eval(line.strip()))
                        except Exception as e2:
                            print(f"Line parsing error: {e2} | Line: {line.strip()}")
                            continue

        # Build a lookup to resolve server_name by tool name when missing
        all_tools = self.registry.discover_tools()
        tool_index = {getattr(t, "name", ""): t for t in all_tools}
        available_servers = list(self.registry.tools_by_server.keys())
        
        for step in steps:
            if isinstance(step, dict):
                tool_name = step.get("tool_name")
                server_name = step.get("server_name")
                if not server_name:
                    if tool_name in tool_index and getattr(tool_index[tool_name], "server_name", ""):
                        server_name = tool_index[tool_name].server_name
                    else:
                        server_name = available_servers[0] if available_servers else ""
                parameters = step.get("parameters", {}) or {}
                plan.add_step(PlanStep(
                    tool_name=tool_name,
                    server_name=server_name,
                    parameters=parameters,
                    description=step.get("description", "")
                ))
        return plan

    def run(self, user_goal: str):
        """End-to-end agent orchestration: plan and execute workflow"""
        plan = self.plan_workflow(user_goal)
        result = self.executor.execute_workflow(plan)
        return result