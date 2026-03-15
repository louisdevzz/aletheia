# Agent Architecture Roadmap

> Forward-looking roadmap and detailed flow for Aletheia's Multi-Agent Research System.

---

## 🧠 Current Multi-Agent System

Aletheia relies on specialized reasoning roles rather than a single monolithic response generator. The current architecture separates concerns to maximize accuracy and minimize hallucinations.

### The Collaborative Core
1. **Planner Agent**: Decomposes complex user requests (e.g., "Write a literature review on X") into atomic retrieval, reading, and synthesizing steps.
2. **Archivist Agent**: Manages the ingestion of documents, updates embeddings, and maintains the integrity of the Knowledge Graph and Vector database.
3. **Scholar Agent**: The primary analytical mind. Interprets retrieved document chunks, synthesizes ideas across multiple papers, and drafts explanations.
4. **Critic Agent**: The strict verifier. Cross-references the Scholar's output against the raw source text. If a claim is unsupported, the Critic rejects the output and triggers a rewrite.
5. **Memory Agent**: Silently observes the user's interests, saving key insights and stylistic preferences to Project and Long-Term storage.

---

## 🗺️ Development Roadmap

### Phase 1: Robust Verification (Current Focus)
- **Enhanced Critic Logic**: Improve the Critic Agent's ability to detect subtle definition drift and misleading implications.
- **Source Traceability UI**: Build seamless frontend connections to map Critic-verified claims directly to PDF highlights.

### Phase 2: Advanced Discovery & Planning
- **Iterative Research Planner**: Upgrade the Planner Agent to dynamically adjust its research plan based on mid-task findings (e.g., discovering a new foundational paper halfway through a review).
- **Proactive Archivist**: Allow the Archivist to suggest new papers from external networks (arXiv, Semantic Scholar) based on the local Knowledge Graph gaps.

### Phase 3: Collaborative Synthesis
- **Multi-System Consensus**: Introduce sub-scholar agents that specialize in different scientific domains (e.g., Methodology Analyst, Result Comparer) that debate and form consensus before final drafting.
- **Style-Engine Refinement**: Allow the Scholar Agent to blend styles (e.g., "Write this technical analysis, but make it understandable for an introductory lecture").

### Phase 4: Autonomous Research Operation
- **Continuous Background Research**: The Memory and Planner agents work in the background while the user is away, monitoring RSS feeds and fetching new pre-prints that align with Long-Term Memory profiles.
- **Automated Literature Reviews**: Given a single prompt, the system autonomously queries, retrieves, criticizes, and writes a comprehensive, fully-cited 10-page literature review.