import os
import json
from typing import List, Dict, Any
from dataclasses import dataclass
from openai import OpenAI
from dotenv import load_dotenv

from core.am3 import Entity, TransformationModel

load_dotenv()


MCP_SERVER_TEMPLATE = '''import sys
import os
import json
import subprocess
from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI
import uvicorn
import threading

SERVER_BASE = "{backend_url}"

mcp = FastMCP("{server_name}")

{tools_code}

if __name__ == "__main__":
    app = FastAPI()

    @app.get("/tools")
    def get_tools():
        tool_manager = mcp._tool_manager
        tools = []
        if hasattr(tool_manager, 'tools'):
            for name, tool in tool_manager.tools.items():
                tools.append({{"name": name, "description": getattr(tool, 'description', '')}})
        elif hasattr(tool_manager, '_tools'):
            for name, tool in tool_manager._tools.items():
                tools.append({{"name": name, "description": getattr(tool, 'description', '')}})
        return {{"tools": tools}}

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


class MCPServerGenerator:
    def __init__(self, config: MCPServerConfig):
        self.config = config
        self.client = OpenAI()
    
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
                    "operations": ["apply", "get"]
                })
        return tools
    
    def generate_tools_code_with_llm(self, tools_spec: List[Dict[str, Any]]) -> str:
        prompt = f"""Generate Python code for an MCP server that dynamically creates tools using a for loop.

Tools specification (list of transformations):
{json.dumps(tools_spec, indent=2)}

Server backend URL: {self.config.backend_url}

CRITICAL Requirements:
1. Define a TRANSFORMATIONS list containing the tool specs
2. Use a for loop to iterate over TRANSFORMATIONS
3. For each transformation, create two tool functions using a closure/factory pattern:
   - apply_<name>_transformation_tool: POST to SERVER_BASE/transformation/<name>/apply with file
   - list_transformation_<name>_tool: GET to SERVER_BASE/transformation/<name>
4. IMPORTANT: Use the existing `mcp` object (already defined as `mcp = FastMCP(...)`) 
   Register tools using `mcp.tool(name=..., description=...)` as a decorator
   DO NOT create your own decorator or placeholder - use the real mcp.tool
5. Example pattern for dynamic tool registration:
   ```
   def make_apply_tool(t_name, desc):
       @mcp.tool(name=f"apply_{{t_name}}_tool", description=desc)
       async def tool_func(file_path: str) -> str:
           # implementation
           return result
       return tool_func
   
   for t in TRANSFORMATIONS:
       make_apply_tool(t["name"], f"Apply {{t['name']}} transformation")
   ```
6. Use async def, subprocess.run with curl, try/except for errors
7. The apply tool should take file_path as parameter and use curl with -F 'IN=@{{file_path}}' format
7. The loop pattern should work for any number of transformations

Output ONLY the Python code (TRANSFORMATIONS list + for loop with factory functions), no markdown, no explanation."""

        print("=" * 60)
        print("LLM PROMPT:")
        print("=" * 60)
        print(prompt)
        print("=" * 60)

        response = self.client.chat.completions.create(
            model="gpt-4.1-nano",
            messages=[{"role": "user", "content": prompt}]
        )
        
        code = response.choices[0].message.content.strip()
        
        print("LLM RESPONSE:")
        print("=" * 60)
        print(code)
        print("=" * 60)
        
        if code.startswith("```"):
            code = code.split("\n", 1)[1]
        if code.endswith("```"):
            code = code.rsplit("```", 1)[0]
        return code
    
    def generate(self, artifacts: List[Entity], output_path: str) -> str:
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


def generate_mcp_server(artifacts: List[Entity], config: MCPServerConfig, output_path: str) -> str:
    generator = MCPServerGenerator(config)
    return generator.generate(artifacts, output_path)
