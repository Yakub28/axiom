-- ============================================================================
-- AXIOM SHARED DATA CONTRACT — db/schema.sql
--
-- This schema is the contract the WHOLE TEAM codes against (data, graph, UI).
-- Any change to it MUST be recorded in docs/DECISIONS.md before being merged,
-- because downstream tracks (ingestion, velocity, citation graph, Streamlit)
-- all depend on these exact table and column names.
--
-- Source of truth: OpenAlex.
-- IMPORTANT: OpenAlex stores abstracts as an inverted index. They MUST be
-- reconstructed into plain text before insertion into papers.abstract here.
-- ============================================================================

PRAGMA foreign_keys = ON;

-- One row per paper (abstract-level unit; also the unit for one Qdrant point).
CREATE TABLE IF NOT EXISTS papers (
    openalex_id      TEXT PRIMARY KEY,   -- e.g. "W2741809807"
    title            TEXT,
    abstract         TEXT,               -- reconstructed PLAIN TEXT (not inverted index)
    publication_year INTEGER,
    venue_id         TEXT,               -- OpenAlex source/venue id
    venue            TEXT,               -- human-readable venue name
    cited_by_count   INTEGER DEFAULT 0,
    doi              TEXT
);

-- Many concepts per paper (OpenAlex concepts/topics). Many-to-one to papers.
CREATE TABLE IF NOT EXISTS concepts (
    paper_id TEXT NOT NULL,              -- FK -> papers.openalex_id
    concept  TEXT NOT NULL,
    level    INTEGER,                    -- OpenAlex concept level (0 = broad)
    FOREIGN KEY (paper_id) REFERENCES papers(openalex_id)
);

-- Citation edges built from each paper's referenced_works[].
-- Present now, consumed in P2 by the NetworkX graph track (decision OD6).
CREATE TABLE IF NOT EXISTS citation_edges (
    src_id TEXT NOT NULL,                -- citing paper (owner of referenced_works)
    dst_id TEXT NOT NULL,                -- cited paper
    year   INTEGER,                      -- citing paper's publication_year
    FOREIGN KEY (src_id) REFERENCES papers(openalex_id)
    -- NOTE: NO foreign key on dst_id by design. referenced_works[] routinely
    -- points at papers outside the local corpus; the graph track needs these
    -- dangling edges, so we must not reject them.
);

-- Provenance / fetch bookkeeping. One row per paper.
CREATE TABLE IF NOT EXISTS paper_provenance (
    paper_id     TEXT PRIMARY KEY,       -- FK -> papers.openalex_id
    source       TEXT,                   -- e.g. "openalex", "synthetic"
    fetched_at   DATETIME,
    text_hash    TEXT,                   -- hash of abstract for dedup/change detection
    has_fulltext BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (paper_id) REFERENCES papers(openalex_id)
);

-- Read-path indexes for the UI filter bar and the P2 graph track.
CREATE INDEX IF NOT EXISTS idx_papers_year    ON papers(publication_year);
CREATE INDEX IF NOT EXISTS idx_papers_venue   ON papers(venue);
CREATE INDEX IF NOT EXISTS idx_concepts_paper ON concepts(paper_id);
CREATE INDEX IF NOT EXISTS idx_edges_src      ON citation_edges(src_id);
CREATE INDEX IF NOT EXISTS idx_edges_dst      ON citation_edges(dst_id);
