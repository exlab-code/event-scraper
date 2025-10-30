# RAG Pipeline Implementation Plan for Fördermittel Semantic Search

**Status**: Planning Phase
**Created**: 2025-10-30

## Overview

This document outlines the implementation plan for a semantic search system using Qdrant vector database and OpenAI embeddings. The goal is to allow users to describe their situation in natural language and find relevant funding programs ranked by similarity, rather than using traditional keyword-based filtering.

## Architecture Design

### System Components

```
User Query → FastAPI Endpoint → Query Embedding → Qdrant Search → Directus Lookup → Ranked Results
```

**Key Technologies**:
- **Vector Database**: Qdrant (Cloud free tier initially)
- **Embeddings**: OpenAI text-embedding-3-small (1,536 dimensions)
- **API**: FastAPI for search endpoint
- **Frontend**: New Svelte page for natural language queries
- **Sync**: Bulk sync + incremental updates

### Data Flow

1. User enters natural language description (e.g., "Wir sind ein gemeinnütziger Verein in Berlin und suchen Förderung für ein Digitalisierungsprojekt bis 50.000 EUR")
2. System extracts optional metadata filters (bundesland, funding_type, amount)
3. Query text gets embedded using OpenAI API
4. Qdrant performs hybrid search (vector similarity + metadata filters)
5. Top candidates fetched from Directus with full details
6. Results ranked and returned with similarity scores

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1)

**Goal**: Build the RAG backend with embedding and vector search capabilities.

**Files to create**:
```
foerdermittel/
├── rag/
│   ├── __init__.py
│   ├── embedding_service.py     # OpenAI embedding wrapper
│   ├── qdrant_client.py         # Qdrant operations
│   ├── sync_to_qdrant.py        # Initial bulk sync script
│   └── search_service.py        # Main search logic
```

#### 1.1 embedding_service.py

**Purpose**: Create embeddings for funding programs and search queries.

**Key Features**:
- Composite text generation from multiple fields
- Batch embedding for efficiency
- German text optimization

**Embedding Strategy**:
```python
def create_embedding_text(program):
    """Combine fields into optimized text for embedding"""
    return "\n".join([
        f"Titel: {program['title']}",
        f"Beschreibung: {program['description']}",
        f"Zielgruppe: {program['target_group']}",
        f"Förderorganisation: {program['funding_organization']}",
        f"Förderart: {program['funding_type']}",
        f"Voraussetzungen: {program['eligibility_criteria']}",
        f"Bundesland: {program['bundesland']}",
        f"Relevanz: {program['relevance_reason']}"
    ])
```

**API Configuration**:
- Model: `text-embedding-3-small` (cost-effective)
- Dimensions: 1,536
- Batch size: 100 texts per API call

#### 1.2 qdrant_client.py

**Purpose**: Manage Qdrant collection and perform vector operations.

**Collection Schema**:
- Name: `foerdermittel_vectors`
- Vector size: 1,536 dimensions
- Distance metric: Cosine similarity
- Payload fields:
  - `directus_id` (int) - Reference to Directus
  - `title` (str)
  - `short_description` (str)
  - `funding_organization` (str)
  - `funding_provider_type` (str) - Bund, Land, EU, Stiftung
  - `bundesland` (str) - For geographic filtering
  - `funding_type` (str) - Zuschuss, Kredit, etc.
  - `funding_amount_min` (float)
  - `funding_amount_max` (float)
  - `relevance_score` (int) - 0-100
  - `status` (str) - Only "published" programs
  - `is_relevant` (bool)
  - `website` (str)

**Key Operations**:
- `initialize_collection()` - Create collection if not exists
- `upsert_program()` - Insert/update single program
- `bulk_upsert()` - Batch insert for efficiency
- `search()` - Hybrid search with metadata filters
- `delete_program()` - Remove from index

#### 1.3 sync_to_qdrant.py

**Purpose**: Initial bulk sync of all published programs from Directus to Qdrant.

**Process**:
1. Fetch all published programs from Directus
2. Generate composite texts for each program
3. Create embeddings in batches (100 at a time)
4. Upload to Qdrant with metadata payloads

**Usage**:
```bash
python3 foerdermittel/rag/sync_to_qdrant.py
```

