"""
Configuration settings for the megamodel system
"""
import os
from dataclasses import dataclass
from typing import Optional

@dataclass
class MCPServerConfig:
    """MCP Server configuration"""
    atl_host: str = "localhost"
    atl_port: int = 8080
    emf_host: str = "localhost" 
    emf_port: int = 8080

@dataclass
class SystemConfig:
    """System configuration"""
    log_level: str = "INFO"
    max_parallel_steps: int = 3
    default_timeout: int = 30
    
    def __post_init__(self):
        # Load from environment variables if available
        self.log_level = os.getenv("LOG_LEVEL", self.log_level)
        self.max_parallel_steps = int(os.getenv("MAX_PARALLEL_STEPS", str(self.max_parallel_steps)))
        self.default_timeout = int(os.getenv("DEFAULT_TIMEOUT", str(self.default_timeout)))

# Global configuration instance
config = SystemConfig()
mcp_config = MCPServerConfig()