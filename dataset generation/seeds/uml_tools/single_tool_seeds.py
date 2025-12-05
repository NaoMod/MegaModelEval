from typing import List
from dataclasses import dataclass

@dataclass
class Seed:
    instruction: str
    level: int
    pattern: str

class SingleToolSeeds:
    """10 diverse single-tool seeds using only apply and get operations, focused on UML transformations"""

    @staticmethod
    def get_seeds() -> List[Seed]:
        return [
            # Level 1 - Full transformation name
            Seed(
                instruction="Apply UML2MOF to ./models/UMLExample.xmi",
                level=1,
                pattern="apply"
            ),
            Seed(
                instruction="Show me the configuration settings for the UML2KM3 transformation",
                level=1,
                pattern="get"
            ),
            # Level 2 - Source and target models mentioned
            Seed(
                instruction="Transform the UML model ./models/UMLExample.xmi into a MOF model",
                level=2,
                pattern="apply"
            ),
            Seed(
                instruction="What transformation can I use to convert UML diagrams to KM3 format?",
                level=2,
                pattern="get"
            ),
            # Level 3 - Only target model mentioned
            Seed(
                instruction="Transform this model /Users/zakariahachm/Downloads/llm-agents-mde/src/examples/uml.xmi to MOF model",
                level=3,
                pattern="apply"
            ),
            Seed(
                instruction="List me the details of the transformation that transforms this file /Users/zakariahachm/Downloads/llm-agents-mde/src/examples/uml.xmi to MOF model",
                level=3,
                pattern="get"
            ),
            # Additional diverse "get" seeds with different phrasing and focus
            Seed(
                instruction="What are the available details for the UMLDI2SVG transformation?",
                level=1,
                pattern="get"
            ),
            Seed(
                instruction="Retrieve the metadata for the UMLCLASSDIAGRAM2UMLPROFILE conversion tool",
                level=1,
                pattern="get"
            ),
            Seed(
                instruction="Give me information about transformations that produce JAVA output from a UML model",
                level=2,
                pattern="get"
            )
        ]