**Expected Output**:
```
Fetching programs from Directus...
Found 1,000 published programs
Generating embeddings...
Uploading to Qdrant...
Successfully synced 1,000 programs
```

#### 1.4 search_service.py

**Purpose**: Main search logic combining embedding, vector search, and Directus lookup.

**Search Flow**:
1. Generate query embedding
2. Build Qdrant filters from metadata
3. Perform vector search (get top 20 candidates)
4. Fetch full details from Directus
5. Re-rank if needed
6. Return top N results with scores

**Hybrid Search**:
- **Semantic**: Vector similarity (cosine distance)
- **Filters**: Exact match on bundesland, funding_type, amount range
- **Boosting**: Combine similarity score with relevance_score

### Phase 2: Search API (Week 2)

**Goal**: Create FastAPI endpoint for semantic search.

**Files to create**:
```
foerdermittel/
└── api/
    ├── __init__.py
    └── search_api.py            # FastAPI search endpoint
```

#### 2.1 search_api.py

**Endpoints**:

**POST /api/foerdermittel/search**
```json
Request:
{
  "query": "Wir sind ein gemeinnütziger Verein...",
  "bundesland": "Berlin",  // optional
  "funding_type": "Zuschuss",  // optional
  "max_amount": 50000,  // optional
  "limit": 10
}

Response:
[
  {
    "id": 123,
    "title": "Demokratie leben!",
    "short_description": "...",
    "funding_organization": "BMFSFJ",
    "bundesland": "bundesweit",
    "funding_type": "Zuschuss",
    "funding_amount_max": 50000,
    "website": "https://...",
    "relevance_score": 90,
    "similarity_score": 0.87,
    "match_explanation": "Relevanz-Score: 90/100"
  }
]
```

**GET /health**
- Health check endpoint
- Returns: `{"status": "healthy"}`

**Configuration**:
- CORS enabled for Svelte frontend
- Request timeout: 30 seconds
- Rate limiting: 100 requests/minute

**Deployment**:
```bash
uvicorn foerdermittel.api.search_api:app --host 0.0.0.0 --port 8000
```

### Phase 3: Frontend Integration (Week 3)

**Goal**: Create Svelte UI for natural language funding program discovery.

**Files to create/modify**:
```
website/src/
├── pages/
│   └── FoerdermittelSearch.svelte  # New semantic search page
└── App.svelte                       # Add route
```

#### 3.1 FoerdermittelSearch.svelte

**UI Components**:

1. **Search Input**:
   - Large textarea for natural language query
   - Placeholder example: "Wir sind ein gemeinnütziger Verein in Berlin..."
   - Enter key to search

2. **Optional Filters** (collapsible):
   - Bundesland dropdown
   - Funding type dropdown (Zuschuss, Kredit, etc.)
   - Max amount input field

3. **Results Display**:
   - Card layout for each program
   - Shows: title, description, organization, bundesland, type, amount
   - Badges: similarity score (%) and relevance score (/100)
   - "Mehr erfahren" button linking to program website

4. **States**:
   - Loading spinner during search
   - Empty state with helpful message
   - Error state with retry option

**API Integration**:
```javascript
async function search() {
  const response = await fetch('http://localhost:8000/api/foerdermittel/search', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({query, bundesland, funding_type, max_amount, limit: 10})
  });
  results = await response.json();
}
```

#### 3.2 App.svelte Route

Add new route:
```javascript
else if (path === '/foerdermittel-search') {
  currentRoute = 'foerdermittel-search';
}
```

Update navigation to include link to semantic search page.

### Phase 4: Incremental Updates (Week 4)

**Goal**: Keep Qdrant synchronized with Directus changes.

**Files to create**:
```
foerdermittel/
└── rag/
    └── incremental_sync.py      # Sync recent changes
```

#### 4.1 incremental_sync.py

**Purpose**: Sync programs that were created/updated recently.

**Process**:
1. Query Directus for programs modified in last 24 hours
2. For each modified program:
   - If published: Generate embedding and upsert to Qdrant
   - If archived: Delete from Qdrant index
3. Log sync results

**Usage**:
```bash
# Sync last 24 hours
python3 foerdermittel/rag/incremental_sync.py

# Or specify custom timeframe
python3 foerdermittel/rag/incremental_sync.py --hours 48
```

