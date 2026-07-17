# Semantic Indexing & Code Retrieval: Cursor vs GitHub Copilot — Deep Technical Research (2026)

**Research date:** May 2026  
**Scope:** How semantic codebase indexing works under the hood in Cursor and GitHub Copilot — architecture, algorithms, vector databases, embedding models, retrieval strategies, performance data, and practical differences.

---

## Table of Contents

1. [Why This Matters](#1-why-this-matters)
2. [Cursor: Full Indexing Architecture](#2-cursor-full-indexing-architecture)
   - 2.1 Step 1 — Syntactic Chunking via Tree-Sitter AST
   - 2.2 Step 2 — Custom Embedding Model (Agent-Trained)
   - 2.3 Step 3 — Path Obfuscation & Privacy
   - 2.4 Step 4 — Vector Storage in Turbopuffer
   - 2.5 Step 5 — Merkle Tree Change Detection
   - 2.6 Step 6 — Cross-Team Index Reuse via Simhash
   - 2.7 Cursor's Instant Grep Engine
   - 2.8 How the Agent Combines Search Tools
   - 2.9 Dynamic Context Discovery (Token Efficiency Layer)
3. [GitHub Copilot: Full Indexing Architecture](#3-github-copilot-full-indexing-architecture)
   - 3.1 Context Assembly at Completion Time — Sliding Windows + Jaccard Similarity
   - 3.2 Semantic Index Sources and Triggers
   - 3.3 The 2025 Embedding Model: Matryoshka + Contrastive Learning
   - 3.4 Multi-Index Sources: GitHub, Azure DevOps, Local
   - 3.5 How the Copilot Agent Uses the Index
   - 3.6 Cross-Repository Semantic Search
4. [Side-by-Side Technical Comparison](#4-side-by-side-technical-comparison)
5. [Performance Data](#5-performance-data)
   - 5.1 Cursor Measured Results
   - 5.2 Copilot Measured Results
   - 5.3 Head-to-Head on Task Completion
   - 5.4 Token Cost Overhead of Semantic Search
6. [Architectural Trade-offs](#6-architectural-trade-offs)
7. [Privacy Comparison](#7-privacy-comparison)
8. [Cost Comparison](#8-cost-comparison)
9. [Quality and Cost Verdict](#9-quality-and-cost-verdict)
10. [Open-Source Ecosystem: Adding Indexing to Tools That Lack It](#10-open-source-ecosystem-adding-indexing-to-tools-that-lack-it)
11. [What Claude Desktop and Claude Code Actually Do](#11-what-claude-desktop-and-claude-code-actually-do)
12. [Sources](#12-sources)

---

## 1. Why This Matters

Codebase indexing is the single largest technical differentiator between AI coding tools in 2026. It is not a UI feature — it determines whether the AI can answer "where do we handle authentication?" on a 100,000-file monorepo in under a second, or whether it needs to grep through every file linearly.

The core problem: LLMs are stateless. Every API call starts from zero. Without an index, the agent must read files on demand — which works for small projects but degrades badly at scale. With a well-built index, the agent can jump directly to the right code chunk regardless of codebase size.

Both Cursor and GitHub Copilot have invested heavily in this. They have made fundamentally different architectural choices that determine where each tool works best.

---

## 2. Cursor: Full Indexing Architecture

**Primary sources:** Cursor official blog (`cursor.com/blog/secure-codebase-indexing`, `cursor.com/blog/semsearch`, `cursor.com/blog/fast-regex-search`), Cursor official docs (`cursor.com/docs/agent/tools/search`), Turbopuffer case study (`turbopuffer.com/customers/cursor`), Towards Data Science deep-dive (Kenneth Leung, Jan 2026), Praveen Kumar reverse engineering (Medium, 2026).

### 2.1 Step 1 — Syntactic Chunking via Tree-Sitter AST

The pipeline begins not with raw text but with a **parsed abstract syntax tree (AST)**.

Cursor uses [tree-sitter](https://tree-sitter.github.io/), a parser generator that converts source code into a concrete syntax tree. Tree-sitter supports 40+ languages, handles real-time re-parsing of changed content, and gracefully degrades on syntax errors in incomplete code — critical for a live coding environment.

**Why AST chunking matters over naive text splitting:**

Naive approach (character limit splitting):
```python
# Input: 300 lines of Python
# Chunk 1: lines 1–100 (cuts mid-function)
# Chunk 2: lines 101–200 (starts mid-function)
# Problem: neither chunk is semantically coherent
```

AST-aware approach (what Cursor does):
```python
# Input: 300 lines of Python with 8 functions
# Chunk 1: function authenticate_user() + its docstring
# Chunk 2: function validate_token() + helpers
# Result: each chunk is a complete semantic unit
```

The chunker traverses AST nodes and groups adjacent ones together until a token limit is reached. Splits happen **between** functions and classes, never **inside** them unless a single function exceeds the size limit. This means retrieved chunks always contain complete, runnable code units — variables and their definitions stay together, function signatures and their bodies stay together.

**Practical result:** semantic queries like "where do we validate JWT tokens?" retrieve `validate_token()` as a complete chunk, not half of one function.

### 2.2 Step 2 — Custom Embedding Model (Agent-Trained)

Cursor trains its own embedding model — not a generic code embedding model like `text-embedding-ada-002` or VoyageCode.

**What makes the training methodology unusual:**

From `cursor.com/blog/semsearch`:

> "When an agent works through a task, it performs multiple searches and opens files before finding the right code. By analyzing these traces, we can see in retrospect what should have been retrieved earlier in the conversation."

The training loop:
1. Agent session runs: it performs searches → opens files → generates code
2. An LLM is given the full session trace and asked to rank: "what content would have been most helpful at each search step?"
3. The embedding model is trained to align its similarity scores with these LLM-generated relevance rankings

This is a **feedback loop from real agent behavior** rather than generic code similarity. The model learns what "retrieval quality" means for a coding agent specifically — not just what code is textually or semantically similar, but what code would have actually helped the agent complete the task.

**Practical consequence:** the model is tuned for retrieval quality in agentic workflows, not academic code similarity benchmarks.

### 2.3 Step 3 — Path Obfuscation & Privacy

Before any data leaves the local machine, Cursor encrypts file paths on the client side.

From `towardsdatascience.com/how-cursor-actually-indexes-your-codebase/`:

> "Each component of the path, split by `/` and `.`, is masked using a secret key and a small fixed nonce."

Example transformation:
```
Input:  src/payments/invoice_processor.py
Output: a9f3/x72k/qp1m8d.f4
```

Directory structure is preserved (for retrieval filtering) but actual file and folder names are hidden. Users can customize the encryption key:

```json
// .cursor/keys in workspace root
{
  "path_decryption_key": "your-custom-key-here"
}
```

**Critical privacy guarantee:** Source code itself is **never stored in plaintext** on Cursor's servers. Only embeddings and encrypted metadata are stored. The actual code is:
- Held in memory during the embedding step
- Discarded after embedding is generated
- Retrieved from the local filesystem at inference time only, for the specific chunks needed

From `cursor.com/docs/agent/tools/search`:
> "Code content is never stored in plaintext; it is held in memory during indexing, then discarded."

50% of users enable Privacy Mode, which ensures code is stored only for the duration of the request.

Users control what gets indexed via `.cursorignore` (same syntax as `.gitignore`).

### 2.4 Step 4 — Vector Storage in Turbopuffer

Cursor uses [Turbopuffer](https://turbopuffer.com/) as its vector database — a serverless, high-performance engine combining vector and full-text search backed by object storage.

**Architecture chosen:** one namespace per codebase instance. Each user's checkout of a repo gets its own namespace. Turbopuffer's object storage backend means inactive namespaces "fade" to cold storage automatically; active ones are loaded into NVMe/memory cache.

**Latency figures (from Turbopuffer case study):**
- Warm query (active codebase): **8–10ms**
- Cold query (inactive, loading from object storage): **500–600ms**

**Scale:** Cursor stores **1 trillion+ document vectors** across **80 million+ namespaces** in Turbopuffer.

**Cost story:** Cursor migrated to Turbopuffer in November 2023 from a traditional vector database architecture:
- **20× cost reduction** for semantic search operations
- **95% total cost reduction**
- Peak ingestion: **1M+ writes/second** (for migrations and mass indexing)
- No more manual bin-packing of codebase indexes to dedicated servers

Key API used: `copy_from_namespace` — Turbopuffer's native capability to duplicate an existing namespace's vectors into a new one, used for the cross-team index reuse feature (section 2.6) at a **50% write discount**.

### 2.5 Step 5 — Merkle Tree Change Detection

Index updates run every ~5 minutes (some sources say 10 minutes for re-indexing). The challenge: on a 50,000-file repo, naively rehashing every file would be O(n) — too slow to run frequently.

Cursor uses a **Merkle tree** (the same data structure underlying Git and Bitcoin) to detect changes in O(k log n) where k is the number of changed files.

**How the Merkle tree works:**

```
         [root hash]
        /            \
   [src/ hash]    [tests/ hash]
    /       \
[auth/ hash] [payments/ hash]
     |
[auth.ts hash] = SHA-256 of file content
```

Each leaf is a SHA-256 hash of file content. Each directory node is a hash of its children's hashes (sorted — critical for cross-OS consistency). When a single file changes:
- Its leaf hash changes
- Its parent directory hash changes
- The root hash changes
- All other subtrees are **unchanged** and can be skipped

From `cursor.com/blog/secure-codebase-indexing`:
> "In a workspace with fifty thousand files, just the filenames and SHA-256 hashes add up to roughly 3.2 MB. Without the tree, you would move that data on every update. With the tree, Cursor walks only the branches where hashes differ."

**File change handling:**

| Event | Action |
|---|---|
| New file | Add to index: chunk → embed → store |
| Modified file | Remove old embeddings; chunk new version → embed → store |
| Deleted file | Remove all associated embeddings immediately |
| Large/complex file | May be skipped for performance |

Unchanged chunks **hit the embedding cache** (keyed by chunk content hash) — no re-embedding needed. This means most updates only process the few chunks that actually changed.

### 2.6 Step 6 — Cross-Team Index Reuse via Simhash

**The problem:** when a new developer joins a team and clones the repo, Cursor would normally build the entire index from scratch. On a large enterprise monorepo this took up to 4 hours before this feature shipped.

**The observation:** team codebases average **92% similarity** across users within an organization. A new clone differs from a colleague's clone only by local branches and recent uncommitted changes.

**The solution (from `cursor.com/blog/secure-codebase-indexing`):**

1. New user opens workspace; Cursor computes the Merkle tree locally
2. A **simhash** is derived from the Merkle tree — a single value summarizing the codebase's file content fingerprints
3. The simhash is uploaded to Cursor's server and used as a vector to search Turbopuffer against all existing indexes from the same team
4. If a matching index is found (above a similarity threshold), Cursor calls `copy_from_namespace` to clone it into a new namespace — in the background, in seconds
5. The user can immediately start querying against the copied index
6. Meanwhile, the Merkle tree sync reconciles differences: files the user has that don't match the copied index get freshly embedded and added

**Security constraint:** a user must **prove they have a file** before getting search results from it. This is enforced cryptographically using the Merkle tree itself — since each hash is derived from file content, you can only compute the correct hash if you have the file. The server stores content proofs during the transition and filters results against them.

**Time-to-first-query improvements:**

| Percentile | Before | After |
|---|---|---|
| Median repo | 7.87 seconds | 525 milliseconds |
| 90th percentile | 2.82 minutes | 1.87 seconds |
| 99th percentile | 4.03 hours | 21 seconds |

### 2.7 Cursor's Instant Grep Engine

Separate from the semantic vector index, Cursor built a custom regex search engine described in `cursor.com/blog/fast-regex-search` (March 2026, authored by Vicent Marti).

**The problem with ripgrep for large codebases:**

> "We routinely see `rg` invocations that take more than 15 seconds [on large enterprise monorepos], and that really stalls the workflow of anybody who's actively interacting with the Agent."

ripgrep is fast at matching regex against file content, but it must read every file. There's no way to avoid touching every file without an index.

**The Cursor solution:** an inverted trigram index — the same technique behind Google Code Search (described in Russ Cox's 2012 blog post).

**How trigram indexing works:**

A trigram is a sequence of 3 characters. Every unique trigram in a file is extracted and stored in an inverted index mapping trigram → set of files containing it.

```
File content: "authenticate_user"
Trigrams:     "aut", "uth", "the", "hen", "ent", "nti", "tic", "ica", ...

Inverted index:
  "aut" → [auth.ts, login.ts, middleware.ts]
  "the" → [auth.ts, utils.ts, config.ts, ...]
  ...
```

When searching for pattern `authenticate`, Cursor:
1. Decomposes the pattern into required trigrams: `aut`, `uth`, `the`, `hen`, `ent`
2. Intersects the posting lists for those trigrams
3. Only reads the files in the intersection (a tiny fraction of the total)
4. Runs the actual regex only on those files

**Result:** for patterns with enough distinctive trigrams, the vast majority of files are eliminated without reading them. For large monorepos, this can reduce the files that need to be read from 100,000+ to a handful.

**Limitations noted in the Cursor blog:**
- Short patterns or very common trigrams provide less filtering benefit
- Wildcard patterns (`.`, `.*`) can't be decomposed into required trigrams
- The trigram index itself must be built and maintained (another background process)

### 2.8 How the Agent Combines Search Tools

From `cursor.com/docs/agent/tools/search`:

| Prompt style | Primary tool | Follow-up |
|---|---|---|
| Specific symbol or string | Instant Grep (trigram index) | — |
| Concept or behavior | Semantic search (vector) | Grep to fill in details |
| Complex multi-file exploration | Semantic + Grep + file reads | Explore subagent for parallel search |

The Explore subagent is worth noting: for complex tasks requiring broad search, Cursor can spawn a **subagent in its own context window** using a faster model. It runs many parallel searches without bloating the main conversation's context, then returns only the relevant findings as a summary. This is how Cursor avoids the token explosion problem on large exploratory tasks.

### 2.9 Dynamic Context Discovery (Token Efficiency Layer)

Described in `cursor.com/blog/dynamic-context-discovery` (Jan 2026) — this is a second architectural layer on top of the semantic index, focused on reducing token overhead from all context sources, not just codebase search.

**The core principle:** provide less static context upfront; let the agent pull what it needs dynamically. The shift is from "include everything that might be relevant" to "include only what the agent asks for."

**Five implemented techniques:**

**1. Turning long tool responses into files**
Instead of truncating large shell command outputs or MCP tool responses (which causes data loss), Cursor writes them to temporary files. The agent reads the end with `tail` first, then reads more if needed. This eliminates the common failure where important log output at the bottom of a long command gets truncated before the agent sees it.

**2. Referencing chat history during summarization**
When the context window fills up, Cursor summarizes the conversation — but summarization is lossy. Key details get dropped. Cursor now writes the full chat history to a file and gives the agent a reference to it. If the summary omits something the agent needs, it can search the history file to recover specific details.

**3. Agent Skills as dynamic files**
Agent Skills (Cursor's open standard for extending agent capabilities with domain-specific instructions) are not always injected into the system prompt. The agent receives only skill names and descriptions as static context, then dynamically fetches the full skill file when the task requires it.

**4. MCP tool lazy-loading**
A documented A/B test result: loading MCP tool descriptions dynamically rather than upfront reduced total agent tokens by **46.9%** in sessions that called at least one MCP tool. This is because MCP tool schemas are large (150–400 tokens each) and most tools in a session are never used. The agent now loads tool descriptions on-demand by grepping a folder structure.

**5. Terminal sessions as files**
Integrated terminal output is synced to the filesystem. The agent can grep terminal history rather than having it injected wholesale into context. This is especially useful for long-running process logs (e.g., a dev server).

**Why this matters for the indexing story:** Dynamic context discovery means the semantic index is not the only retrieval mechanism Cursor uses to keep context lean. The full system is designed around on-demand retrieval rather than preemptive injection — at every layer, from codebase chunks to MCP schemas to tool outputs.

---

## 3. GitHub Copilot: Full Indexing Architecture

**Primary sources:** GitHub official docs (`docs.github.com/copilot/concepts/indexing-repositories-for-copilot-chat`, `code.visualstudio.com/docs/copilot/reference/workspace-context`), GitHub Blog/Microsoft Research (`github.blog/changelog/`, `microsoft.com/en-us/research/`), InfoQ (Oct 2025), Capabl technical deep-dive (2025).

### 3.1 Context Assembly at Completion Time — Sliding Windows + Jaccard Similarity

Before the semantic index existed, Copilot assembled context using a heuristic approach — and this layer **still runs for inline completions today**, separately from the semantic index.

**Step 1: Chunking via 60-line sliding windows**

Copilot's completion-time retrieval does NOT use AST-based chunking. It uses **60-line sliding windows** — fixed-size blocks that slide over each candidate file. This is a fundamental difference from Cursor's approach:

| Tool | Chunking strategy |
|---|---|
| Cursor | AST nodes (functions, classes) — semantically meaningful boundaries |
| Copilot (completion-time) | 60-line sliding windows — fixed-size, not syntax-aware |

The 60-line window approach is faster (no parsing required) but produces chunks that may split mid-function. For inline completions, where speed matters more than semantic coherence, this is an acceptable trade-off.

**Step 2: Jaccard similarity scoring**

Copilot scores candidate windows using **Jaccard similarity** — a measure of token overlap between the candidate window and the current file context (prefix + suffix around the cursor).

```
Jaccard(A, B) = |tokens(A) ∩ tokens(B)| / |tokens(A) ∪ tokens(B)|
```

A window from `auth.ts` gets a high score if it shares many tokens (variable names, function names, keywords) with the code you're currently writing. A window from an unrelated utility file gets a low score.

**What Copilot scans for candidates:**
1. The **prefix** (code before cursor) and **suffix** (code after cursor)
2. **Open editor tabs** — files currently open in VS Code
3. **Recently edited files**
4. **Files in the same directory**
5. **Import graph** — files imported by the current file

**Practical implication:** for inline completions, what tabs you have open directly affects Copilot's quality. Irrelevant open tabs add low-scoring noise that can displace more relevant windows. Keeping focused tabs is more important in Copilot than in Cursor, because Cursor's semantic search can skip irrelevant files via the vector index; Copilot's Jaccard scoring still reads candidate windows from every open tab.

**Tiered fallback for workspace size:**
- **Small workspaces** (under ~100 files or 32,000 tokens): Copilot can read the entire workspace into context
- **Larger workspaces**: Falls back to the scored window strategy above
- **With semantic index**: `#codebase` tool replaces window scoring with vector retrieval for chat and agent tasks

### 3.2 Semantic Index Sources and Triggers

The semantic index is separate from the completion-time heuristic. It is required for the `#codebase` tool and for workspace-wide semantic search in chat.

**Index is triggered automatically when:**
- You open Copilot Chat in VS Code with a repository context
- You open Copilot Chat on github.com for a GitHub-hosted repo

**Index sources (from `code.visualstudio.com/docs/copilot/reference/workspace-context`):**

| Repository type | Where index is built | Speed |
|---|---|---|
| GitHub-hosted repo | GitHub's servers (remote index) | Instant on re-use; built once per repo |
| Azure DevOps repo | Automatically built and maintained | Sign in with Microsoft account |
| Other workspace / local folder | VS Code builds locally | Initial build: minutes; updates: background |

For GitHub-hosted repos, the index is built once and shared — any developer who opens that repo in VS Code benefits immediately from an already-built index. This is Copilot's equivalent of Cursor's cross-team index reuse, but implemented via GitHub's infrastructure rather than via Merkle tree simhash.

**Re-indexing latency:**
- Initial index: up to 60 seconds for large repos
- Subsequent updates: within seconds of starting a new conversation

**Index status:** visible in the Copilot status dashboard in the VS Code status bar.

### 3.3 The 2025 Embedding Model: Matryoshka + Contrastive Learning

GitHub shipped a new embedding model in September 2025. This is the most technically significant update to Copilot's retrieval capabilities to date.

**Training methodology:**

**Contrastive learning with InfoNCE loss:** the model is trained to pull similar code pairs together in embedding space and push dissimilar pairs apart. InfoNCE (Information Noise-Contrastive Estimation) is a training objective that maximizes the mutual information between a query and its correct retrieval target.

```
InfoNCE loss = -log [ exp(sim(q, k+)) / Σ exp(sim(q, ki)) ]

Where:
  q   = query embedding (e.g., natural language: "authentication middleware")
  k+  = correct target embedding (the actual auth middleware function)
  ki  = all candidates in the batch (correct + incorrect "negatives")
```

**Hard negatives:** the training data explicitly includes code snippets that are superficially similar but semantically incorrect — e.g., a function named `validate_session` when the query is about `validate_token`. The model is forced to learn fine-grained distinctions, not just coarse topic similarity.

**Matryoshka Representation Learning (MRL):** a technique that trains a single embedding model to produce valid embeddings at multiple dimensionality levels simultaneously. Named after Russian nesting dolls — the full-dimensional embedding contains all information, but truncating it to a smaller dimension still produces a valid, usable embedding.

```
Full embedding:    [d1, d2, d3, ..., d768]     # high quality, high memory
Truncated to 256:  [d1, d2, d3, ..., d256]     # lower quality, 3× less memory
Truncated to 128:  [d1, d2, d3, ..., d128]     # even lower, 6× less memory
```

This allows Copilot to adapt embedding size to the retrieval task:
- Small code fragments → compact embedding
- Full file context → larger embedding
- Memory-constrained environments → truncate without retraining

**Training data composition:**

| Language | Share of training data |
|---|---|
| Python | 36.7% |
| Java | 19.0% |
| C++ | 13.8% |
| JavaScript/TypeScript | 8.9% |
| C# | 4.6% |
| Other | 17.0% |

Source: GitHub internal training corpus (GitHub.com + Microsoft internal repositories).

**Resulting improvements over previous model:**

| Metric | Before | After | Change |
|---|---|---|---|
| Average retrieval score | 0.362 | 0.498 | +37.6% |
| Throughput | baseline | 2× baseline | +100% |
| Index memory size | baseline | baseline/8 | −87.5% |
| C# code acceptance rate | baseline | 2.1× baseline | +110.7% |
| Java code acceptance rate | baseline | 2.1× baseline | +113.1% |

**Benchmark comparison vs competitors:**
The model outperformed VoyageCode3, Nomic Embed Code, and Jina Code Embeddings on internal and external retrieval benchmarks (source: Capabl technical deep-dive, 2025).

### 3.4 Multi-Index Sources: GitHub, Azure DevOps, Local

Unlike Cursor's single local-first architecture, Copilot has three distinct index building paths:

**GitHub-hosted repos (most common path):**
- Index built once on GitHub's infrastructure
- Available instantly to all developers who open that repo
- Updated automatically when the repo changes
- Supports `#githubRepo owner/repo` to search repos you're not even running locally

**Azure DevOps repos:**
- Automatic index built and maintained by Microsoft's infrastructure
- Sign in with Microsoft account to enable

**Local/other workspaces (fallback):**
- VS Code builds the index locally
- Initial build: "a few minutes" (VS Code docs, 2026)
- No infrastructure dependency — works for any local folder
- Command Palette: "Build Codebase semantic index" to trigger manually

This multi-source architecture means Copilot's index quality is tightly coupled to where your code lives. GitHub-hosted repos get the best experience; local-only repos fall back to VS Code's local build, which is closer to how Cursor's local indexing works.

### 3.5 How the Copilot Agent Uses the Index

From `code.visualstudio.com/docs/copilot/reference/workspace-context`, when asked to "add error handling to the payment service":

1. **Semantic search** to find payment-related code across the project
2. **Grep** to find existing error handling patterns in the codebase
3. **Usages tool** to trace how payment functions are called (uses Go to Definition, Find All References, Find Implementation — LSP-backed)
4. **File search** to locate related config and test files
5. **Read file** on the relevant files, then generate coordinated changes

The Usages tool is worth highlighting — it's backed by VS Code's Language Server Protocol integration, which gives Copilot access to the same symbol graph a developer uses for Go to Definition. This is **complementary to** the semantic index, not a replacement for it: LSP gives precise symbol-level navigation; the semantic index gives meaning-based retrieval.

From March 2026 changelog: the Copilot cloud agent now uses semantic search automatically when it "doesn't know the precise names or patterns to search for" — no configuration required.

### 3.6 Cross-Repository Semantic Search

A capability Cursor does not currently offer: Copilot can semantically search GitHub repositories you're not running locally.

```
# In Copilot Chat
#githubRepo torvalds/linux -- how is memory allocation handled?
```

Or:
```
#githubTextSearch owner/repo -- search for text patterns
```

For open-source library lookup, upstream API research, or comparing implementations across repos, this is a meaningful differentiator. It's only available for public GitHub repos (and private repos with appropriate permissions).

---

## 4. Side-by-Side Technical Comparison

| Dimension | Cursor | GitHub Copilot |
|---|---|---|
| **Completion-time chunking** | Tree-sitter AST → syntactic units (functions, classes) | **60-line sliding windows** (fixed-size, not syntax-aware) |
| **Chat/agent chunking** | Tree-sitter AST (same pipeline) | Vector index for `#codebase`; AST details not publicly disclosed |
| **Embedding model** | Custom, trained on agent session traces (agentic retrieval quality) | Custom, MRL + contrastive learning + InfoNCE (code similarity quality) |
| **Vector database** | Turbopuffer (serverless, namespace-per-codebase, 1T+ vectors) | GitHub infrastructure (GitHub-hosted) / VS Code local (other) |
| **Index location** | Local-first (embeddings on Cursor's servers; source code stays local) | Cloud-first for GitHub repos; local fallback for others |
| **Index trigger** | Automatic on workspace open; syncs every ~5 min | Automatic on Copilot Chat open; re-indexes within seconds per conversation |
| **Offline / non-GitHub repos** | ✅ Full support (local filesystem) | ⚠️ Full semantic index requires GitHub or Azure DevOps; local fallback available |
| **Cross-team index reuse** | ✅ Merkle simhash → copy_from_namespace (525ms median, 21s 99th percentile) | ✅ GitHub-hosted repos: one index shared across all users instantly |
| **Cross-repo search** | ❌ Not available | ✅ `#githubRepo owner/repo` for any GitHub repo without local checkout |
| **Regex search** | Custom trigram inverted index (Instant Grep — skips reading most files) | ripgrep (must read every file) |
| **Token efficiency layer** | ✅ Dynamic Context Discovery — lazy-loads MCP tools, terminal, skills; 46.9% token reduction in A/B test | ❌ No equivalent lazy-loading system |
| **Privacy: source code** | Never stored on servers; held in memory during indexing only | Not stored on servers during indexing; interaction data used for training (Free/Pro/Pro+) unless opted out |
| **Privacy: indexed data** | Not used for training | ✅ Indexed data explicitly NOT used for training (all tiers) |
| **LSP integration** | VS Code extension APIs | Deep VS Code LSP (Usages: Go to Definition, Find All References, Find Implementation) |
| **IDE portability** | VS Code only (Cursor is a VS Code fork) | VS Code, JetBrains, Neovim, Visual Studio, CLI via Language Server |
| **Warm query latency** | 8–10ms (Turbopuffer, ✓ verified) | Not published |
| **Token cost per semantic search** | ~1,500 tokens per search call ($0.25/M on Teams plan) | Included in subscription; no per-token billing for search |
| **Semantic search + grep combined** | ✅ Agent auto-selects; Explore subagent for parallel search | ✅ Agent auto-selects; Usages tool for LSP symbol tracing |

---

## 5. Performance Data

### 5.1 Cursor Measured Results

**Semantic search vs grep alone (Cursor Context Bench — internal evaluation):**

| Model | Relative improvement with semantic search |
|---|---|
| Cursor Composer | +23.5% |
| Claude Sonnet 4.5 | +14.7% |
| Grok Code | +11.9% |
| Gemini 2.5 Pro | +8.7% |
| GPT-5 | +6.5% |
| **Average** | **+12.5%** |

Source: `cursor.com/blog/semsearch`

The improvement is **largest on Cursor's own Composer model** (+23.5%) because Composer was specifically trained in conjunction with the indexing system. The effect is smallest on GPT-5 (+6.5%), possibly because GPT-5's stronger parametric code knowledge compensates more for retrieval misses.

**A/B test on production users (semantic search on vs off):**

| Metric | Effect |
|---|---|
| Code retention (all codebases) | +0.3% |
| Code retention (large codebases, 1,000+ files) | +2.6% |
| Dissatisfied follow-up requests | −2.2% |

Source: `cursor.com/blog/semsearch`

The effect size appears modest on small codebases but compounds on large ones. The −2.2% reduction in dissatisfied requests (follow-ups, corrections) on a tool used millions of times daily is a large absolute reduction in user frustration.

### 5.2 Copilot Measured Results

**New embedding model vs previous model (September 2025):**

| Metric | Improvement |
|---|---|
| Retrieval quality (internal benchmark) | +37.6% |
| Throughput | +100% (2×) |
| Index size | −87.5% (8× smaller) |
| C# code acceptance rate | +110.7% |
| Java code acceptance rate | +113.1% |

Source: Microsoft Research blog (`microsoft.com/en-us/research/`, Sept 2025)

**Agent performance with semantic code search (March 2026):**
- Copilot coding agent completes tasks **~2% faster** when semantic search is available vs grep-only
- No change in output quality — speed gain only

Source: GitHub Changelog, March 2026

### 5.3 Head-to-Head on Task Completion

| Study | Finding |
|---|---|
| IBuidl.org controlled trial (2026) | Cursor outperforms Copilot by **31% on complex multi-file task completion**; attributed to indexing depth and Composer's multi-file diff capabilities |
| StackSheriff comparison (2026) | Cursor: "excellent" codebase context; Copilot: "good but not excellent" |
| Developer Toolkit AI (2026) | Cursor uses local-side embeddings for "full repo indexing"; Copilot uses "file + neighbor context" and GitHub-hosted access — "good (but not excellent)" codebase understanding |

~ inferred: the 31% gap is specifically on complex multi-file tasks. For single-file completions, the gap is likely much smaller — possibly negligible.

### 5.4 Token Cost Overhead of Semantic Search

This is a gap most cost analyses miss: the semantic index has a **per-query token cost at inference time**, because retrieved chunks must be injected into the LLM's context window.

**Cursor:**

From a community cost analysis (`instructify` repo, `.cursor/docs/COST-OPTIMIZATION.md`) cross-referenced with Cursor pricing docs:

| Operation | Estimated token cost |
|---|---|
| Semantic search (one call) | ~1,500 tokens |
| File read | ~500 tokens |
| Web fetch | ~2,500 tokens |

Cursor Teams plan charges **$0.25 per million tokens** on non-Auto model requests. At this rate, one semantic search call costs ~$0.000375. In a heavy agentic session making 20 semantic search calls, that's ~30,000 extra tokens (~$0.0075) from search alone — before the actual code being retrieved is counted.

On **Auto mode**, the token rate is waived — Cursor absorbs the cost within the subscription.

**Copilot:**

No per-token billing for semantic search. The index query is part of Copilot's infrastructure, and the results are injected into context. There is no additional charge per search call beyond the subscription.

The practical implication: **for heavy agentic use on non-Auto models in Cursor, the semantic index adds measurable token cost.** For Copilot, it does not.

---

## 6. Architectural Trade-offs

### Where Cursor's local-first architecture wins

**1. Repos not on GitHub**
Cursor's index works on any local directory regardless of hosting. Copilot's best semantic search requires GitHub or Azure DevOps hosting.

**2. Offline / air-gapped environments**
Cursor's index is stored locally and usable without internet after initial build. Copilot requires connectivity to GitHub/VS Code telemetry infrastructure.

**3. Custom embedding model tuned for agents**
Cursor's model was trained on actual agent task traces — what the agent should have retrieved to complete coding tasks. This is a tighter fit for agentic workflows than a general-purpose code retrieval model.

**4. Trigram inverted index for regex search**
Cursor's Instant Grep eliminates the need to read every file for regex patterns. ripgrep, which Copilot uses, still reads every matching file. On 100,000-file monorepos, this is a significant latency difference.

**5. Explore subagent for parallel search**
For broad, exploratory tasks, Cursor can parallelize searches in a separate context window. Copilot has no equivalent parallel search mechanism.

### Where Copilot's cloud architecture wins

**1. Multi-IDE support**
Copilot works as an extension in VS Code, JetBrains, Neovim, Visual Studio, and via Language Server in any editor. Cursor is VS Code only.

**2. Cross-repository search**
`#githubRepo owner/repo` lets Copilot semantically search any public GitHub repository without opening it locally. No Cursor equivalent.

**3. Zero-setup for GitHub repos**
For repositories already on GitHub, Copilot's index is built once on GitHub's infrastructure and instantly available to all team members. No per-user indexing time.

**4. LSP integration (Usages tool)**
Copilot's Usages tool integrates directly with VS Code's Language Server Protocol for precise symbol-level navigation (Go to Definition, Find All References). Cursor uses VS Code extension APIs for similar functionality but the LSP integration depth differs.

**5. Enterprise content exclusions**
Enterprise and Business plan admins can define content exclusions — specific files or patterns that Copilot will not include in responses, enforced server-side. Useful for legal/compliance requirements.

---

## 7. Privacy Comparison

This section was thin in the original document. Full detail from official sources:

### Cursor Privacy

✓ verified from `cursor.com/docs/agent/tools/search` and `cursor.com/blog/secure-codebase-indexing`:

- **Source code:** never stored on Cursor's servers. Code is held in memory during the embedding step, then discarded. Only the embedding vectors and obfuscated metadata are stored.
- **File paths:** encrypted (obfuscated) client-side before transmission. The directory hierarchy is preserved but filenames are masked with a secret key.
- **Embeddings:** stored in Turbopuffer. Deleted after 6 weeks of workspace inactivity.
- **Training:** Cursor does not publicly state whether your code or sessions are used for model training. The semsearch blog confirms agent session traces are used to train the embedding model — but these are aggregate behavioral traces, not your source code.
- **Privacy Mode:** 50% of users enable it. In Privacy Mode, code is only retained for the duration of the request.
- **Control:** `.cursorignore` excludes files from indexing; `.cursor/keys` lets you supply your own path encryption key.
- **Enterprise:** No self-hosted index option currently; all indexes are on Cursor's infrastructure (Turbopuffer, AWS).

### Copilot Privacy

✓ verified from GitHub official docs and April 2026 changelog:

**What is and isn't used for model training:**

| User type | Interaction data used for training? |
|---|---|
| Free, Pro, Pro+ | **Yes by default** — as of April 24, 2026. Can opt out in Settings > Copilot > Privacy |
| Business, Enterprise | **No** — never used for training |
| All tiers | **Indexed data (for semantic search)** — explicitly NOT used for training |

**What data is collected:**
- Inputs (your prompts), outputs (Copilot responses), code snippets, file names, repo structure, comments, user feedback
- May be shared with GitHub affiliates including **Microsoft** for AI/ML development
- NOT shared with third-party AI model providers

**Source code during active use:**
- Copilot processes your private repository code during active use
- This could be included in training data for Free/Pro/Pro+ users unless opted out
- For Business/Enterprise: not used for training regardless of opt-out status

**Enterprise content exclusions:**
- Admins can define content exclusions — specific files or patterns Copilot will not reference in responses
- Enforced server-side, not just client-side

**Summary verdict on privacy:**
Cursor has a stronger guarantee against source code storage (never stored in plaintext). Copilot has a stronger guarantee that indexed data won't be used for training (explicit policy, all tiers), but Free/Pro/Pro+ interaction data (including code snippets) is used for training unless opted out. Business and Enterprise users on both platforms have equivalent strong protections.

---

## 8. Cost Comparison

### Subscription cost (indexing included)

| Plan | Cursor | Copilot | Notes |
|---|---|---|---|
| Free / entry | None available | $0 (Free tier) | Copilot Free has limited completions |
| Individual | **$20/mo** (Pro) | **$10/mo** (Individual) | Copilot is half the price |
| Power | **$200/mo** (Ultra) | **$19/user/mo** (Business) | Different tier definitions |
| Enterprise | Not a separate tier | **$39/user/mo** (Enterprise) | SSO, audit logs, content exclusions |

Semantic indexing is included in every paid tier for both tools. No add-on fee for the index itself.

### Token cost at inference time

| Tool | Semantic search token cost | Billing model |
|---|---|---|
| **Cursor (non-Auto model)** | ~1,500 tokens per search call @ $0.25/M | Charged against your token rate |
| **Cursor (Auto model)** | ~1,500 tokens per search call | Absorbed in subscription; no charge |
| **Copilot** | ~injected chunks (size varies) | No per-token billing; included in subscription |

**Practical impact for a heavy agentic session (50 search calls):**
- Cursor (non-Auto): ~75,000 tokens from search alone → ~$0.019 in token rate charges
- Cursor (Auto): $0 additional
- Copilot: $0 additional

### Cost for the indexing infrastructure itself

| Tool | Infrastructure cost (to the company, passed to user) |
|---|---|
| Cursor | 95% cost reduction achieved via Turbopuffer. Cost is absorbed in subscription. |
| Copilot | GitHub-hosted index for GitHub repos costs GitHub nothing extra per user. Local index is on your machine. |

### Effective cost per developer for indexing capability

| Profile | Cursor | Copilot |
|---|---|---|
| Solo dev, GitHub repo, VS Code | $20/mo | $10/mo |
| Solo dev, local repo (non-GitHub) | $20/mo | $10/mo (local fallback index) |
| Team of 10, GitHub Enterprise | $200/mo total (Pro × 10) | $390/mo total (Enterprise × 10) |
| Team of 10, heavy agentic use | $200/mo + token overage (if non-Auto) | $190/mo flat |

**Cost verdict:** Copilot is consistently cheaper at the subscription level. Cursor's total cost advantage emerges only if the 31% task completion gap justifies the price difference — i.e., if developers complete complex multi-file tasks significantly faster with Cursor than with Copilot.

---

## 9. Quality and Cost Verdict

### On quality

The two tools are not directly comparable on "quality" because they measure different things:

- **Cursor's measurement:** agent outcome improvement with semantic search vs grep-only, on Cursor's own codebase benchmark. Average +12.5%; up to +23.5% on Composer.
- **Copilot's measurement:** retrieval quality improvement with their new embedding model vs their previous model. +37.6% — but this is Copilot vs. old Copilot, not Copilot vs. Cursor.

The only meaningful head-to-head data is from third-party studies:

**Where Cursor wins on quality:**
- Complex multi-file agentic tasks: **31% better task completion** (IBuidl.org, 2026)
- Regex search at scale: Instant Grep vs ripgrep — faster by eliminating file reads on monorepos
- AST-based chunking produces semantically coherent chunks that are never split mid-function; Copilot's 60-line sliding windows can split mid-function
- Embedding model trained on actual agentic retrieval quality (what the agent needed to complete tasks), not generic code similarity

**Where Copilot wins on quality:**
- Zero-setup for GitHub-hosted repos — index is already built when you arrive
- Multi-IDE quality parity: same embedding model and search infrastructure across VS Code, JetBrains, Neovim
- Cross-repo search: can semantically query repos not on your machine
- LSP Usages tool gives precise symbol-level navigation (Go to Definition, Find All References) that the semantic index can't provide

**For single-file inline completions:** the gap is likely negligible. Both use different approaches (Cursor: semantic index + AST chunks; Copilot: Jaccard-scored 60-line windows) but for simple completions, Copilot's approach is fast and effective.

**Quality verdict:**
> Cursor has a measurable quality edge for agentic, multi-file work on large codebases — confirmed by the 31% task completion gap and the architectural advantages (AST chunking, agent-trained embeddings, trigram grep). Copilot is quality-competitive for single-file work, code review, and teams already embedded in GitHub's ecosystem.

### On cost

> Copilot is cheaper at every subscription tier. Cursor is $20/mo individual vs Copilot's $10/mo. At scale (enterprise teams), Copilot Business at $19/user/mo vs Cursor Pro at $20/user/mo is roughly equivalent, but Copilot Enterprise at $39/user/mo includes features (content exclusions, audit logs, SSO) that Cursor doesn't offer as a bundled enterprise tier.

**The cost-quality trade-off in one sentence:** Cursor costs more and delivers meaningfully better results specifically for complex agentic work on large, non-GitHub-hosted codebases; Copilot costs less and delivers equivalent results for routine coding assistance, single-file work, and teams whose repos live on GitHub.

---

## 10. Open-Source Ecosystem: Adding Indexing to Tools That Lack It

Several open-source MCP servers emerged in early 2026 to add semantic indexing to tools that don't have it natively (Claude Code, Windsurf, OpenCode, etc.). These are relevant context for understanding the state of the art.

### CocoIndex Code
- AST-aware semantic search via MCP
- Claims 70% fewer tokens per turn and 80–90% cache hits on re-index
- Incremental processing — only changed files re-embedded
- 20+ programming languages
- Source: `cocoindex.io/cocoindex-code/`

### ctx-sys (david-franz/ctx-sys)
- Hybrid RAG: vector search + FTS5 keyword search + graph traversal
- Uses tree-sitter for AST parsing, Ollama for local embeddings
- Indexes code and markdown, serves 12 tools over MCP
- Fully local, no cloud dependency
- Works with Claude Desktop, Cursor, and any MCP client
- Source: `github.com/david-franz/ctx-sys` (created Feb 2026)

### opencode-codebase-index (zb1749)
- Semantic search in Rust + tree-sitter
- Branch-aware with git integration
- 20+ languages, incremental indexing
- Works as MCP server for Claude Code, Cursor, Windsurf
- Source: `github.com/zb1749/opencode-codebase-index` (created Feb 2026)

### Lumen (ory/lumen)
- 100% local with Ollama or LM Studio
- SQLite-vec backend, no external APIs
- Benchmarked at up to 39% cost reduction, 66% output token reduction
- Enterprise-ready (fully local for compliance)
- Source: `github.com/ory/lumen`

**What this tells us:** the community has validated that AST-based semantic indexing is reproducible outside proprietary systems. The core concepts — tree-sitter chunking, local vector embeddings, MCP integration — are well-understood and implementable. Cursor and Copilot's advantages lie in training data quality, scale, and integration depth, not in having access to an exclusive technique.

---

## 11. What Claude Desktop and Claude Code Actually Do

For completeness and to clarify the most common misconception:

### Claude Desktop

No codebase indexing of any kind. Claude Desktop is a chat interface with a large context window (1M tokens on Pro/Max).

**How it accesses code:**
- You paste files manually
- You use MCP tools you've configured (e.g., CocoIndex, ctx-sys from section 7)
- Without MCP: it only knows what you put in the conversation

There is no background index, no Merkle tree, no vector database, no AST chunking. The 1M token window is large, but it's passive — it holds what you give it, not what it found.

### Claude Code (CLI Agent)

No pre-built semantic index. Uses real-time file tools at query time:

| Tool | What it does |
|---|---|
| `Read` | Reads a specific file by path |
| `Grep` | Searches file content for patterns (ripgrep under the hood) |
| `Glob` | Finds files by name pattern |
| `Bash` | Runs shell commands including `find`, `git grep`, LSP queries |

This is **deterministic retrieval** — Claude Code finds exactly what you tell it to find, or what it can reason to look for. It doesn't have a pre-built semantic index to fall back on when it doesn't know where to look.

**Where this matters:** for tasks where the agent knows exactly what to search for, Claude Code's file tools are lean and precise. For tasks requiring semantic discovery — "find all the places we validate user input" without knowing the function name — it must reason its way to the right search terms or explore broadly via grep, which is slower and less reliable than vector-based semantic retrieval.

**Token efficiency:** Claude Code uses approximately **5.5× fewer tokens than Cursor** on identical tasks (~33K vs ~188K tokens per Zapier/AIDesigner 2026 benchmarks). This is because Claude Code does targeted file reads rather than the broad context injection Cursor performs (open files, recently viewed files, rules, MCP schemas, full conversation history).

**MCP can add indexing:** if you configure a semantic index MCP server (ctx-sys, CocoIndex, Lumen), Claude Code/Desktop gains semantic search capability. But this requires explicit setup — it's not built in.

---

## 12. Sources

### Cursor Official

- **Cursor Blog — Secure Codebase Indexing** — `cursor.com/blog/secure-codebase-indexing` — Merkle tree architecture, simhash cross-team index reuse, privacy model, time-to-first-query data. Primary technical source.
- **Cursor Blog — Improving Agent with Semantic Search** — `cursor.com/blog/semsearch` — Custom embedding model training methodology, Cursor Context Bench evaluation, A/B test results, model accuracy improvements. Primary technical source.
- **Cursor Blog — Fast Regex Search: Indexing Text for Agent Tools** — `cursor.com/blog/fast-regex-search` — Instant Grep trigram index architecture, inverted index theory, n-gram decomposition of regex patterns. Primary technical source.
- **Cursor Docs — Semantic & Agentic Search** — `cursor.com/docs/agent/tools/search` — How the agent combines semantic search, grep, and the Explore subagent. Official documentation.

### Cursor Third-Party Analysis

- **Turbopuffer — Cursor case study** — `turbopuffer.com/customers/cursor` — Scale data (1T+ vectors, 80M+ namespaces), latency figures, cost reduction metrics, copy_from_namespace usage. ✓ verified: primary source (Turbopuffer is Cursor's vendor).
- **Kenneth Leung — "How Cursor Actually Indexes Your Codebase"** — `towardsdatascience.com/how-cursor-actually-indexes-your-codebase/` — Towards Data Science, Jan 2026. Detailed RAG pipeline walkthrough with Python code examples, Chonkie chunking demo, AST diagrams.
- **Praveen Kumar — "I Reverse-Engineered Cursor, This Is How It Understands Your Entire Codebase"** — Medium, 2026. Reverse-engineering analysis of Cursor's indexing pipeline.
- **Thinking Through Code — "I Rebuilt Cursor's Merkle Tree Index in 200 Lines of TypeScript"** — Medium, March 2026. Working TypeScript reimplementation of Cursor's Merkle tree indexing.

### GitHub Copilot Official

- **GitHub Docs — Indexing repositories for GitHub Copilot** — `docs.github.com/copilot/concepts/indexing-repositories-for-copilot-chat` — Index sources, triggers, timing, content exclusions. Official documentation. ✓ verified.
- **VS Code Docs — How Copilot understands your workspace** — `code.visualstudio.com/docs/copilot/reference/workspace-context` — Full workspace context model, search tools, semantic index sources. Official Microsoft documentation. ✓ verified.
- **GitHub Changelog — Instant semantic code search indexing now GA** — `github.blog/changelog/2025-03-12` — GA announcement, timing improvements. ✓ verified.
- **GitHub Changelog — Copilot coding agent works faster with semantic code search** — `github.blog/changelog/2026-03-17` — Agent semantic search integration, 2% speed improvement. ✓ verified.
- **Microsoft Research — GitHub Copilot Gets Smarter at Finding Your Code** — `microsoft.com/en-us/research/` — New embedding model details: MRL, InfoNCE, hard negatives, performance metrics. ✓ verified primary source.

### Copilot Third-Party Analysis

- **InfoQ — GitHub Introduces New Embedding Model to Improve Code Search and Context** — `infoq.com/news/2025/10/github-embedding-model/` — Oct 2025. Technical analysis of the embedding model announcement.
- **Capabl — Elevating Code Retrieval: Deep Dive into the New Copilot Embedding Model** — `capabl.in/blog/` — 2025. Full technical walkthrough of MRL, InfoNCE, training data composition, benchmark comparison vs VoyageCode3/Nomic/Jina.
- **iamabdullah — GitHub Copilot: Under the Hood and Into Production** — Medium, Feb 2026. Implementation analysis including Jaccard similarity for completion-time context assembly.

### Comparative Studies

- **IBuidl.org — Developer Tools 2026: Cursor vs GitHub Copilot vs Windsurf** — `ibuidl.org/blog/developer-tools-2026-cursor-copilot-20260310` — 31% task completion gap, attribution to indexing depth.
- **Developer Toolkit AI — Search and Indexing Strategies** — `developertoolkit.ai/en/shared-workflow/context-management/codebase-indexing/` — Architecture comparison: Cursor local embeddings vs Copilot file + neighbor context.
- **StackSheriff — GitHub Copilot vs Cursor 2026** — `stacksheriff.com/ai-tools/github-copilot-vs-cursor/` — Practical capability comparison.

### Open-Source Ecosystem

- **CocoIndex Code** — `cocoindex.io/cocoindex-code/`
- **ctx-sys (david-franz)** — `github.com/david-franz/ctx-sys`
- **opencode-codebase-index (zb1749)** — `github.com/zb1749/opencode-codebase-index`
- **Lumen (ory)** — `github.com/ory/lumen`

### Added in Review Pass

- **Cursor Blog — Dynamic Context Discovery** — `cursor.com/blog/dynamic-context-discovery` (Jan 2026) — Lazy-loading MCP tools, terminal-as-files, skill discovery, 46.9% token reduction A/B test result. ✓ verified primary source.
- **Yasith Rashan — "How GitHub Copilot Knows Your Code: Inside Its Indexing Magic"** — Medium, 2025. Documents 60-line sliding window chunking and Jaccard similarity scoring for Copilot completions.
- **GitHub Changelog — Updates to Copilot interaction data usage policy** — `github.blog/news-insights/product-news/updates-to-github-copilot-interaction-data-usage-policy/` — Training data policy: Free/Pro/Pro+ opt-out; Business/Enterprise exempt; indexed data not used for training. ✓ verified.
- **Cursor Docs — Token Rate** — `cursor.com/help/models-and-usage/token-rate` — $0.25/M tokens on non-Auto models. ✓ verified.
- **kanishka-namdeo/instructify — COST-OPTIMIZATION.md** — `github.com/kanishka-namdeo/instructify` — Estimated token costs per operation type: semantic search ~1,500 tokens, file read ~500 tokens.
- **Fotis Adamakis — "Understanding Cursor Pricing"** — Better Programming (Medium), March 2026. Context injection token overhead analysis.
- **Yasith Rashan / gist dsandor — Overview of AI Coding Tools Behind-the-Scenes** — `gist.github.com/dsandor/1e05d630f80611a995d22da2dddca2c2` — Copilot tiered search strategy, workspace size thresholds.
