from typing import List
from dataclasses import dataclass

@dataclass
class Seed:
    instruction: str
    level: int
    pattern: str

class TableMultiToolSeeds:

    @staticmethod
    def get_seeds() -> List[Seed]:
        return [
            # LEVEL 1 - Full transformation names
            Seed(
                instruction="First show me the configuration of Table2SVGBarChart and then transform ./examples/table1.xmi using Table2SVGBarChart transformation",
                level=1,
                pattern="get, apply"
            ),
            Seed(
                instruction="Compare the configurations of the Table2SVGPieChart and Table2SpreadsheetMLSimplified transformations",
                level=1,
                pattern="get, get"
            ),
            Seed(
                instruction="Transform ./examples/table2.xmi with Table2TabularHTML and then check the Table2TabularHTML configuration",
                level=1,
                pattern="apply, get"
            ),
            Seed(
                instruction="Transform ./examples/table3.xmi using Table2SVGBarChart and then transform ./examples/table4.xmi using Table2SVGPieChart",
                level=1,
                pattern="apply, apply"
            ),
            # LEVEL 2 - Source and target models mentioned
            Seed(
                instruction="Show me the configuration settings of the transformation that transforms a Measure into a Table and then transform ./examples/measure1.xmi from a Measure model to a Table model",
                level=2,
                pattern="get, apply"
            ),
            Seed(
                instruction="Transform the JavaSource model ./examples/source1.xmi to Table and then compare the configurations of the transformation that transforms a Table into a TabularHTML",
                level=2,
                pattern="apply, get"
            ),
            Seed(
                instruction="Transform the Table model ./examples/table5.xmi to SpreadsheetMLSimplified and then transform the Table model ./examples/table6.xmi to TabularHTML",
                level=2,
                pattern="apply, apply"
            ),
            Seed(
                instruction="Show me the configuration settings of the transformation that transforms a Table into a SVGPieChart and then show me the configuration settings of the transformation that transforms a Table into a SVGBarChart",
                level=2,
                pattern="get, get"
            ),
            # LEVEL 3 - Only target model mentioned
            Seed(
                instruction="Transform this model /data/table7.xmi to SVGBarChart and then transform this model /data/table8.xmi to SVGPieChart",
                level=3,
                pattern="apply, apply"
            ),
            Seed(
                instruction="Show me the transformation that transforms this file /data/measure2.xmi to Table then transform this model /data/table9.xmi to TabularHTML",
                level=3,
                pattern="get, apply"
            ),
            Seed(
                instruction="Show me the transformation that transforms this file /data/table10.xmi to SpreadsheetMLSimplified then show me the transformation that transforms this file /data/table11.xmi to TabularHTML",
                level=3,
                pattern="get, get"
            ),
            Seed(
                instruction="Transform this model /data/source2.xmi to Table then show me the transformation that transforms this file /data/source3.xmi to Table",
                level=3,
                pattern="apply, get"
            )
        ]
