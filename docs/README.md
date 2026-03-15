# Aletheia Documentation

Welcome to the Aletheia project documentation.

Aletheia is an autonomous **Multi-Agent Research System** designed to read academic papers, verify its own answers, and generate grounded reports mimicking the user's specific writing style.

## Core Documentation

- [Core Architecture](./CORE_ARCHITECTURE.md): The high-level overview of Aletheia, detailing the document processing pipeline, the hybrid retrieval engine, the knowledge graph, and the memory structures.
- [Agent Architecture Roadmap](./AGENT_ARCHITECTURE_ROADMAP.md): Detailed information on the multi-agent system that runs Aletheia, the responsibilities of each agent (Scholar, Critic, Archivist, Planner, Memory), and the future roadmap for advanced collaborative synthesis.
- [Setup & Installation](./SETUP.md): Start here to learn how to deploy, configure, and connect your own Aletheia instance to your database and LLM providers.

## Project Philosophy

> **Core Principle: AI should never invent knowledge when the source already exists.**

All components in Aletheia are built around this philosophy. The system requires accurate citation mechanics and a multi-agent verification loop (Critic Agent) to ensure responses remain faithful to the original sources retrieved by the system.
