import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../src')))

import os
from typing import Annotated, TypedDict
from dotenv import load_dotenv
from langchain_ollama import ChatOllama
from langchain_community.vectorstores import FAISS
from langchain_community.embeddings import OllamaEmbeddings
from langchain_core.documents import Document
import json
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, START
from langgraph.graph.message import add_messages

from langgraph.prebuilt import ToolNode, tools_condition
from langchain_mcp_adapters.tools import load_mcp_tools

from src.mcp_ext.client import MCPClient

load_dotenv()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5-nano-2025-08-07")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

class State(TypedDict):
    messages: Annotated[list, add_messages]
    selected_tools: list[str]
    metamodel_name: str | None
    file_paths: list[dict]
class ATLAgent:

    def __init__(self, client: MCPClient):
        self.client = client
        
        # Initialize OpenAI chat model (configure OPENAI_API_KEY in environment)
        openai_model = os.getenv("OPENAI_MODEL", OPENAI_MODEL)
        self.model = ChatOpenAI(
            model=openai_model,
            temperature=0.1,
            max_retries=2
        )

    async def analyze_input(self, state: State) -> State:
        """Analyze the input to extract metamodel information."""
        session = await self.client.get_session()
        response = await session.list_tools()
        
        # Get the extract_input_metamodel_name tool
        extract_tool = [{
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.inputSchema
        } for tool in response.tools if tool.name == "extract_input_metamodel_name"]
        
        if extract_tool:
            llm_with_tool = self.model.bind_tools(extract_tool)
            result = llm_with_tool.invoke(state["messages"])
            return {"messages": [result]}
        
        return state

    async def select_tools(self, state: State) -> State:
        """Select relevant tools based on the user's request."""
        session = await self.client.get_session()
        response = await session.list_tools()
        
        # Get the user message
        user_message = ""
        for msg in state["messages"]:
            if hasattr(msg, 'content') and msg.__class__.__name__ == "HumanMessage":
                user_message = msg.content
                break
        
        # Extract transformation name (looking for patterns like Class2Relational)
        import re
        transformation_pattern = re.findall(r'([A-Z][a-zA-Z0-9]*2[A-Z][a-zA-Z0-9]*)', user_message)
        
        priority_tools = []
        other_tools = []
        
        for tool in response.tools:
            # Always include extract tool
            if tool.name == "extract_input_metamodel_name":
                priority_tools.insert(0, tool.name)
            # Prioritize tools matching the transformation name
            elif transformation_pattern and any(t.lower() in tool.name.lower() for t in transformation_pattern):
                priority_tools.append(tool.name)
            else:
                other_tools.append(tool.name)
        
        # Combine: priority tools first, then others, limit to 100 total
        selected_tools = priority_tools + other_tools
        selected_tools = selected_tools[:100]
        
        print(f"Selected {len(selected_tools)} tools")
        if priority_tools:
            print(f"Priority tools: {priority_tools[:5]}")
        
        return {
            "selected_tools": selected_tools
        }

    async def agent(self, state: State) -> State:
        """Process the state using the selected tools."""
        session = await self.client.get_session()
        response = await session.list_tools()
        
        # Only use selected tools from state
        selected_tool_names = state.get("selected_tools", [])
        
        # Format tools properly for the LLM
        all_tools = [{
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.inputSchema
        } for tool in response.tools if tool.name in selected_tool_names]
        
        # Limit to 100 tools
        all_tools = all_tools[:100]
        
        print(f"Passing {len(all_tools)} tools to LLM")
        
        # Create system prompt - check if first message is a SystemMessage
        from langchain_core.messages import SystemMessage
        
        messages = list(state["messages"])  # Create a copy
        
        if not messages or not isinstance(messages[0], SystemMessage):
            full_prompt = (
                "You are a transformation handler agent. Follow these rules strictly:\n"
                "1. LISTING TRANSFORMATIONS:\n"
                "   - SINGLE transformation: Use list_transformation_<transformation_name>_tool\n"
                "     Input: NONE (leave input blank)\n"
                "     Example: To get, list or show the details of 'Class2Relational', use the tool 'list_transformation_Class2Relational_tool' without any input.\n"
                "2. APPLYING TRANSFORMATIONS:\n"
                "   - Tool: apply_<transformation_name>_transformation_tool\n"
                "   - Input format: ONLY the file path, as file_path\n"
            )
            messages.insert(0, SystemMessage(content=full_prompt))

        # Bind tools to the model
        llm_with_tools = self.model.bind_tools(all_tools)
        
        # Process the state
        return {"messages": [llm_with_tools.invoke(messages)]}

    async def create_agent(self):
        """Create the agent's graph"""
        session = await self.client.get_session()
        # Create the graph
        builder = StateGraph(State)
        # REMOVE analyze_input - it's causing the issue
        builder.add_node("select_tools", self.select_tools)
        builder.add_node("agent", self.agent)
        
        # Create tools from MCP tools
        tools = await load_mcp_tools(session)
        builder.add_node("tools", ToolNode(tools=tools))

        # Simplified flow: START -> select_tools -> agent -> tools (if needed) -> agent
        builder.add_edge(START, "select_tools")
        builder.add_edge("select_tools", "agent")
        builder.add_conditional_edges(
            "agent", 
            tools_condition,
            {
                "tools": "tools",
                "__end__": "__end__"
            }
        )
        builder.add_edge("tools", "agent")

        return builder.compile()

