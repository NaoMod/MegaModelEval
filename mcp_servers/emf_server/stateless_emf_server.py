import os
import sys
import json
import logging
import threading
from typing import Dict, Any, List, Union
from fastapi import FastAPI
import uvicorn
import requests
from mcp.server.fastmcp import FastMCP

# Constants
EMF_SERVER_BASE = os.environ.get("EMF_SERVER_BASE", "http://localhost:8080")

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger('emf_mcp_stateless')

# Initialize the MCP server
mcp = FastMCP("emf_stateless")

# Session storage (client-side)
active_sessions: Dict[str, Dict[str, Any]] = {}
# Track created object IDs by session and class name
session_objects: Dict[str, Dict[str, List[Union[str, int]]]] = {}


def parse_id_from_user_input(user_input: str) -> Union[str, int]:
    """Try to convert to int when possible; otherwise return the original string."""
    if user_input is None:
        return ""
    s = str(user_input).strip()
    if s == "" or s.lower() == "none":
        return s
    try:
        return int(s)
    except ValueError:
        return s


def add_object_to_session(session_id: str, class_name: str, object_id: Union[str, int]):
    session_objects.setdefault(session_id, {}).setdefault(class_name, []).append(object_id)


def remove_object_from_session(session_id: str, class_name: str, object_id: Union[str, int]):
    try:
        session_objects.get(session_id, {}).get(class_name, []).remove(object_id)
    except (ValueError, AttributeError):
        pass


def get_session_objects(session_id: str, class_name: str = None) -> Dict[str, List[Union[str, int]]]:
    data = session_objects.get(session_id, {})
    if class_name:
        return {class_name: data.get(class_name, [])}
    return data


def format_object_list(session_id: str, class_name: str) -> str:
    objs = get_session_objects(session_id, class_name)
    ids = objs.get(class_name, [])
    return f"Available {class_name} objects: {ids if ids else '[]'}"


def make_request(method: str, endpoint: str, **kwargs) -> requests.Response:
    url = f"{EMF_SERVER_BASE}{endpoint}"
    return requests.request(method, url, timeout=30, **kwargs)


# =============
# MCP Tools
# =============

@mcp.tool(name="start_metamodel_session_stateless",
          description="Start a new session by uploading a .ecore file to the stateless EMF server. Returns sessionId.")
