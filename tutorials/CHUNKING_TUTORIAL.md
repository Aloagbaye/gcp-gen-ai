# Comprehensive Guide to Text Chunking for RAG Systems

## Table of Contents

1. [Introduction: What is Chunking and Why Does It Matter?](#introduction)
2. [Understanding Tokens](#understanding-tokens)
3. [The Fundamental Trade-offs](#fundamental-trade-offs)
4. [Chunking Strategies Explained](#chunking-strategies)
5. [Chunk Size vs. LLM Context Windows](#chunk-size-vs-llm-context-windows)
6. [When to Increase Chunk Size](#when-to-increase-chunk-size)
7. [When to Reduce Chunk Size](#when-to-reduce-chunk-size)
8. [Model-Specific Recommendations](#model-specific-recommendations)
9. [Advanced Chunking Techniques](#advanced-chunking-techniques)
10. [Implementation Guide](#implementation-guide)
11. [Evaluation and Optimization](#evaluation-and-optimization)

---

## Introduction: What is Chunking and Why Does It Matter?

### What is Chunking?

**Text chunking** is the process of breaking down large documents into smaller, manageable pieces (chunks) for processing in RAG systems. Instead of embedding or retrieving entire documents, we split them into semantically meaningful segments.

### Why Chunk?

**1. LLM Context Window Limits**
- Every LLM has a maximum number of tokens it can process in a single request
- Even with large context windows (128K+ tokens), you can't fit everything
- Chunking allows selective retrieval of relevant portions

**2. Precision in Retrieval**
- Smaller chunks = more precise retrieval
- Vector search finds the exact relevant section, not entire documents
- Reduces noise from irrelevant parts of long documents

**3. Cost Optimization**
- Embedding costs scale with token count
- Smaller chunks = more embeddings, but more precise = fewer retrieved chunks needed
- LLM generation costs: less context = lower token usage

**4. Semantic Coherence**
- Well-chunked text maintains semantic meaning
- Each chunk should be a complete thought or topic
- Better embeddings = better retrieval

### The Chunking Dilemma

**Too Small Chunks**:
- ❌ Lose context and meaning
- ❌ Fragmented information
- ❌ More chunks to manage
- ❌ Higher embedding costs
- ✅ More precise retrieval
- ✅ Better for specific fact extraction

**Too Large Chunks**:
- ❌ Less precise retrieval
- ❌ More irrelevant content in context
- ❌ Harder to pinpoint exact information
- ✅ Better context preservation
- ✅ Better for complex reasoning
- ✅ Fewer chunks to manage

**The Sweet Spot**: Balance between precision and context preservation.

---

## Understanding Tokens

### What is a Token?

A **token** is the fundamental unit of text that LLMs process. It's not exactly a word or a character, but rather a piece of text that the model's tokenizer breaks your input into.

### Token vs. Word vs. Character

**Approximate Conversions** (English text):
- **1 token ≈ 0.75 words** (on average)
- **1 token ≈ 4 characters** (on average)
- **100 tokens ≈ 75 words ≈ 1 paragraph**

**Examples**:
```
Text: "The quick brown fox jumps over the lazy dog."
Tokens: ~9 tokens (varies by tokenizer)
Words: 9 words
Characters: 44 characters

Text: "Machine learning is a subset of artificial intelligence."
Tokens: ~10 tokens
Words: 10 words
Characters: 58 characters
```

### Why Tokens Matter

**1. LLM Processing**
- LLMs process text as sequences of tokens
- Context windows are measured in tokens, not words
- Token limits determine how much text you can send to a model

**2. Cost Calculation**
- Most LLM APIs charge per token (input + output)
- Embedding APIs also charge per token
- Accurate token counting = accurate cost estimation

**3. Chunking Precision**
- Chunk sizes are specified in tokens for accuracy
- Word counts vary (short words vs. long words)
- Token counts are consistent across different text types

### Tokenization Differences

**Different tokenizers produce different counts**:

```
Text: "Hello, world!"

GPT models (tiktoken):
- "Hello" = 1 token
- "," = 1 token  
- " world" = 1 token
- "!" = 1 token
Total: ~4 tokens

Some other models:
- May split "Hello" into "Hel" + "lo"
- May combine punctuation differently
Total: Could be 3-6 tokens
```

**Key Point**: Always use the tokenizer that matches your target LLM model for accurate counting.

### Counting Tokens in Practice

**Python Example** (using tiktoken for GPT models):
```python
import tiktoken

# Get encoding for specific model
encoding = tiktoken.encoding_for_model("gpt-4")

# Count tokens
text = "Your text here"
tokens = encoding.encode(text)
token_count = len(tokens)

print(f"Text: {text}")
print(f"Tokens: {token_count}")
```

**For Vertex AI / Gemini**:
```python
# Vertex AI uses different tokenization
# Use their API or approximate with character count
# Rough estimate: characters / 4 ≈ tokens
```

**Common Token Counts**:
- **1 sentence**: ~15-25 tokens
- **1 paragraph**: ~100-150 tokens
- **1 page (single-spaced)**: ~500-800 tokens
- **1 page (double-spaced)**: ~250-400 tokens

### Token Limits by Model

Different models have different token limits:

| Model | Input Tokens | Output Tokens | Total Context |
|-------|--------------|---------------|---------------|
| GPT-3.5-turbo | 4,096 | 4,096 | 4,096 |
| GPT-4 | 8,192 | 8,192 | 8,192 |
| GPT-4-turbo | 128,000 | 4,096 | 128,000 |
| Gemini 1.5 Pro | 1,000,000 | 8,192 | 1,000,000 |
| Claude 3 Opus | 200,000 | 4,096 | 200,000 |

**Important**: When chunking, you need to account for:
- System prompt tokens
- User query tokens
- Retrieved chunk tokens
- Response tokens (reserved)

### Practical Token Estimation

**Quick Estimates** (for planning):
- **Short email**: 50-100 tokens
- **Blog post**: 500-2,000 tokens
- **Research paper**: 5,000-15,000 tokens
- **Book chapter**: 10,000-30,000 tokens

**For Chunking**:
- Always count tokens, not words
- Use the tokenizer matching your target model
- Leave safety margin (10-20%) for variations
- Account for overlap when calculating total tokens

---

## The Fundamental Trade-offs

### 1. Precision vs. Context

```
Small Chunks (200-400 tokens):
Query: "What is the revenue in Q3?"
Retrieved: "Q3 revenue was $5.2M, up 15% from Q2."
✅ Precise answer
❌ Missing context: What was Q2 revenue? What caused the increase?

Large Chunks (1000-2000 tokens):
Query: "What is the revenue in Q3?"
Retrieved: [Entire financial report section with Q1, Q2, Q3, Q4 data, analysis, trends]
✅ Complete context
❌ More noise, harder to find exact answer
```

### 2. Retrieval Quality vs. Generation Quality

**Small Chunks**:
- Better retrieval: Vector search finds exact relevant section
- Weaker generation: LLM may lack context for complex reasoning

**Large Chunks**:
- Weaker retrieval: Vector search may retrieve partially relevant chunks
- Better generation: LLM has more context for comprehensive answers

### 3. Cost vs. Performance

**Small Chunks**:
- More embeddings to generate (higher ingestion cost)
- More chunks to retrieve (higher query cost)
- But: More precise = fewer chunks needed per query

**Large Chunks**:
- Fewer embeddings (lower ingestion cost)
- Fewer chunks to retrieve
- But: Less precise = may need more chunks to cover query

### 4. Overlap: The Safety Net

**Overlap** prevents information loss at chunk boundaries:

```
Without Overlap:
Chunk 1: "...the company announced a new product launch in Q3. The product features..."
Chunk 2: "...advanced AI capabilities and improved user experience. Sales projections..."

Problem: "The product features" is cut off from "advanced AI capabilities"

With Overlap (100 tokens):
Chunk 1: "...the company announced a new product launch in Q3. The product features advanced AI capabilities..."
Chunk 2: "...The product features advanced AI capabilities and improved user experience. Sales projections..."

✅ Information preserved across boundaries
```

**Overlap Guidelines**:
- **10-20% of chunk size**: Standard recommendation
- **Small chunks (200-400 tokens)**: 50-100 token overlap
- **Medium chunks (500-800 tokens)**: 80-150 token overlap
- **Large chunks (1000-2000 tokens)**: 150-300 token overlap

---

## Chunking Strategies Explained

### 1. Fixed-Size Chunking

**Simplest approach**: Divide text into equal-sized chunks.

```python
def fixed_size_chunk(text: str, chunk_size: int = 500, overlap: int = 50):
    """Split text into fixed-size chunks."""
    tokens = tokenize(text)
    chunks = []
    start = 0
    
    while start < len(tokens):
        end = min(start + chunk_size, len(tokens))
        chunk_text = detokenize(tokens[start:end])
        chunks.append({
            "text": chunk_text,
            "start": start,
            "end": end
        })
        start = end - overlap
    
    return chunks
```

**Pros**:
- Simple to implement
- Predictable chunk sizes
- Easy to manage

**Cons**:
- May split sentences/paragraphs mid-thought
- Ignores semantic boundaries
- Can break context

**Use When**:
- Uniform document structure
- Simple use cases
- Quick prototyping

### 2. Sentence-Aware Chunking

**Respects sentence boundaries**: Never splits mid-sentence.

```python
import re

def sentence_aware_chunk(text: str, chunk_size: int = 500, overlap: int = 50):
    """Chunk by sentences, respecting boundaries."""
    # Split into sentences
    sentences = re.split(r'(?<=[.!?])\s+', text)
    
    chunks = []
    current_chunk = []
    current_size = 0
    
    for sentence in sentences:
        sentence_tokens = count_tokens(sentence)
        
        if current_size + sentence_tokens > chunk_size and current_chunk:
            # Save current chunk
            chunks.append({
                "text": " ".join(current_chunk),
                "size": current_size
            })
            
            # Start new chunk with overlap
            overlap_sentences = current_chunk[-overlap//50:]  # Approximate
            current_chunk = overlap_sentences + [sentence]
            current_size = sum(count_tokens(s) for s in current_chunk)
        else:
            current_chunk.append(sentence)
            current_size += sentence_tokens
    
    # Add final chunk
    if current_chunk:
        chunks.append({
            "text": " ".join(current_chunk),
            "size": current_size
        })
    
    return chunks
```

**Pros**:
- Preserves sentence integrity
- Better semantic units
- More natural boundaries

**Cons**:
- Variable chunk sizes
- May create very small or very large chunks
- Still ignores paragraph/topic boundaries

**Use When**:
- General-purpose RAG
- Narrative text
- Documents with clear sentence structure

### 3. Paragraph-Aware Chunking

**Respects paragraph boundaries**: Chunks at paragraph level.

```python
def paragraph_aware_chunk(text: str, chunk_size: int = 500, overlap: int = 50):
    """Chunk by paragraphs."""
    paragraphs = text.split('\n\n')  # Double newline = paragraph
    
    chunks = []
    current_chunk = []
    current_size = 0
    
    for para in paragraphs:
        para_tokens = count_tokens(para)
        
        if current_size + para_tokens > chunk_size and current_chunk:
            chunks.append({
                "text": "\n\n".join(current_chunk),
                "size": current_size
            })
            
            # Overlap: keep last paragraph
            current_chunk = [current_chunk[-1], para] if current_chunk else [para]
            current_size = sum(count_tokens(p) for p in current_chunk)
        else:
            current_chunk.append(para)
            current_size += para_tokens
    
    if current_chunk:
        chunks.append({
            "text": "\n\n".join(current_chunk),
            "size": current_size
        })
    
    return chunks
```

**Pros**:
- Preserves topic coherence
- Natural document structure
- Better for structured documents

**Cons**:
- Paragraphs vary greatly in size
- May need to split very long paragraphs
- Less granular than sentence-level

**Use When**:
- Structured documents (reports, articles)
- Documents with clear paragraph structure
- Topic-based retrieval

### 4. Semantic Chunking

**Uses embeddings to find semantic boundaries**: Groups similar content together.

```python
from sentence_transformers import SentenceTransformer
import numpy as np

def semantic_chunk(text: str, chunk_size: int = 500, similarity_threshold: float = 0.7):
    """Chunk based on semantic similarity."""
    sentences = split_sentences(text)
    model = SentenceTransformer('all-MiniLM-L6-v2')
    
    # Embed all sentences
    embeddings = model.encode(sentences)
    
    chunks = []
    current_chunk = [sentences[0]]
    current_embedding = embeddings[0]
    
    for i in range(1, len(sentences)):
        # Check similarity with current chunk
        similarity = np.dot(current_embedding, embeddings[i]) / (
            np.linalg.norm(current_embedding) * np.linalg.norm(embeddings[i])
        )
        
        current_tokens = sum(count_tokens(s) for s in current_chunk)
        
        if similarity < similarity_threshold or current_tokens >= chunk_size:
            # Start new chunk
            chunks.append({
                "text": " ".join(current_chunk),
                "size": current_tokens
            })
            current_chunk = [sentences[i]]
            current_embedding = embeddings[i]
        else:
            # Add to current chunk
            current_chunk.append(sentences[i])
            # Update chunk embedding (average)
            current_embedding = (current_embedding * (len(current_chunk) - 1) + embeddings[i]) / len(current_chunk)
    
    if current_chunk:
        chunks.append({
            "text": " ".join(current_chunk),
            "size": sum(count_tokens(s) for s in current_chunk)
        })
    
    return chunks
```

**Pros**:
- Groups semantically related content
- Natural topic boundaries
- Better for complex documents

**Cons**:
- More computationally expensive
- Requires embedding model
- Variable chunk sizes

**Use When**:
- Complex documents with multiple topics
- Research papers, technical documentation
- When semantic coherence is critical

### 5. Recursive Chunking

**Hierarchical approach**: Try larger chunks first, split if too large.

```python
def recursive_chunk(text: str, chunk_size: int = 500, min_chunk_size: int = 100):
    """Recursively split text into chunks."""
    if count_tokens(text) <= chunk_size:
        return [{"text": text, "size": count_tokens(text)}]
    
    # Try splitting by paragraphs
    paragraphs = text.split('\n\n')
    if len(paragraphs) > 1:
        chunks = []
        for para in paragraphs:
            chunks.extend(recursive_chunk(para, chunk_size, min_chunk_size))
        return chunks
    
    # Try splitting by sentences
    sentences = split_sentences(text)
    if len(sentences) > 1:
        chunks = []
        current = []
        current_size = 0
        
        for sent in sentences:
            sent_size = count_tokens(sent)
            if current_size + sent_size > chunk_size and current:
                chunks.extend(recursive_chunk(" ".join(current), chunk_size, min_chunk_size))
                current = [sent]
                current_size = sent_size
            else:
                current.append(sent)
                current_size += sent_size
        
        if current:
            chunks.extend(recursive_chunk(" ".join(current), chunk_size, min_chunk_size))
        return chunks
    
    # Last resort: fixed-size split
    return fixed_size_chunk(text, chunk_size)
```

**Pros**:
- Adapts to document structure
- Handles various document types
- Respects natural boundaries when possible

**Cons**:
- More complex implementation
- Can be slower
- Variable chunk sizes

**Use When**:
- Mixed document types
- Unknown document structure
- Production systems handling diverse content

---

## Chunk Size vs. LLM Context Windows

### Understanding Context Windows

**Context window** = Maximum tokens an LLM can process in a single request (input + output).

**Token Counts** (approximate):
- 1 token ≈ 0.75 words (English)
- 1 token ≈ 4 characters
- 100 tokens ≈ 75 words ≈ 1 paragraph

### LLM Context Window Comparison

| Model | Context Window | Recommended Chunk Size | Max Chunks (Top-K=8) |
|-------|---------------|------------------------|---------------------|
| **GPT-3.5-turbo** | 4,096 tokens | 200-400 tokens | 8-16 chunks |
| **GPT-4** | 8,192 tokens | 300-600 tokens | 10-20 chunks |
| **GPT-4-turbo** | 128,000 tokens | 500-2,000 tokens | 50-200 chunks |
| **Claude 3 Opus** | 200,000 tokens | 1,000-3,000 tokens | 60-200 chunks |
| **Gemini 1.5 Pro** | 1,000,000 tokens | 2,000-5,000 tokens | 150-400 chunks |
| **Gemini 1.5 Flash** | 1,000,000 tokens | 1,000-3,000 tokens | 300-800 chunks |

### Context Window Budget Allocation

**Typical RAG Request Structure**:
```
Total Context = System Prompt + User Query + Retrieved Chunks + Response

Example (GPT-4, 8K context):
- System Prompt: ~200 tokens
- User Query: ~50 tokens
- Response: ~500 tokens (reserved)
- Available for Chunks: ~7,250 tokens
- With Top-K=8: ~900 tokens per chunk (max)
- Recommended: 500-800 tokens per chunk (safety margin)
```

### Chunk Size Formula

```
Optimal Chunk Size = (Context Window - System Prompt - Query - Response Buffer) / Top-K / Safety Factor

Where:
- Safety Factor: 0.7-0.8 (leave room for variations)
- Top-K: Number of chunks to retrieve (typically 5-10)

Example (GPT-4, Top-K=8):
= (8,192 - 200 - 50 - 500) / 8 / 0.75
= 7,442 / 8 / 0.75
= ~1,240 tokens per chunk (max)
= Recommended: 600-800 tokens (balanced)
```

---

## When to Increase Chunk Size

### Scenario 1: Large Context Window Models

**Models**: Gemini 1.5 Pro (1M tokens), Claude 3 Opus (200K tokens), GPT-4-turbo (128K tokens)

**Why Increase**:
- ✅ Can fit more context
- ✅ Better for complex reasoning
- ✅ Preserves document structure
- ✅ Fewer chunks to manage

**Recommended Chunk Sizes**:
- **Gemini 1.5 Pro**: 2,000-5,000 tokens
- **Claude 3 Opus**: 1,500-3,000 tokens
- **GPT-4-turbo**: 1,000-2,000 tokens

**Example**:
```python
# For Gemini 1.5 Pro with 1M context window
chunk_size = 3000  # tokens
overlap = 300      # tokens (10%)

# Can retrieve 200+ chunks if needed
top_k = 50  # More chunks = better context
```

### Scenario 2: Complex Reasoning Tasks

**Tasks**: Multi-step reasoning, analysis, synthesis

**Why Increase**:
- ✅ Need complete context for reasoning
- ✅ Relationships between concepts matter
- ✅ Better for "why" and "how" questions

**Example Query**: "Analyze the relationship between Q3 revenue growth and the product launch strategy."

**Small Chunks (500 tokens)**:
```
Chunk 1: "Q3 revenue was $5.2M, up 15% from Q2."
Chunk 2: "The new product launched in August."
Chunk 3: "Marketing spend increased 20% in Q3."
```
❌ LLM must connect information across chunks

**Large Chunks (2000 tokens)**:
```
Chunk 1: [Complete Q3 financial section with revenue, product launch details, marketing strategy, analysis]
```
✅ LLM has complete context for analysis

**Recommended**: 1,500-3,000 tokens for complex reasoning

### Scenario 3: Structured Documents

**Documents**: Technical specifications, legal documents, research papers

**Why Increase**:
- ✅ Sections are naturally long
- ✅ Context within section is critical
- ✅ Breaking sections loses meaning

**Example**: Technical Specification
```
Section: "API Authentication"
- Overview (200 tokens)
- OAuth 2.0 Flow (800 tokens)
- Token Management (600 tokens)
- Error Handling (400 tokens)
Total: 2,000 tokens
```

**Small Chunks (500 tokens)**: Splits OAuth flow across chunks ❌
**Large Chunks (2000 tokens)**: Keeps entire section together ✅

**Recommended**: 1,500-2,500 tokens for structured documents

### Scenario 4: Narrative/Story Content

**Content**: Novels, articles, blog posts with narrative flow

**Why Increase**:
- ✅ Narrative coherence matters
- ✅ Context builds across paragraphs
- ✅ Breaking narrative loses flow

**Recommended**: 1,000-2,000 tokens for narrative content

### Scenario 5: Code Documentation

**Content**: Code examples with explanations, API documentation

**Why Increase**:
- ✅ Code + explanation should stay together
- ✅ Examples need full context
- ✅ Breaking code blocks is problematic

**Example**:
```python
# Function definition (50 tokens)
def process_data(data):
    # Explanation of algorithm (300 tokens)
    # Code implementation (200 tokens)
    # Usage examples (400 tokens)
    # Edge cases (300 tokens)
Total: 1,250 tokens
```

**Recommended**: 1,000-2,000 tokens for code documentation

---

## When to Reduce Chunk Size

### Scenario 1: Small Context Window Models

**Models**: GPT-3.5-turbo (4K), older models (2K-4K)

**Why Reduce**:
- ✅ Limited context budget
- ✅ Need to fit multiple chunks
- ✅ Precision more important than context

**Recommended Chunk Sizes**:
- **GPT-3.5-turbo (4K)**: 200-400 tokens
- **GPT-3.5 (2K)**: 150-300 tokens
- **Older models**: 100-250 tokens

**Example**:
```python
# For GPT-3.5-turbo with 4K context
chunk_size = 300  # tokens
overlap = 50      # tokens
top_k = 8         # chunks
# Total: ~2,400 tokens (leaves room for prompt + response)
```

### Scenario 2: Fact Extraction Tasks

**Tasks**: "What is X?", "When did Y happen?", "Who is Z?"

**Why Reduce**:
- ✅ Need precise, specific answers
- ✅ Less context needed
- ✅ Smaller chunks = more precise retrieval

**Example Query**: "What is the company's revenue in Q3?"

**Large Chunks (2000 tokens)**:
```
Retrieved: [Entire 10-page financial report]
- Contains Q1, Q2, Q3, Q4 data
- Contains analysis, projections, comparisons
- LLM must find Q3 revenue among all data
```

**Small Chunks (400 tokens)**:
```
Retrieved: "Q3 2024 Financial Results: Revenue was $5.2M, up 15% from Q2."
- Precise answer
- Minimal noise
```

**Recommended**: 300-500 tokens for fact extraction

### Scenario 3: High Precision Requirements

**Use Cases**: Legal documents, medical records, financial data

**Why Reduce**:
- ✅ Accuracy is critical
- ✅ Need exact citations
- ✅ Less room for error

**Example**: Legal Contract
```
Query: "What is the termination clause?"
Small Chunk (400 tokens): Exact clause text ✅
Large Chunk (2000 tokens): Entire contract section, may include irrelevant clauses ❌
```

**Recommended**: 300-600 tokens for high-precision tasks

### Scenario 4: Conversational RAG

**Use Cases**: Chatbots, Q&A systems with follow-up questions

**Why Reduce**:
- ✅ Need to retrieve specific information quickly
- ✅ Multiple turns in conversation
- ✅ Context accumulates across turns

**Recommended**: 300-500 tokens for conversational systems

### Scenario 5: Real-Time/Low-Latency Systems

**Constraints**: Fast response times, limited processing

**Why Reduce**:
- ✅ Fewer tokens to process = faster
- ✅ Less embedding computation
- ✅ Faster vector search

**Trade-off**: May need more chunks, but each is faster to process

**Recommended**: 300-600 tokens for low-latency systems

---

## Model-Specific Recommendations

### GPT-3.5-turbo (4,096 tokens)

**Context Budget**:
- System: 200 tokens
- Query: 50 tokens
- Response: 500 tokens
- Available: ~3,300 tokens
- With Top-K=8: ~400 tokens per chunk

**Recommended Chunk Size**: **200-400 tokens**
- Small chunks for precision
- Overlap: 40-80 tokens (10-20%)
- Top-K: 5-8 chunks

**Best For**:
- Fact extraction
- Simple Q&A
- Cost-sensitive applications

**Example**:
```python
chunk_config = {
    "chunk_size": 300,
    "overlap": 60,
    "strategy": "sentence_aware",
    "top_k": 8
}
```

### GPT-4 (8,192 tokens)

**Context Budget**:
- Available: ~7,400 tokens
- With Top-K=8: ~900 tokens per chunk

**Recommended Chunk Size**: **500-800 tokens**
- Balanced precision and context
- Overlap: 80-150 tokens (10-20%)
- Top-K: 8-10 chunks

**Best For**:
- General-purpose RAG
- Analysis tasks
- Mixed query types

**Example**:
```python
chunk_config = {
    "chunk_size": 600,
    "overlap": 100,
    "strategy": "paragraph_aware",
    "top_k": 8
}
```

### GPT-4-turbo (128,000 tokens)

**Context Budget**:
- Available: ~127,000 tokens
- With Top-K=20: ~6,000 tokens per chunk (theoretical max)
- Practical: 1,000-2,000 tokens per chunk

**Recommended Chunk Size**: **1,000-2,000 tokens**
- Large chunks for context preservation
- Overlap: 150-300 tokens (10-15%)
- Top-K: 15-25 chunks

**Best For**:
- Complex reasoning
- Long-form analysis
- Multi-document synthesis

**Example**:
```python
chunk_config = {
    "chunk_size": 1500,
    "overlap": 200,
    "strategy": "semantic",
    "top_k": 20
}
```

### Gemini 1.5 Pro (1,000,000 tokens)

**Context Budget**:
- Massive context window
- Can fit entire books
- Practical limit: processing time and cost

**Recommended Chunk Size**: **2,000-5,000 tokens**
- Very large chunks
- Overlap: 300-500 tokens (10%)
- Top-K: 30-50 chunks (or more)

**Best For**:
- Extremely long documents
- Research papers
- Comprehensive analysis
- Multi-chapter books

**Example**:
```python
chunk_config = {
    "chunk_size": 3000,
    "overlap": 300,
    "strategy": "semantic",
    "top_k": 40
}
```

### Gemini 1.5 Flash (1,000,000 tokens)

**Context Budget**: Same as Pro, but faster/cheaper

**Recommended Chunk Size**: **1,000-3,000 tokens**
- Large chunks, but slightly smaller than Pro
- Optimized for speed
- Overlap: 150-300 tokens
- Top-K: 20-40 chunks

**Best For**:
- Fast responses with large context
- Cost-effective large-context RAG
- Real-time applications needing context

**Example**:
```python
chunk_config = {
    "chunk_size": 2000,
    "overlap": 200,
    "strategy": "paragraph_aware",
    "top_k": 30
}
```

### Claude 3 Opus (200,000 tokens)

**Context Budget**:
- Very large context window
- Excellent reasoning capabilities

**Recommended Chunk Size**: **1,500-3,000 tokens**
- Large chunks for complex reasoning
- Overlap: 200-400 tokens
- Top-K: 20-40 chunks

**Best For**:
- Complex analysis
- Multi-step reasoning
- Long-form content generation

**Example**:
```python
chunk_config = {
    "chunk_size": 2500,
    "overlap": 300,
    "strategy": "semantic",
    "top_k": 25
}
```

### Summary Table

| Model | Context | Chunk Size | Overlap | Top-K | Use Case |
|-------|---------|------------|---------|-------|----------|
| GPT-3.5-turbo | 4K | 200-400 | 40-80 | 5-8 | Fact extraction, simple Q&A |
| GPT-4 | 8K | 500-800 | 80-150 | 8-10 | General RAG, analysis |
| GPT-4-turbo | 128K | 1,000-2,000 | 150-300 | 15-25 | Complex reasoning |
| Gemini 1.5 Flash | 1M | 1,000-3,000 | 150-300 | 20-40 | Fast large-context |
| Gemini 1.5 Pro | 1M | 2,000-5,000 | 300-500 | 30-50 | Research, long docs |
| Claude 3 Opus | 200K | 1,500-3,000 | 200-400 | 20-40 | Complex analysis |

---

## Advanced Chunking Techniques

### 1. Hierarchical Chunking

**Concept**: Create chunks at multiple levels (document → section → paragraph → sentence).

```python
class HierarchicalChunk:
    def __init__(self, text, level, parent=None):
        self.text = text
        self.level = level  # 0=document, 1=section, 2=paragraph, 3=sentence
        self.parent = parent
        self.children = []
        self.embedding = None

def hierarchical_chunk(document):
    """Create multi-level chunk hierarchy."""
    # Level 0: Document
    doc_chunk = HierarchicalChunk(document.text, level=0)
    
    # Level 1: Sections
    sections = split_sections(document.text)
    for section in sections:
        section_chunk = HierarchicalChunk(section, level=1, parent=doc_chunk)
        doc_chunk.children.append(section_chunk)
        
        # Level 2: Paragraphs
        paragraphs = split_paragraphs(section)
        for para in paragraphs:
            para_chunk = HierarchicalChunk(para, level=2, parent=section_chunk)
            section_chunk.children.append(para_chunk)
    
    return doc_chunk
```

**Benefits**:
- Retrieve at appropriate granularity
- Can expand to parent/child chunks
- Better for structured documents

### 2. Sliding Window with Metadata

**Concept**: Overlapping chunks with rich metadata for better retrieval.

```python
def sliding_window_chunk(text, window_size=500, step_size=400):
    """Sliding window with metadata enrichment."""
    chunks = []
    sentences = split_sentences(text)
    
    start_idx = 0
    while start_idx < len(sentences):
        end_idx = min(start_idx + window_size, len(sentences))
        window_sentences = sentences[start_idx:end_idx]
        
        chunk_text = " ".join(window_sentences)
        
        # Enrich with metadata
        chunk = {
            "text": chunk_text,
            "start_sentence": start_idx,
            "end_sentence": end_idx,
            "token_count": count_tokens(chunk_text),
            "entities": extract_entities(chunk_text),
            "keywords": extract_keywords(chunk_text),
            "summary": summarize(chunk_text)  # Optional
        }
        
        chunks.append(chunk)
        start_idx += step_size  # Overlap = window_size - step_size
    
    return chunks
```

### 3. Content-Aware Chunking

**Concept**: Adjust chunk size based on content type.

```python
def content_aware_chunk(text, content_type):
    """Adjust chunking based on content type."""
    if content_type == "code":
        return code_chunk(text, chunk_size=800)  # Code needs more context
    elif content_type == "table":
        return table_chunk(text, chunk_size=600)  # Tables are structured
    elif content_type == "narrative":
        return narrative_chunk(text, chunk_size=1000)  # Narrative needs flow
    elif content_type == "technical":
        return technical_chunk(text, chunk_size=1200)  # Technical docs need context
    else:
        return default_chunk(text, chunk_size=500)
```

### 4. Query-Adaptive Chunking

**Concept**: Adjust chunking strategy based on expected query types.

```python
def adaptive_chunk(text, query_profile):
    """Chunk based on expected query characteristics."""
    if query_profile == "factual":
        # Small chunks for precise facts
        return sentence_aware_chunk(text, chunk_size=300)
    elif query_profile == "analytical":
        # Large chunks for analysis
        return paragraph_aware_chunk(text, chunk_size=1500)
    elif query_profile == "exploratory":
        # Medium chunks for exploration
        return semantic_chunk(text, chunk_size=800)
    else:
        return default_chunk(text, chunk_size=500)
```

---

## Implementation Guide

### Complete Chunking Implementation

**File**: `ingestion/processors/chunk.py`

```python
import re
import tiktoken
from typing import List, Dict, Optional
from enum import Enum

class ChunkingStrategy(Enum):
    FIXED = "fixed"
    SENTENCE = "sentence"
    PARAGRAPH = "paragraph"
    SEMANTIC = "semantic"
    RECURSIVE = "recursive"

class Chunker:
    def __init__(
        self,
        chunk_size: int = 500,
        overlap: int = 50,
        strategy: ChunkingStrategy = ChunkingStrategy.SENTENCE,
        model: str = "gpt-4"  # For token counting
    ):
        self.chunk_size = chunk_size
        self.overlap = overlap
        self.strategy = strategy
        self.encoding = tiktoken.encoding_for_model(model)
    
    def count_tokens(self, text: str) -> int:
        """Count tokens in text."""
        return len(self.encoding.encode(text))
    
    def split_sentences(self, text: str) -> List[str]:
        """Split text into sentences."""
        # Handle common sentence endings
        pattern = r'(?<=[.!?])\s+'
        sentences = re.split(pattern, text)
        return [s.strip() for s in sentences if s.strip()]
    
    def split_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs."""
        paragraphs = text.split('\n\n')
        return [p.strip() for p in paragraphs if p.strip()]
    
    def chunk(self, text: str, doc_id: str) -> List[Dict]:
        """Main chunking method."""
        if self.strategy == ChunkingStrategy.FIXED:
            return self._fixed_chunk(text, doc_id)
        elif self.strategy == ChunkingStrategy.SENTENCE:
            return self._sentence_chunk(text, doc_id)
        elif self.strategy == ChunkingStrategy.PARAGRAPH:
            return self._paragraph_chunk(text, doc_id)
        elif self.strategy == ChunkingStrategy.SEMANTIC:
            return self._semantic_chunk(text, doc_id)
        elif self.strategy == ChunkingStrategy.RECURSIVE:
            return self._recursive_chunk(text, doc_id)
        else:
            raise ValueError(f"Unknown strategy: {self.strategy}")
    
    def _fixed_chunk(self, text: str, doc_id: str) -> List[Dict]:
        """Fixed-size chunking."""
        tokens = self.encoding.encode(text)
        chunks = []
        start = 0
        chunk_index = 0
        
        while start < len(tokens):
            end = min(start + self.chunk_size, len(tokens))
            chunk_tokens = tokens[start:end]
            chunk_text = self.encoding.decode(chunk_tokens)
            
            chunks.append({
                "chunk_id": f"{doc_id}_chunk_{chunk_index}",
                "text": chunk_text,
                "chunk_index": chunk_index,
                "start_token": start,
                "end_token": end,
                "token_count": len(chunk_tokens)
            })
            
            start = end - self.overlap
            chunk_index += 1
        
        return chunks
    
    def _sentence_chunk(self, text: str, doc_id: str) -> List[Dict]:
        """Sentence-aware chunking."""
        sentences = self.split_sentences(text)
        chunks = []
        current_chunk = []
        current_size = 0
        chunk_index = 0
        
        for sentence in sentences:
            sentence_tokens = self.count_tokens(sentence)
            
            if current_size + sentence_tokens > self.chunk_size and current_chunk:
                # Save current chunk
                chunk_text = " ".join(current_chunk)
                chunks.append({
                    "chunk_id": f"{doc_id}_chunk_{chunk_index}",
                    "text": chunk_text,
                    "chunk_index": chunk_index,
                    "token_count": current_size
                })
                
                # Start new chunk with overlap
                overlap_tokens = self.overlap
                overlap_sentences = []
                overlap_size = 0
                
                # Add sentences for overlap (backwards from end)
                for s in reversed(current_chunk):
                    s_tokens = self.count_tokens(s)
                    if overlap_size + s_tokens <= overlap_tokens:
                        overlap_sentences.insert(0, s)
                        overlap_size += s_tokens
                    else:
                        break
                
                current_chunk = overlap_sentences + [sentence]
                current_size = overlap_size + sentence_tokens
                chunk_index += 1
            else:
                current_chunk.append(sentence)
                current_size += sentence_tokens
        
        # Add final chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append({
                "chunk_id": f"{doc_id}_chunk_{chunk_index}",
                "text": chunk_text,
                "chunk_index": chunk_index,
                "token_count": current_size
            })
        
        return chunks
    
    def _paragraph_chunk(self, text: str, doc_id: str) -> List[Dict]:
        """Paragraph-aware chunking."""
        paragraphs = self.split_paragraphs(text)
        chunks = []
        current_chunk = []
        current_size = 0
        chunk_index = 0
        
        for para in paragraphs:
            para_tokens = self.count_tokens(para)
            
            # If single paragraph exceeds chunk size, split it
            if para_tokens > self.chunk_size:
                # Split large paragraph by sentences
                para_sentences = self.split_sentences(para)
                for sent in para_sentences:
                    sent_tokens = self.count_tokens(sent)
                    if current_size + sent_tokens > self.chunk_size and current_chunk:
                        chunks.append({
                            "chunk_id": f"{doc_id}_chunk_{chunk_index}",
                            "text": "\n\n".join(current_chunk),
                            "chunk_index": chunk_index,
                            "token_count": current_size
                        })
                        current_chunk = [sent]
                        current_size = sent_tokens
                        chunk_index += 1
                    else:
                        current_chunk.append(sent)
                        current_size += sent_tokens
            elif current_size + para_tokens > self.chunk_size and current_chunk:
                # Save current chunk
                chunks.append({
                    "chunk_id": f"{doc_id}_chunk_{chunk_index}",
                    "text": "\n\n".join(current_chunk),
                    "chunk_index": chunk_index,
                    "token_count": current_size
                })
                
                # Start new chunk with overlap (last paragraph)
                current_chunk = [current_chunk[-1], para] if current_chunk else [para]
                current_size = sum(self.count_tokens(p) for p in current_chunk)
                chunk_index += 1
            else:
                current_chunk.append(para)
                current_size += para_tokens
        
        if current_chunk:
            chunks.append({
                "chunk_id": f"{doc_id}_chunk_{chunk_index}",
                "text": "\n\n".join(current_chunk),
                "chunk_index": chunk_index,
                "token_count": current_size
            })
        
        return chunks
    
    def _recursive_chunk(self, text: str, doc_id: str) -> List[Dict]:
        """Recursive chunking."""
        if self.count_tokens(text) <= self.chunk_size:
            return [{
                "chunk_id": f"{doc_id}_chunk_0",
                "text": text,
                "chunk_index": 0,
                "token_count": self.count_tokens(text)
            }]
        
        # Try paragraphs first
        paragraphs = self.split_paragraphs(text)
        if len(paragraphs) > 1:
            all_chunks = []
            for i, para in enumerate(paragraphs):
                para_chunks = self._recursive_chunk(para, f"{doc_id}_para{i}")
                # Adjust chunk IDs
                for chunk in para_chunks:
                    chunk["chunk_id"] = f"{doc_id}_chunk_{len(all_chunks)}"
                    chunk["chunk_index"] = len(all_chunks)
                all_chunks.extend(para_chunks)
            return all_chunks
        
        # Try sentences
        sentences = self.split_sentences(text)
        if len(sentences) > 1:
            return self._sentence_chunk(text, doc_id)
        
        # Last resort: fixed-size
        return self._fixed_chunk(text, doc_id)
    
    def _semantic_chunk(self, text: str, doc_id: str) -> List[Dict]:
        """Semantic chunking (requires embedding model)."""
        # For now, fall back to sentence chunking
        # Full implementation would require sentence-transformers
        return self._sentence_chunk(text, doc_id)


# Factory function for easy usage
def create_chunker(
    model_context: int = 8000,
    top_k: int = 8,
    strategy: str = "sentence"
) -> Chunker:
    """
    Create chunker optimized for specific model and use case.
    
    Args:
        model_context: LLM context window size
        top_k: Number of chunks to retrieve
        strategy: Chunking strategy
    
    Returns:
        Configured Chunker instance
    """
    # Calculate optimal chunk size
    system_tokens = 200
    query_tokens = 50
    response_tokens = 500
    safety_factor = 0.75
    
    available_tokens = model_context - system_tokens - query_tokens - response_tokens
    optimal_chunk_size = int((available_tokens / top_k) * safety_factor)
    
    # Clamp to reasonable range
    optimal_chunk_size = max(200, min(optimal_chunk_size, 5000))
    
    # Calculate overlap (10-20% of chunk size)
    overlap = int(optimal_chunk_size * 0.15)
    
    return Chunker(
        chunk_size=optimal_chunk_size,
        overlap=overlap,
        strategy=ChunkingStrategy[strategy.upper()],
        model="gpt-4"  # For token counting
    )


# Usage examples
if __name__ == "__main__":
    # Example 1: GPT-4 configuration
    chunker_gpt4 = create_chunker(
        model_context=8192,
        top_k=8,
        strategy="sentence"
    )
    
    text = "Your document text here..."
    chunks = chunker_gpt4.chunk(text, doc_id="doc_123")
    
    # Example 2: Gemini 1.5 Pro configuration
    chunker_gemini = create_chunker(
        model_context=1000000,
        top_k=30,
        strategy="semantic"
    )
    chunker_gemini.chunk_size = 3000
    chunker_gemini.overlap = 300
    
    # Example 3: Custom configuration
    chunker_custom = Chunker(
        chunk_size=600,
        overlap=100,
        strategy=ChunkingStrategy.PARAGRAPH
    )
```

### Integration with Ingestion Pipeline

```python
# In ingestion/function/main.py
from processors.chunk import create_chunker

def ingest_document(event, context):
    # ... extract text ...
    
    # Create chunker based on model
    model_context = int(os.getenv("MODEL_CONTEXT", "8192"))
    top_k = int(os.getenv("TOP_K", "8"))
    
    chunker = create_chunker(
        model_context=model_context,
        top_k=top_k,
        strategy=os.getenv("CHUNKING_STRATEGY", "sentence")
    )
    
    chunks = chunker.chunk(extracted_text, doc_id=doc_id)
    
    # ... continue with embedding and upsert ...
```

---

## Evaluation and Optimization

### Metrics to Track

**1. Chunk Size Distribution**:
```python
def analyze_chunk_sizes(chunks: List[Dict]) -> Dict:
    sizes = [c["token_count"] for c in chunks]
    return {
        "mean": sum(sizes) / len(sizes),
        "median": sorted(sizes)[len(sizes) // 2],
        "min": min(sizes),
        "max": max(sizes),
        "std": (sum((x - sum(sizes)/len(sizes))**2 for x in sizes) / len(sizes))**0.5
    }
```

**2. Retrieval Precision**:
- How often is the correct chunk retrieved?
- Is the answer in the retrieved chunks?

**3. Answer Quality**:
- Does the LLM generate accurate answers?
- Are citations correct?

**4. Cost Analysis**:
- Embedding costs (tokens embedded)
- LLM generation costs (context tokens used)

### A/B Testing Chunk Sizes

```python
def test_chunk_sizes(text: str, sizes: List[int], queries: List[str]):
    """Test different chunk sizes on same document."""
    results = {}
    
    for size in sizes:
        chunker = Chunker(chunk_size=size, overlap=int(size * 0.15))
        chunks = chunker.chunk(text, "test_doc")
        
        # Embed chunks
        embeddings = embed_chunks(chunks)
        
        # Test queries
        query_results = []
        for query in queries:
            # Retrieve and generate answer
            retrieved = retrieve(query, embeddings, top_k=8)
            answer = generate_answer(query, retrieved)
            
            # Evaluate (manual or automated)
            quality_score = evaluate_answer(query, answer, retrieved)
            query_results.append(quality_score)
        
        results[size] = {
            "num_chunks": len(chunks),
            "avg_quality": sum(query_results) / len(query_results),
            "avg_retrieval_time": measure_retrieval_time(queries),
            "avg_generation_time": measure_generation_time(queries)
        }
    
    return results
```

### Optimization Checklist

- [ ] Measure chunk size distribution
- [ ] Test retrieval precision with different sizes
- [ ] Evaluate answer quality
- [ ] Measure latency (retrieval + generation)
- [ ] Calculate costs (embedding + generation)
- [ ] Test with different overlap values
- [ ] Test with different chunking strategies
- [ ] Validate with real user queries
- [ ] Monitor production metrics

### Decision Framework

**Choose Small Chunks (200-500 tokens) When**:
- ✅ Using small context window models (GPT-3.5, etc.)
- ✅ Fact extraction tasks
- ✅ High precision requirements
- ✅ Cost-sensitive applications
- ✅ Real-time/low-latency needs

**Choose Medium Chunks (500-1000 tokens) When**:
- ✅ General-purpose RAG
- ✅ Balanced precision and context
- ✅ GPT-4 or similar models
- ✅ Mixed query types

**Choose Large Chunks (1000-3000+ tokens) When**:
- ✅ Large context window models (Gemini, Claude, GPT-4-turbo)
- ✅ Complex reasoning tasks
- ✅ Structured documents
- ✅ Narrative content
- ✅ Code documentation

---

## Conclusion

Chunking is a critical component of RAG systems that directly impacts:
- **Retrieval Quality**: How well you find relevant information
- **Generation Quality**: How well the LLM can answer questions
- **Cost**: Embedding and generation expenses
- **Latency**: Response times

**Key Takeaways**:
1. **No one-size-fits-all**: Chunk size depends on model, task, and document type
2. **Balance is key**: Trade-off between precision and context
3. **Overlap matters**: Prevents information loss at boundaries
4. **Strategy matters**: Sentence/paragraph/semantic chunking have different use cases
5. **Test and optimize**: Measure performance and adjust based on results

**Recommended Starting Points**:
- **GPT-3.5-turbo**: 300 tokens, sentence-aware
- **GPT-4**: 600 tokens, paragraph-aware
- **GPT-4-turbo**: 1500 tokens, semantic
- **Gemini 1.5**: 2000-3000 tokens, semantic
- **Claude 3**: 2000-2500 tokens, semantic

**Remember**: Start with recommendations, measure performance, and iterate based on your specific use case!
