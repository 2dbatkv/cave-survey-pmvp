-- Cave Survey Application
-- PostgreSQL Database Initialization Script

-- Enable necessary extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- USER MANAGEMENT
-- ============================================

CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username VARCHAR(255) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),

    -- Indexes
    CONSTRAINT users_username_key UNIQUE (username),
    CONSTRAINT users_email_key UNIQUE (email)
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- ============================================
-- SURVEY DATA
-- ============================================

CREATE TABLE IF NOT EXISTS surveys (
    id SERIAL PRIMARY KEY,
    title VARCHAR(255),
    section VARCHAR(255),
    description TEXT,
    owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE,

    -- S3 storage info
    s3_json_key VARCHAR(500),
    s3_png_key VARCHAR(500),
    json_url VARCHAR(1000),
    png_url VARCHAR(1000),

    -- Survey metadata
    num_stations INTEGER,
    num_shots INTEGER,
    total_slope_distance DOUBLE PRECISION,
    total_horizontal_distance DOUBLE PRECISION,

    -- Bounding box (coordinates)
    min_x DOUBLE PRECISION,
    max_x DOUBLE PRECISION,
    min_y DOUBLE PRECISION,
    max_y DOUBLE PRECISION,
    min_z DOUBLE PRECISION,
    max_z DOUBLE PRECISION
);

CREATE INDEX IF NOT EXISTS idx_surveys_title ON surveys(title);
CREATE INDEX IF NOT EXISTS idx_surveys_section ON surveys(section);
CREATE INDEX IF NOT EXISTS idx_surveys_owner ON surveys(owner_id);
CREATE INDEX IF NOT EXISTS idx_surveys_created ON surveys(created_at);

-- Trigger to auto-update updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_surveys_updated_at BEFORE UPDATE ON surveys
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- ============================================
-- FEEDBACK SYSTEM
-- ============================================

CREATE TABLE IF NOT EXISTS feedback (
    id SERIAL PRIMARY KEY,
    feedback_text TEXT NOT NULL,
    submitted_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    user_session VARCHAR(255),
    category VARCHAR(100) DEFAULT 'general',
    priority VARCHAR(50) DEFAULT 'normal',
    status VARCHAR(50) DEFAULT 'new'
);

CREATE INDEX IF NOT EXISTS idx_feedback_submitted ON feedback(submitted_at);
CREATE INDEX IF NOT EXISTS idx_feedback_status ON feedback(status);
CREATE INDEX IF NOT EXISTS idx_feedback_category ON feedback(category);

-- ============================================
-- DEMO MODE SETTINGS
-- ============================================

CREATE TABLE IF NOT EXISTS settings (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT,
    description TEXT,
    category VARCHAR(50),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert default settings
INSERT INTO settings (key, value, description, category, updated_at)
VALUES
    ('app_name', 'Cave Survey Application', 'Application name', 'app', NOW()),
    ('demo_mode_enabled', 'false', 'Whether demo mode is active', 'system', NOW()),
    ('demo_mode_disclaimer', 'Demonstration data only. These surveys are fictional examples for testing purposes.', 'Disclaimer for demo/mockup mode', 'system', NOW()),
    ('max_shots_per_survey', '1000', 'Maximum shots allowed per survey', 'limits', NOW()),
    ('max_surveys_per_user', '50', 'Maximum surveys per user', 'limits', NOW())
ON CONFLICT (key) DO NOTHING;

-- ============================================
-- VIEWS
-- ============================================

-- View for survey statistics
CREATE OR REPLACE VIEW v_survey_stats AS
SELECT
    u.username,
    u.email,
    COUNT(s.id) as survey_count,
    SUM(s.num_stations) as total_stations,
    SUM(s.num_shots) as total_shots,
    SUM(s.total_slope_distance) as total_distance_mapped,
    MAX(s.created_at) as latest_survey_date
FROM users u
LEFT JOIN surveys s ON u.id = s.owner_id
GROUP BY u.id, u.username, u.email;

-- ============================================
-- SUCCESS MESSAGE
-- ============================================

DO $$
BEGIN
    RAISE NOTICE '✓ Cave Survey database initialized successfully';
    RAISE NOTICE '  - Users table created';
    RAISE NOTICE '  - Surveys table created';
    RAISE NOTICE '  - Feedback table created';
    RAISE NOTICE '  - Settings table created with defaults';
    RAISE NOTICE '  - Indexes and views created';
END $$;
