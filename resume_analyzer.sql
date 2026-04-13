-- ============================================================
-- Mocka AI – Full Database Schema
-- Run this once in MySQL / phpMyAdmin / TablePlus etc.
-- ============================================================

CREATE DATABASE IF NOT EXISTS resume_analyzer
  DEFAULT CHARACTER SET utf8mb4
  DEFAULT COLLATE utf8mb4_unicode_ci;

USE resume_analyzer;

-- ── Users ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS users (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  username    VARCHAR(100)  NOT NULL UNIQUE,
  email       VARCHAR(255)  UNIQUE,
  password    VARCHAR(255)  NULL,          -- NULL for Google-only accounts
  google_id   VARCHAR(255)  UNIQUE,        -- Google sub ID
  avatar_url  VARCHAR(500)  NULL,          -- Google profile picture URL
  created_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,

  INDEX idx_users_email (email),
  INDEX idx_users_google (google_id)
) ENGINE=InnoDB;

-- ── OTP / Password-reset codes ─────────────────────────────────────
CREATE TABLE IF NOT EXISTS otp_codes (
  id          INT AUTO_INCREMENT PRIMARY KEY,
  email       VARCHAR(255)  NOT NULL,
  code        VARCHAR(10)   NOT NULL,
  expires_at  DATETIME      NOT NULL,
  used        TINYINT(1)    DEFAULT 0,
  created_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,

  INDEX idx_otp_email (email)
) ENGINE=InnoDB;

-- ── Analysis sessions ──────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS chats (
  id               INT AUTO_INCREMENT PRIMARY KEY,
  user_id          INT           NOT NULL,
  jd_filename      VARCHAR(255)  DEFAULT NULL,
  resume_filename  VARCHAR(255)  DEFAULT NULL,
  relevance_score  TEXT          DEFAULT NULL,   -- Full text from AI
  skill_gaps       TEXT          DEFAULT NULL,   -- Skill gap bullet points
  questions        TEXT          DEFAULT NULL,   -- Newline-separated questions
  created_at       TIMESTAMP     DEFAULT CURRENT_TIMESTAMP,

  FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
  INDEX idx_chats_user (user_id),
  INDEX idx_chats_created (created_at)
) ENGINE=InnoDB;

-- ============================================================
-- Quick sanity check
-- ============================================================
SELECT 'Tables created successfully!' AS status;
SHOW TABLES;
