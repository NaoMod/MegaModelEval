"""
Workflow Executor - Simple workflow execution
"""
import os
import re
import asyncio
from typing import Dict, Any, Optional
import time

from src.core.megamodel import MegamodelRegistry
from src.mcp_ext.client import MCPClient
from src.agents.execution import MCPInvocation
from src.agents.planning import WorkflowPlan, PlanStep

# TODO: perform an Object grounding. Check the feasability to cover other LLM planning criteria
class WorkflowExecutor:
    """Simple workflow executor"""
    
    def __init__(self, registry: MegamodelRegistry):
        self.registry = registry
        self.mcp_clients = {}  # Store MCP clients by server name
    
    async def connect_to_mcp_server(self, server_name: str) -> Optional[MCPClient]:
        """Connect to an MCP server using the modern protocol"""
        if server_name in self.mcp_clients:
            return self.mcp_clients[server_name]
            
        server = self.registry.get_mcp_server(server_name)
        if not server:
            raise ValueError(f"Server not found: {server_name}")
            
        # Get server script path from metadata or configuration
        server_script_path = server.metadata.get("script_path")
        if not server_script_path:
            print(f"Warning: No script path configured for server {server_name}")
            return None
            
        # Create and connect client
        client = MCPClient()
        try:
            await client.connect_to_server(server_script_path)
            self.mcp_clients[server_name] = client
            return client
        except Exception as e:
            print(f"Failed to connect to MCP server {server_name}: {str(e)}")
            return None
    
    async def execute_step_async(self, step: PlanStep) -> Dict[str, Any]:
        """Execute a single workflow step using async MCP client"""
        step.start_execution()
        start_time = time.time()
        try:
            print(f"[MCP] Executing tool '{step.tool_name}' (server={step.server_name})")
            
            # Connect to MCP server if needed
            client = await self.connect_to_mcp_server(step.server_name)
            
            if not client:
                raise ValueError(f"Could not connect to MCP server: {step.server_name}")
            
            # Get session and call the tool using the async MCP client
            session = await client.get_session()
            result = await session.call_tool(step.tool_name, step.parameters or {})
            
            duration = time.time() - start_time
            step.mark_completed(result)
            return {
                "step_id": step.step_id,
                "success": True,
                "result": result,
                "duration": duration
            }
        except Exception as e:
            duration = time.time() - start_time
            step.mark_failed(str(e))
            return {
                "step_id": step.step_id,
                "success": False,
                "error": str(e),
                "duration": duration
            }
    
    def execute_step(self, step: PlanStep) -> Dict[str, Any]:
        """Execute a single workflow step, using async method with event loop"""
        try:
            # Run the async method in an event loop
            return asyncio.run(self.execute_step_async(step))
        except Exception as e:
            step.mark_failed(str(e))
            return {
                "step_id": step.step_id,
                "success": False,
                "error": f"Async execution error: {str(e)}",
                "duration": 0
            }
    
    async def execute_workflow_async(self, plan: WorkflowPlan) -> Dict[str, Any]:
        """Execute a complete workflow asynchronously"""
        session = self.registry.create_session()
        session.start()
        trace = session.create_new_trace()
        
        plan.start_execution()
        results = []
        
        try:
            while not plan.check_completion():
                ready_steps = plan.get_ready_steps()
                
                if not ready_steps:
                    break  # No more steps to execute
                
                for step in ready_steps:
                    result = await self.execute_step_async(step)
                    results.append(result)
                    
                    # Add to trace
                    invocation = MCPInvocation(
                        tool_name=step.tool_name,
                        server_name=step.server_name,
                        arguments=step.parameters,
                        result=result.get("result", {}),
                        success=result["success"]
                    )
                    trace.add_invocation(invocation)
                
                plan._update_step_readiness()
            
            session.end()
            return {
                "session_id": session.session_id,
                "status": plan.status.value,
                "results": results,
                "trace_analysis": trace.analyze()
            }
        except Exception as e:
            session.end()
            return {
                "session_id": session.session_id,
                "status": "error",
                "error": str(e),
                "results": results,
                "trace_analysis": trace.analyze()
            }
        finally:
            # Clean up MCP clients
            await self.cleanup_mcp_clients()
    
    def execute_workflow(self, plan: WorkflowPlan) -> Dict[str, Any]:
        """Execute a complete workflow"""
        try:
            # Run the async method in an event loop
            return asyncio.run(self.execute_workflow_async(plan))
        except Exception as e:
            return {
                "status": "error",
                "error": f"Async execution error: {str(e)}",
                "results": []
            }
    
    async def cleanup_mcp_clients(self):
        """Clean up all MCP clients"""
        for server_name, client in self.mcp_clients.items():
            try:
                print(f"Cleaning up MCP client for {server_name}")
                await client.cleanup()
            except Exception as e:
                print(f"Error cleaning up MCP client for {server_name}: {str(e)}")
        self.mcp_clients = {}
