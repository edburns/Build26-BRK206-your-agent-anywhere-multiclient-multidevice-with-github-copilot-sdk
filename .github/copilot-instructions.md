This is a Microsoft Build 2026 session content repository for **BRK206**: demonstrating the GitHub Copilot SDK across multiple languages and platforms.

## Project context

This repo contains:
- A **C# Blazor demo** in `src/AgentOrchestrator/` — a real-estate lead-management agent pipeline using the Copilot SDK for .NET.
- A **Java demo** (in progress) in `src/java-agent-orchestrator/` — the same demo ported to Jakarta EE 11 + PrimeFaces + OpenLiberty, using the Copilot SDK for Java 1.0.7-SNAPSHOT.
- Planning documents in `dd-3017826-java-real-estate-demo-remove-before-merge/`.

## Java demo technology stack

- **Runtime:** OpenLiberty 26.0.0.5
- **Platform:** Jakarta EE 11 (Faces 4.0, CDI 4.0, WebSocket 2.1, JSON-B 3.0, Persistence 3.2)
- **UI:** PrimeFaces 15.0.16 (jakarta classifier)
- **AI:** Copilot SDK for Java 1.0.7-SNAPSHOT (`com.github:copilot-sdk-java`)
- **Database:** H2 in-memory
- **Build:** Maven, Liberty Maven Plugin
- **JDK:** 25+

## Key constraints

- Never commit secrets, API keys, or credentials. Use environment variables.
- Do not modify LICENSE, LICENSE-DOCS, CODE_OF_CONDUCT.md, or SECURITY.md.
- Do not add large binary files (PowerPoint, video, recordings) to the repo. Links are fine.
- The `dd-3017826-java-real-estate-demo-remove-before-merge/` folder contains planning docs and notes. Reference them for context.
- Favor Jakarta EE open standards over proprietary frameworks (e.g., prefer CDI over Spring, JPA over Hibernate-specific APIs).
- Use the `@CopilotTool` annotation API (ADR-005) for tool definitions — this is the headline Java SDK feature to demonstrate.

## Working with the Java demo

- Start Maven commands from `src/java-agent-orchestrator/`.
- Run the app: `mvn clean package liberty:run`
- The Copilot SDK for Java is installed in the local Maven repository as `com.github:copilot-sdk-java:1.0.7-SNAPSHOT`.

## Working with the C# demo

- Start from `src/AgentOrchestrator/`.
- Run: `dotnet run`

## Issue Support

If a user asks for help filing an issue, or reports a problem:
- Check `.github/ISSUE_TEMPLATE/` to discover available issue templates
- If templates exist, match the user's request to the best-fit template and walk them through the fields
- If no templates exist, create a plain issue with a clear title and description
- Check `gh label list` for available labels and apply relevant ones
- Do not hardcode template names or labels — always discover what's available at runtime
