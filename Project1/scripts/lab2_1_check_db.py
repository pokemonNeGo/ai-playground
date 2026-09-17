import sqlite3
from pathlib import Path

DB_PATH = Path("data/processed/ru_wikipedia_5000_normalized.sqlite3")

def main():
    if not DB_PATH.exists():
        print(f"❌ База данных не найдена: {DB_PATH}")
        return
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("=" * 60)
    print("📊 ПРОВЕРКА РЕЗУЛЬТАТОВ CHUNKING (Лаб 2.1)")
    print("=" * 60)
    
    # 1. Сколько всего чанков?
    print("\n1️⃣ Сколько всего чанков?")
    cursor.execute("SELECT COUNT(*) FROM chunks")
    total_chunks = cursor.fetchone()[0]
    print(f"   Всего чанков: {total_chunks}")
    
    # 2. Сколько документов с чанками?
    print("\n2️⃣ Сколько документов имеют чанки?")
    cursor.execute("SELECT COUNT(DISTINCT doc_id) FROM chunks")
    docs_with_chunks = cursor.fetchone()[0]
    print(f"   Документов с чанками: {docs_with_chunks}")
    
    # 3. Среднее количество чанков на документ
    print("\n3️⃣ Среднее количество чанков на документ:")
    cursor.execute("""
        SELECT AVG(chunk_count) FROM (
            SELECT COUNT(*) as chunk_count 
            FROM chunks 
            GROUP BY doc_id
        )
    """)
    avg_chunks = cursor.fetchone()[0]
    print(f"   Среднее: {avg_chunks:.2f} чанков/документ")
    
    # 4. Топ-5 документов по количеству чанков
    print("\n4️⃣ Топ-5 документов по количеству чанков:")
    cursor.execute("""
        SELECT doc_id, COUNT(*) as chunk_count 
        FROM chunks 
        GROUP BY doc_id 
        ORDER BY chunk_count DESC 
        LIMIT 5
    """)
    top_docs = cursor.fetchall()
    for i, (doc_id, count) in enumerate(top_docs, 1):
        print(f"   {i}. {doc_id}: {count} чанков")
    
    # 5. Пример первого чанка
    print("\n5️⃣ Пример первого чанка:")
    cursor.execute("SELECT * FROM chunks LIMIT 1")
    chunk = cursor.fetchone()
    if chunk:
        print(f"   chunk_id: {chunk[0]}")
        print(f"   doc_id: {chunk[1]}")
        print(f"   chunk_index: {chunk[2]}")
        print(f"   text (первые 100 симв.): {chunk[3][:100]}...")
        print(f"   start_char: {chunk[4]}")
        print(f"   end_char: {chunk[5]}")
    
    # 6. Проверка перекрытия (overlap)
    print("\n6️⃣ Проверка перекрытия между чанками:")
    cursor.execute("""
        SELECT c1.doc_id, c1.chunk_index, c2.chunk_index,
               c1.end_char, c2.start_char,
               c1.end_char - c2.start_char as overlap
        FROM chunks c1
        JOIN chunks c2 ON c1.doc_id = c2.doc_id AND c2.chunk_index = c1.chunk_index + 1
        WHERE c1.end_char > c2.start_char
        LIMIT 3
    """)
    overlaps = cursor.fetchall()
    if overlaps:
        for doc_id, idx1, idx2, end1, start2, overlap in overlaps:
            print(f"   Doc {doc_id}: чанки {idx1}→{idx2}, перекрытие = {overlap} симв.")
    else:
        print("   ⚠️ Перекрытие не обнаружено (возможно, overlap=0)")
    
    print("\n" + "=" * 60)
    print("✅ Проверка завершена!")
    print("=" * 60)
    
    conn.close()

if __name__ == "__main__":
    main()