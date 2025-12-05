from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum

@dataclass
class Entity:
    """Base entity in the AM3 megamodel"""
    uri: str
    name: str = ""
    metadata: dict = field(default_factory=dict)
    
    #If the name is not provided , we set the last part of the uri.
    def __post_init__(self):
        if not self.name:
            self.name = self.uri.split('/')[-1] if '/' in self.uri else self.uri

@dataclass
class Relationship:
    """Represents relationships between entities"""
    source: Entity
    target: Entity
    relationship_type: str = "conformsTo"
    # gets its own independent empty dictionary (not shared across instances).
    properties: dict = field(default_factory=dict)

class ModelType(Enum):
    REFERENCE = "reference"
    TRANSFORMATION = "transformation" 
    TERMINAL = "terminal"

@dataclass
class Model(Entity):
    """Base model class"""
    conformsTo: Optional['Model'] = None
    model_type: ModelType = ModelType.TERMINAL
    content_path: Optional[str] = None
    
    def __post_init__(self):
        super().__post_init__()

@dataclass
class ReferenceModel(Model):
    """Metamodel definition (e.g., .ecore files)"""
    metamodel_content: Optional[str] = None
    
    def __post_init__(self):
        super().__post_init__()
        self.model_type = ModelType.REFERENCE

@dataclass
class TransformationModel(Model):
    """Model transformation definition (e.g., .atl files)"""
    source_metamodel: Optional[ReferenceModel] = None
    target_metamodel: Optional[ReferenceModel] = None
    transformation_language: str = "ATL"
    # Sample source model paths provided by the ATL server
    sample_sources: List[str] = field(default_factory=list)
    
    def __post_init__(self):
        super().__post_init__()
        self.model_type = ModelType.TRANSFORMATION

@dataclass
class TerminalModel(Model):
    """Concrete model instance (e.g., .xmi files)"""
    instance_data: Optional[dict] = None
    
    def __post_init__(self):
        super().__post_init__()
        self.model_type = ModelType.TERMINAL

@dataclass
class DirectedRelationship(Relationship):
    """Directed relationship with specific semantics"""
    direction: str = "forward"
