import logging
import re
import sys
import os
import json
import subprocess
from mcp.server.fastmcp import FastMCP
from typing import Dict, Any, List
    # Add /tools endpoint to expose all registered tools
from fastapi import FastAPI
import uvicorn

# Constants
ATL_SERVER_BASE = "http://localhost:8080"

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger('atl_mcp_server')

# Initialize the MCP server
mcp = FastMCP("atl")

def fetch_transformations() -> list:
    """Fetch enabled transformations from the ATL server."""
    result = subprocess.run(['curl', '-X', 'GET', f'{ATL_SERVER_BASE}/transformations/enabled'], 
                          capture_output=True, text=True, check=True)
    return json.loads(result.stdout)

def get_transformation_details(transformation_name: str) -> Dict[str, Any]:
    """Get details of a specific transformation."""
    result = subprocess.run(['curl', '-X', 'GET', f'{ATL_SERVER_BASE}/transformations/enabled'], 
                          capture_output=True, text=True, check=True)
    transformations = json.loads(result.stdout)
    return next((t for t in transformations if t["name"] == transformation_name), None)

def create_transformation_description(transformation_name: str) -> str:
    """Create a description for the apply transformation tool."""
    transformation = get_transformation_details(transformation_name)
    if not transformation:
        return f"Transformation {transformation_name} not found"
    
    input_path = transformation["input_metamodels"][0]["path"]
    input_model = input_path.split("/")[-1].replace(".ecore", "")
    
    output_path = transformation["output_metamodels"][0]["path"]
    output_model = output_path.split("/")[-1].replace(".ecore", "")
    
    return f"Input metamodel: {input_model}, Output metamodel: {output_model}. This tool transforms {input_model} model into {output_model} model."

def generate_get_tool_description(transformation_name: str) -> str:
    """Create a description for the get transformation tool."""
    transformation = get_transformation_details(transformation_name)
    if not transformation:
        return f"Transformation {transformation_name} not found"
    
    input_path = transformation["input_metamodels"][0]["path"]
    input_model = input_path.split("/")[-1].replace(".ecore", "")
    
    output_path = transformation["output_metamodels"][0]["path"]
    output_model = output_path.split("/")[-1].replace(".ecore", "")
    
    return f"Displays details of transformation {transformation_name} that transforms {input_model} model into {output_model} model."

def _extract_from_content(content: str) -> str:
    """Extract metamodel name from XMI file content."""
    simple_xmlns_pattern = r'xmlns="([^"]*)"'
    match = re.search(simple_xmlns_pattern, content)
    if match:
        return match.group(1)

    complex_xmlns_pattern = r'xmlns:(\w+)="([^"]*)"'
    matches = re.findall(complex_xmlns_pattern, content)
    
    filtered_matches = [
        (prefix, url) for prefix, url in matches 
        if not prefix in ['xmi', 'xsi']
    ]
    
    if filtered_matches:
        metamodel_prefix = filtered_matches[0][0]
        root_pattern = rf'<{metamodel_prefix}:\w+'
        if re.search(root_pattern, content):
            return metamodel_prefix.upper()

    return None

@mcp.tool(name="extract_input_metamodel_name", description="Extracts the metamodel name from an XMI file. The input should be a file path to an XMI file. Returns the metamodel name (like 'Class', 'Grafcet', 'ECORE', or 'KM3').")
async def get_input_metamodel(file_path: str) -> str:
    """Extract the metamodel name from an XMI file."""
    try:
        file_path = str(file_path).strip()
        with open(file_path, 'r', encoding='utf-8') as file:
            content = file.read()
        metamodel_name = _extract_from_content(content)
        return f"Input metamodel name: {metamodel_name}" if metamodel_name else "Could not extract metamodel name from the file."
    except FileNotFoundError:
        return f"Error: File not found at path: {file_path}"
    except Exception as e:
        return f"An error occurred while processing the file: {str(e)}"
    

def get_transformation_names() -> List[str]:
    """Get list of enabled transformation names from the ATL server."""
    result = subprocess.run(['curl', '-X', 'GET', f'{ATL_SERVER_BASE}/transformations/enabled'], 
                          capture_output=True, text=True, check=True)
    transformations = json.loads(result.stdout)
    return [t["name"] for t in transformations]