import asyncio
from src.mcp_ext.client import MCPClient

PROMPT = (
    "You are a transformation handler agent. Follow these rules strictly:\n"
    "1. LISTING TRANSFORMATIONS:\n"
    "   - SINGLE transformation: Use list_transformation_<transformation_name>_tool\n"
    "     Input: NONE (leave input blank)\n"
    "     Example: To get, list or show the details of 'Class2Relational', use the tool 'list_transformation_Class2Relational_tool' without any input.\n"
    "2. APPLYING TRANSFORMATIONS:\n"
    "   - Tool: apply_<transformation_name>_transformation_tool\n"
    "   - Input format: ONLY the file path, as file_path\n"
)

INSTRUCTION = (
    "Apply the transformation Class2Realational to this file: "
    "/Users/zakariahachm/Documents/Phd_Zakaria/Scripts/atl-server/sample sources/Class.xmi and then Apply the transformation Ant2Maven to this file:/Users/zakariahachm/Downloads/atl_zoo/Ant2Maven/example/build1Ant.xmi",
    "Apply the transformation Ant2Maven to this file: "
    "/Users/zakariahachm/Downloads/atl_zoo/Ant2Maven/example/build1Ant.xmi",

    "Apply the transformation Book2Publication to this file: "
    "/Users/zakariahachm/Downloads/atl_zoo/Book2Publication/Book/modelBook.xmi",

     "Apply the transformation XML2Make to this file: "
    "/Users/zakariahachm/Downloads/atl_zoo/Make2Ant/example/makeFile.xmi",

     "Apply the transformation Maven2Ant to this file: "
    "/Users/zakariahachm/Downloads/atl_zoo/Maven2Ant/example/mavenFile.xmi",

     "Apply the transformation KM32OWL to this file: "
    "/Users/zakariahachm/Downloads/atl_zoo/KM32OWL/Samples/KM3-KM3.xmi",

     "Apply the transformation KM32Problem to this file: "
    "/Users/zakariahachm/Downloads/atl_zoo/KM32Problem/Models/test-KM3.xmi",

     "Apply the transformation Ant2XML to this file: "
    "/Users/zakariahachm/Downloads/atl_zoo/Make2Ant/example/antFile.xmi",

     "Apply the transformation XML2Make to this file: "
    "/Users/zakariahachm/Downloads/atl_zoo/Make2Ant/example/makeFile.xmi",

     "Apply the transformation KM32DOT to this file: "
    "/Users/zakariahachm/Downloads/atl_zoo/KM32DOT/KM32DOT/Models/KM3-KM3.xmi"

)

ATL_SERVER_SCRIPT = "mcp_servers/atl_server/atl_mcp_server.py"

async def main():
    client = MCPClient()
    try:
        await client.connect_to_server(ATL_SERVER_SCRIPT)
        
        # Create the agent
        agent = ATLAgent(client)
        agent.client = client  # Make sure the client is accessible
        
        # Build the agent graph
        graph = await agent.create_agent()
        
        # Import message types
        from langchain_core.messages import HumanMessage
        
        # Run each instruction one by one
        for i, instruction in enumerate(INSTRUCTION, 1):
            print(f"\n{'='*60}")
            print(f"INSTRUCTION {i}/{len(INSTRUCTION)}")
            print(f"{'='*60}")
            print(f"\n{instruction}\n")
            
            try:
                # Run the agent with the current instruction
                result = await graph.ainvoke({
                    "messages": [HumanMessage(content=instruction)],
                    "selected_tools": [],  # Agent will select tools dynamically
                    "metamodel_name": None,
                    "file_paths": []
                })
                
                # Print the response
                print("\nAgent Response:")
                for msg in result["messages"]:
                    if hasattr(msg, 'content'):
                        print(f"\nRole: {msg.__class__.__name__}")
                        print(f"Content: {msg.content}")
                        if hasattr(msg, 'tool_calls') and msg.tool_calls:
                            print(f"Tool Calls: {msg.tool_calls}")
                    else:
                        print(f"\n{msg}")
                        
            except Exception as e:
                print(f"Error processing instruction {i}: {e}")
                import traceback
                traceback.print_exc()
            
            print(f"\n{'='*60}")
            print(f"END OF INSTRUCTION {i}")
            print(f"{'='*60}\n")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Properly cleanup
        if client:
            try:
                await client.cleanup()
            except:
                pass

if __name__ == "__main__":
    asyncio.run(main())