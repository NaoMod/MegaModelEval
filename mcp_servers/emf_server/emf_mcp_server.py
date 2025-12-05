import logging
import sys
import os
import json
import requests
from typing import Dict, Any, List, Union
from mcp.server.fastmcp import FastMCP

# Constants
EMF_SERVER_BASE = "http://localhost:8080"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger('emf_mcp_server')

# Initialize the MCP server
mcp = FastMCP("emf_dynamic")

# Session storage
active_sessions = {}
# Store object IDs by session and class
session_objects = {}


def parse_id_from_user_input(user_input: str) -> Union[str, int]:
    """Convert user input to appropriate ID type."""
    if not user_input or user_input.lower() in ['none', '']:
        return user_input
    
    # Try to convert to integer if possible (most object IDs)
    try:
        return int(user_input)
    except ValueError:
        # Return as string (for session IDs and other string-based IDs)
        return user_input

def remove_object_from_session(session_id: str, class_name: str, object_id: Any):
    """Remove an object ID from session tracking."""
    if (session_id in session_objects and 
        class_name in session_objects[session_id]):
        try:
            session_objects[session_id][class_name].remove(object_id)
        except ValueError:
            pass

def add_object_to_session(session_id: str, class_name: str, object_id: Any):
    """Add an object ID to session tracking."""
    # Initialize empty containers
    if session_id not in session_objects:
        session_objects[session_id] = {}
    if class_name not in session_objects[session_id]:
        session_objects[session_id][class_name] = []
    
    # Store the ID
    session_objects[session_id][class_name].append(object_id)

def get_session_objects(session_id: str, class_name: str = None) -> Dict[str, List[Any]]:
    """Get all objects for a session, optionally filtered by class."""
    if session_id not in session_objects:
        return {}
    if class_name:
        # Get only class objects
        return {class_name: session_objects[session_id].get(class_name, [])}
    # Get all objects in session
    return session_objects[session_id]

def format_object_list(session_id: str, class_name: str) -> str:
    """Format object list for display."""
    objects = get_session_objects(session_id, class_name)
    if not objects or class_name not in objects or not objects[class_name]:
        return f"No {class_name} objects found in session."
    
    object_ids = objects[class_name]
    return f"Available {class_name} objects: {object_ids}" 

def make_request(method: str, endpoint: str, **kwargs) -> requests.Response:
    """Make HTTP request to EMF server."""
    url = f"{EMF_SERVER_BASE}{endpoint}"
    return requests.request(method, url, **kwargs)

def extract_classes_from_openapi(openapi_spec: Dict[str, Any]) -> List[str]:
    """Extract class names from OpenAPI spec paths."""
    classes = set()
    if 'paths' in openapi_spec:
        for path in openapi_spec['paths']:
            # Extract class name from path like /metamodel/{sessionId}/ClassName
            parts = path.split('/')
            if len(parts) >= 4 and parts[1] == 'metamodel' and parts[2] == '{sessionId}':
                class_name = parts[3]
                if '{' not in class_name:  # Not a parameter
                    classes.add(class_name)
    return list(classes)

def extract_features_from_openapi(openapi_spec: Dict[str, Any], class_name: str) -> List[str]:
    """Extract feature names for a specific class from OpenAPI spec."""
    features = set()
    if 'paths' in openapi_spec:
        for path in openapi_spec['paths']:
            # Extract feature name from path like /metamodel/{sessionId}/ClassName/{id}/featureName
            parts = path.split('/')
            if (len(parts) >= 6 and parts[1] == 'metamodel' and 
                parts[2] == '{sessionId}' and parts[3] == class_name and 
                parts[4] == '{id}' and '{' not in parts[5]):
                features.add(parts[5])
    return list(features)

