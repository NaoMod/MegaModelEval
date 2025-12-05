import sys
import os
import asyncio
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.am3 import ReferenceModel, TransformationModel
from core.megamodel import MegamodelRegistry
from core.mcp_generator import MCPServerGenerator, MCPServerConfig, generate_mcp_server
from run_agent_versions import populate_registry

async def main():
    print("=== Loading transformations from Megamodel ===")
    registry = MegamodelRegistry()
    await populate_registry(registry)
    
    # Get all TransformationModel entities from the registry
    transformations = registry.find_entities_by_type(TransformationModel)
    print(f"Found {len(transformations)} transformations:")
    for t in transformations:
        src = t.source_metamodel.name if t.source_metamodel else "?"
        tgt = t.target_metamodel.name if t.target_metamodel else "?"
        print(f"  - {t.name}: {src} -> {tgt}")
    
    print("\n=== Generating MCP Server ===")
    config = MCPServerConfig(name="atl_generated", backend_url="http://localhost:8080", port=8081)
    output = os.path.join(os.path.dirname(__file__), '..', 'generated_mcp_servers', 'atl_generated_server.py')
    generate_mcp_server(transformations, config, output)
    print(f"Generated: {output}")

if __name__ == "__main__":
    asyncio.run(main())