@mcp.tool(
    name="list_transformation_samples_tool",
    description=(
        "List sample source model paths for enabled transformations. "
        "Optionally provide a transformation_name to filter the results."
    ),
)
async def list_transformation_samples(transformation_name: str = "") -> str:
    """Return sample sources for transformations, optionally filtered by name.

    When no name is provided, returns the full JSON array from the ATL server endpoint
    `/transformations/samples`. When a name is provided, returns the entry matching the
    transformation name or a message if none is found.
    """
    try:
        cmd = ['curl', '-s', '-X', 'GET', f'{ATL_SERVER_BASE}/transformations/samples']
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)

        if transformation_name:
            match = next((t for t in data if t.get('name') == transformation_name), None)
            if not match:
                return f"No samples found for transformation '{transformation_name}'."
            return json.dumps(match, indent=2)

        return json.dumps(data, indent=2)
    except subprocess.CalledProcessError as e:
        return f"Error fetching samples: {e.stderr}"
    except Exception as e:
        return f"Error: {str(e)}"

# Create dynamic tools for each transformation
transformations = fetch_transformations()
for t in transformations:
    name = t["name"]
    
    def create_apply_transformation(trans_name: str):
        @mcp.tool(name=f"apply_{trans_name}_transformation_tool", 
                 description=create_transformation_description(trans_name))
        async def apply_transformation(file_path: str) -> str:
            """Apply an ATL transformation to a model file."""
            try:
                # Handle dictionary input if needed
                if isinstance(file_path, dict):
                    file_path = next(iter(file_path.values()), '')
                
                file_path = str(file_path).strip()
                if not os.path.exists(file_path):
                    return f"Error: File not found at {file_path}"
                
                transformation_name = trans_name
                # Prepare the command for the transformation
                command = [
                    'curl', 
                    '-X', 'POST',
                    f'{ATL_SERVER_BASE}/transformation/{transformation_name}/apply', 
                    '-F', f'IN=@{file_path}'
                ]
                result = subprocess.run(command, capture_output=True, text=True, check=True)
                return f"Transformation {transformation_name} applied successfully:\n{result.stdout}"
            except subprocess.CalledProcessError as e:
                return f"Error applying transformation: {e.stderr}"
            except Exception as e:
                return f"Error: {str(e)}"
        return apply_transformation

    def create_get_transformation(trans_name: str):
        @mcp.tool(name=f"list_transformation_{trans_name}_tool", 
                 description=generate_get_tool_description(trans_name))
        async def get_transformation_info() -> str:
            """Get details about a specific ATL transformation."""
            try:
                transformation_name = trans_name
                command = ['curl', '-X', 'GET', f'{ATL_SERVER_BASE}/transformation/{transformation_name}']
                result = subprocess.run(command, capture_output=True, text=True, check=True)
                return f"Transformation '{transformation_name}':\n{result.stdout}"
            except subprocess.CalledProcessError as e:
                return f"Error fetching transformation: {e.stderr}"
        return get_transformation_info

    # Register the tools with the correct closure
    create_apply_transformation(name)
    create_get_transformation(name)

if __name__ == "__main__":

    app = FastAPI()

    @app.get("/tools")
    def get_tools():
        # Access tool manager from MCP
        tool_manager = mcp._tool_manager
        tools = []
        if hasattr(tool_manager, 'tools'):
            for name, tool in tool_manager.tools.items():
                desc = getattr(tool, 'description', '')
                tools.append({"name": name, "description": desc})
        elif hasattr(tool_manager, '_tools'):
            for name, tool in tool_manager._tools.items():
                desc = getattr(tool, 'description', '')
                tools.append({"name": name, "description": desc})
        return {"tools": tools}

    # Start FastAPI server in a separate thread
    import threading
    def run_fastapi():
        logger.info("Starting FastAPI server on port 8081")
        uvicorn.run(app, host="0.0.0.0", port=8081, log_level="info")

    threading.Thread(target=run_fastapi, daemon=True).start()

    try:
        logger.info("Starting ATL MCP server")
        mcp.run(transport='stdio')
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        sys.exit(1)