def get_feature_type_info(openapi_spec: Dict[str, Any], class_name: str, feature_name: str) -> Dict[str, Any]:
    """Extract type information for a feature from OpenAPI spec."""
    path = f"/metamodel/{{sessionId}}/{class_name}/{{id}}/{feature_name}"
    
    if ('paths' in openapi_spec and path in openapi_spec['paths'] and 
        'put' in openapi_spec['paths'][path]):
        
        put_spec = openapi_spec['paths'][path]['put']
        if ('requestBody' in put_spec and 'content' in put_spec['requestBody'] and
            'application/json' in put_spec['requestBody']['content'] and
            'schema' in put_spec['requestBody']['content']['application/json']):
            
            schema = put_spec['requestBody']['content']['application/json']['schema']
            return {
                'is_containment': schema.get('x-containment', False),
                'value_type': schema.get('properties', {}).get('value', {}).get('type', 'string'),
                'schema': schema
            }
    
    return {'is_containment': False, 'value_type': 'string', 'schema': {}}

def create_dynamic_tools_for_session(session_id: str, openapi_spec: Dict[str, Any]):
    """Create dynamic tools for a specific session based on OpenAPI spec."""
    if 'paths' not in openapi_spec:
        return
    
    for path, methods in openapi_spec['paths'].items():
        path_parts = path.split('/')
        
        # Handle POST routes for creating objects: /metamodel/{sessionId}/ClassName
        if (len(path_parts) == 4 and path_parts[1] == 'metamodel' and 
            path_parts[2] == '{sessionId}' and 'post' in methods):
            class_name = path_parts[3]
            create_object_creation_tool(session_id, class_name, methods['post'])
        
        # Handle PUT routes for updating features: /metamodel/{sessionId}/ClassName/{id}/featureName
        elif (len(path_parts) == 6 and path_parts[1] == 'metamodel' and 
              path_parts[2] == '{sessionId}' and path_parts[4] == '{id}' and 'put' in methods):
            class_name = path_parts[3]
            feature_name = path_parts[5]
            feature_info = get_feature_type_info(openapi_spec, class_name, feature_name)
            create_feature_update_tool(session_id, class_name, feature_name, methods['put'], feature_info)

def create_object_creation_tool(session_id: str, class_name: str, spec: Dict[str, Any]):
    """Create a tool for creating objects of a specific class."""
    tool_name = f"create_{class_name.lower()}_{session_id[:8]}"
    description = f"Create a new {class_name} object in session {session_id[:8]}... Returns the created object with its ID."
    
    @mcp.tool(name=tool_name, description=description)
    async def create_object_dynamic() -> str:
        try:
            response = make_request('POST', f'/metamodel/{session_id}/{class_name}')
            
            if response.status_code == 200:
                result = response.json()
                object_id = result.get('id')
                
                if object_id is not None:
                    add_object_to_session(session_id, class_name, object_id)
                    return f"{class_name} object created successfully!\nID: {object_id}\nFull response: {json.dumps(result, indent=2)}"
                else:
                    return f"{class_name} object created but no ID returned: {json.dumps(result, indent=2)}"
            else:
                return f"Error creating {class_name} object: {response.text}"
                
        except Exception as e:
            return f"Error: {str(e)}"
    mcp.add_tool(fn=create_object_dynamic, name=tool_name)


def create_feature_update_tool(session_id: str, class_name: str, feature_name: str, 
                              spec: Dict[str, Any], feature_info: Dict[str, Any]):
    """Create a tool for updating a specific feature of a class."""
    tool_name = f"update_{class_name.lower()}_{feature_name}_{session_id[:8]}"
    
    is_containment = feature_info.get('is_containment', False)
    value_type = feature_info.get('value_type', 'string')
    
    containment_info = " (containment reference)" if is_containment else ""
    type_info = f" (expects {value_type})" if value_type != 'string' else ""
    
    description = (f"Update {feature_name} of {class_name} in session {session_id[:8]}...{containment_info}{type_info}. ")
    
    @mcp.tool(name=tool_name, description=description)
    async def update_feature_dynamic(object_id: str = "", value: str = "") -> str:
        try:
            if not value:
                available_objects = format_object_list(session_id, class_name)
                return f"Please provide both object_id and value.\n{available_objects}"
            
            # Parse the object_id to the correct type
            parsed_object_id = parse_id_from_user_input(object_id)
            
            data = {'value': value}
            response = make_request('PUT', f'/metamodel/{session_id}/{class_name}/{parsed_object_id}/{feature_name}', 
                                   json=data)
            
            if response.status_code == 200:
                result = response.json()
                return f"{class_name}[{parsed_object_id}].{feature_name} updated successfully!\nNew value: {value}\nResponse: {json.dumps(result, indent=2)}"
            else:
                return f"Error updating {class_name}[{parsed_object_id}].{feature_name}: {response.text}"
                
        except Exception as e:
            return f"Error: {str(e)}"
    mcp.add_tool(fn=update_feature_dynamic, name=tool_name)

