-- ============================================================
--  Student Expense Tracker  |  MySQL Database Schema
--  Subject : Database Management System (SQL)
-- ============================================================

-- Create and use the database
CREATE DATABASE IF NOT EXISTS expense_tracker;
USE expense_tracker;

-- ============================================================
-- TABLE 1: users
-- Stores student account information
-- ============================================================
CREATE TABLE IF NOT EXISTS users (
    id         INT          PRIMARY KEY AUTO_INCREMENT,
    name       VARCHAR(100) NOT NULL,
    email      VARCHAR(150) UNIQUE NOT NULL,
    password   VARCHAR(255) NOT NULL,
    created_at DATETIME     DEFAULT NOW()
);

-- ============================================================
-- TABLE 2: categories
-- Predefined expense categories
-- ============================================================
CREATE TABLE IF NOT EXISTS categories (
    id    INT         PRIMARY KEY AUTO_INCREMENT,
    name  VARCHAR(50) NOT NULL,
    icon  VARCHAR(10) DEFAULT '💰',
    color VARCHAR(20) DEFAULT '#7c3aed',
    UNIQUE KEY unique_category_name (name)
);

-- ============================================================
-- TABLE 3: expenses
-- Core table holding every recorded expense
-- ============================================================
CREATE TABLE IF NOT EXISTS expenses (
    id             INT           PRIMARY KEY AUTO_INCREMENT,
    user_id        INT           NOT NULL,
    category_id    INT,
    amount         DECIMAL(10,2) NOT NULL CHECK (amount > 0),
    description    VARCHAR(255),
    date           DATE          NOT NULL,
    payment_method VARCHAR(50)   DEFAULT 'Cash',
    FOREIGN KEY (user_id)     REFERENCES users(id)      ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE SET NULL
);

-- ============================================================
-- TABLE 4: budgets
-- Monthly budget limits per category per user
-- ============================================================
CREATE TABLE IF NOT EXISTS budgets (
    id           INT           PRIMARY KEY AUTO_INCREMENT,
    user_id      INT           NOT NULL,
    category_id  INT           NOT NULL,
    limit_amount DECIMAL(10,2) NOT NULL CHECK (limit_amount > 0),
    month        TINYINT       NOT NULL,
    year         YEAR          NOT NULL,
    UNIQUE KEY unique_budget (user_id, category_id, month, year),
    FOREIGN KEY (user_id)     REFERENCES users(id)      ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE
);

-- ============================================================
-- TABLE 5: income
-- Optional income records for net savings calculation
-- ============================================================
CREATE TABLE IF NOT EXISTS income (
    id      INT           PRIMARY KEY AUTO_INCREMENT,
    user_id INT           NOT NULL,
    amount  DECIMAL(10,2) NOT NULL CHECK (amount > 0),
    source  VARCHAR(100),
    date    DATE          NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

-- ============================================================
-- Seed default categories (INSERT IGNORE skips if name already exists)
-- ============================================================
INSERT IGNORE INTO categories (name, icon, color) VALUES
    ('Food',         '🍔', '#f97316'),
    ('Transport',    '🚌', '#3b82f6'),
    ('Stationery',   '📚', '#8b5cf6'),
    ('Rent',         '🏠', '#10b981'),
    ('Health',       '💊', '#ef4444'),
    ('Entertainment','🎮', '#f59e0b'),
    ('Clothing',     '👕', '#ec4899'),
    ('Other',        '📦', '#6b7280');
