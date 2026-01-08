from typing import List
from dataclasses import dataclass

@dataclass
class Seed:
    instruction: str
    level: int
    pattern: str

class MultiToolSeeds:
    """Multi-tool seeds combining exactly two operations for EMF model management"""

    @staticmethod
    def get_seeds() -> List[Seed]:
        return [
            # LEVEL 1 - Start session and create object
            Seed(
                instruction="Start a metamodel session with ./ecore/simpleModel.ecore, get the session ID, then create a new Package object in the session abc123",
                level=1,
                pattern="start_metamodel_session_stateless(metamodel_file_path='./ecore/simpleModel.ecore'), create_object(session_id='abc123', class_name='Package')"
            ),
            Seed(
                instruction="Initialize a metamodel session with ./ecore/uml.ecore and then create a new Class object in session xyz789",
                level=1,
                pattern="start_metamodel_session_stateless(metamodel_file_path='./ecore/uml.ecore'), create_object(session_id='xyz789', class_name='Class')"
            ),           
            # LEVEL 1 - Create and list features
            Seed(
                instruction="Create a new Attribute object in session abc123 and then list all available features for Attribute",
                level=1,
                pattern="create_object(session_id='abc123', class_name='Attribute'), list_features(session_id='abc123', class_name='Attribute')"
            ),
            Seed(
                instruction="Create a new DataType in session xyz789 and then show the features available for DataType",
                level=1,
                pattern="create_object(session_id='xyz789', class_name='DataType'), list_features(session_id='xyz789', class_name='DataType')"
            ),
            
            # LEVEL 1 - Create and inspect
            Seed(
                instruction="Create a new Class object with id 1 in session abc123 and then inspect its current value ",
                level=1,
                pattern="create_object(session_id='abc123', class_name='Class'), inspect_instance(session_id='abc123', class_name='Class', object_id='1')"
            ),
            Seed(
                instruction="Create a new Package object with the id 1 in session xyz789 and then inspect its value",
                level=1,
                pattern="create_object(session_id='xyz789', class_name='Package'), inspect_instance(session_id='xyz789', class_name='Package', object_id='1')"
            ),
            
            # LEVEL 2 - List features and create
            Seed(
                instruction="List all available features for Package in session abc123, then create a new Package object in that session",
                level=2,
                pattern="list_features(session_id='abc123', class_name='Package'), create_object(session_id='abc123', class_name='Package')"
            ),
            Seed(
                instruction="Show the features available for Association in session xyz789, then create a new Association object",
                level=2,
                pattern="list_features(session_id='xyz789', class_name='Association'), create_object(session_id='xyz789', class_name='Association')"
            ),
            
            # LEVEL 3 - Inspect and update
            Seed(
                instruction="Inspect the Package object with id 5 in session abc123, then update its visibility feature to 'public'",
                level=3,
                pattern="inspect_instance(session_id='abc123', class_name='Package', object_id='5'), update_feature(session_id='abc123', class_name='Package', object_id='5', feature_name='visibility', value='public')"
            ),
            Seed(
                instruction="Inspect the Class instance with id 3 in session xyz789, then update its abstract property to true",
                level=3,
                pattern="inspect_instance(session_id='xyz789', class_name='Class', object_id='3'), update_feature(session_id='xyz789', class_name='Class', object_id='3', feature_name='abstract', value='true')"
            ),
            
            # LEVEL 3 - Create and delete
            Seed(
                instruction="Create a new Attribute object in session abc123 with id 7, then delete this Attribute from the session",
                level=3,
                pattern="create_object(session_id='abc123', class_name='Attribute'), delete_object(session_id='abc123', class_name='Attribute', object_id='7')"
            ),
            Seed(
                instruction="Create a new Operation object in session xyz789, then remove it",
                level=3,
                pattern="create_object(session_id='xyz789', class_name='Operation'), delete_object(session_id='xyz789', class_name='Operation', object_id='2')"
            )
            ]