def create_delete_tools_for_session(session_id: str, openapi_spec: Dict[str, Any]):
    """Create delete tools for each class in the session."""
    classes = extract_classes_from_openapi(openapi_spec)
    
    for class_name in classes:
        # Create delete object tool
        tool_name = f"delete_{class_name.lower()}_{session_id[:8]}"
        
        @mcp.tool(name=tool_name, 
                 description=f"Delete a {class_name} object in session {session_id[:8]}.")
        async def delete_object_dynamic(object_id: str = "", cls_name: str = class_name) -> str:
            try:
                parsed_object_id = parse_id_from_user_input(object_id)
                response = make_request('DELETE', f'/metamodel/{session_id}/{cls_name}/{parsed_object_id}')
                
                if response.status_code == 200:
                    # Remove from tracking
                    remove_object_from_session(session_id, cls_name, parsed_object_id)
                    result = response.json()
                    return f"{cls_name} object [{parsed_object_id}] deleted successfully: {json.dumps(result, indent=2)}"
                else:
                    return f"Error deleting {cls_name} object: {response.text}"
                    
            except Exception as e:
                return f"Error: {str(e)}"
        mcp.add_tool(fn=delete_object_dynamic, name=tool_name)
        
        # Create clear feature tools for each feature
        features = extract_features_from_openapi(openapi_spec, class_name)
        for feature_name in features:
            clear_tool_name = f"clear_{class_name.lower()}_{feature_name}_{session_id[:8]}"
            
            @mcp.tool(name=clear_tool_name, 
                     description=f"Clear {feature_name} of {class_name} in session {session_id[:8]}.")
            async def clear_feature_dynamic(object_id: str = "", cls_name: str = class_name, feat_name: str = feature_name) -> str:
                try:
                    parsed_object_id = parse_id_from_user_input(object_id)
                    response = make_request('DELETE', f'/metamodel/{session_id}/{cls_name}/{parsed_object_id}/{feat_name}')
                    
                    if response.status_code == 200:
                        result = response.json()
                        return f"{cls_name}[{parsed_object_id}].{feat_name} cleared successfully: {json.dumps(result, indent=2)}"
                    else:
                        return f"Error clearing {cls_name}.{feat_name}: {response.text}"
                        
                except Exception as e:
                    return f"Error: {str(e)}"
            mcp.add_tool(fn=clear_feature_dynamic, name=clear_tool_name)

@mcp.tool(name="list_session_objects", 
          description="List all objects created in a session, organized by class type.")
async def list_session_objects(session_id: str) -> str:
    """List all objects in a session."""
    if session_id not in active_sessions:
        return f"Session {session_id} not found"
    
    objects = get_session_objects(session_id)
    if not objects:
        return f"No objects created in session {session_id}"
    
    result_lines = [f"Session {session_id} objects:"]
    total_objects = 0
    
    for class_name, object_ids in objects.items():
        if object_ids:
            result_lines.append(f"\n{class_name} ({len(object_ids)} objects):")
            for obj_id in object_ids:
                result_lines.append(f"  ID {obj_id}")
            total_objects += len(object_ids)
    
    result_lines.append(f"\nTotal objects: {total_objects}")
    return "\n".join(result_lines)

