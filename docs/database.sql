-- NewsFlow Database Schema for Supabase
-- Run this in Supabase SQL Editor

-- Enable pgvector extension for vector similarity search
CREATE EXTENSION IF NOT EXISTS vector;

-- ============================================
-- ARTICLES TABLE
-- Stores raw news articles with vector embeddings
-- ============================================
CREATE TABLE articles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    title VARCHAR(500) NOT NULL,
    content TEXT NOT NULL,
    summary TEXT,
    url VARCHAR(1000) NOT NULL UNIQUE,
    source VARCHAR(100) NOT NULL,
    author VARCHAR(200),
    published_at TIMESTAMP WITH TIME ZONE,
    cluster_id UUID,
    embedding VECTOR(384),
    keywords TEXT[],
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'archived', 'deleted')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for articles
CREATE INDEX idx_articles_cluster_id ON articles(cluster_id);
CREATE INDEX idx_articles_status ON articles(status);
CREATE INDEX idx_articles_source ON articles(source);
CREATE INDEX idx_articles_created_at ON articles(created_at DESC);
CREATE INDEX idx_articles_published_at ON articles(published_at DESC);

-- Vector similarity index (IVFFlat for performance)
CREATE INDEX idx_articles_embedding ON articles 
    USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Full-text search index
CREATE INDEX idx_articles_search ON articles 
    USING gin(to_tsvector('english', title || ' ' || COALESCE(content, '')));

