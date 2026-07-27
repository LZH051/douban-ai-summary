PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS movies (
    movie_id INTEGER PRIMARY KEY AUTOINCREMENT,
    douban_id INTEGER NOT NULL UNIQUE,
    title TEXT NOT NULL,
    rating REAL NOT NULL CHECK (rating >= 0 AND rating <= 10),
    rating_count INTEGER NOT NULL CHECK (rating_count >= 0),
    introduction TEXT NOT NULL,
    source_url TEXT NOT NULL UNIQUE,
    collected_at TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_movies_rating ON movies(rating);
CREATE INDEX IF NOT EXISTS idx_movies_rating_count ON movies(rating_count);

CREATE TABLE IF NOT EXISTS ai_summaries (
    summary_id INTEGER PRIMARY KEY AUTOINCREMENT,
    movie_id INTEGER NOT NULL UNIQUE,
    summary TEXT NOT NULL,
    model_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (movie_id) REFERENCES movies(movie_id)
        ON UPDATE CASCADE ON DELETE CASCADE
);