**Cron Setup**:
```bash
# Add to crontab - run hourly
0 * * * * cd /path/to/Event-Scraper && python3 foerdermittel/rag/incremental_sync.py >> logs/qdrant_sync.log 2>&1
```

**Integration with Analyzer**:
After `foerdermittel_analyzer.py` processes programs, automatically sync to Qdrant:
```python
# At end of analyzer
subprocess.run(["python3", "foerdermittel/rag/incremental_sync.py"])
```

## Technical Specifications

### Embedding Strategy

**Field Selection**:
Combine multiple fields into single text for embedding:
- Title (high weight)
- Description (high weight)
- Target group (medium weight)
- Eligibility criteria (medium weight)
- Organization and type (low weight)

**Why Composite Embeddings?**:
- Captures semantic meaning across all relevant fields
- Better than embedding each field separately
- Simpler architecture
- Lower query cost (1 embedding vs. multiple)

**Text Length**:
- Average: ~500 tokens per program
- Max: 8,191 tokens (within model limits)
- No chunking needed for funding programs

### Search Scoring

**Combined Score Formula**:
```python
final_score = (
    0.7 * cosine_similarity +  # Semantic match
    0.3 * (relevance_score / 100)  # Pre-computed relevance
)
```

**Score Threshold**:
- Minimum similarity: 0.5 (50%)
- Programs below threshold filtered out
- Prevents irrelevant results

**Re-ranking Options**:
1. **Simple**: Use combined score (fast, cheap)
2. **LLM Re-ranking**: Use GPT-4o-mini for top 10 (better quality, higher cost)

### Metadata Filtering

**Supported Filters**:
- `bundesland` (exact match) - Geographic filtering
- `funding_type` (exact match) - Zuschuss, Kredit, etc.
- `funding_amount_max` (range) - Maximum funding <= user's requested amount
- `status` (always "published") - Only show active programs
- `is_relevant` (always true) - Only NGO-relevant programs

**Filter Combination**:
All filters are AND-ed together (must match all specified filters).

## Cost Estimates

### Embedding Costs (OpenAI)

**Initial Sync** (1,000 programs):
- 1,000 programs × 500 tokens = 500K tokens
- Cost: 500K × $0.02/1M = **$0.01**

**Monthly Updates** (100 new/changed programs):
- 100 programs × 500 tokens = 50K tokens/month
- Cost: 50K × $0.02/1M = **$0.001/month**

**Query Embeddings** (10,000 searches/month):
- 10K queries × 100 tokens = 1M tokens/month
- Cost: 1M × $0.02/1M = **$0.02/month**

### Qdrant Hosting

**Option 1: Qdrant Cloud Free Tier** (Recommended initially):
- Storage: 1GB (sufficient for ~10K programs)
- Operations: 1M per month
- Cost: **$0/month**

**Option 2: Qdrant Cloud Standard**:
- Storage: 10GB
- Operations: 10M per month
- Cost: **$25/month**

**Option 3: Self-hosted** (Docker):
- Storage: ~10MB for 1K programs
- Memory: 500MB RAM
- Cost: **$0** (use existing server)

### Total Monthly Operating Cost

| Component | Cost |
|-----------|------|
| Embeddings (updates) | $0.001 |
| Query embeddings | $0.02 |
| Qdrant hosting | $0 (free tier) |
| **Total** | **~$0.02/month** |

**Scale Estimates**:
- At 100K queries/month: ~$5/month
- With LLM re-ranking: +$10-20/month
- Qdrant standard tier: +$25/month
- **Maximum realistic cost: $50/month**

## Performance Metrics

### Expected Performance

**Search Latency**:
- Query embedding: 50-100ms
- Qdrant search: 50-150ms
- Directus lookup: 50-100ms
- **Total: 150-350ms**

**Throughput**:
- Concurrent queries: 100+ QPS
- Indexing speed: 1,000 programs in 2-3 minutes

**Accuracy**:
- Target: >80% of queries return relevant results
- Top-3 click-through rate: >60%
- Empty result rate: <10%

### Monitoring & Optimization

