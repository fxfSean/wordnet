CREATE SCHEMA vocab;
REVOKE ALL ON SCHEMA vocab FROM PUBLIC;

CREATE TABLE vocab.words (
    word_id text PRIMARY KEY,
    lemma text NOT NULL UNIQUE,
    content_version integer NOT NULL CHECK (content_version > 0)
);

CREATE TABLE vocab.word_senses (
    word_id text NOT NULL REFERENCES vocab.words (word_id),
    sense_id text NOT NULL,
    pos text NOT NULL CHECK (pos IN ('noun', 'verb', 'adj', 'adv')),
    definition_en text NOT NULL CHECK (length(trim(definition_en)) > 0),
    examples_en text[] NOT NULL DEFAULT '{}',
    display_order integer NOT NULL CHECK (display_order > 0),
    is_primary boolean NOT NULL DEFAULT false,
    review_status text NOT NULL DEFAULT 'pending' CHECK (review_status IN ('pending', 'approved', 'rejected')),
    source jsonb NOT NULL CHECK (jsonb_typeof(source) = 'object'),
    PRIMARY KEY (word_id, sense_id),
    UNIQUE (word_id, display_order)
);

CREATE TABLE vocab.wordbooks (
    book_id text PRIMARY KEY,
    title text NOT NULL,
    enabled boolean NOT NULL DEFAULT false,
    content_version integer NOT NULL CHECK (content_version > 0),
    source jsonb NOT NULL CHECK (jsonb_typeof(source) = 'object')
);

CREATE TABLE vocab.wordbook_items (
    book_id text NOT NULL REFERENCES vocab.wordbooks (book_id),
    word_id text NOT NULL REFERENCES vocab.words (word_id),
    display_order integer NOT NULL CHECK (display_order > 0),
    PRIMARY KEY (book_id, word_id),
    UNIQUE (book_id, display_order)
);

CREATE TABLE vocab.users (
    openid text PRIMARY KEY,
    daily_goal integer NOT NULL DEFAULT 20 CHECK (daily_goal BETWEEN 1 AND 100),
    selected_book text REFERENCES vocab.wordbooks (book_id),
    time_zone text NOT NULL DEFAULT 'Asia/Shanghai'
);

CREATE TABLE vocab.user_word_progress (
    openid text NOT NULL REFERENCES vocab.users (openid),
    word_id text NOT NULL,
    sense_id text NOT NULL,
    stage integer NOT NULL DEFAULT 0 CHECK (stage BETWEEN 0 AND 7),
    correct_streak integer NOT NULL DEFAULT 0 CHECK (correct_streak >= 0),
    correct_count integer NOT NULL DEFAULT 0 CHECK (correct_count >= 0),
    wrong_count integer NOT NULL DEFAULT 0 CHECK (wrong_count >= 0),
    next_review_at timestamptz NOT NULL,
    updated_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (openid, word_id, sense_id),
    FOREIGN KEY (word_id, sense_id) REFERENCES vocab.word_senses (word_id, sense_id)
);
CREATE INDEX user_word_progress_due_idx ON vocab.user_word_progress (openid, next_review_at);

CREATE TABLE vocab.study_sessions (
    openid text NOT NULL REFERENCES vocab.users (openid),
    session_id text NOT NULL,
    book_id text NOT NULL REFERENCES vocab.wordbooks (book_id),
    study_date date NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (openid, session_id)
);
CREATE INDEX study_sessions_date_idx ON vocab.study_sessions (openid, study_date);

CREATE TABLE vocab.study_events (
    openid text NOT NULL REFERENCES vocab.users (openid),
    event_id text NOT NULL,
    session_id text,
    word_id text NOT NULL,
    sense_id text NOT NULL,
    rating text NOT NULL CHECK (rating IN ('know', 'fuzzy', 'dont_know')),
    occurred_at timestamptz NOT NULL,
    received_at timestamptz NOT NULL DEFAULT now(),
    result jsonb NOT NULL CHECK (jsonb_typeof(result) = 'object'),
    PRIMARY KEY (openid, event_id),
    FOREIGN KEY (openid, session_id) REFERENCES vocab.study_sessions (openid, session_id),
    FOREIGN KEY (word_id, sense_id) REFERENCES vocab.word_senses (word_id, sense_id)
);
CREATE INDEX study_events_recent_idx ON vocab.study_events (openid, occurred_at);
