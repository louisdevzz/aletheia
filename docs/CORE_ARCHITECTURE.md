# Aletheia: Core Architecture

> Comprehensive guide to the core architecture underlying the Aletheia research agent.

---

## 📋 Table of Contents

1. [System Overview](#1-system-overview)
2. [Document Processing Pipeline](#2-document-processing-pipeline)
3. [Retrieval Engine](#3-retrieval-engine)
4. [Knowledge Graph](#4-knowledge-graph)
5. [Memory System](#5-memory-system)
6. [Writing & Style Engine](#6-writing--style-engine)

---

## 1. System Overview

Aletheia is an **autonomous research agent structure** built to minimize hallucinations and enforce strict document grounding. It is not a simple chatbot wrapper; instead, it is a complex context engineering pipeline that guarantees traceable and verifiable knowledge synthesis.

The architecture ensures that Aletheia behaves as a **long-term research collaborator**, scaling from processing single documents to analyzing thousands of sources while maintaining the user's specific writing style.

### High-Level Architecture Flow

```
User Query
      │
      ▼
Agent Interface
      │
      ▼
Task Planner
      │
      ▼
Research Agent System
      │
      ├── Retrieval Engine (Vector + BM25 Search)
      ├── Knowledge Graph (Relationships)
      ├── Memory System (Context + History)
      ├── Reasoning Agents (Scholar + Critic)
      │
      ▼
Grounded Response (Traced to Original Source)
```

---

## 2. Document Processing Pipeline

The foundation of Aletheia's truth-grounding relies on how documents are ingested and processed.

```
PDF / Document Upload
      ↓
Document Parser (Text Extraction)
      ↓
Semantic Chunking (Contextually aware splits)
      ↓
Embedding Generation (Vectorization)
      ↓
Metadata Extraction (Title, Authors, Year, Citations)
      ↓
Vector Database & Document Store
```

- **Objective:** Convert complex, unstructured academic formats (like PDFs) into highly searchable, semantically distinct chunks.
- **Strict Grounding:** The system guarantees that the AI can only retrieve from this internal database, enforcing a "Zero-Hallucination" boundary.

---

## 3. Retrieval Engine

Aletheia uses a retrieval engine specifically tuned for academic knowledge recovery.

The engine uses a **hybrid approach**:
1. **Vector Similarity Search**: Finds semantically related concepts even if exact keywords aren't used.
2. **Keyword Search (BM25)**: Ensures specific terminology, acronyms, and names are precisely located.
3. **Citation Traversal**: Crawls the citation network to bring in related referenced literature context.
4. **Topic Filtering**: Restricts searches to user-defined research topics or specific projects.

---

## 4. Knowledge Graph

Research knowledge is not a flat list of documents; it's an interconnected web of ideas. Aletheia constructs a localized **Knowledge Graph** to represent these relationships.

**Example Structure:**
```
[Paper A] 
   ├── Method: [Diffusion Model]
   ├── Dataset: [CIFAR-10]
   └── Cites: [Paper B]
        └── Insight: [Training Optimization]
```

By traversing the Knowledge Graph, Aletheia can reason *across* papers—identifying methodologies shared between studies, or finding consensus/disagreements on a specific topic—rather than treating each paper in isolation.

---

## 5. Memory System

A conversational chatbot resets between sessions. Aletheia accumulates knowledge over time through a structured memory hierarchy.

### Short-Term Memory
- Retains context of the current conversation or session.
- Tracks temporary logical steps used by the multi-agent system.

### Project Memory
- Scoped to specific research endeavors.
- Maintains collections of literature, working notes, and ongoing hypotheses for a specific thesis or paper.

### Long-Term Memory
- The overarching intelligence of the agent.
- Learns the user's core research interests, previously explored ideas, and frequently used domain-specific concepts.
- Serves as the backbone of Aletheia's value as a "personal research intelligence system."

---

## 6. Writing & Style Engine

One of the largest bottlenecks in using AI for research writing is the generic, robotic text it outputs. Aletheia implements a **dynamic style transfer** mechanism.

- **Ingestion:** Users upload previous papers, reports, notes, or essays.
- **Pattern Extraction:** The system extracts tone, vocabulary preferences, academic structure, and formatting quirks.
- **Style Memory:** Builds a reproducible "voice profile."
- **Generation:** When drafting summaries or reports, the Scholar Agent invokes this Style Memory as few-shot examples, forcing the model to seamlessly mimic the user's academic voice without complex prompt engineering.