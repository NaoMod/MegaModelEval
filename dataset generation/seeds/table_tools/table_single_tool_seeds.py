from typing import List
from dataclasses import dataclass

@dataclass
class Seed:
    instruction: str
    level: int
    pattern: str

class TableSingleToolSeeds:
    """10 diverse single-tool seeds for Table transformations using only apply and get operations"""

    @staticmethod
    def get_seeds() -> List[Seed]:
        return [
            # Level 1 - Full transformation name
            Seed(
                instruction="Apply Table2SVGBarChart to ./examples/table1.xmi",
                level=1,
                pattern="apply"
            ),
            Seed(
                instruction="Show me the configuration settings for the Table2SVGBarChart transformation",
                level=1,
                pattern="get"
            ),
            Seed(
                instruction="Apply Table2SpreadsheetMLSimplified to ./examples/table2.xmi",
                level=1,
                pattern="apply"
            ),
            Seed(
                instruction="Show me the configuration settings for the Table2SpreadsheetMLSimplified transformation",
                level=1,
                pattern="get"
            ),
            # Level 2 - Source and target models mentioned
            Seed(
                instruction="Transform the Table model ./examples/table3.xmi into a SVGPieChart model",
                level=2,
                pattern="apply"
            ),
            Seed(
                instruction="What transformation can I use to convert a Measure model to a Table?",
                level=2,
                pattern="get"
            ),
            # Level 3 - Only target model mentioned
            Seed(
                instruction="Transform this model /data/table4.xmi to TabularHTML model",
                level=3,
                pattern="apply"
            ),
            Seed(
                instruction="List me the details of the transformation that transforms this file /data/source1.xmi to Table model",
                level=3,
                pattern="get"
            ),
            # Additional diverse "get" seeds with different phrasing and focus
            Seed(
                instruction="What are the available details for the JavaSource2Table transformation?",
                level=1,
                pattern="get"
            ),
            Seed(
                instruction="Retrieve the metadata for the Measure2Table conversion tool",
                level=1,
                pattern="get"
            ),
            Seed(
                instruction="Give me information about transformations that produce SpreadsheetMLSimplified output from a Table model",
                level=2,
                pattern="get"
            )
        ]
