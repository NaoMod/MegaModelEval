from typing import List
from dataclasses import dataclass


@dataclass
class Seed:
    instruction: str
    level: int
    pattern: str

class SingleToolSeeds:
    """Single-tool seeds for OpenRewrite recipes"""

    @staticmethod
    def get_seeds() -> List[Seed]:
        return [
            # LEVEL 1 - Direct recipe name with explicit parameters
            Seed(
                instruction="Apply the fix_static_analysis_issues recipe to ./projects/my-app/build.gradle",
                level=1,
                pattern="recipe_application"
            ),
            Seed(
                instruction="Show me the details of the migrate_to_java_17 recipe",
                level=1,
                pattern="recipe_info"
            ),
            Seed(
                instruction="Run the fix_checkstyle_violations recipe on ./workspace/billing-service/build.gradle",
                level=1,
                pattern="recipe_application"
            ),
            Seed(
                instruction="What does the migrate_junit4_to_junit5 recipe do?",
                level=1,
                pattern="recipe_info"
            ),
            
            # LEVEL 2 - Task-based with context (what to achieve)
            Seed(
                instruction="I need to upgrade my project to Java 21, the build file is at ./projects/legacy-app/build.gradle",
                level=2,
                pattern="recipe_application"
            ),
            Seed(
                instruction="Which recipe should I use to migrate from Spring Boot 2 to Spring Boot 3?",
                level=2,
                pattern="recipe_info"
            ),
            Seed(
                instruction="Fix all the Checkstyle violations in the project at ./workspace/api-gateway/build.gradle",
                level=2,
                pattern="recipe_application"
            ),
            Seed(
                instruction="I want to know about the recipe that migrates from Log4j to SLF4J",
                level=2,
                pattern="recipe_info"
            ),
            
            # LEVEL 3 - Natural language task (no recipe name, problem-focused)
            Seed(
                instruction="My Java project uses JUnit 4 and I want to modernize the testing framework, project root is ./projects/ecommerce-platform",
                level=3,
                pattern="recipe_application"
            ),
            Seed(
                instruction="What are my options for upgrading an old Java 8 codebase to a recent version?",
                level=3,
                pattern="recipe_info"
            ),
            Seed(
                instruction="The static analysis tool is reporting many issues in ./workspace/payment-service/build.gradle, can you help fix them?",
                level=3,
                pattern="recipe_application"
            ),
            Seed(
                instruction="I have a Spring Boot 1 application that needs to be updated, what recipes are available?",
                level=3,
                pattern="recipe_info"
            )

            
        ]