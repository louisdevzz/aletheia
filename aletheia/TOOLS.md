# TOOLS.md - Your Toolkit

*Skills define how tools work. This file is for your specifics — the stuff that's unique to your setup.*

---

## What Goes Here

Document environment-specific details:
- Tool configurations and defaults
- Preferred search parameters
- Document processing preferences
- API keys and endpoints (if not in env)
- Custom behaviors you've agreed on with the user

---

## Available Tools

### 🔍 document_search

**Purpose:** Search through uploaded PDF documents using hybrid retrieval (Vector + BM25 + Reranking)

**When to use:**
- User asks about their uploaded files
- Questions containing: "file", "document", "PDF", "tài liệu", "upload", "what does it say"
- Any query about content in their documents

**Parameters:**
- `query` (required): What to search for
- `top_k` (optional): Number of results, default 5
- `doc_id` (optional): Search within specific document only

**Best practices:**
- Always search before answering document questions
- Cite sources with format: `[1] filename.pdf (Page X): "quote"`
- If no results, say so clearly — don't hallucinate
- Combine multiple results into coherent answers

**Configuration:**
- Hybrid search weight (alpha): 0.5 (equal vector + keyword)
- Reranker: cross-encoder/ms-marco-MiniLM-L-6-v2
- Vector DB: Milvus
- Keyword search: Elasticsearch (BM25)

---

### 🧮 calculator

**Purpose:** Perform mathematical calculations safely via AST evaluation

**When to use:**
- Mathematical expressions (2+2, sin(45), etc.)
- When precision matters more than estimation
- Unit conversions, percentages, financial calculations

**Supported operations:**
- Basic: +, -, *, /, //, %
- Power: **, pow()
- Math: sin, cos, tan, sqrt, log, exp, abs, round
- Constants: pi, e

**Best practices:**
- Use for any calculation where precision matters
- Show your work if the calculation is complex
- Don't use for simple estimates (just say "about 50")

---

### 💬 Direct Response (No Tool)

**Purpose:** General knowledge responses without document search

**When to use:**
- Greetings ("Hello!", "Good morning")
- General knowledge questions ("What's the weather?", "Who invented...")
- Small talk and clarifications
- When user explicitly says "don't search"

**Best practices:**
- Be concise for simple questions
- Don't over-explain
- Acknowledge limitations ("I don't have real-time data for...")

---

## Document Processing Configuration

### PDF Parsing
- **Parser:** Vision LLM (GPT-4o / Gemini / Kimi)
- **Output:** Markdown with preserved structure
- **Handles:** Text, tables, formulas, multi-column layouts

### Ingestion Pipeline
1. PDF → Images (per page)
2. Vision LLM → Markdown
3. Markdown → Paragraphs → Sentences
4. Store in 3 layers:
   - SQLite (ground truth)
   - Milvus (embeddings)
   - Elasticsearch (BM25 index)

### Citation System
- **Granularity:** Character-level offsets
- **Format:** `[index] filename.pdf (Page N): "exact text"`
- **Accuracy:** Must match source document exactly

---

## Custom Configurations

*Add your specific preferences here as you learn them:*

### Preferred Defaults
- Default search top_k: 5
- Citation style: [1] format with quotes
- Response length: [user preference]

### Document Types
- Primary document types user works with:
- Special handling for: [tables / formulas / multi-language / etc.]

### User Preferences
- Language: [auto-detect / specific]
- Tone: [formal / casual / technical]
- Detail level: [concise / thorough]
- Citation frequency: [always / important points only]

---

## Tool Selection Guidelines

**Use document_search when:**
- User mentions "file", "document", "PDF", "upload", "tài liệu"
- Question references content they showed you
- They ask "what does it say about..."
- Any doubt about whether it's in their docs

**Use calculator when:**
- Mathematical expression detected
- Precision required
- Financial or scientific calculations

**Use direct response when:**
- Clearly general knowledge
- Greetings or small talk
- User says "don't search" or "no need to look up"

**When in doubt:**
- Prefer document_search for document-related queries
- It's better to search and find nothing than to miss relevant info
- The user can always clarify if you search unnecessarily

---

## Error Handling

**If document_search fails:**
- Explain the error clearly
- Suggest alternatives (rephrase query, check if document uploaded)
- Don't make up answers

**If calculator fails:**
- Show the expression that failed
- Explain why (syntax error, unsupported operation)
- Offer to help fix it

**If you don't know which tool to use:**
- It's okay to ask: "Should I search your documents for this, or is this general knowledge?"
- Better to ask than guess wrong

---

## Tool Extensions

*Future tools may be added here:*
- Web search
- Code execution
- File system operations
- External API integrations

---

*Keep this file updated as you learn the user's preferences and as the system evolves.*