@mcp.tool(name="start_metamodel_session", 
          description="Start a new session with a metamodel file. Upload the metamodel (.ecore) file and get a session ID with dynamically created tools for each class and feature.")
async def start_metamodel_session(metamodel_file_path: str) -> str:
    """Start a new session with a metamodel file."""
    try:
        if not os.path.exists(metamodel_file_path):
            return f"Error: File not found at {metamodel_file_path}"
        
        with open(metamodel_file_path, 'rb') as f:
            files = {'file': f}
            response = make_request('POST', '/metamodel/start', files=files)
            
        if response.status_code == 200:
            result = response.json()
            session_id = result['sessionId']
            openapi_spec = result['routes']
            
            # Store session info
            active_sessions[session_id] = {
                'openapi_spec': openapi_spec,
                'metamodel_file': metamodel_file_path
            }
            
            # Extract available classes and features
            classes = extract_classes_from_openapi(openapi_spec)
            
            # Create dynamic tools for this session
            create_dynamic_tools_for_session(session_id, openapi_spec)
            create_delete_tools_for_session(session_id, openapi_spec)

            session_info = {
                'sessionId': session_id,
                'availableClasses': classes,
                'message': f"Session started successfully. Created dynamic tools for classes: {', '.join(classes)}"
            }
            
            return json.dumps(session_info, indent=2)
        else:
            return f"Error starting session: {response.text}"
            
    except Exception as e:
        return f"Error: {str(e)}"

@mcp.tool(name="get_session_info", 
          description="Get detailed information about a specific session including available classes and their features.")
async def get_session_info(session_id: str) -> str:
    """Get detailed information about a session."""
    if session_id not in active_sessions:
        return f"Session {session_id} not found"
    
    session_data = active_sessions[session_id]
    openapi_spec = session_data['openapi_spec']
    classes = extract_classes_from_openapi(openapi_spec)
    
    session_info = {
        'sessionId': session_id,
        'metamodelFile': session_data['metamodel_file'],
        'availableClasses': classes,
        'classFeatures': {}
    }
    
    # Get features for each class
    for class_name in classes:
        features = extract_features_from_openapi(openapi_spec, class_name)
        session_info['classFeatures'][class_name] = features
    
    return json.dumps(session_info, indent=2)

@mcp.tool(name="debug_tools", 
          description="Show all registered tools")
async def debug_tools() -> str:
    """Show all registered tools."""
    try:
        result = [f"Active sessions: {len(active_sessions)}", ""]
        
        # Access the tool manager
        tool_manager = mcp._tool_manager
        
        result.append("=== REGISTERED TOOLS ===")
        
        tool_names = []
        tool_count = 0
        
        # Try to access tools through tool manager
        if hasattr(tool_manager, 'tools'):
            tools = tool_manager.tools
            if hasattr(tools, 'keys'):
                tool_names = list(tools.keys())
                tool_count = len(tool_names)
                result.append(f"Found {tool_count} tools:")
                for name in sorted(tool_names):
                    result.append(f"  - {name}")
        
        elif hasattr(tool_manager, '_tools'):
            tools = tool_manager._tools
            if hasattr(tools, 'keys'):
                tool_names = list(tools.keys())
                tool_count = len(tool_names)
                result.append(f"Found {tool_count} tools:")
                for name in sorted(tool_names):
                    result.append(f"  - {name}")
        
        if tool_count == 0:
            result.append("No tools found in tool manager!")
        
        return "\n".join(result)
        
    except Exception as e:
        return f"Error: {str(e)}"

if __name__ == "__main__":
    # Add /tools endpoint to expose all registered tools
    from fastapi import FastAPI
    import uvicorn

    app = FastAPI()

    @app.get("/tools")
    def get_tools():
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
        logger.info("Starting FastAPI server on port 8082")
        uvicorn.run(app, host="0.0.0.0", port=8082, log_level="info")

    threading.Thread(target=run_fastapi, daemon=True).start()

    try:
        logger.info("Starting EMF MCP server")
        mcp.run(transport='stdio')
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        sys.exit(1)

