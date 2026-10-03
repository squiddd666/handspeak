-- HandSpeak application schema. Import into an empty utf8mb4 MariaDB database.
CREATE TABLE IF NOT EXISTS users (
 id CHAR(32) PRIMARY KEY, email VARCHAR(254) NOT NULL UNIQUE,
 password_hash VARCHAR(255) NOT NULL, role ENUM('user','admin') NOT NULL DEFAULT 'user',
 active TINYINT NOT NULL DEFAULT 1 CHECK(active IN (0,1)), created_at VARCHAR(40) NOT NULL
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS auth_sessions (
 token_hash CHAR(64) PRIMARY KEY, user_id CHAR(32) NOT NULL, expires_at DOUBLE NOT NULL,
 FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE, INDEX(expires_at)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS password_resets (
 token_hash CHAR(64) PRIMARY KEY, user_id CHAR(32) NOT NULL, expires_at DOUBLE NOT NULL,
 FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE CASCADE, INDEX(expires_at)
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS gestures (
 symbol VARCHAR(30) PRIMARY KEY, name VARCHAR(100) NOT NULL, description TEXT NOT NULL,
 enabled TINYINT NOT NULL DEFAULT 1 CHECK(enabled IN (0,1))
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS sessions (
 id CHAR(32) PRIMARY KEY, message TEXT NOT NULL, character_count INT NOT NULL,
 duration_ms INT NOT NULL DEFAULT 0, created_at VARCHAR(40) NOT NULL,
 owner_id VARCHAR(64) NOT NULL DEFAULT '', user_id CHAR(32) NULL,
 INDEX sessions_owner(owner_id,created_at),
 FOREIGN KEY(user_id) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS detections (
 id BIGINT PRIMARY KEY AUTO_INCREMENT, session_id CHAR(32) NOT NULL,
 symbol VARCHAR(30) NOT NULL, confidence DOUBLE NOT NULL CHECK(confidence BETWEEN 0 AND 1),
 latency_ms DOUBLE NOT NULL CHECK(latency_ms BETWEEN 0 AND 60000), correct TINYINT NULL,
 created_at VARCHAR(40) NOT NULL,
 FOREIGN KEY(session_id) REFERENCES sessions(id) ON DELETE CASCADE
) ENGINE=InnoDB;
CREATE TABLE IF NOT EXISTS evaluations (
 id BIGINT PRIMARY KEY AUTO_INCREMENT, respondent_type VARCHAR(40) NOT NULL,
 accuracy INT NOT NULL CHECK(accuracy BETWEEN 1 AND 5),
 usability INT NOT NULL CHECK(usability BETWEEN 1 AND 5),
 performance INT NOT NULL CHECK(performance BETWEEN 1 AND 5),
 comments TEXT NOT NULL, created_at VARCHAR(40) NOT NULL
) ENGINE=InnoDB;
-- Serialize rare bootstrap/reset transactions with the same guarantee as SQLite BEGIN IMMEDIATE.
CREATE TABLE IF NOT EXISTS app_locks (name VARCHAR(32) PRIMARY KEY) ENGINE=InnoDB;
INSERT IGNORE INTO app_locks(name) VALUES('auth_write');
