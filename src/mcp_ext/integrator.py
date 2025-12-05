
from typing import Dict, List, Any, Optional

from mcp_ext.infrastructure import MCPServer, MCPCapability

class MCPServerIntegrator:
    """Simple integrator for MCP servers"""
    
    def __init__(self, registry: Any):
        self.registry = registry
    
    def setup_atl_server(self, host: str = "localhost", port: int = 8080, tools_port: int = 8081) -> MCPServer:
        """Setup ATL server - tools will be discovered via MCP"""
        atl_server = MCPServer(
            host=host, 
            port=port, 
            name="atl_server",
            tools_port=tools_port
        )
        
        atl_server.add_capability(MCPCapability(
            input_types=["ecore", "xmi"],
            output_types=["ecore", "xmi"], 
            can_execute=True,
            description="ATL transformations"
        ))
        
        self.registry.register_mcp_server("atl_server", atl_server)
        return atl_server
    
    def setup_emf_server(self, host: str = "localhost", port: int = 8080, tools_port: int = 8082) -> MCPServer:
        """Setup EMF server - tools will be discovered via MCP"""
        emf_server = MCPServer(
            host=host,
            port=port, 
            name="emf_server",
            tools_port=tools_port
        )
        
        emf_server.add_capability(MCPCapability(
            input_types=["ecore", "xmi"],
            output_types=["ecore", "xmi"],
            can_execute=True,
            description="EMF model operations"
        ))
        
        self.registry.register_mcp_server("emf_server", emf_server)
        return emf_server