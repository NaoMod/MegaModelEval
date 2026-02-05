import os
import sys
import json
import asyncio
import requests
from typing import List, Dict, Any
from dataclasses import dataclass
from openai import OpenAI
from dotenv import load_dotenv

# Ensure project root and src are on path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from src.core.am3 import Entity, TransformationModel
from src.core.megamodel import MegamodelRegistry

load_dotenv()


async def get_artifacts_from_megamodel() -> List[TransformationModel]:
    """Fetch TransformationModel artifacts from the megamodel registry."""
    # Import here to avoid circular imports
    from scripts.run_agent_versions import populate_registry
    
    registry = MegamodelRegistry()
    await populate_registry(registry)
    
    # Get all TransformationModel entities from the registry
    transformations = registry.find_entities_by_type(TransformationModel)
    return transformations


MCP_SERVER_TEMPLATE = '''import sys
import os
import json
import subprocess
import threading
import asyncio
from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI
import uvicorn

SERVER_BASE = "{backend_url}"

mcp = FastMCP("{server_name}")

{tools_code}

if __name__ == "__main__":
    # List registered tools using MCP's built-in method
    print(f"Registered tools: {{list(mcp._tool_manager._tools.keys())}}")
    
    # Create FastAPI app for HTTP access
    app = FastAPI()
    
    @app.get("/tools")
    def get_tools():
        tools = []
        for name, tool in mcp._tool_manager._tools.items():
            desc = getattr(tool, 'description', '')
            tools.append({{"name": name, "description": desc}})
        return {{"tools": tools}}
    
    @app.post("/tools/{{tool_name}}")
    async def call_tool(tool_name: str, params: dict = None):
        if tool_name in mcp._tool_manager._tools:
            tool = mcp._tool_manager._tools[tool_name]
            if params:
                result = await tool.fn(**params)
            else:
                result = await tool.fn()
            return {{"result": result}}
        return {{"error": f"Tool {{tool_name}} not found"}}
    
    # Start FastAPI server in a separate thread
    def run_fastapi():
        uvicorn.run(app, host="0.0.0.0", port={port}, log_level="info")
    
    threading.Thread(target=run_fastapi, daemon=True).start()
    
    mcp.run(transport='stdio')
'''


@dataclass
class MCPServerConfig:
    name: str
    backend_url: str = "http://localhost:8080"
    port: int = 8081


def fetch_backend_spec(backend_url: str) -> List[Dict[str, Any]]:
    """Fetch the API spec from the backend server's /spec endpoint."""
    try:
        response = requests.get(f"{backend_url}/spec", timeout=5)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Warning: Could not fetch backend spec from {backend_url}/spec: {e}")
        return []


class MCPServerGenerator:
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.client = OpenAI()
        self.backend_spec = fetch_backend_spec(config.backend_url)
    
    def extract_tools_spec(self, artifacts: List[Entity]) -> List[Dict[str, Any]]:
        tools = []
        for artifact in artifacts:
            if isinstance(artifact, TransformationModel):
                src = artifact.source_metamodel.name if artifact.source_metamodel else "Unknown"
                tgt = artifact.target_metamodel.name if artifact.target_metamodel else "Unknown"
                
                tools.append({
                    "name": artifact.name,
                    "source_metamodel": src,
                    "target_metamodel": tgt,
                })
        return tools
    
    def generate_tools_code_with_llm(self, tools_spec: List[Dict[str, Any]]) -> str:
        prompt = f"""Generate Python code that creates MCP tools dynamically using a for loop.

Artifacts to expose as tools:
{json.dumps(tools_spec, indent=2)}

Backend API spec (available endpoints):
{json.dumps(self.backend_spec, indent=2)}

Server backend URL: {self.config.backend_url}

REQUIREMENTS:
1. Analyze the API spec to identify which endpoints apply to each artifact
2. Define a list containing the artifact specs
3. For each artifact, create tool functions for relevant endpoints from the spec
4. Use factory functions with a for loop for dynamic registration

CONSTRAINTS - YOU MUST FOLLOW:
- DO NOT add import statements (already provided in template)
- DO NOT initialize mcp (already defined as `mcp = FastMCP(...)`)
- DO NOT define SERVER_BASE or BASE_URL (use `SERVER_BASE` which exists)
- Use `subprocess.run` with curl (NOT asyncio.create_subprocess_exec)
- For POST with file upload, use: curl -F 'IN=@{{file_path}}'
- For GET requests, use: curl -X GET
- CRITICAL: Always append the URL to the cmd list before subprocess.run! Example: cmd.append(url)

PATTERN TO FOLLOW:
```
ITEMS = [...]  # list of artifacts

def make_tool_for_endpoint_X(item_name, ...):
    @mcp.tool(name=f"..._{{item_name}}_tool", description="...")
    async def func(...) -> str:
        url = f"{{SERVER_BASE}}/endpoint/{{item_name}}"
        cmd = ["curl", "-s", "-X", "GET"]
        # ... add any options to cmd ...
        cmd.append(url)  # IMPORTANT: Always append URL to cmd!
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else f"Error: {{result.stderr}}"
    return func

for item in ITEMS:
    make_tool_for_endpoint_X(item["name"], ...)
```

Output ONLY the Python code (list + factory functions + loop). No markdown, no imports, no explanation."""


        response = self.client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{"role": "user", "content": prompt}]
        )
        
        code = response.choices[0].message.content.strip()
        
        if code.startswith("```"):
            code = code.split("\n", 1)[1]
        if code.endswith("```"):
            code = code.rsplit("```", 1)[0]
        return code
    
    def generate(self, artifacts: List[Entity], output_path: str) -> str:
        print(f"Fetched backend spec: {len(self.backend_spec)} endpoints")
        for ep in self.backend_spec:
            print(f"  {ep.get('methods', '')} {ep.get('path', '')}")
        
        tools_spec = self.extract_tools_spec(artifacts)
        tools_code = self.generate_tools_code_with_llm(tools_spec)
        
        server_code = MCP_SERVER_TEMPLATE.format(
            backend_url=self.config.backend_url,
            server_name=self.config.name,
            port=self.config.port,
            tools_code=tools_code
        )
        
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(server_code)        
        return server_code


def generate_mcp_server(config: MCPServerConfig, output_path: str, artifacts: List[Entity] = None) -> str:
    """Generate an MCP server.
    
    Args:
        config: Server configuration
        output_path: Path to write the generated server code
        artifacts: Optional list of entities. If not provided, fetches from megamodel.
    """
    generator = MCPServerGenerator(config)
    
    if artifacts is None:
        # Fetch artifacts from the megamodel
        print("Fetching artifacts from megamodel...")
        artifacts = asyncio.run(get_artifacts_from_megamodel())
        print(f"Found {len(artifacts)} transformation artifacts in megamodel")
    
    return generator.generate(artifacts, output_path)


if __name__ == "__main__":
    # Generate an MCP server using artifacts from the megamodel
    config = MCPServerConfig(name='atl_generated', backend_url='http://localhost:8080', port=8081)
    output_path = os.path.join(os.path.dirname(__file__), '..', '..', 'generated_mcp_servers', 'atl_generated_server.py')
    generate_mcp_server(config, output_path)
    print(f"Server generated at: {output_path}")
