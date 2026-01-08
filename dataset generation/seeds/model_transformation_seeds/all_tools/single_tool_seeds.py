from typing import List
from dataclasses import dataclass


@dataclass
class Seed:
    instruction: str
    level: int
    pattern: str

class SingleToolSeeds:
    """10 diverse single-tool seeds using only apply and get operations"""

    @staticmethod
    def get_seeds() -> List[Seed]:
        return [
            # Level 1 - Full transformation name
            Seed(
                instruction="Apply Mantis2XML to ./atl_zoo/SoftwareQualityControl2MantisBTFile/modelsExamples/MantisExample.xmi",
                level=1,
                pattern="apply"
            ),
            Seed(
                instruction="Show me the configuration settings for the PNML2XML transformation",
                level=1,
                pattern="get"
            ),
            

            # Level 2 - Source and target models mentioned
            Seed(
                instruction="Transform the KM3 model ./atl_zoo/KM32EMF/Sample-KM3.xmi into a DSL model",
                level=2,
                pattern="apply"
            ),
            Seed(
                instruction="What transformation can I use to convert MySQL schemas to KM3 format?",
                level=2,
                pattern="get"
            ),

            # Level 3 - Only target model mentioned
            Seed(
                instruction="Transform this model /Users/zakariahachm/Downloads/llm-agents-mde/src/examples/class.xmi to Relational model",
                level=3,
                pattern="apply"
            ),
            Seed(
                instruction= "List me the details of the transformation that transforms this file /Users/zakariahachm/Downloads/llm-agents-mde/src/examples/class.xmi to Relational model",
                level=3,
                pattern="get"
            ),
            # Additional diverse "get" seeds with different phrasing and focus
            Seed(
                instruction="What are the available details for the Class2Relational transformation?",
                level=1,
                pattern="get"
            ),
            Seed(
                instruction="Retrieve the metadata for the PNML2XML conversion tool",
                level=1,
                pattern="get"
            ),

            Seed(
                instruction="Give me information about transformations that produce XML output from an Ant model",
                level=2,
                pattern="get"
            )
        ]
        