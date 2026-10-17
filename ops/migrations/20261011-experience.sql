CREATE TABLE IF NOT EXISTS vocabulary_settings (
 word_id VARCHAR(80) PRIMARY KEY, description TEXT NOT NULL, video_path VARCHAR(255) NOT NULL,
 hidden TINYINT NOT NULL DEFAULT 0, updated_at VARCHAR(40) NOT NULL
) CHARACTER SET utf8mb4;
CREATE TABLE IF NOT EXISTS match_feedback (
 id VARCHAR(32) PRIMARY KEY, owner_id VARCHAR(80) NOT NULL, predicted VARCHAR(80) NOT NULL,
 expected VARCHAR(80) NOT NULL, verdict VARCHAR(16) NOT NULL, model VARCHAR(200) NOT NULL,
 status VARCHAR(16) NOT NULL DEFAULT 'pending', created_at VARCHAR(40) NOT NULL,
 INDEX feedback_owner_time(owner_id,created_at)
) CHARACTER SET utf8mb4;
