import sys
import os
import json
import subprocess
from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI
import uvicorn
import threading

SERVER_BASE = "http://localhost:8080"

mcp = FastMCP("atl_generated")

TRANSFORMATIONS = [
    {
        "name": "KM32DSL",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "KM32EMF",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "PNML2XML",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "Mantis2XML",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "XML2Ant",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "SimpleClass2SimpleRDBMS",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "XML2XSLT",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "Families2Persons",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "MySQL2KM3",
        "source_metamodel": "IN",
        "target_metamodel": "IN",
        "operations": ["apply", "get"]
    },
    {
        "name": "Ant2Maven",
        "source_metamodel": "OUT",
        "target_metamodel": "OUTMaven",
        "operations": ["apply", "get"]
    },
    {
        "name": "UML2Measure",
        "source_metamodel": "UML2MOF_2",
        "target_metamodel": "UML2MOF_2",
        "operations": ["apply", "get"]
    },
    {
        "name": "KM32OWL",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "Grafcet2PetriNet",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "PathExp2PetriNet",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "XML2MySQL",
        "source_metamodel": "OUT",
        "target_metamodel": "IN",
        "operations": ["apply", "get"]
    },
    {
        "name": "RedundantInheritance_with_context",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "ATOM2RSS",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "UML2KM3",
        "source_metamodel": "UML",
        "target_metamodel": "UML",
        "operations": ["apply", "get"]
    },
    {
        "name": "A2B",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "Make2Ant",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "PNML2PetriNet",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "Table2SVGBarChart",
        "source_metamodel": "Table",
        "target_metamodel": "SVGBarChart",
        "operations": ["apply", "get"]
    },
    {
        "name": "TextualPathExp2PathExp",
        "source_metamodel": "IN",
        "target_metamodel": "IN",
        "operations": ["apply", "get"]
    },
    {
        "name": "XML2R2ML",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "KM32Problem",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "Ant2XML",
        "source_metamodel": "OUT",
        "target_metamodel": "IN",
        "operations": ["apply", "get"]
    },
    {
        "name": "Class2Relational",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "XML2DSL",
        "source_metamodel": "OUT",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "Uml2Amble",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "XML2SpreadsheetMLSimplified",
        "source_metamodel": "OUT",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "XML2PNML",
        "source_metamodel": "OUT",
        "target_metamodel": "IN",
        "operations": ["apply", "get"]
    },
    {
        "name": "R2ML2WSDL",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "PathExp2TextualPathExp",
        "source_metamodel": "IN",
        "target_metamodel": "IN",
        "operations": ["apply", "get"]
    },
    {
        "name": "Partial2totalRoleB",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "Partial2totalRoleA",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "XML2Book",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "Table2SpreadsheetMLSimplified",
        "source_metamodel": "Table",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "XML2Make",
        "source_metamodel": "IN",
        "target_metamodel": "IN",
        "operations": ["apply", "get"]
    },
    {
        "name": "PetriNet2XML",
        "source_metamodel": "OUT",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "Activity2BPMN",
        "source_metamodel": "UML",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "Table2SVGPieChart",
        "source_metamodel": "Table",
        "target_metamodel": "SVGPieChart",
        "operations": ["apply", "get"]
    },
    {
        "name": "Table2TabularHTML",
        "source_metamodel": "Table",
        "target_metamodel": "TabularHTML",
        "operations": ["apply", "get"]
    },
    {
        "name": "XML2GeoTrans",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "Book2Publication",
        "source_metamodel": "OUT",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "KM32Metrics",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "DSL2KM3",
        "source_metamodel": "OUT",
        "target_metamodel": "IN",
        "operations": ["apply", "get"]
    },
    {
        "name": "XSLT2XQuery",
        "source_metamodel": "OUT",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "XML2WSDL",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "XML2PetriNet",
        "source_metamodel": "OUT",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "Maven2Ant",
        "source_metamodel": "OUTMaven",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "PetriNet2PNML",
        "source_metamodel": "OUT",
        "target_metamodel": "IN",
        "operations": ["apply", "get"]
    },
    {
        "name": "Measure2Table",
        "source_metamodel": "Measure",
        "target_metamodel": "Table",
        "operations": ["apply", "get"]
    },
    {
        "name": "PetriNet2Grafcet",
        "source_metamodel": "OUT",
        "target_metamodel": "IN",
        "operations": ["apply", "get"]
    },
    {
        "name": "PetriNet2PathExp",
        "source_metamodel": "OUT",
        "target_metamodel": "IN",
        "operations": ["apply", "get"]
    },
    {
        "name": "PrimaryKey_with_context",
        "source_metamodel": "IN",
        "target_metamodel": "IN",
        "operations": ["apply", "get"]
    },
    {
        "name": "XML2RSS",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "XML2DXF",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "METAH2ACME",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "KM32DOT",
        "source_metamodel": "IN",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    },
    {
        "name": "JavaSource2Table",
        "source_metamodel": "JavaSource",
        "target_metamodel": "Table",
        "operations": ["apply", "get"]
    },
    {
        "name": "XML2KML",
        "source_metamodel": "OUT",
        "target_metamodel": "OUT",
        "operations": ["apply", "get"]
    }
]

SERVER_BASE = "http://localhost:8080"

for t in TRANSFORMATIONS:
    t_name = t["name"]
    description = f"Transformation tool for {t_name}"

    def make_apply_tool(transformation_name, desc):
        @mcp.tool(name=f"apply_{transformation_name}_tool", description=desc)
        async def apply_tool(file_path: str) -> str:
            import subprocess
            cmd = [
                "curl",
                "-X", "POST",
                f"{SERVER_BASE}/transformation/{transformation_name}/apply",
                "-F", f"IN=@{file_path}"
            ]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                return result.stdout
            except subprocess.CalledProcessError as e:
                return f"Error applying {transformation_name}: {e.stderr}"
        return apply_tool

    def make_get_tool(transformation_name, desc):
        @mcp.tool(name=f"list_transformation_{transformation_name}_tool", description=desc)
        async def list_tool() -> str:
            import subprocess
            url = f"{SERVER_BASE}/transformation/{transformation_name}"
            cmd = ["curl", "-X", "GET", url]
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
                return result.stdout
            except subprocess.CalledProcessError as e:
                return f"Error listing {transformation_name}: {e.stderr}"
        return list_tool

    # For each transformation, create apply and list tools if operations include 'apply' and 'get'
    if "apply" in t["operations"]:
        make_apply_tool(t_name, description)
    if "get" in t["operations"]:
        make_get_tool(t_name, description)

if __name__ == "__main__":
    app = FastAPI()

    @app.get("/tools")
    def get_tools():
        tool_manager = mcp._tool_manager
        tools = []
        if hasattr(tool_manager, 'tools'):
            for name, tool in tool_manager.tools.items():
                tools.append({"name": name, "description": getattr(tool, 'description', '')})
        elif hasattr(tool_manager, '_tools'):
            for name, tool in tool_manager._tools.items():
                tools.append({"name": name, "description": getattr(tool, 'description', '')})
        return {"tools": tools}

    def run_fastapi():
        uvicorn.run(app, host="0.0.0.0", port=8081, log_level="info")

    threading.Thread(target=run_fastapi, daemon=True).start()

    mcp.run(transport='stdio')
