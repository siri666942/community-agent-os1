CREATE TABLE IF NOT EXISTS opsie_accounts (
  account_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  username VARCHAR(80) NOT NULL UNIQUE,
  password_hash VARCHAR(255) NOT NULL,
  role ENUM('teacher','parent') NOT NULL,
  user_id BIGINT UNSIGNED NOT NULL,
  display_name VARCHAR(191) NOT NULL,
  active BOOLEAN NOT NULL DEFAULT TRUE,
  FOREIGN KEY (user_id) REFERENCES users(user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS opsie_sessions (
  token_hash CHAR(64) PRIMARY KEY,
  account_id BIGINT UNSIGNED NOT NULL,
  expires_at DATETIME(3) NOT NULL,
  FOREIGN KEY (account_id) REFERENCES opsie_accounts(account_id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS opsie_demo (
  demo_key VARCHAR(80) PRIMARY KEY,
  group_id BIGINT UNSIGNED NOT NULL,
  source_group_id BIGINT UNSIGNED NOT NULL,
  offset_seconds BIGINT NOT NULL,
  created_at DATETIME(3) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS opsie_inbound_reviews (
  message_key VARCHAR(80) PRIMARY KEY,
  conversation_id BIGINT UNSIGNED NOT NULL,
  sender_id BIGINT UNSIGNED NOT NULL,
  effective_time DATETIME(3) NOT NULL,
  status ENUM('pending','running','complete','failed') NOT NULL,
  is_sensitive BOOLEAN NULL,
  details JSON NULL,
  policy_version VARCHAR(120) NOT NULL,
  updated_at DATETIME(3) NOT NULL,
  INDEX opsie_inbound_date (effective_time,is_sensitive,status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS opsie_jobs (
  job_id CHAR(32) PRIMARY KEY,
  account_id BIGINT UNSIGNED NOT NULL,
  conversation_id BIGINT UNSIGNED NOT NULL,
  target_message_key VARCHAR(80) NOT NULL,
  target_user_id BIGINT UNSIGNED NOT NULL,
  context_revision VARCHAR(80) NOT NULL,
  policy_version VARCHAR(120) NOT NULL,
  status ENUM('queued','running','succeeded','failed','interrupted') NOT NULL,
  result JSON NULL,
  error TEXT NULL,
  created_at DATETIME(3) NOT NULL,
  updated_at DATETIME(3) NOT NULL,
  INDEX opsie_job_conversation (conversation_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS opsie_outbound_reviews (
  review_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  conversation_id BIGINT UNSIGNED NOT NULL,
  account_id BIGINT UNSIGNED NOT NULL,
  text_hash CHAR(64) NOT NULL,
  status VARCHAR(32) NOT NULL,
  details JSON NOT NULL,
  confirmed BOOLEAN NOT NULL DEFAULT FALSE,
  variant VARCHAR(32) NULL,
  edited BOOLEAN NOT NULL DEFAULT FALSE,
  message_id BIGINT UNSIGNED NULL,
  policy_version VARCHAR(120) NOT NULL,
  created_at DATETIME(3) NOT NULL,
  INDEX opsie_review_message (message_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS opsie_tags (
  tag_id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT PRIMARY KEY,
  user_id BIGINT UNSIGNED NOT NULL,
  tag VARCHAR(191) NOT NULL,
  account_id BIGINT UNSIGNED NOT NULL,
  created_at DATETIME(3) NOT NULL,
  UNIQUE KEY opsie_tag_user (user_id,tag)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS opsie_profile_cache (
  user_id BIGINT UNSIGNED PRIMARY KEY,
  summary TEXT NOT NULL,
  source_revision VARCHAR(120) NOT NULL,
  updated_at DATETIME(3) NOT NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
