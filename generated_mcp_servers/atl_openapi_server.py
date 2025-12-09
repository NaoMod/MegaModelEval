import sys
import os
import json
import subprocess
import threading
from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI
import uvicorn

SERVER_BASE = "http://localhost:8080"

mcp = FastMCP("atl_openapi")


@mcp.tool(name="transformations_tool", description="""Returns a JSON array of all available ATL transformations.""")
async def transformations_tool() -> str:
    """
    List all transformations
    """
    url = f"{SERVER_BASE}/transformations"
    cmd = ["curl", "-s", "-X", "GET"]
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"


@mcp.tool(name="transformations_enabled_tool", description="""Returns only transformations that are marked as enabled.""")
async def transformations_enabled_tool() -> str:
    """
    List enabled transformations
    """
    url = f"{SERVER_BASE}/transformations/enabled"
    cmd = ["curl", "-s", "-X", "GET"]
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"


@mcp.tool(name="transformations_samples_tool", description="""Returns enabled transformations with non-empty sample source model paths.""")
async def transformations_samples_tool() -> str:
    """
    List transformations with sample models
    """
    url = f"{SERVER_BASE}/transformations/samples"
    cmd = ["curl", "-s", "-X", "GET"]
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"


@mcp.tool(name="transformations_search_tool", description="""Search for a term in all ATL transformation files.""")
async def transformations_search_tool(query: str) -> str:
    """
    Search transformations
    """
    url = f"{SERVER_BASE}/transformations/search"
    cmd = ["curl", "-s", "-X", "GET"]
    query_parts = []
    if query:
        query_parts.append(f"query={query}")
    if query_parts:
        url = url + "?" + "&".join(query_parts)
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"


@mcp.tool(name="transformations_byInputMetamodel_tool", description="""Returns transformations grouped by input metamodels (only >2 transformations).""")
async def transformations_byInputMetamodel_tool() -> str:
    """
    Categorize transformations by input metamodel
    """
    url = f"{SERVER_BASE}/transformations/byInputMetamodel"
    cmd = ["curl", "-s", "-X", "GET"]
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"


@mcp.tool(name="transformation_hasTransformation_tool", description="""Search for transformations matching input and output metamodels.""")
async def transformation_hasTransformation_tool(inputMetamodel: str, outputMetamodel: str) -> str:
    """
    Find transformations by metamodels
    """
    url = f"{SERVER_BASE}/transformation/hasTransformation"
    cmd = ["curl", "-s", "-X", "GET"]
    query_parts = []
    if inputMetamodel:
        query_parts.append(f"inputMetamodel={inputMetamodel}")
    if outputMetamodel:
        query_parts.append(f"outputMetamodel={outputMetamodel}")
    if query_parts:
        url = url + "?" + "&".join(query_parts)
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"


@mcp.tool(name="transformation_Name_tool", description="""Get transformation by name""")
async def transformation_Name_tool(Name: str) -> str:
    """
    Get transformation by name
    """
    url = f"{SERVER_BASE}/transformation/{Name}"
    cmd = ["curl", "-s", "-X", "GET"]
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"


@mcp.tool(name="post_transformation_Name_apply_tool", description="""Apply an ATL transformation to uploaded input model(s).
Field names should match the input metamodel names (e.g., IN, INMaven).
""")
async def post_transformation_Name_apply_tool(Name: str, file_path: str) -> str:
    """
    Apply a transformation
    """
    url = f"{SERVER_BASE}/transformation/{Name}/apply"
    cmd = ["curl", "-s", "-X", "POST"]
    if file_path:
        cmd.extend(["-F", f"IN=@{file_path}"])
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"


@mcp.tool(name="post_transformation_add_tool", description="""Add a new transformation""")
async def post_transformation_add_tool(name: str, atlFilePath: str, inputMetamodelPath1: str, outputMetamodelPath1: str, description: str = None) -> str:
    """
    Add a new transformation
    """
    url = f"{SERVER_BASE}/transformation/add"
    cmd = ["curl", "-s", "-X", "POST"]
    if name:
        cmd.extend(["-d", f"name={name}"])
    if atlFilePath:
        cmd.extend(["-d", f"atlFilePath={atlFilePath}"])
    if description:
        cmd.extend(["-d", f"description={description}"])
    if inputMetamodelPath1:
        cmd.extend(["-d", f"inputMetamodelPath1={inputMetamodelPath1}"])
    if outputMetamodelPath1:
        cmd.extend(["-d", f"outputMetamodelPath1={outputMetamodelPath1}"])
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"


@mcp.tool(name="post_transformation_chain_tool", description="""Apply multiple transformations sequentially.""")
async def post_transformation_chain_tool(transformationChain: str, file_path: str) -> str:
    """
    Apply a chain of transformations
    """
    url = f"{SERVER_BASE}/transformation/chain"
    cmd = ["curl", "-s", "-X", "POST"]
    if file_path:
        cmd.extend(["-F", f"file=@{file_path}"])
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"


@mcp.tool(name="debug_transformations_tool", description="""Debug endpoint for transformations""")
async def debug_transformations_tool() -> str:
    """
    Debug endpoint for transformations
    """
    url = f"{SERVER_BASE}/debug/transformations"
    cmd = ["curl", "-s", "-X", "GET"]
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"


@mcp.tool(name="spec_tool", description="""List all registered routes""")
async def spec_tool() -> str:
    """
    List all registered routes
    """
    url = f"{SERVER_BASE}/spec"
    cmd = ["curl", "-s", "-X", "GET"]
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"


@mcp.tool(name="openapi_tool", description="""Get OpenAPI specification""")
async def openapi_tool() -> str:
    """
    Get OpenAPI specification
    """
    url = f"{SERVER_BASE}/openapi"
    cmd = ["curl", "-s", "-X", "GET"]
    cmd.append(url)
    result = subprocess.run(cmd, capture_output=True, text=True)
    return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"

if __name__ == "__main__":
    # List registered tools using MCP's built-in method
    print(f"Registered tools: {list(mcp._tool_manager._tools.keys())}")
    
    # Create FastAPI app for HTTP access
    app = FastAPI()
    
    @app.get("/tools")
    def get_tools():
        tools = []
        for name, tool in mcp._tool_manager._tools.items():
            desc = getattr(tool, 'description', '')
            tools.append({"name": name, "description": desc})
        return {"tools": tools}
    
    @app.post("/tools/{tool_name}")
    async def call_tool(tool_name: str, params: dict = None):
        if tool_name in mcp._tool_manager._tools:
            tool = mcp._tool_manager._tools[tool_name]
            if params:
                result = await tool.fn(**params)
            else:
                result = await tool.fn()
            return {"result": result}
        return {"error": f"Tool {tool_name} not found"}
    
    # Start FastAPI server in a separate thread
    def run_fastapi():
        uvicorn.run(app, host="0.0.0.0", port=8081, log_level="info")
    
    threading.Thread(target=run_fastapi, daemon=True).start()
    
    mcp.run(transport='stdio')