-- ============================================
-- CLUSTERS TABLE
-- Groups of similar articles
-- ============================================
CREATE TABLE clusters (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(200) NOT NULL,
    description TEXT,
    centroid VECTOR(384),
    article_count INTEGER DEFAULT 0,
    similarity_threshold FLOAT DEFAULT 0.85,
    status VARCHAR(20) DEFAULT 'active' CHECK (status IN ('active', 'merged', 'archived')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for clusters
CREATE INDEX idx_clusters_status ON clusters(status);
CREATE INDEX idx_clusters_created_at ON clusters(created_at DESC);

-- Foreign key: articles.cluster_id -> clusters.id (required for PostgREST JOIN/nested select)
ALTER TABLE articles
ADD CONSTRAINT fk_articles_cluster
FOREIGN KEY (cluster_id)
REFERENCES clusters(id)
ON DELETE SET NULL;

-- ============================================
-- CRAWL_HISTORY TABLE
-- Tracks crawling operations
-- ============================================
CREATE TABLE crawl_history (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    source VARCHAR(100) NOT NULL,
    url VARCHAR(1000),
    status VARCHAR(20) NOT NULL CHECK (status IN ('success', 'failed', 'pending', 'running')),
    articles_found INTEGER DEFAULT 0,
    articles_added INTEGER DEFAULT 0,
    error_message TEXT,
    started_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    completed_at TIMESTAMP WITH TIME ZONE,
    duration_ms INTEGER
);

-- Indexes for crawl_history
CREATE INDEX idx_crawl_history_status ON crawl_history(status);
CREATE INDEX idx_crawl_history_source ON crawl_history(source);
CREATE INDEX idx_crawl_history_created_at ON crawl_history(started_at DESC);

-- ============================================
-- VIEWS FOR CONVENIENCE
-- ============================================

-- View: Active articles with cluster info
CREATE VIEW vw_articles_with_clusters AS
SELECT 
    a.id,
    a.title,
    a.summary,
    a.url,
    a.source,
    a.author,
    a.published_at,
    a.keywords,
    a.status,
    a.created_at,
    c.id AS cluster_id,
    c.name AS cluster_name,
    c.article_count AS cluster_size,
    s.content AS ai_summary,
    s.key_points AS ai_key_points
FROM articles a
LEFT JOIN clusters c ON a.cluster_id = c.id
LEFT JOIN summaries s ON c.id = s.cluster_id
WHERE a.status = 'active'
ORDER BY a.published_at DESC;

-- View: Cluster statistics
CREATE VIEW vw_cluster_stats AS
SELECT 
    c.id,
    c.name,
    c.article_count,
    c.status,
    c.created_at,
    c.updated_at,
    s.content AS summary,
    COUNT(a.id) AS actual_article_count,
    MIN(a.published_at) AS earliest_article,
    MAX(a.published_at) AS latest_article,
    ARRAY_AGG(DISTINCT a.source) AS sources
FROM clusters c
LEFT JOIN summaries s ON c.id = s.cluster_id
LEFT JOIN articles a ON c.id = a.cluster_id AND a.status = 'active'
GROUP BY c.id, c.name, c.article_count, c.status, c.created_at, c.updated_at, s.content;

-- ============================================
-- FUNCTIONS AND TRIGGERS
-- ============================================

-- Function: Update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers for updated_at
CREATE TRIGGER update_articles_updated_at BEFORE UPDATE ON articles
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_clusters_updated_at BEFORE UPDATE ON clusters
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_summaries_updated_at BEFORE UPDATE ON summaries
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Function: Update cluster article count
CREATE OR REPLACE FUNCTION update_cluster_article_count()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'INSERT' AND NEW.cluster_id IS NOT NULL THEN
        UPDATE clusters 
        SET article_count = article_count + 1,
            updated_at = NOW()
        WHERE id = NEW.cluster_id;
    ELSIF TG_OP = 'UPDATE' AND OLD.cluster_id IS DISTINCT FROM NEW.cluster_id THEN
        -- Decrement old cluster
        IF OLD.cluster_id IS NOT NULL THEN
            UPDATE clusters 
            SET article_count = article_count - 1,
                updated_at = NOW()
            WHERE id = OLD.cluster_id;
        END IF;
        -- Increment new cluster
        IF NEW.cluster_id IS NOT NULL THEN
            UPDATE clusters 
            SET article_count = article_count + 1,
                updated_at = NOW()
            WHERE id = NEW.cluster_id;
        END IF;
    ELSIF TG_OP = 'DELETE' AND OLD.cluster_id IS NOT NULL THEN
        UPDATE clusters 
        SET article_count = article_count - 1,
            updated_at = NOW()
        WHERE id = OLD.cluster_id;
    END IF;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_cluster_count 
    AFTER INSERT OR UPDATE OR DELETE ON articles
    FOR EACH ROW EXECUTE FUNCTION update_cluster_article_count();

-- ============================================
-- VECTOR SIMILARITY FUNCTIONS
-- ============================================

-- Function: Find similar articles
CREATE OR REPLACE FUNCTION find_similar_articles(
    query_embedding VECTOR(384),
    similarity_threshold FLOAT DEFAULT 0.85,
    max_results INTEGER DEFAULT 10
)
RETURNS TABLE (
    id UUID,
    title VARCHAR(500),
    url VARCHAR(1000),
    source VARCHAR(100),
    similarity FLOAT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        a.id,
        a.title,
        a.url,
        a.source,
        1 - (a.embedding <=> query_embedding) AS similarity
    FROM articles a
    WHERE a.status = 'active'
        AND a.embedding IS NOT NULL
        AND 1 - (a.embedding <=> query_embedding) > similarity_threshold
    ORDER BY a.embedding <=> query_embedding
    LIMIT max_results;
END;
$$ language 'plpgsql';

-- Function: Find articles in cluster
CREATE OR REPLACE FUNCTION get_cluster_articles(cluster_uuid UUID)
RETURNS TABLE (
    id UUID,
    title VARCHAR(500),
    content TEXT,
    url VARCHAR(1000),
    source VARCHAR(100),
    published_at TIMESTAMP WITH TIME ZONE,
    similarity_to_centroid FLOAT
) AS $$
DECLARE
    cluster_centroid VECTOR(384);
BEGIN
    SELECT centroid INTO cluster_centroid FROM clusters WHERE id = cluster_uuid;
    
    RETURN QUERY
    SELECT 
        a.id,
        a.title,
        a.content,
        a.url,
        a.source,
        a.published_at,
        1 - (a.embedding <=> cluster_centroid) AS similarity_to_centroid
    FROM articles a
    WHERE a.cluster_id = cluster_uuid AND a.status = 'active'
    ORDER BY a.embedding <=> cluster_centroid;
END;
$$ language 'plpgsql';

-- ============================================
-- ROW LEVEL SECURITY (RLS) POLICIES
-- ============================================

-- Enable RLS on all tables
ALTER TABLE articles ENABLE ROW LEVEL SECURITY;
ALTER TABLE clusters ENABLE ROW LEVEL SECURITY;
ALTER TABLE crawl_history ENABLE ROW LEVEL SECURITY;

-- Public read access for active content
CREATE POLICY "Public can read active articles" ON articles
    FOR SELECT USING (status = 'active');

CREATE POLICY "Public can read active clusters" ON clusters
    FOR SELECT USING (status = 'active');

-- Service role can do everything (for backend)
CREATE POLICY "Service role full access" ON articles
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access" ON clusters
    FOR ALL USING (auth.role() = 'service_role');

CREATE POLICY "Service role full access" ON crawl_history
    FOR ALL USING (auth.role() = 'service_role');

-- ============================================
-- SAMPLE DATA (Optional - for testing)
-- ============================================

-- Insert sample cluster
INSERT INTO clusters (name, description, similarity_threshold) VALUES
    ('AI Model Releases', 'Latest AI model announcements and releases', 0.85),
    ('Developer Tools', 'New tools and frameworks for developers', 0.85),
    ('ChatGPT Updates', 'OpenAI ChatGPT related news', 0.85);

-- Note: Sample articles would need actual embeddings
-- Use the backend API to insert real articles

-- ============================================
-- PERFORMANCE OPTIMIZATION
-- ============================================

-- Vacuum and analyze for query optimization
-- VACUUM ANALYZE articles;
-- VACUUM ANALYZE clusters;
-- VACUUM ANALYZE summaries;
-- VACUUM ANALYZE crawl_history;
