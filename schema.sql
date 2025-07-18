-- schema.sql
-- Содержит SQL-запросы для создания всех таблиц базы данных

DROP TABLE IF EXISTS messages;
DROP TABLE IF EXISTS channel_subscribers;
DROP TABLE IF EXISTS group_members;
DROP TABLE IF EXISTS private_chats;
DROP TABLE IF EXISTS chats;
DROP TABLE IF EXISTS users;

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    email TEXT UNIQUE,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL,
    avatar_url TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL,
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users (username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);

CREATE TABLE chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT NOT NULL CHECK(type IN ('private', 'group', 'channel')),
    name TEXT,
    avatar_url TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL,
    owner_id INTEGER, -- НОВОЕ: Добавлен столбец owner_id для каналов
    FOREIGN KEY (owner_id) REFERENCES users(id) ON DELETE SET NULL -- Если пользователь-владелец удален, owner_id становится NULL
);

CREATE TABLE private_chats (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL UNIQUE,
    user1_id INTEGER NOT NULL,
    user2_id INTEGER NOT NULL,
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE,
    FOREIGN KEY (user1_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (user2_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(user1_id, user2_id)
);

CREATE TABLE group_members (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    group_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    role TEXT NOT NULL DEFAULT 'member', -- 'admin', 'member', 'restricted'
    joined_at TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL,
    FOREIGN KEY (group_id) REFERENCES chats(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(group_id, user_id)
);

CREATE TABLE channel_subscribers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    joined_at TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL,
    FOREIGN KEY (channel_id) REFERENCES chats(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE(channel_id, user_id)
);

-- Новая таблица для сообщений
CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chat_id INTEGER NOT NULL,
    sender_id INTEGER, -- Может быть NULL, если пользователь удален (FOREIGN KEY ON DELETE SET NULL)
    message_type TEXT NOT NULL CHECK(message_type IN ('text', 'file')),
    content TEXT,
    file_url TEXT,
    file_name TEXT,
    file_size INTEGER,
    sent_at TEXT DEFAULT CURRENT_TIMESTAMP NOT NULL,
    is_deleted BOOLEAN DEFAULT FALSE NOT NULL,
    deleted_by INTEGER, -- Пользователь, который удалил сообщение (мягкое удаление)
    FOREIGN KEY (chat_id) REFERENCES chats(id) ON DELETE CASCADE,
    FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE SET NULL,
    FOREIGN KEY (deleted_by) REFERENCES users(id) ON DELETE SET NULL,
    CHECK ( (message_type = 'text' AND content IS NOT NULL AND file_url IS NULL) OR
            (message_type = 'file' AND content IS NULL AND file_url IS NOT NULL) )
);

-- Индексы для ускорения поиска по связям
CREATE INDEX IF NOT EXISTS idx_private_chats_user1_user2 ON private_chats (user1_id, user2_id);
CREATE INDEX IF NOT EXISTS idx_group_members_group_user ON group_members (group_id, user_id);
CREATE INDEX IF NOT EXISTS idx_channel_subscribers_channel_user ON channel_subscribers (channel_id, user_id);
CREATE INDEX IF NOT EXISTS idx_messages_chat_id ON messages (chat_id);
CREATE INDEX IF NOT EXISTS idx_messages_sender_id ON messages (sender_id);
CREATE INDEX IF NOT EXISTS idx_messages_sent_at ON messages (sent_at);