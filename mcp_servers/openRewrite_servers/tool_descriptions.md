# Popular OpenRewrite recipes

## Recipe 1: Common static analysis issue remediation

This recipe automatically resolves common static analysis issues in the codebase
``In: build.gradle    out: project with fixed static issues``


## Recipe 2: Automatically fix Checkstyle violations
This recipe automatically reformats Java code to ensure consistent indentation, spacing, and brace placement, aligning the codebase with Checkstyle formatting rules.
``In: build.gradle    out: project with unified formatting``

## Recipe 3: Migrate to Java 17
This recipe automatically upgrade an older java codebase to Java 17 
``In: build.gradle    out: project conforming to java 17``


## Recipe 4: Migrate to Java 21
This recipe automatically upgrade your Java 8 or Java 11 projects to Java 21
``In: build.gradle    out: project conforming to java 21``


## Recipe 5: Migrate to Java 25
This recipe automatically upgrade your Java 8, 11, or 17 projects to Java 25.
``In: build.gradle    out: project conforming to java 25``


## Recipe 6: Migrate to JUnit 5 from JUnit 4
This recipe perform an automated migration from the venerable JUnit 4 testing framework to its successor JUnit 5.
``In: build.gradle    out: project using  JUnit 5.``


## Recipe 7: Migrate to JUnit 5 from JUnit 4
This recipe perform an automated migration from the venerable JUnit 4 testing framework to its successor JUnit 5.

``In: build.gradle    out: project using  JUnit 5.``


## Recipe 8: Migrate to Spring Boot 3 from Spring Boot 2
This recipe perform an automated migration from Spring Boot 2.x to Spring Boot 3.5.

``In: Root_project    out: project conforming to  Spring Boot 3.``


## Recipe 9: Migrate to Spring Boot 3.3
This recipe migrate applications to the latest Spring Boot 3.3 release5.

``In: Root_project    out: project conforming to  Spring Boot 3.3.``


## Recipe 10: Migrate to Spring Boot 2 from Spring Boot 1
This recipe migrate applications from SpringBoot 1 to SpringBoot 2.

``In: build.gradle    out: project conforming to  Spring Boot 2.``


## Recipe 11: Migrate to Quarkus 2 from Quarkus 1
This recipe migrate applications from from Quarkus 1.x to Quarkus 2.x.

``In: Root_project    out: project conforming to  Quarkus 2.``


## Recipe 12: Migrate to Micronaut 4 from Micronaut 3
This recipe perform an automated migration from Micronaut 3.x to Micronaut 4.x

``In: Root_project    out: project conforming to Micronaut 3.``


## Recipe 13: Migrate to Micronaut 3 from Micronaut 2
This recipe perform an automated migration from Micronaut 2.x to Micronaut 3.x

``In: Root_project    out: project conforming to Micronaut 3.x.``

## Recipe 14: Migrate to SLF4J from Log4j
This recipe perform an automated migration from Apache Log4j (handling both log4j 1.x or log4j 2.x) to the Simple Logging Facade for Java (SLF4J).

``In: Root_project    out: project conforming to SLF4J.``


## Recipe 15: Use SLF4J Parameterized Logging
This recipe automatically refactor logging statements to take advantage of performance improvements offered by using slf4j parameterized logging over String concatenation.

``In: Root_project    out: project conforming to SLF4J.``


## Recipe 16: Refactoring with declarative YAML recipes
This recipe declaratively renames a Java package (e.g., from com.yourorg.foo to com.yourorg.bar) and automatically updates all dependent code to use the new package name.

``In: Root_project, old _package_name, new_package_name    out: project using the new_package_name``


## Recipe 17: Automating Maven dependency management
This recipe analyzes and manages project dependencies to identify and resolve version conflicts, unexpected transitive dependencies, and other dependency-related issues.
``In: build.gradle    out: A cleaned and consistent dependency tree with resolved conflicts and removed or updated problematic dependencies.``


## Recipe 18: Migrate to AssertJ from Hamcrest
This recipe  perform an automated migration from Hamcrest to AssertJ

``In: Root_project   out: project using AssertJ``
