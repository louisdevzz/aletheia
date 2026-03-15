# Aletheia: The Research Intelligence Architecture

Aletheia differentiates itself from typical RAG applications through its **Multi-Agent Research System**. It does not leverage a single language model response. It coordinates highly specialized agents to break down, retrieve, synthesize, and rigorously verify academic claims.

## The Aletheia Agents

### 1. The Planner Agent
Complex research demands a layered approach.
- **Role:** The task orchestrator.
- **Responsibility:** Decomposes complex user queries like "Summarize the methodology of paper X and compare it to paper Y." It delegates to the Retriever, Scholar, and Critic in an organized workflow.
- **Focus:** Strategy and execution flow.

### 2. The Archivist Agent
Research is built on structured knowledge.
- **Role:** The data manager.
- **Responsibility:** Ingests PDFs, chunks text, creates embeddings, manages metadata, and maps out the *Knowledge Graph* (e.g., tracking citation networks such as Paper A citing Paper B).
- **Focus:** Organization and knowledge preservation.

### 3. The Scholar Agent
Information extraction is only the first step.
- **Role:** The analytical mind and writer.
- **Responsibility:** Processes document chunks retrieved from the Vector Database. Synthesizes concepts, drafts explanations, structures reports, and seamlessly assumes the user's personal *Writing Style* based on patterns stored in Memory.
- **Focus:** Comprehension, synthesis, and creation.

### 4. The Critic Agent
Trust nothing an AI outputs without verifying the source.
- **Role:** The auditor.
- **Responsibility:** Executes Aletheia's "Zero-Hallucination" philosophy. For every claim the Scholar drafts, the Critic compares it against the raw, retrieved text from the original PDF. If inconsistencies, missing citations, or hallucinated facts are detected, it rejects the draft and initiates a rewrite.
- **Focus:** Verification, fact-checking, and grounding.

### 5. The Memory Agent
A true research companion grows alongside its owner.
- **Role:** The observer.
- **Responsibility:** Monitors the user's interactions over time. Updates Short-Term, Project, and Long-Term Memory. Learns the user's research interests, frequently queried topics, and stylistic quirks to personalize future interactions.
- **Focus:** Adaptation and continuity.

## Agent Interaction Loop

```text
User Question
      │
      ▼
[Planner Agent] ──▶ Evaluates scope & creates execution plan
      │
      ▼
[Archivist Agent / Retriever] ──▶ Extracts context & relationships
      │
      ▼
[Scholar Agent] ──▶ Synthesizes retrieved data & drafts response
      │
      ▼
[Critic Agent] ──▶ Validates logic against raw source
┌─────┴─────┐
│    NO     │ YES
▼           ▼
REWRITE   [Memory Agent] ──▶ Logs insights & updates profile
            │
            ▼
   Grounded User Response
```