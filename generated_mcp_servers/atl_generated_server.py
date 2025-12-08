import sys
import os
import json
import subprocess
import threading
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

def make_transformations_tool(item_name, path, methods):
    @mcp.tool(name=f"{item_name}_transform", description=f"Transform using {item_name}")
    def transformation_tool():
        cmd = ["curl", "-X", "GET", f"{SERVER_BASE}{path}"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
    return transformation_tool

def make_enabled_tool(item_name):
    @mcp.tool(name=f"{item_name}_enabled", description=f"Check if {item_name} transformation is enabled")
    def enabled_tool():
        cmd = ["curl", "-X", "GET", f"{SERVER_BASE}/transformations/enabled"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
    return enabled_tool

def make_samples_tool(item_name):
    @mcp.tool(name=f"{item_name}_samples", description=f"Get samples for {item_name}")
    def samples_tool():
        cmd = ["curl", "-X", "GET", f"{SERVER_BASE}/transformations/samples"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
    return samples_tool

def make_has_transformation_tool(item_name):
    @mcp.tool(name=f"{item_name}_hasTransformation", description=f"Check if {item_name} has transformation")
    def has_transformation():
        cmd = ["curl", "-X", "GET", f"{SERVER_BASE}/transformation/hasTransformation"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
    return has_transformation

def make_get_transformation_by_name_tool(item_name):
    @mcp.tool(name=f"{item_name}_getTransformation", description=f"Get {item_name} transformation details")
    def get_transformation():
        cmd = ["curl", "-X", "GET", f"{SERVER_BASE}/transformation/{item_name}"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
    return get_transformation

def make_apply_transformation_tool(item_name):
    @mcp.tool(name=f"{item_name}_apply", description=f"Apply {item_name} transformation")
    def apply_transformation():
        cmd = ["curl", "-X", "POST", f"{SERVER_BASE}/transformation/{item_name}/apply"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
    return apply_transformation

def make_add_transformation_tool(item_name):
    @mcp.tool(name=f"{item_name}_add", description=f"Add {item_name} transformation")
    def add_transformation():
        cmd = ["curl", "-X", "POST", f"{SERVER_BASE}/transformation/add"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"
    return add_transformation

for artifact in ARTIFACTS:
    name = artifact["name"]
    source = artifact["source_metamodel"]
    target = artifact["target_metamodel"]

    # Determine applicable endpoints
    # For GET /transformations: all
    make_transformations_tool(name, "/transformations", "[GET]")
    # For GET /transformations/enabled: depending on source or target?
    # For simplicity, associate with all artifacts
    make_enabled_tool(name)
    # For GET /transformations/samples
    make_samples_tool(name)
    # For GET /transformation/hasTransformation
    make_has_transformation_tool(name)
    # For GET /transformation/:idOrName
    make_get_transformation_by_name_tool(name)
    # For POST /transformation/:idOrName/apply
    make_apply_transformation_tool(name)
    # For POST /transformation/add
    make_add_transformation_tool(name)

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
    def call_tool(tool_name: str):
        if tool_name in mcp._tool_manager._tools:
            tool = mcp._tool_manager._tools[tool_name]
            # Call the tool function
            result = tool.fn()
            return {"result": result}
        return {"error": f"Tool {tool_name} not found"}
    
    # Start FastAPI server in a separate thread
    def run_fastapi():
        uvicorn.run(app, host="0.0.0.0", port=8081, log_level="info")
    
    threading.Thread(target=run_fastapi, daemon=True).start()
    
    mcp.run(transport='stdio')