async def start_metamodel_session_stateless(metamodel_file_path: str) -> str:
    try:
        if not os.path.exists(metamodel_file_path):
            return f"Error: File not found at {metamodel_file_path}"
        with open(metamodel_file_path, 'rb') as f:
            files = {'file': f}
            resp = make_request('POST', '/metamodel/start', files=files)
        if resp.status_code != 200:
            return f"Error starting session: {resp.text}"
        result = resp.json()
        session_id = result.get('sessionId')
        if not session_id:
            return f"Error: Server did not return sessionId. Raw: {resp.text}"
        active_sessions[session_id] = {
            'routes': result.get('routes', {}),
            'metamodel_file': metamodel_file_path
        }
        return json.dumps({
            'sessionId': session_id,
            'message': 'Session started. Use other tools with this sessionId.'
        }, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(name="create_object",
          description="Create a new object instance. Provide session_id and class_name.")
async def create_object(session_id: str, class_name: str) -> str:
    try:
        if session_id not in active_sessions:
            return f"Session {session_id} not found. Start a session first."
        resp = make_request('POST', f'/metamodel/{session_id}/{class_name}')
        if resp.status_code != 200:
            return f"Error creating {class_name}: {resp.text}"
        data = resp.json()
        obj_id = data.get('id')
        if obj_id is not None:
            add_object_to_session(session_id, class_name, obj_id)
        return json.dumps({'class': class_name, 'id': obj_id, 'status': data.get('status')}, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(name="update_feature",
          description="Update a feature on an object. Provide session_id, class_name, object_id, feature_name, value (string or JSON).")
async def update_feature(session_id: str, class_name: str, object_id: str, feature_name: str, value: str) -> str:
    try:
        if session_id not in active_sessions:
            return f"Session {session_id} not found."
        parsed_object_id = parse_id_from_user_input(object_id)

        # Try to auto-parse 'value' as JSON for lists/numbers/booleans; fallback to raw string
        body_value: Any
        try:
            body_value = json.loads(value)
        except Exception:
            body_value = value

        resp = make_request(
            'PUT', f'/metamodel/{session_id}/{class_name}/{parsed_object_id}/{feature_name}',
            json={'value': body_value},
            headers={'Content-Type': 'application/json'}
        )
        if resp.status_code != 200:
            return f"Error updating {class_name}[{parsed_object_id}].{feature_name}: {resp.text}"
        return json.dumps({'status': 'updated', 'class': class_name, 'id': parsed_object_id, 'feature': feature_name, 'value': body_value}, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(name="clear_feature",
          description="Clear (unset) a feature on an object. Provide session_id, class_name, object_id, feature_name.")
async def clear_feature(session_id: str, class_name: str, object_id: str, feature_name: str) -> str:
    try:
        if session_id not in active_sessions:
            return f"Session {session_id} not found."
        parsed_object_id = parse_id_from_user_input(object_id)
        resp = make_request('DELETE', f'/metamodel/{session_id}/{class_name}/{parsed_object_id}/{feature_name}')
        if resp.status_code != 200:
            return f"Error clearing {class_name}[{parsed_object_id}].{feature_name}: {resp.text}"
        return json.dumps({'status': 'cleared', 'class': class_name, 'id': parsed_object_id, 'feature': feature_name}, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(name="delete_object",
          description="Delete an object. Provide session_id, class_name, object_id.")
async def delete_object(session_id: str, class_name: str, object_id: str) -> str:
    try:
        if session_id not in active_sessions:
            return f"Session {session_id} not found."
        parsed_object_id = parse_id_from_user_input(object_id)
        resp = make_request('DELETE', f'/metamodel/{session_id}/{class_name}/{parsed_object_id}')
        if resp.status_code != 200:
            return f"Error deleting {class_name}[{parsed_object_id}]: {resp.text}"
        remove_object_from_session(session_id, class_name, parsed_object_id)
        return json.dumps({'status': 'deleted', 'class': class_name, 'id': parsed_object_id}, indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(name="list_features",
          description="List features of a class using the stateless introspection endpoint. Provide session_id and class_name.")
async def list_features(session_id: str, class_name: str) -> str:
    try:
        if session_id not in active_sessions:
            return f"Session {session_id} not found."
        resp = make_request('GET', f'/metamodel/{session_id}/{class_name}/features')
        if resp.status_code != 200:
            return f"Error listing features for {class_name}: {resp.text}"
        return json.dumps(resp.json(), indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(name="inspect_instance",
          description="Inspect an instance's values using stateless introspection. Provide session_id, class_name, object_id.")
async def inspect_instance(session_id: str, class_name: str, object_id: str) -> str:
    try:
        if session_id not in active_sessions:
            return f"Session {session_id} not found."
        parsed_object_id = parse_id_from_user_input(object_id)
        resp = make_request('GET', f'/metamodel/{session_id}/{class_name}/{parsed_object_id}')
        if resp.status_code != 200:
            return f"Error inspecting {class_name}[{parsed_object_id}]: {resp.text}"
        return json.dumps(resp.json(), indent=2)
    except Exception as e:
        return f"Error: {e}"


@mcp.tool(name="list_session_objects",
          description="List all locally tracked objects for a session (IDs captured when creating objects via this client).")
async def list_session_objects_tool(session_id: str) -> str:
    if session_id not in active_sessions:
        return f"Session {session_id} not found"
    objs = get_session_objects(session_id)
    if not objs:
        return f"No objects created via this client in session {session_id}"
    lines = [f"Session {session_id} objects:"]
    total = 0
    for cls, ids in objs.items():
        lines.append(f"\n{cls} ({len(ids)} objects):")
        for oid in ids:
            lines.append(f"  ID {oid}")
        total += len(ids)
    lines.append(f"\nTotal objects: {total}")
    return "\n".join(lines)


@mcp.tool(name="get_session_info",
          description="Get stored info about a session in this client (metamodel path, routes summary).")
async def get_session_info(session_id: str) -> str:
    data = active_sessions.get(session_id)
    if not data:
        return f"Session {session_id} not found"
    info = {
        'sessionId': session_id,
        'metamodelFile': data.get('metamodel_file'),
        'routes': data.get('routes')
    }
    return json.dumps(info, indent=2)


@mcp.tool(name="debug_tools",
          description="List all registered MCP tools in this process.")
async def debug_tools() -> str:
    try:
        tool_manager = getattr(mcp, '_tool_manager', None)
        names: List[str] = []
        if tool_manager is not None:
            if hasattr(tool_manager, 'tools') and isinstance(tool_manager.tools, dict):
                names = list(tool_manager.tools.keys())
            elif hasattr(tool_manager, '_tools') and isinstance(tool_manager._tools, dict):
                names = list(tool_manager._tools.keys())
        names.sort()
        return "\n".join([f"Found {len(names)} tools:"] + names)
    except Exception as e:
        return f"Error: {e}"


if __name__ == "__main__":

    app = FastAPI()

    @app.get("/tools")
    def get_tools():
        tool_manager = getattr(mcp, '_tool_manager', None)
        tools = []
        if tool_manager is not None:
            if hasattr(tool_manager, 'tools') and isinstance(tool_manager.tools, dict):
                for name, tool in tool_manager.tools.items():
                    desc = getattr(tool, 'description', '')
                    tools.append({"name": name, "description": desc})
            elif hasattr(tool_manager, '_tools') and isinstance(tool_manager._tools, dict):
                for name, tool in tool_manager._tools.items():
                    desc = getattr(tool, 'description', '')
                    tools.append({"name": name, "description": desc})
        return {"tools": tools}

    def run_fastapi():
        logger.info("Starting FastAPI server on port 8082")
        uvicorn.run(app, host="0.0.0.0", port=8082, log_level="info")

    threading.Thread(target=run_fastapi, daemon=True).start()

    try:
        logger.info("Starting EMF Stateless MCP server (transport=stdio)")
        mcp.run(transport='stdio')
    except Exception as e:
        logger.error(f"Server error: {e}")
        sys.exit(1)
