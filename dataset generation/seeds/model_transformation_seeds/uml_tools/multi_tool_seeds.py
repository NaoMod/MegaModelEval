from typing import List
from dataclasses import dataclass

@dataclass
class Seed:
    instruction: str
    level: int
    pattern: str

class MultiToolSeeds:
    """Multi-tool seeds focused on UML transformations"""

    @staticmethod
    def get_seeds() -> List[Seed]:
        return [
            # LEVEL 1 - Full transformation names
            Seed(
                instruction="First show me the configuration of UML2MOF and then transform ./models/UMLExample.xmi using UML2KM3 transformation",
                level=1,
                pattern="get, apply"
            ),
            Seed(
                instruction="Compare the configurations of UMLDI2SVG and UMLCLASSDIAGRAM2UMLPROFILE transformations",
                level=1,
                pattern="get, get"
            ),
            Seed(
                instruction="Transform ./models/UMLExample.xmi with UML2JAVA and then check the UML2OWL configuration",
                level=1,
                pattern="apply, get"
            ),
            Seed(
                instruction="Transform ./models/UMLExample.xmi using UML2MOF_2 and then transform ./models/UMLExample.xmi using UML2Measure",
                level=1,
                pattern="apply, apply"
            ),
            # LEVEL 2 - Source and target models mentioned
            Seed(
                instruction="Show me the configuration settings of the transformation that transforms a UML into a MOF model and then transform ./models/UMLExample.xmi from a UML model to a KM3 model",
                level=2,
                pattern="get, apply"
            ),
            Seed(
                instruction="Transform the UML model ./models/UMLExample.xmi to JAVA and then compare the configurations of the transformation that transforms a UML into an OWL",
                level=2,
                pattern="apply, get"
            ),
            Seed(
                instruction="Transform the UML model ./models/UMLExample.xmi to MOF and then transform the UML model ./models/UMLExample.xmi to Measure",
                level=2,
                pattern="apply, apply"
            ),
            Seed(
                instruction="Show me the configuration settings of the transformation that transforms a UML into a MOF and then show me the configuration settings of the transformation that transforms a UML into a KM3",
                level=2,
                pattern="get, get"
            ),
            # LEVEL 3 - Only target model mentioned
            Seed(
                instruction="Transform this model /Users/zakariahachm/Downloads/llm-agents-mde/src/examples/class.xmi to MOF model and then transform this model /Users/zakariahachm/Downloads/llm-agents-mde/src/examples/class.xmi to JAVA model",
                level=3,
                pattern="apply, apply"
            ),
            Seed(
                instruction="Show me the transformation that transforms this file /Users/zakariahachm/Downloads/llm-agents-mde/src/examples/class.xmi to MOF model then transform this model /Users/zakariahachm/Downloads/llm-agents-mde/src/examples/class.xmi to OWL model",
                level=3,
                pattern="get, apply"
            ),
            Seed(
                instruction="Show me the transformation that transforms this file /Users/zakariahachm/Downloads/llm-agents-mde/src/examples/class.xmi to MOF model then show me the transformation that transforms this file /Users/zakariahachm/Downloads/llm-agents-mde/src/examples/class.xmi to KM3 model",
                level=3,
                pattern="get, get"
            ),
            Seed(
                instruction="Transform this model /Users/zakariahachm/Downloads/llm-agents-mde/src/examples/class.xmi to MOF model then show me the transformation that transforms this file /Users/zakariahachm/Downloads/llm-agents-mde/src/examples/class.xmi to Measure model",
                level=3,
                pattern="apply, get"
            )
        ]