**Key Metrics to Track**:
1. Query latency (p50, p95, p99)
2. Empty result rate
3. User clicks on top 3 results
4. Cost per query
5. Qdrant storage usage

**Optimization Strategies**:
1. **Caching**: Cache frequent queries (Redis)
2. **Batch Processing**: Process multiple queries together
3. **Score Threshold Tuning**: Adjust based on empty result rate
4. **Dimensionality Reduction**: Reduce from 1,536 to 768 dims if storage becomes issue

## Dependencies

### Python Packages

```bash
pip install qdrant-client openai fastapi uvicorn python-multipart
```

**Version Requirements**:
- qdrant-client >= 1.7.0
- openai >= 1.0.0
- fastapi >= 0.104.0
- uvicorn >= 0.24.0

### Environment Variables

Add to `.env`:
```bash
# Qdrant Configuration
QDRANT_URL=https://your-cluster.qdrant.io:6333
QDRANT_API_KEY=your-qdrant-api-key

# OpenAI (already configured)
OPENAI_API_KEY=your-openai-api-key

# Optional: Redis for caching
REDIS_URL=redis://localhost:6379
```

## Deployment Strategy

### Development Setup

1. **Qdrant**: Use Docker locally
   ```bash
   docker run -p 6333:6333 qdrant/qdrant
   ```

2. **API**: Run with uvicorn
   ```bash
   uvicorn foerdermittel.api.search_api:app --reload --port 8000
   ```

3. **Frontend**: Existing Svelte dev server
   ```bash
   npm run dev
   ```

### Production Setup

1. **Qdrant**: Start with Cloud free tier
   - Sign up at https://cloud.qdrant.io
   - Create cluster
   - Get API key

2. **Initial Sync**: Run once to populate index
   ```bash
   python3 foerdermittel/rag/sync_to_qdrant.py
   ```

3. **API Deployment**: Options:
   - Same server as Directus
   - Separate API server
   - Serverless (AWS Lambda/Google Cloud Functions)

4. **Cron Job**: Set up incremental sync
   ```bash
   0 * * * * cd /path/to/Event-Scraper && python3 foerdermittel/rag/incremental_sync.py
   ```

5. **Frontend**: Add link in navigation
   - Update main menu to include "Semantic Search"
   - Keep existing filter-based search as alternative

## Testing Strategy

### Unit Tests

Test each component independently:

1. **embedding_service.py**:
   - Test text generation from program data
   - Test batch embedding (mock OpenAI API)
   - Test error handling

2. **qdrant_client.py**:
   - Test collection creation
   - Test upsert operations
   - Test search with filters
   - Test deletion

3. **search_service.py**:
   - Test end-to-end search flow
   - Test score combination
   - Test empty results handling

### Integration Tests

Test full workflow:

1. **Sync Test**:
   - Create test programs in Directus
   - Run sync script
   - Verify programs in Qdrant

2. **Search Test**:
   - Sample queries in German
   - Verify relevant results returned
   - Check score ordering

3. **Update Test**:
   - Modify program in Directus
   - Run incremental sync
   - Verify updated in Qdrant

### User Acceptance Testing

Real-world test scenarios:

1. **NGO in Berlin looking for digitalization funding**:
   - Query: "Wir sind ein Verein in Berlin und suchen Förderung für Digitalisierung"
   - Expected: Programs like "Digital für alle", Berlin-specific programs
   - Score: >0.7 similarity

2. **Small organization needing small grants**:
   - Query: "Kleine gemeinnützige Organisation braucht Zuschuss bis 10.000 EUR"
   - Expected: Micro-grant programs, accessible funding
   - Filter: max_amount=10000

3. **Education project in Bavaria**:
   - Query: "Bildungsprojekt in Bayern für Kinder und Jugendliche"
   - Expected: Bayern education programs
   - Filter: bundesland=Bayern

## Migration & Rollback Plan

### Rollout Strategy

**Phase 1: Beta Testing** (Week 1-2):
- Deploy to staging environment
- Internal testing with team
- Fix critical bugs

**Phase 2: Soft Launch** (Week 3):
- Add as "Experimental" feature
- Link from existing filter page
- Collect user feedback

**Phase 3: Full Launch** (Week 4+):
- Remove "Experimental" label
- Add to main navigation
- Monitor usage and optimize

