import hashlib
from typing import List, Dict, Any

def chunk_text_fixed_size(
    doc_id: str, 
    text: str, 
    chunk_size: int = 500, 
    overlap: int = 50
) -> List[Dict[str, Any]]:
    """
    Разбивает текст на чанки фиксированного размера с перекрытием.
    
    :param doc_id: ID родительского документа
    :param text: Текст документа
    :param chunk_size: Размер чанка в символах
    :param overlap: Размер перекрытия в символах
    :return: Список словарей с чанками
    """
    if not text or not text.strip():
        return []

    chunks = []
    step = chunk_size - overlap
    if step <= 0:
        raise ValueError("Overlap должен быть меньше chunk_size")

    start = 0
    chunk_index = 0
    
    while start < len(text):
        end = start + chunk_size
        chunk_text_part = text[start:end]
        
        # Если остался очень маленький хвост (меньше 10% от чанка), 
        # лучше приклеить его к предыдущему чанку, чтобы не создавать мусор.
        # Но для базовой версии пока просто берем как есть.
        
        # Генерируем уникальный chunk_id
        # Формат: doc_id + индекс, чтобы легко было искать
        chunk_id = f"{doc_id}_c{chunk_index:04d}"
        
        chunk_data = {
            "chunk_id": chunk_id,
            "doc_id": doc_id,
            "text": chunk_text_part,
            "chunk_index": chunk_index,
            "start_char": start,
            "end_char": min(end, len(text)),
            "metadata": {
                "chunking_strategy": "fixed_size",
                "chunk_size": chunk_size,
                "overlap": overlap
            }
        }
        chunks.append(chunk_data)
        
        start += step
        chunk_index += 1

    return chunks