from typing import List
from dataclasses import dataclass


@dataclass
class Seed:
    instruction: str
    level: int
    pattern: str

class MultiToolSeeds:

    @staticmethod
    def get_seeds() -> List[Seed]:
        return [
            # LEVEL 1 - Full transformation names 
            Seed(
                instruction="First show me the configuration of Class2Relational and then transform ./atl_zoo/PNML2XML/modelsExamples/PetriNet2.xmi using PNML2XML transformation",
                level=1,
                pattern="get, apply"
            ),
            Seed(
                instruction="Compare the configurations of the Mantis2XML and MySQL2KM3 transformations",
                level=1,
                pattern="get, get"
            ),
            Seed(
                instruction="Transform ./atl_zoo/KM32EMF/Sample-KM3.xmi with KM32DSL and then check the PNML2XML configuration",
                level=1,
                pattern="apply, get"
            ),
            Seed(
                instruction="Transform ./atl_zoo/Ant2Maven/Examples/input/Ant/build.xmi using Ant2Maven and then transform ./atl_zoo/BibTeX2DocBook/samples/sample1.xmi using BibTeX2DocBook",
                level=1,
                pattern="apply, apply"
            ),
            # LEVEL 2 - Source and target models mentioned
            Seed(
                instruction="Show me the configuration settings of the transformation that transforms a Class into a Relational model and then transform ./atl_zoo/PNML2XML/modelsExamples/PetriNet2.xmi from a PNML model to a XML model",
                level=2,
                pattern="get, apply"

            ),
            Seed(
                instruction="Transform the KM3 model ./atl_zoo/KM32EMF/Sample-KM3.xmi to DSL and then compare the configurations of the transformation that transforms a MySQL into a KM3",
                level=2,
                pattern="apply, get"
            ),
            Seed(
                instruction="Transform the Book model /Publication/outputModelPublication.xmi to a Publication model and then transform the Family model ./atl_zoo/BibTeX2DocBook/samples/sample1.xmi to a Persons model",
                level=2,
                pattern="apply, apply"
            ),
            Seed(
                instruction="Show me the configuration settings of the transformation that transforms a Class into a Relational and then show me the configuration settings of the transformation that transforms a Ant into a Maven",
                level=2,
                pattern="get, get"
            ),

            # LEVEL 3 - Only target model mentioned 
            Seed(
                instruction="Transform this model /Users/zakariahachm/Downloads/llm-agents-mde/src/examples/class.xmi to Relational model and then transform this model /Users/zakariahachm/Downloads/llm-agents-mde/src/examples/petrinet.xmi to XML model",
                level=3,
                pattern="apply, apply"
            ),
            Seed(
                instruction= "Show me the transformation that transforms this file /Users/zakariahachm/Downloads/llm-agents-mde/src/examples/mantis.xmi to XML model then transform this model /Users/zakariahachm/Downloads/llm-agents-mde/src/examples/ant.xmi to Maven model", 
                level=3,
                pattern="get, apply"
            ),
            Seed(
                instruction= "Show me the transformation that transforms this file /Users/zakariahachm/Downloads/llm-agents-mde/src/examples/class.xmi to Relational model then show me the transformation that transforms this file /Users/zakariahachm/Downloads/llm-agents-mde/src/examples/bibtex.xmi to a Book model", 
                level=3,
                pattern="get, get"
            ),
            Seed(
                instruction= "Transform this model /MetamodelBridge/Models/SimpleExample/DSL2EMF/SimpleExampleMM-XML.xmi to DSL model then show me the transformation that transforms this file /Users/zakariahachm/Downloads/llm-agents-mde/src/examples/mysql.xmi to KM3 model", 
                level=3,
                pattern="apply, get"
            )
            ]
    