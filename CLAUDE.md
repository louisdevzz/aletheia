# Prompting & Context Instructions for AI Assistants
*Project: Aletheia*

If you are an AI assistant (e.g., Claude, LLMs, or coding agents) reading this file, you must adhere to the following principles, architectural boundaries, and branding requirements when writing code, answering questions, or generating content for the Aletheia project.

## 1. Project Philosophy

Aletheia is a **personal truth-grounded AI research assistant**. 

### The Core Law
> **AI should never invent knowledge when the source already exists.**

- **Zero-Hallucination Design**: Aletheia actively attempts to solve AI hallucinations in academic software. When writing features, prioritize strict retrieval grounding, source traceability, and verification pipelines over generic generation.
- **Research Companion, Not Chatbot**: Aletheia is framed as a long-term intelligence system with Memory and a Multi-Agent architecture. It learns writing styles and domain preferences over time.
- **Personalization**: Each instance is a standalone deployment owned by a single researcher.

## 2. Core Architecture Awareness

As a contributor, you must correctly map new features to the existing Aletheia architecture components:

*   **Document Processing Pipeline**: Ingestion, semantic chunking, and embedding.
*   **Knowledge Graph**: Linking concepts, sources, and methods across documents.
*   **Memory System**: Divided into Short-Term (session), Project (scoped task), and Long-Term (user profile) memory.
*   **Writing & Style Engine**: Mechanisms for extracting tone and formatting from past work for style transfer operations.

## 3. The Agent System

Aletheia is an autonomous **Multi-Agent Research System**. Features should generally be assigned to their corresponding Agent:
- **Planner Agent**: Task orchestration and plan decomposition.
- **Scholar Agent**: Document analysis, summarization, and writing (Drafting).
- **Critic Agent**: Strict fact-checking against source text (Verification).
- **Archivist Agent**: Managing embeddings, the knowledge graph, and user libraries.
- **Memory Agent**: Storing and retrieving user preferences and topics over time.

## 4. Coding & Implementation Guidelines

- Build modular systems. Ensure the logic for individual Agents runs efficiently entirely severed from the broader stack if tested independently.
- Always include robust logging and tracking. Traceability is key to Aletheia's UI (e.g., clicking an AI claim immediately highlights the source PDF text). Feature development must always preserve source node metadata.
- When producing documentation updates, maintain a professional, academic, yet bold and clean layout. Use the `🦀` emoji sparingly as the unofficial mascot.