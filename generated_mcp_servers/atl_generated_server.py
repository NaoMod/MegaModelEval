import sys
import os
import json
import subprocess
import threading
import asyncio
from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI
import uvicorn

SERVER_BASE = "http://localhost:8080"

mcp = FastMCP("atl_generated")

ARTIFACTS = [
    {"name": "KM32DSL", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "KM32EMF", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "PNML2XML", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "Mantis2XML", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "XML2Ant", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "SimpleClass2SimpleRDBMS", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "XML2XSLT", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "Families2Persons", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "MySQL2KM3", "source_metamodel": "IN", "target_metamodel": "IN"},
    {"name": "Ant2Maven", "source_metamodel": "OUT", "target_metamodel": "OUTMaven"},
    {"name": "UML2Measure", "source_metamodel": "UML2MOF_2", "target_metamodel": "UML2MOF_2"},
    {"name": "KM32OWL", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "Grafcet2PetriNet", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "PathExp2PetriNet", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "XML2MySQL", "source_metamodel": "OUT", "target_metamodel": "IN"},
    {"name": "RedundantInheritance_with_context", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "ATOM2RSS", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "UML2KM3", "source_metamodel": "UML", "target_metamodel": "IN"},
    {"name": "A2B", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "Make2Ant", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "PNML2PetriNet", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "Table2SVGBarChart", "source_metamodel": "Table", "target_metamodel": "SVGBarChart"},
    {"name": "TextualPathExp2PathExp", "source_metamodel": "IN", "target_metamodel": "IN"},
    {"name": "XML2R2ML", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "KM32Problem", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "Ant2XML", "source_metamodel": "OUT", "target_metamodel": "IN"},
    {"name": "Class2Relational", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "XML2DSL", "source_metamodel": "OUT", "target_metamodel": "OUT"},
    {"name": "Uml2Amble", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "XML2SpreadsheetMLSimplified", "source_metamodel": "OUT", "target_metamodel": "OUT"},
    {"name": "XML2PNML", "source_metamodel": "OUT", "target_metamodel": "IN"},
    {"name": "R2ML2WSDL", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "PathExp2TextualPathExp", "source_metamodel": "IN", "target_metamodel": "IN"},
    {"name": "Partial2totalRoleB", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "Partial2totalRoleA", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "XML2Book", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "Table2SpreadsheetMLSimplified", "source_metamodel": "Table", "target_metamodel": "OUT"},
    {"name": "XML2Make", "source_metamodel": "IN", "target_metamodel": "IN"},
    {"name": "PetriNet2XML", "source_metamodel": "OUT", "target_metamodel": "OUT"},
    {"name": "Activity2BPMN", "source_metamodel": "UML", "target_metamodel": "OUT"},
    {"name": "Table2SVGPieChart", "source_metamodel": "Table", "target_metamodel": "SVGPieChart"},
    {"name": "Table2TabularHTML", "source_metamodel": "Table", "target_metamodel": "TabularHTML"},
    {"name": "XML2GeoTrans", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "Book2Publication", "source_metamodel": "OUT", "target_metamodel": "OUT"},
    {"name": "KM32Metrics", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "DSL2KM3", "source_metamodel": "OUT", "target_metamodel": "IN"},
    {"name": "XSLT2XQuery", "source_metamodel": "OUT", "target_metamodel": "OUT"},
    {"name": "XML2WSDL", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "XML2PetriNet", "source_metamodel": "OUT", "target_metamodel": "OUT"},
    {"name": "Maven2Ant", "source_metamodel": "OUTMaven", "target_metamodel": "OUT"},
    {"name": "PetriNet2PNML", "source_metamodel": "OUT", "target_metamodel": "IN"},
    {"name": "Measure2Table", "source_metamodel": "Measure", "target_metamodel": "Table"},
    {"name": "PetriNet2Grafcet", "source_metamodel": "OUT", "target_metamodel": "IN"},
    {"name": "PetriNet2PathExp", "source_metamodel": "OUT", "target_metamodel": "IN"},
    {"name": "PrimaryKey_with_context", "source_metamodel": "IN", "target_metamodel": "IN"},
    {"name": "XML2RSS", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "XML2DXF", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "METAH2ACME", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "KM32DOT", "source_metamodel": "IN", "target_metamodel": "OUT"},
    {"name": "JavaSource2Table", "source_metamodel": "JavaSource", "target_metamodel": "Table"},
    {"name": "XML2KML", "source_metamodel": "OUT", "target_metamodel": "OUT"}
]

def make_transform_tool(item_name, description, method="GET"):
    @mcp.tool(name=f"{item_name}_transformation_tool", description=description)
    async def transformation_tool(*, input_model_path=None) -> str:
        url = f"{SERVER_BASE}/transformation/{item_name}"
        cmd = ["curl", "-s"]
        if method.upper() == "GET":
            cmd.extend(["-X", "GET"])
        elif method.upper() == "POST":
            cmd.extend(["-X", "POST"])
        if input_model_path:
            cmd.extend(["-F", f"IN=@{input_model_path}"])
        cmd.append(url)
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
    return transformation_tool

def make_apply_tool(item_name, description):
    @mcp.tool(name=f"{item_name}_apply_tool", description=description)
    async def apply_tool(input_files=None) -> str:
        url = f"{SERVER_BASE}/transformation/{item_name}/apply"
        cmd = ["curl", "-s", "-X", "POST"]
        if input_files:
            for file_path in input_files:
                cmd.extend(["-F", f"IN=@{file_path}"])
        cmd.append(url)
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
    return apply_tool

def make_search_by_input_metamodel_tool(item_name, description):
    @mcp.tool(name=f"{item_name}_search_input_metamodel_tool", description=description)
    async def search_input_metamodel(input_metamodel) -> str:
        url = f"{SERVER_BASE}/transformation/hasTransformation"
        # Normally, implement with query params, but curl command here can be adapted as needed
        cmd = ["curl", "-G", f"{SERVER_BASE}/transformation/hasTransformation", "--data-urlencode", f"inputMetamodel={input_metamodel}"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
    return search_input_metamodel

for artifact in ARTIFACTS:
    name = artifact["name"]
    src_mm = artifact["source_metamodel"]
    tgt_mm = artifact["target_metamodel"]
    
    # Assign description text based on possible endpoints
    description_transform = f"Run transformation for {name}"
    description_apply = f"Apply transformation {name}"
    description_search_input = f"Search transformations by input metamodel {src_mm}"

    # Check which endpoints are relevant based on API spec analysis
    # For simplicity, assume transformations and apply are generally applicable
    globals()[f"{name}_transformation"] = make_transform_tool(name, description_transform)
    globals()[f"{name}_apply"] = make_apply_tool(name, description_apply)
    # For transformations that support inputMetamodel search
    if src_mm in {"IN", "UML", "Table", "JavaSource"}:
        globals()[f"{name}_search_by_input_metamodel"] = make_search_by_input_metamodel_tool(name, description_search_input)

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