### Rollback Plan

If semantic search has issues:

1. **Keep existing filter system**: Always available as fallback
2. **Feature flag**: Can disable new search page
3. **Data safety**: Directus remains source of truth
4. **No migration**: Qdrant is additive, not replacing anything

## Future Enhancements

### Phase 2 Features (Post-Launch)

1. **Clarifying Questions**:
   - After initial search, ask 2-3 follow-up questions
   - "In welchem Bundesland ist Ihre Organisation?"
   - "Wie hoch ist Ihr Projektbudget?"
   - Refine results based on answers

2. **Query History & Personalization**:
   - Store successful searches
   - Learn which programs users find helpful
   - Boost similar programs in future searches

3. **Match Explanations**:
   - Use GPT-4o-mini to generate "Why this matches"
   - Highlight relevant keywords from query
   - Increase user confidence in results

4. **Export & Notifications**:
   - Save search results
   - Get email when new matching programs added
   - Calendar integration for deadlines

5. **Multi-language Support**:
   - English query translation
   - Bilingual results display

## Success Criteria

### Launch Criteria

Before going live:
- [ ] All tests passing
- [ ] <500ms average search latency
- [ ] API documentation complete
- [ ] User guide written
- [ ] Cost monitoring set up
- [ ] Backup/restore procedure tested

### Post-Launch KPIs

Track for first 30 days:

**Usage Metrics**:
- Daily active searches
- Average queries per user
- Repeat usage rate

**Quality Metrics**:
- Click-through rate (target: >50%)
- Empty result rate (target: <10%)
- User satisfaction (feedback buttons)

**Technical Metrics**:
- Search latency (target: <500ms p95)
- Error rate (target: <1%)
- Cost per search (target: <$0.001)

**Decision Points**:
- If usage is low (<10 searches/day): Improve UI/marketing
- If empty results >15%: Lower similarity threshold
- If cost >$50/month: Optimize batching or switch to self-hosting

## Risks & Mitigations

### Technical Risks

1. **Qdrant Downtime**:
   - Risk: Service unavailable
   - Mitigation: Fallback to traditional filter search
   - SLA: 99.9% uptime on Cloud tier

2. **OpenAI API Limits**:
   - Risk: Rate limiting or quota exceeded
   - Mitigation: Implement exponential backoff, caching
   - Monitoring: Alert if >100 errors/hour

3. **Poor Search Quality**:
   - Risk: Users don't find relevant programs
   - Mitigation: A/B test with traditional search, tune threshold
   - Fallback: Keep filter-based search prominent

### Cost Risks

1. **Unexpected Usage Spike**:
   - Risk: Viral growth → high costs
   - Mitigation: Set OpenAI spending limits ($100/month)
   - Monitoring: Daily cost tracking

2. **Storage Growth**:
   - Risk: Exceed free tier limits
   - Mitigation: Archive old programs, compress vectors
   - Threshold: Alert at 80% capacity

## Documentation Requirements

### User Documentation

Create guide for users:
- How to write effective search queries
- Example queries and results
- When to use semantic vs. filter search
- How to interpret similarity scores

### Developer Documentation

Document for future maintainers:
- Architecture diagram
- API endpoint specifications
- Sync job schedule and monitoring
- Troubleshooting guide
- Cost optimization strategies

### Operations Manual

For production support:
- How to restart services
- How to re-sync entire index
- How to monitor performance
- How to scale up (more storage, self-hosting)

## Conclusion

This RAG pipeline transforms funding program discovery from keyword-based filtering to semantic understanding. Users can describe their situation naturally, and the system finds relevant programs even when they don't know exact keywords.

**Key Benefits**:
- Better user experience (natural language)
- Improved discovery (semantic matching)
- Flexible filtering (combine with metadata)
- Scalable architecture (vector search)
- Cost-effective (~$5/month initially)

**Next Steps**:
1. Review and approve this plan
2. Set up Qdrant account
3. Begin Phase 1 implementation
4. Test with real user queries
5. Iterate based on feedback

---

**Document Version**: 1.0
**Last Updated**: 2025-10-30
**Author**: Claude Code
**Status**: Awaiting Implementation
