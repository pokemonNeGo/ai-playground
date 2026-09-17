import sys
from pathlib import Path

# Добавляем корневую директорию проекта в пути поиска модулей
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import sqlite3
import json
import logging
from pathlib import Path
from tqdm import tqdm

# Импортируем нашу функцию
from src.chunking.fixed_size import chunk_text_fixed_size

# --- НАСТРОЙКИ ---
DB_PATH = Path("data/processed/ru_wikipedia_5000_normalized.sqlite3")
CHUNK_SIZE = 500   # символов
OVERLAP = 50       # символов
LOG_PATH = Path("data/processed/lab2_1_chunking.log")

# --- ЛОГИРОВАНИЕ ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(LOG_PATH, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def init_db(conn: sqlite3.Connection):
    """Создаёт таблицу chunks, если её нет"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS chunks (
            chunk_id TEXT PRIMARY KEY,
            doc_id TEXT NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            start_char INTEGER NOT NULL,
            end_char INTEGER NOT NULL,
            metadata_json TEXT NOT NULL,
            FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
        )
    """)
    # Индексы для быстрого поиска
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chunks_doc_id ON chunks(doc_id)")
    conn.commit()

def main():
    if not DB_PATH.exists():
        logging.error(f"База данных не найдена по пути {DB_PATH}. Сначала выполни Лаб 1.3!")
        return

    logging.info(f"Начинаем чанкинг. Chunk size: {CHUNK_SIZE}, Overlap: {OVERLAP}")
    
    conn = sqlite3.connect(DB_PATH)
    init_db(conn)
    
    # Очищаем таблицу chunks перед новым прогоном (чтобы не было дублей при перезапуске)
    conn.execute("DELETE FROM chunks")
    conn.commit()

    # Читаем все документы
    cursor = conn.execute("SELECT doc_id, text FROM documents")
    documents = cursor.fetchall()
    
    total_chunks = 0
    
    # Используем tqdm для красивого прогресс-бара
    for doc_id, text in tqdm(documents, desc="Chunking documents"):
        chunks = chunk_text_fixed_size(
            doc_id=doc_id, 
            text=text, 
            chunk_size=CHUNK_SIZE, 
            overlap=OVERLAP
        )
        
        if chunks:
            # Готовим данные для batch insert
            data_to_insert = [
                (
                    c["chunk_id"], 
                    c["doc_id"], 
                    c["chunk_index"], 
                    c["text"], 
                    c["start_char"], 
                    c["end_char"], 
                    json.dumps(c["metadata"], ensure_ascii=False)
                )
                for c in chunks
            ]
            conn.executemany("""
                INSERT INTO chunks (chunk_id, doc_id, chunk_index, text, start_char, end_char, metadata_json)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, data_to_insert)
            total_chunks += len(chunks)
            
    conn.commit()
    conn.close()
    
    logging.info(f"Готово! Создано {total_chunks} чанков из {len(documents)} документов.")
    logging.info(f"Лог сохранен в {LOG_PATH}")

if __name__ == "__main__":
    main()