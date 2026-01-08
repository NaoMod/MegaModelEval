from typing import List
from dataclasses import dataclass



@dataclass
class Seed:
    instruction: str
    level: int
    pattern: str

class SingleToolSeeds:
    """10 diverse single-tool seeds - each requiring exactly one tool call with all parameters"""

    @staticmethod
    def get_seeds() -> List[Seed]:
        return [
            # Level 1 - Start session with file path
            Seed(
                instruction="Start a metamodel session by uploading the file ./ecore/Family.ecore",
                level=1,
                pattern="start_metamodel_session_stateless(metamodel_file_path='./ecore/Family.ecore')"
            ),
            Seed(
                instruction="Initialize a metamodel session with the file ./ecore/uml.ecore",
                level=1,
                pattern="start_metamodel_session_stateless(metamodel_file_path='./ecore/uml.ecore')"
            ),
            
            # Level 1 - Create object with session and class
            Seed(
                instruction="Create a new Family object in session abc123def456",
                level=1,
                pattern="create_object(session_id='abc123def456', class_name='Family')"
            ),
            Seed(
                instruction="Create a new Person object in session xyz789uvw012",
                level=1,
                pattern="create_object(session_id='xyz789uvw012', class_name='Person')"
            ),
            
            # Level 2 - List features with session and class
            Seed(
                instruction="List all available features for the Class entity in session abc123def456",
                level=2,
                pattern="list_features(session_id='abc123def456', class_name='Class')"
            ),
            Seed(
                instruction="Show the features available for an Association class in session xyz789uvw012",
                level=2,
                pattern="list_features(session_id='xyz789uvw012', class_name='Association')"
            ),

            # Level 2 - Inspect instance with session, class, and object id
            Seed(
                instruction="Inspect the Package object with id 5 in session abc123def456",
                level=2,
                pattern="inspect_instance(session_id='abc123def456', class_name='Package', object_id='5')"
            ),
            Seed(
                instruction="Show details of the Class instance with id 3 in session xyz789uvw012",
                level=2,
                pattern="inspect_instance(session_id='xyz789uvw012', class_name='Class', object_id='3')"
            ),

            # Level 3 - Update feature with all parameters
            Seed(
                instruction="Update the visibility feature of Class object id 2 in session abc123def456 to 'public'",
                level=3,
                pattern="update_feature(session_id='abc123def456', class_name='Class', object_id='2', feature_name='visibility', value='public')"
            ),
            Seed(
                instruction="Set the abstract property to true for interface object id 4 in session xyz789uvw012",
                level=3,
                pattern="update_feature(session_id='xyz789uvw012', class_name='Interface', object_id='4', feature_name='abstract', value='true')"
            )
        ]