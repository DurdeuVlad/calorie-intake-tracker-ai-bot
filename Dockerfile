FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /workspace
COPY pom.xml .
COPY src src
RUN mvn -q -DskipTests package

FROM eclipse-temurin:21-jre
USER root
RUN apt-get update && apt-get install --no-install-recommends -y wget && rm -rf /var/lib/apt/lists/*
RUN addgroup --system app && adduser --system --ingroup app app
USER app
WORKDIR /app
COPY --chown=app:app --from=build /workspace/target/food-journal-bot-*.jar app.jar
EXPOSE 8080
ENV MANAGEMENT_PORT=8081
HEALTHCHECK --interval=30s --timeout=3s --start-period=45s --retries=3 CMD wget -q -O - "http://localhost:${MANAGEMENT_PORT}/actuator/health/readiness" || exit 1
ENTRYPOINT ["java","-XX:MaxRAMPercentage=75.0","-jar","/app/app.jar"]
