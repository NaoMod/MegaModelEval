from typing import List
from dataclasses import dataclass


@dataclass
class Seed:
    instruction: str
    level: int
    pattern: str

class MultiToolSeeds:
    """Multi-tool seeds for OpenRewrite recipes"""

    @staticmethod
    def get_seeds() -> List[Seed]:
        return [
            # LEVEL 1 - Direct recipe names with explicit parameters
            Seed(
                instruction="First show me the configuration of migrate_to_java_17 and then apply fix_static_analysis_issues to ./projects/banking-app/build.gradle",
                level=1,
                pattern="info, application"
            ),
            Seed(
                instruction="Compare the details of migrate_springboot2_to_springboot3 and migrate_quarkus1_to_quarkus2 recipes",
                level=1,
                pattern="info, info"
            ),
            Seed(
                instruction="Apply fix_checkstyle_violations to ./workspace/api/build.gradle and then apply migrate_junit4_to_junit5 to the same project",
                level=1,
                pattern="application, application"
            ),
            Seed(
                instruction="Run migrate_to_java_21 on ./projects/inventory-service/build.gradle and then show me the details of use_slf4j_parameterized_logging",
                level=1,
                pattern="application, info"
            ),
            
            # LEVEL 2 - Task-based with some context
            Seed(
                instruction="I need to upgrade my project to Java 17 at ./workspace/crm-system/build.gradle, but first tell me what the Java 21 migration recipe does",
                level=2,
                pattern="info, application"
            ),
            Seed(
                instruction="What are the differences between the Spring Boot 2 to 3 migration and the Spring Boot 3.3 migration recipes?",
                level=2,
                pattern="info, info"
            ),
            Seed(
                instruction="Fix the static analysis issues in ./projects/auth-service/build.gradle and then migrate the tests from JUnit 4 to JUnit 5",
                level=2,
                pattern="application, application"
            ),
            Seed(
                instruction="Upgrade ./workspace/notification-service/build.gradle to Java 21 and then show me information about the SLF4J migration recipe",
                level=2,
                pattern="application, info"
            ),
            
            # LEVEL 3 - Natural language, problem-focused
            Seed(
                instruction="My codebase at ./projects/legacy-erp has both code quality issues and uses an old Java version, can you help fix the quality issues first then upgrade to a modern Java version?",
                level=3,
                pattern="application, application"
            ),
            Seed(
                instruction="I'm considering upgrading my Spring Boot application, but I also want to understand what Quarkus migration options are available",
                level=3,
                pattern="info, info"
            ),
            Seed(
                instruction="Before I migrate my project at ./workspace/analytics-platform to a newer framework, I want to know what migration recipes exist, then apply the most appropriate one",
                level=3,
                pattern="info, application"
            ),
            Seed(
                instruction="Clean up the dependencies in ./projects/data-processor/build.gradle and then modernize the testing framework to use the latest version",
                level=3,
                pattern="application, application"
            )
        ]