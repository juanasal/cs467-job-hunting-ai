USE jobhunt;

CREATE TABLE user_sessions (
    session_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
    user_id INT UNSIGNED NOT NULL,

    -- SHA-256 hash of the random session token, never the raw token.
    token_hash CHAR(64) NOT NULL,

    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_activity_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at DATETIME NOT NULL,
    revoked_at DATETIME NULL DEFAULT NULL,

    PRIMARY KEY (session_id),

    UNIQUE KEY uq_user_sessions_token_hash (token_hash),
    KEY idx_user_sessions_user (user_id),
    KEY idx_user_sessions_expiration (expires_at),

    CONSTRAINT fk_user_sessions_user
        FOREIGN KEY (user_id)
        REFERENCES users (user_id)
        ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;