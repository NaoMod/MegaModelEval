"""
MCP Server Generator from OpenAPI Spec

Generates an MCP server with one tool per route from an OpenAPI specification.
No LLM required - purely programmatic generation.
"""

import os
import sys
import json
import yaml
from typing import Dict, Any
from dataclasses import dataclass
import re
# Ensure src is on path for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))



@dataclass
class MCPServerConfig:
    name: str
    backend_url: str = None  # Will be deduced from OpenAPI spec if not set
    port: int = 8081  # MCP server port (FastAPI/uvicorn), user-configurable

def extract_backend_url_from_openapi_spec(spec: dict):
    """Extract backend_url from OpenAPI"""
    servers = spec.get('servers', [])
    if servers:
        url = servers[0].get('url', '')
        m = re.match(r'^(https?://[^/]+)', url)
        backend_url = m.group(1) if m else url
        return backend_url
    return "http://localhost:8080"


MCP_SERVER_HEADER = '''import sys
import os
import json
import subprocess
import threading
from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI
import uvicorn

SERVER_BASE = "{backend_url}"

mcp = FastMCP("{server_name}")

'''

# Template footer for MCP server, including FastAPI app and main loop (Optional)
MCP_SERVER_FOOTER = '''
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


def load_openapi_spec(spec_path: str) -> Dict[str, Any]:
    """Load OpenAPI spec from file (YAML or JSON)."""
    with open(spec_path, 'r') as f:
        if spec_path.endswith('.yaml') or spec_path.endswith('.yml'):
            return yaml.safe_load(f)
        else:
            return json.load(f)


def path_to_tool_name(path: str, method: str) -> str:
    """Convert API path to a valid tool name."""
    # Remove leading slash and replace special chars
    name = path.lstrip('/')
    name = name.replace('/', '_').replace('{', '').replace('}', '').replace('-', '_')
    # Add method prefix for non-GET methods
    if method.lower() != 'get':
        name = f"{method.lower()}_{name}"
    return f"{name}_tool" # Example: GET /transformations/enabled -> transformations_enabled_tool


def extract_parameters(operation: Dict[str, Any], path: str) -> Dict[str, Any]:
    """Extract parameters from OpenAPI operation."""
    params = {
        'path_params': [],
        'query_params': [],
        'body_params': [],
        'file_upload': False,
        'file_field_name': 'IN'
    }
    
    path_param_matches = re.findall(r'\{(\w+)\}', path) # find all the names betwen accolades
    params['path_params'] = path_param_matches
    
    # Extract from parameters array
    for param in operation.get('parameters', []):
        param_name = param.get('name')
        param_in = param.get('in')
        required = param.get('required', False)
        
        if param_in == 'path':
            if param_name not in params['path_params']:
                params['path_params'].append(param_name)
        elif param_in == 'query':
            params['query_params'].append({
                'name': param_name,
                'required': required,
                'schema': param.get('schema', {})
            })
    
    # Check for request body (file upload or form data)
    request_body = operation.get('requestBody', {})
    content = request_body.get('content', {})
    
    if 'multipart/form-data' in content:
        schema = content['multipart/form-data'].get('schema', {})
        properties = schema.get('properties', {})
        
        for prop_name, prop_schema in properties.items():
            if prop_schema.get('format') == 'binary':
                params['file_upload'] = True
                params['file_field_name'] = prop_name
            else:
                params['body_params'].append({
                    'name': prop_name,
                    'required': prop_name in schema.get('required', []),
                    'schema': prop_schema
                })
    
    elif 'application/x-www-form-urlencoded' in content:
        schema = content['application/x-www-form-urlencoded'].get('schema', {})
        properties = schema.get('properties', {})
        required_fields = schema.get('required', [])
        
        for prop_name, prop_schema in properties.items():
            params['body_params'].append({
                'name': prop_name,
                'required': prop_name in required_fields,
                'schema': prop_schema
            })
    
    return params


def generate_tool_function(path: str, method: str, operation: Dict[str, Any], tool_name: str) -> str:
    """Generate a single tool function."""
    
    summary = operation.get('summary', f'{method.upper()} {path}')
    description = operation.get('description', summary)
    # Escape triple quotes in description
    description = description.replace('"""', '\\"\\"\\"')
    params = extract_parameters(operation, path)
    
    # Sort parameters: required first, then optional
    required_params = []
    optional_params = []
    
    # Add path parameters (always required)
    for p in params['path_params']:
        required_params.append(f'{p}: str')
    
    # Add query parameters
    for p in params['query_params']:
        if p['required']:
            required_params.append(f"{p['name']}: str")
        else:
            optional_params.append(f"{p['name']}: str = None")
    
    # Add body/form parameters
    for p in params['body_params']:
        if p['required']:
            required_params.append(f"{p['name']}: str")
        else:
            optional_params.append(f"{p['name']}: str = None")
    
    # Add file upload parameter (required)
    if params['file_upload']:
        required_params.append('file_path: str')
    
    # Build function signature string (required params first, then optional)
    all_params = required_params + optional_params
    signature = ', '.join(all_params) if all_params else ''
    
    # Build URL with path parameters
    url_path = path
    for p in params['path_params']:
        url_path = url_path.replace('{' + p + '}', '{' + p + '}')  # Keep as f-string placeholder
    
    # Build the function body
    lines = []
    lines.append(f'@mcp.tool(name="{tool_name}", description="""{description}""")')
    lines.append(f'async def {tool_name.replace("-", "_")}({signature}) -> str:')
    lines.append(f'    """')
    lines.append(f'    {summary}')
    lines.append(f'    """')
    lines.append(f'    url = f"{{SERVER_BASE}}{url_path}"')
    lines.append(f'    cmd = ["curl", "-s", "-X", "{method.upper()}"]')
    
    # Add query parameters handling
    if params['query_params']:
        lines.append('    query_parts = []')
        for p in params['query_params']:
            pname = p['name']
            lines.append(f'    if {pname}:')
            lines.append(f'        query_parts.append(f"{pname}={{{pname}}}")')
        lines.append('    if query_parts:')
        lines.append('        url = url + "?" + "&".join(query_parts)')
    
    # Add form data handling
    if params['body_params'] and not params['file_upload']:
        for p in params['body_params']:
            pname = p['name']
            lines.append(f'    if {pname}:')
            lines.append(f'        cmd.extend(["-d", f"{pname}={{{pname}}}"])')
    
    # Add file upload handling
    if params['file_upload']:
        field_name = params['file_field_name']
        lines.append(f'    if file_path:')
        lines.append(f'        cmd.extend(["-F", f"{field_name}=@{{file_path}}"])')
    
    # Append URL and execute
    lines.append('    cmd.append(url)')
    lines.append('    result = subprocess.run(cmd, capture_output=True, text=True)')
    lines.append('    return result.stdout if result.returncode == 0 else f"Error: {result.stderr}"')
    
    return '\n' + '\n'.join(lines) + '\n'


class OpenAPIMCPGenerator:
    """Generate MCP server from OpenAPI specification."""
    
    def __init__(self, config: MCPServerConfig):
        self.config = config
    
    def generate(self, openapi_spec: Dict[str, Any], output_path: str) -> str:
        """Generate MCP server code from OpenAPI spec."""
        
        tools_code = []
        paths = openapi_spec.get('paths', {})
        
        print(f"Generating tools for {len(paths)} paths...")
        
        for path, path_item in paths.items():
            # Handle each HTTP method
            for method in ['get', 'post', 'put', 'delete', 'patch']:
                if method in path_item:
                    operation = path_item[method]
                    tool_name = path_to_tool_name(path, method)
                    
                    print(f"  {method.upper()} {path} -> {tool_name}")
                    
                    tool_code = generate_tool_function(path, method, operation, tool_name)
                    tools_code.append(tool_code)
        
        # Assemble full server code
        server_code = MCP_SERVER_HEADER.format(
            backend_url=self.config.backend_url,
            server_name=self.config.name
        )
        
        server_code += '\n'.join(tools_code)
        
        server_code += MCP_SERVER_FOOTER.format(
            port=self.config.port
        )
        
        # Write to file
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(server_code)
        
        print(f"\nGenerated {len(tools_code)} tools")
        print(f"Server written to: {output_path}")
        
        return server_code


def generate_mcp_server_from_openapi(
    config: MCPServerConfig,
    output_path: str,
    openapi_spec_path: str = None,
    openapi_spec_url: str = None
) -> str:
    """
    Generate an MCP server from an OpenAPI specification.
    
    Args:
        config: Server configuration
        output_path: Path to write the generated server code
        openapi_spec_path: Path to OpenAPI spec file (YAML or JSON)
        openapi_spec_url: URL to fetch OpenAPI spec from
    
    Returns:
        Generated server code as string
    """
    # Load OpenAPI spec
    if openapi_spec_path:
        print(f"Loading OpenAPI spec from: {openapi_spec_path}")
        spec = load_openapi_spec(openapi_spec_path)
    else:
        raise ValueError("Either openapi_spec_path or openapi_spec_url must be provided")

    # If backend_url is not set, extract from OpenAPI spec
    if config.backend_url is None:
        config.backend_url = extract_backend_url_from_openapi_spec(spec)
        print(f"[INFO] Using backend_url {config.backend_url} from OpenAPI spec")

    generator = OpenAPIMCPGenerator(config)
    return generator.generate(spec, output_path)


if __name__ == "__main__":
    # Default paths
    workspace_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
    openapi_path = os.path.join(workspace_root, 'openapi.yaml')
    output_path = os.path.join(workspace_root, 'generated_mcp_servers', 'atl_openapi_server.py')
    
    config = MCPServerConfig(
        name='atl_openapi',
        backend_url=None,  # Let it be inferred from OpenAPI spec
        port=8081  # MCP server port (FastAPI/uvicorn)
    )
    
    generate_mcp_server_from_openapi(
        config=config,
        output_path=output_path,
        openapi_spec_path=openapi_path
    )
