import logging
import sys
import json
from mcp.server.fastmcp import FastMCP
from fastapi import FastAPI
import uvicorn
# Start FastAPI server in a separate thread
import threading
# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stderr)]
)
logger = logging.getLogger('openrewrite_mcp_server')

# Initialize the MCP server
mcp = FastMCP("openrewrite")

# Recipe definitions
RECIPES = [
    {
        "name": "fix_static_analysis_issues",
        "description": "Common static analysis issue remediation. Automatically resolves common static analysis issues in the codebase. Input: build.gradle path",
        "input": "build.gradle path"
    },
    {
        "name": "fix_checkstyle_violations",
        "description": "Automatically fix Checkstyle violations. Reformats Java code to ensure consistent indentation, spacing, and brace placement. Input: build.gradle path",
        "input": "build.gradle path"
    },
    {
        "name": "migrate_to_java_17",
        "description": "Migrate to Java 17. Automatically upgrades an older Java codebase to Java 17. Input: build.gradle path",
        "input": "build.gradle path"
    },
    {
        "name": "migrate_to_java_21",
        "description": "Migrate to Java 21. Automatically upgrades Java 8 or Java 11 projects to Java 21. Input: build.gradle path",
        "input": "build.gradle path"
    },
    {
        "name": "migrate_to_java_25",
        "description": "Migrate to Java 25. Automatically upgrades Java 8, 11, or 17 projects to Java 25. Input: build.gradle path",
        "input": "build.gradle path"
    },
    {
        "name": "migrate_junit4_to_junit5",
        "description": "Migrate to JUnit 5 from JUnit 4. Performs automated migration from JUnit 4 to JUnit 5. Input: build.gradle path",
        "input": "build.gradle path"
    },
    {
        "name": "migrate_springboot2_to_springboot3",
        "description": "Migrate to Spring Boot 3 from Spring Boot 2. Performs automated migration from Spring Boot 2.x to Spring Boot 3.5. Input: Root project path",
        "input": "Root project path"
    },
    {
        "name": "migrate_to_springboot_3_3",
        "description": "Migrate to Spring Boot 3.3. Migrates applications to the latest Spring Boot 3.3 release. Input: Root project path",
        "input": "Root project path"
    },
    {
        "name": "migrate_springboot1_to_springboot2",
        "description": "Migrate to Spring Boot 2 from Spring Boot 1. Migrates applications from Spring Boot 1 to Spring Boot 2. Input: build.gradle path",
        "input": "build.gradle path"
    },
    {
        "name": "migrate_quarkus1_to_quarkus2",
        "description": "Migrate to Quarkus 2 from Quarkus 1. Migrates applications from Quarkus 1.x to Quarkus 2.x. Input: Root project path",
        "input": "Root project path"
    },
    {
        "name": "migrate_micronaut3_to_micronaut4",
        "description": "Migrate to Micronaut 4 from Micronaut 3. Performs automated migration from Micronaut 3.x to Micronaut 4.x. Input: Root project path",
        "input": "Root project path"
    },
    {
        "name": "migrate_micronaut2_to_micronaut3",
        "description": "Migrate to Micronaut 3 from Micronaut 2. Performs automated migration from Micronaut 2.x to Micronaut 3.x. Input: Root project path",
        "input": "Root project path"
    },
    {
        "name": "migrate_log4j_to_slf4j",
        "description": "Migrate to SLF4J from Log4j. Performs automated migration from Apache Log4j (1.x or 2.x) to SLF4J. Input: Root project path",
        "input": "Root project path"
    },
    {
        "name": "use_slf4j_parameterized_logging",
        "description": "Use SLF4J Parameterized Logging. Refactors logging statements to use SLF4J parameterized logging. Input: Root project path",
        "input": "Root project path"
    },
    {
        "name": "refactor_package_rename",
        "description": "Refactoring with declarative YAML recipes. Renames a Java package and updates all dependent code. Input: Root project path, old_package_name, new_package_name",
        "input": "Root project path, old_package_name, new_package_name"
    },
    {
        "name": "manage_maven_dependencies",
        "description": "Automating Maven dependency management. Analyzes and manages project dependencies to resolve conflicts. Input: build.gradle path",
        "input": "build.gradle path"
    },
    {
        "name": "migrate_hamcrest_to_assertj",
        "description": "Migrate to AssertJ from Hamcrest. Performs automated migration from Hamcrest to AssertJ. Input: Root project path",
        "input": "Root project path"
    }
]

# Create dynamic tools for each recipe

# Register apply and get-details tools for each recipe
for recipe in RECIPES:
    recipe_name = recipe["name"]
    recipe_desc = recipe["description"]

    def create_recipe_tools(name: str, description: str, recipe_obj: dict):
        # Apply tool
        @mcp.tool(name=f"apply_{name}_recipe_tool", description=description)
        async def apply_recipe(**kwargs) -> str:
            """Apply an OpenRewrite recipe (mock implementation)."""
            return f"Recipe '{name}' applied successfully"

        # Get details tool
        @mcp.tool(name=f"get_{name}_details_tool", description=f"Get details for the '{name}' OpenRewrite recipe.")
        async def get_recipe_details_tool() -> str:
            return json.dumps(recipe_obj, indent=2)

        return apply_recipe, get_recipe_details_tool

    create_recipe_tools(recipe_name, recipe_desc, recipe)


@mcp.tool(
    name="list_all_recipes_tool",
    description="List all available OpenRewrite recipes with their descriptions and input requirements."
)
async def list_all_recipes() -> str:
    """List all available OpenRewrite recipes."""
    recipes_info = []
    for i, recipe in enumerate(RECIPES, 1):
        recipes_info.append(f"Recipe {i}: {recipe['name']}\n  Description: {recipe['description']}\n  Input: {recipe['input']}")
    return "\n\n".join(recipes_info)


@mcp.tool(
    name="get_recipe_details_tool",
    description="Get detailed information about a specific OpenRewrite recipe by name."
)
async def get_recipe_details(recipe_name: str) -> str:
    """Get details about a specific recipe."""
    for recipe in RECIPES:
        if recipe["name"] == recipe_name:
            return json.dumps(recipe, indent=2)
    return f"Recipe '{recipe_name}' not found."


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

    def run_fastapi():
        logger.info("Starting FastAPI server on port 8082")
        uvicorn.run(app, host="0.0.0.0", port=8089, log_level="info")

    threading.Thread(target=run_fastapi, daemon=True).start()

    try:
        logger.info("Starting OpenRewrite MCP server")
        mcp.run(transport='stdio')
    except Exception as e:
        logger.error(f"Server error: {str(e)}")
        sys.exit(1)