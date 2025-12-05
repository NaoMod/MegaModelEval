from typing import Dict, List, Optional, Any
import uuid
from agents.execution import AgentSession
from core.am3 import Entity, Relationship, Model
from agents.planning import WorkflowPlan

class MegamodelRegistry:
    """Central registry for the extended AM3 megamodel"""
    
    def __init__(self):
    
        self.entities: Dict[str, Entity] = {}
        self.relationships: List[Relationship] = []

        self.mcp_servers: Dict[str, Any] = {}  # Will store MCPServer objects
        self.tools_by_server: Dict[str, List[Any]] = {}  # Will store MCPTool objects
        self.sessions: Dict[str, Any] = {}  # Will store AgentSession objects
        self.workflow_plans: Dict[str, Any] = {}  # Will store WorkflowPlan objects
        
        # Indexes for fast lookup
        self._models_by_type: Dict[str, List[Model]] = {
            "reference": [],
            "transformation": [],
            "terminal": []
        }
        

    def register_entity(self, entity: Entity) -> str:
        """Register an entity in the megamodel"""
        self.entities[entity.uri] = entity
        
        if isinstance(entity, Model):
            model_type = entity.model_type.value
            if model_type in self._models_by_type:
                self._models_by_type[model_type].append(entity)
        
        return entity.uri
    
    def get_entity(self, uri: str) -> Optional[Entity]:
        """Get entity by URI"""
        return self.entities.get(uri)
    
    def find_entities_by_type(self, entity_type: type) -> List[Entity]:
        """Find all entities of a specific type"""
        return [entity for entity in self.entities.values() 
                if isinstance(entity, entity_type)]
    
    def register_relationship(self, relationship: Relationship) -> None:
        """Register a relationship"""
        self.relationships.append(relationship)
    
    def find_relationships(self, source_uri: str = None, target_uri: str = None, 
                          relationship_type: str = None) -> List[Relationship]:
        """Find relationships matching criteria"""
        results = []
        for rel in self.relationships:
            if (source_uri is None or rel.source.uri == source_uri) and \
               (target_uri is None or rel.target.uri == target_uri) and \
               (relationship_type is None or rel.relationship_type == relationship_type):
                results.append(rel)
        return results
    
    
    def register_mcp_server(self, name: str, server: Any) -> None:
        """Register MCP server"""
        self.mcp_servers[name] = server
        self.tools_by_server[name] = getattr(server, 'tools', [])
    
    def register_mcp_server_with_script(self, name: str, server: Any, script_path: str) -> None:
        """Register MCP server with script path for async client connection"""
        # Add script path to server metadata
        if not hasattr(server, 'metadata'):
            server.metadata = {}
        server.metadata['script_path'] = script_path
        self.register_mcp_server(name, server)
    
    def get_mcp_server(self, name: str) -> Optional[Any]:
        """Get MCP server by name"""
        return self.mcp_servers.get(name)
    
    def discover_tools(self, server_name: str = None) -> List[Any]:
        """Discover available tools from MCP servers"""
        if server_name:
            return self.tools_by_server.get(server_name, [])
        # Return all tools from all servers
        all_tools = []
        for tools in self.tools_by_server.values():
            all_tools.extend(tools)
        return all_tools
    
    def find_tools_by_capability(self, input_type: str = None, 
                                output_type: str = None) -> List[Any]:
        """Find tools that can handle specific input/output types"""
        matching_tools = []
        for server_name, server in self.mcp_servers.items():
            capabilities = getattr(server, 'capabilities', [])
            for capability in capabilities:
                input_types = getattr(capability, 'input_types', [])
                output_types = getattr(capability, 'output_types', [])
                if (input_type is None or input_type in input_types) and \
                   (output_type is None or output_type in output_types):
                    matching_tools.extend(self.tools_by_server[server_name])
        return matching_tools
    
    #  Session & Workflow Management 
    def create_session(self, context: Dict[str, Any] = None) -> Any:
        """Create new agent session"""
        session = AgentSession(context=context or {})
        self.sessions[session.session_id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[Any]:
        """Get session by ID"""
        return self.sessions.get(session_id)
    
    def create_workflow_plan(self, goal: Any) -> Any:
        """Create workflow plan"""
        plan = WorkflowPlan(goal=goal)
        plan_id = str(uuid.uuid4())
        self.workflow_plans[plan_id] = plan
        
        return plan
    
    def get_workflow_plan(self, plan_id: str) -> Optional[Any]:
        """Get workflow plan by ID"""
        return self.workflow_plans.get(plan_id)
    


    
    def query_models(self, metamodel_uri: str = None, 
                    model_type: str = None) -> List[Model]:
        """Query models by criteria"""
        models = []
        
        if model_type and model_type in self._models_by_type:
            candidates = self._models_by_type[model_type]
        else:
            candidates = self.find_entities_by_type(Model)
        
        for model in candidates:
            if metamodel_uri is None or \
               (hasattr(model, 'conformsTo') and model.conformsTo and 
                model.conformsTo.uri == metamodel_uri):
                models.append(model)
        
        return models
    
    def get_execution_statistics(self) -> Dict[str, Any]:
        """Get execution statistics across all sessions"""
        total_sessions = len(self.sessions)
        total_plans = len(self.workflow_plans)
        
        total_invocations = 0
        successful_invocations = 0
        
        for session in self.sessions.values():
            for trace in session.execution_traces:
                total_invocations += len(trace.invocations)
                successful_invocations += sum(1 for inv in trace.invocations if inv.success)
        
        return {
            "total_sessions": total_sessions,
            "total_workflow_plans": total_plans,
            "total_invocations": total_invocations,
            "successful_invocations": successful_invocations,
            "success_rate": (successful_invocations / total_invocations * 100) if total_invocations > 0 else 0,
            "registered_entities": len(self.entities),
            "registered_relationships": len(self.relationships),
            "active_mcp_servers": len(self.mcp_servers)
        }
    