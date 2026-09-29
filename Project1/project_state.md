📊 Project1 State: RAG End-to-End Pipeline
🎯 Цель проекта
Построить работающий конвейер «документы → ответы с цитатами» для большой базы документов (5000+) и измерить влияние проектных решений на качество поиска и генерации.
Итоговый артефакт: репозиторий с API (FastAPI), схемой архитектуры и таблицами измерений.
📅 Прогресс выполнения
| Лабораторная|Название|Статус|Дата|Ключевые решения|
| ---|---|---|---|---|
| 1.1|Выбор и загрузка корпуса|✅ Выполнена|2026-09-17|Русская Википедия (wikimedia/wikipedia, 20231101.ru), 5000 статей, JSONL|
| 1.2|Парсер документов|✅ Выполнена|2026-09-17|parse() / safe_parse(); regex-очистка wiki-разметки, пустых скобок и пробелов; логирование ошибок в lab1_2_parse_errors.jsonl; распарсено 5000/5000, все маркеры качества = 0|
| 1.3|Нормализация и дедупликация|✅ Выполнена|2026-09-17|Хранение: SQLite; Unicode NFC + нормализация пробелов/переносов; дедупликация по doc_id и full_hash; страницы-неоднозначности удалены; отчёт в lab1_3_dedup_report.json|
| 1.4|Chunking: фиксированный размер|✅ Выполнена|2026-09-17|chunk_size=500 символов, overlap=50 символов (шаг 450); 138 785 чанков из 4910 документов; таблица chunks в SQLite|
| 1.5|Chunking: структурное|✅ Выполнена|2026-09-17|Структурное чанкование по заголовкам/абзацам; таблица  chunks_structural ; сравнение распределения длин со стратегией A|
| 1.6|Эмбеддинги и Qdrant|✅ Выполнена|2026-09-22|Модель BAAI/bge-m3 (локальная копия models/bge-m3, ModelScope), вектор 1024, device cuda; Qdrant Docker (контейнер qdrant, том qdrant_storage), коллекция rag_documents, Cosine; bat ch 32 (смоук) / 128 (полный прогон); загружено 138 785 точек из таблицы chunks|
| 1.7|BM25-индекс|✅ Выполнена|2026-09-22|SQLite FTS5; таблица chunks_fts; search_bm25() top-10; OR-запрос; rebuild-скрипт|
| 1.8|Плотный поиск|✅ Выполнена|2026-09-23|Dense-поиск через Qdrant REST (bge-m3, normalize_embeddings=True), топ-10 по 20 самостоятельным запросам; наблюдения: docs/lab1_8_observations.md; ошибки: ambiguity (q16–q19), chun k_context_loss/precision_noise (короткие чанки без сущности), coverage_gap (q20); top-k первичного поиска = 20 для Лаб 1.9|
| 1.9|Гибридный поиск (RRF)|✅ Выполнена|2026-09-29|RRF поверх BM25 top-20 и dense top-20 (k=60, слияние по chunk_id, только ранги); сравнение bm25/dense/hybrid на 20 запросах Лаб 1.8; ручная разметка топ-10 (600 оценок); метрики: bm25 P@10 0.620 / MRR 0.879, dense 0.805 / 0.917, hybrid 0.745 / 0.975|
| 1.10|Реранкинг|⏳ Не начата|-|-|
| 1.11|Генерация с цитатами|⏳ Не начата|-|-|
| 1.12|Инкрементальное обновление|⏳ Не начата|-|-|
| 1.13|Parent-child чанки|⏳ Не начата|-|-|
| 1.14|Сравнительный эксперимент|⏳ Не начата|-|-|
| 1.15|Итоговая документация|⏳ Не начата|-|-|
🏗 Архитектурные решения
1.1 Источник данных
Корпус: Russian Wikipedia subset, Hugging Face  `wikimedia/wikipedia`
Конфигурация:  `20231101.ru`
Количество документов: 5000
Формат документов: JSON Lines; поля  `doc_id` ,  `title` ,  `text` ,  `source` ,  `date` ,  `metadata`
1.2 Хранилище документов и итоговый формат корпуса
Сырые и промежуточные артефакты
Формат сырого среза: JSONL
Путь к сырому срезу: `data/raw/ru_wikipedia_5000.jsonl`
Статистика Лаб 1.1: `data/processed/lab1_1_corpus_stats.json`
Распарсенный корпус (Лаб 1.2): `data/processed/ru_wikipedia_5000_parsed.jsonl`, 5000 документов, `failed = 0`
Ошибки парсинга (Лаб 1.2): `data/processed/lab1_2_parse_errors.jsonl` (пустой: 0 ошибок)
Статистика Лаб 1.2: `data/processed/lab1_2_parse_stats.json`
Лог Лаб 1.2: `data/processed/lab1_2_parse.log`
Итоговый формат хранения после Лаб 1.3
Решение: используем SQLite как основной формат хранения нормализованного корпуса.
Нормализованный корпус: `data/processed/ru_wikipedia_5000_normalized.sqlite3`
Таблица документов: `documents`
Отчёт о нормализации и дедупликации: `data/processed/lab1_3_dedup_report.json`
Список удалённых дубликатов: `data/processed/lab1_3_duplicates.jsonl`
Список удалённых страниц-неоднозначностей: `data/processed/lab1_3_disambig.jsonl`
Лог Лаб 1.3: `data/processed/lab1_3_normalize.log`
Точное количество документов после дедупликации и фильтрации страниц-неоднозначностей фиксируется в отчёте: `data/processed/lab1_3_dedup_report.json`
Артефакты чанкинга (Лаб 1.4)
Чанки хранятся в той же SQLite-базе, что и документы.
Таблица чанков: `chunks` (в `data/processed/ru_wikipedia_5000_normalized.sqlite3`)
Лог Лаб 1.4: `data/processed/lab1_4_chunking.log`
Артефакты структурного чанкинга (Лаб 1.5)
Чанки стратегии B хранятся в той же SQLite-базе, что и документы.
Таблица чанков: `chunks_structural` (в `data/processed/ru_wikipedia_5000_normalized.sqlite3`)
Лог Лаб 1.5: `data/processed/lab1_5_chunking.log`
Отчёт Лаб 1.5: `data/processed/lab1_5_structural_stats.json`
Сравнение распределения длин: `data/processed/lab1_5_length_comparison.json`
Гистограмма распределения длин: `data/processed/lab1_5_length_histogram.csv`
Почему SQLite
удобно хранить таблицу документов;
можно выполнять SQL-запросы;
легко проверять дубликаты через `GROUP BY`;
не нужен отдельный сервер;
достаточно для корпуса из 5000+ документов;
удобно для дальнейших этапов: chunking, BM25, поиск, анализ.
Parquet рассматривался как альтернатива для колоночной аналитики, но для текущего конвейера важнее простая таблица документов и удобные проверки через SQL.
1.3 Парсер (Лаб 1.2)
Точка входа:  `parse(doc) -> {"text": ..., "metadata": ...}` , файл  `src/ingestion/parser.py`
Безопасная обёртка:  `safe_parse(doc) -> (result | None, error | None)`  — один повреждённый документ не прерывает обработку корпуса
Очистка: wiki-ссылки, шаблоны,  `<ref>` , HTML-теги, URL, пустые скобки вида  `( , , , )` , нормализация пробелов и переносов
Ошибки:  `ParserError`  + логирование в консоль и файл; построчные ошибки пишутся в  `lab1_2_parse_errors.jsonl`
Контроль качества:  `scripts/lab1_2_check_quality.py`
Финальный отчёт по 5000 документов: все маркеры разметки = 0
1.4 Нормализация и дедупликация (Лаб 1.3)
Точки входа:
Модуль нормализации: `src/ingestion/normalize.py`
Основной скрипт: `scripts/lab1_3_normalize_dedup.py`
Проверка SQLite-базы: `scripts/lab1_3_check_db.py`
Тесты: `tests/test_normalize.py`
Назначение этапа:
На этапе Лаб 1.3 распарсенный корпус приводится к единому стандарту, очищается от дубликатов и страниц-неоднозначностей, после чего сохраняется в финальную таблицу документов.
Правила нормализации текста:
Unicode NFC;
нормализация переводов строк: `\r\n` и `\r` приводятся к `\n`;
табуляции заменяются на пробелы;
лишние пробелы внутри строк схлопываются;
пустые строки в начале и конце удаляются;
повторяющиеся пустые строки схлопываются до одного пустого раздела;
регистр сохранённого текста не меняется.
Важное решение:
Текст в таблице `documents` сохраняется в читаемом нормализованном виде, но не переводится полностью в нижний регистр.
Для дедупликации используется отдельное нормализованное представление: lowercase + схлопывание пробельных символов.
Это позволяет находить документы, которые отличаются только регистром и пробелами.
Дедупликация, порядок обработки:
Проверка валидности документа: есть `doc_id`; есть непустой `text`; JSON корректно читается.
Дедупликация по `doc_id`.
Фильтрация страниц-неоднозначностей.
Дедупликация по нормализованному заголовку и тексту.
Ключ контентной дедупликации:
`full_hash = sha256(normalized_title + "\n" + normalized_text_for_hash)`
где `normalized_text_for_hash` — текст в нижнем регистре со схлопнутыми пробелами.
Страницы-неоднозначности определяются эвристически.
Маркеры:
в заголовке есть `(значения)`;
в начале текста встречаются фразы: `может означать`; `многозначное слово`; `многозначное понятие`; `список значений`.
Поведение по умолчанию:
Страницы-неоднозначности удаляются из финального корпуса.
Список удалённых страниц сохраняется в: `data/processed/lab1_3_disambig.jsonl`
Это позволяет проверить, какие документы были удалены, и при необходимости смягчить или ужесточить эвристики.
Итоговая таблица: `documents`
Поля таблицы:
| Поле|Назначение|
| ---|---|
| doc_id|уникальный идентификатор документа|
| title|нормализованный заголовок|
| text|нормализованный очищенный текст|
| source|источник|
| date|дата, если есть; в текущем срезе часто отсутствует|
| text_chars|количество символов|
| text_words|приблизительное количество слов через  .split()|
| title_norm_hash|sha256 от нормализованного заголовка|
| text_norm_hash|sha256 от нормализованного текста|
| full_hash|sha256 от связки заголовок + текст|
| is_disambig|флаг страницы-неоднозначности|
| metadata_json|JSON с метаданными, включая блок normalization|
Контроль качества Лаб 1.3:
python scripts/lab1_3_check_db.py
Скрипт показывает:
количество документов;
количество документов с `is_disambig = 1`;
количество дублирующихся `full_hash`;
минимальную, максимальную и среднюю длину текста;
примеры документов.
Ожидаемое состояние при настройке `REMOVE_DISAMBIG = True`:
disambig_in_table = 0
duplicate_full_hashes = 0
1.5 Chunking стратегии
Стратегия A (фиксированный размер) — Лаб 1.4 ✅
Размер чанка: 500 символов
Перекрытие (overlap): 50 символов
Шаг между началами чанков: chunk_size − overlap = 450 символов
Единица измерения: символы. Решение: для первой итерации  выбрано простое «скользящее окно» по символам; переход к токенам возможен в Лаб 1.6 при необходимости.
Формат chunk_id:  `{doc_id}_c{chunk_index:04d}`  (например,  `7_c0000` )
Точка входа:  `chunk_text_fixed_size()`  в  `src/chunking/fixed_size.py`
Скрипт обработки:  `scripts/lab1_4_chunk_corpus.py`
Скрипт проверки:  `scripts/lab1_4_check_db.py`
Тесты:  `tests/test_chunking.py`  (4 теста)
Результат: 138 785 чанков из 4910 документов; среднее 28.27 чанков/документ; перекрытие между соседними чанками проверено и равно 50 символам.
Стратегия B (структурное) — Лаб 1.5 ✅
Метод разбиения: по заголовкам/абзацам; длинные блоки дополнительно режутся по предложениям, затем по пробелам
Максимальный размер чанка: 500 символов
Перекрытие (overlap): 0 симво лов
Единица измерения: символы
Формат chunk_id:  `{doc_id}_s{chunk_index:04d}`  (например,  `7_s0000` )
Точка входа:  `chunk_text_structural()`  в  `src/chunking/structural.py`
Скрипт обработки:  `scripts/lab1_5_chunk_structural.py`
Скрипт проверки:  `scripts/lab1_5_check_db.py`
Скрипт сравнения:  `scripts/lab1_5_compare_chunks.py`
Тесты:  `tests/test_chunking_structural.py`
Результат: таблица  `chunks_structural`  в той же SQLite-базе; выполнено сравнение распределения длин со стратегией A.
Parent-child (Лаб 1.13)
Parent chunk size: [определится]
Child chunk size: [определится]
1.6 Эмбеддинги
Модель: BAAI/bge-m3 через sentence-transformers; веса — локальная копия models/bge-m3 (источник ModelScope из-за троттлинга HF)
Размерность вектора: 1024
Batch size для обработки: 32 по умолчанию (.env); полный прогон — 128 (аргумент --batch-size)
Нормализация векторов: normalize_embeddings=True
Префиксы passage:/query: не используются (bge-m3)
Устройство: cuda (NVIDIA GeForce RTX 3060 Laptop GPU, сборка torch CUDA 12.6)
Что эмбеддится: только chunks.text; title/source хранятся в payload, в вектор не подмешиваются
Модуль: src/indexing/embeddings.py
Скрипт загрузки: scripts/lab1_6_embed_qdrant.py
Отчёт: data/processed/lab1_6_embedding_report.json
Лог: data/processed/lab1_6_embedding.log
1.7 Векторная база данных
Тип: Qdrant
Способ запуска: Docker, контейнер qdrant, том qdrant_storage, порт 6333
Название коллекции: rag_documents
Метрика сходства: Cosine
Point id: детерминированный uuid5 от chunk_id (повторный апсерт обновляет точки, дубли не создаются)
Payload точки: chunk_id, doc_id, title, source, chunk_index, start_char, end_char, text, chunking_strategy, chunk_metadata, embedding_model, embedded_at
Модуль: src/indexing/qdrant_index.py
Проверка: scripts/lab1_6_check_qdrant.py (поиск через REST POST /points/search)
1.8 Текстовый поиск (BM25)
Реализация: SQLite FTS5 внутри той же SQLite-базы, что и таблица  `chunks` .
Источник индексации: таблица  `chunks`  (стратегия fixed_size, Лаб 1.4).
FTS-таблица:  `chunks_fts`  (виртуальная таблица FTS5 в  `data/processed/ru_wikipedia_5000_normalized.sqlite3` ).
Токенизация:  `unicode61` ; русской лемматизации нет, поиск совпадает по словоформам запроса.
Подготовка запроса: текст нижним регистром, пунктуация отбрасывается, запрос превращается в безопасный FTS5-вид  `"слово1" OR "слово2" OR "слово3"`  (OR — чтобы многословные запросы не давали пустую выдачу; документы со всеми словами запроса ранжируются выше).
Точка входа:  `search_bm25(query, top_k=10)`  в  `src/indexing/bm25_index.py` .
Обёртка топ-10 (требование лабы):  `search_bm25_top10(query)` .
Поля результата:  `chunk_id` ,  `doc_id` ,  `text` ,  `start_char` ,  `end_char` ,  `score` .
Семантика скора:  `bm25()`  в FTS5 возвращает отрицательные значения; чем МЕНЬШЕ score, тем выше релевантность (учесть при слиянии с dense-поиском в Лаб 1.9).
Сборка индекса:  `scripts/lab1_7_build_bm25.py`  (DROP + CREATE + INSERT … SELECT + optimize; идемпотентно).
Проверка доступности FTS5:  `scripts/lab1_7_check_fts5.py` .
Проверка индекса:  `scripts/lab1_7_check_bm25.py`  (совпадение числа строк  `chunks`  и  `chunks_fts` , тестовый запрос).
Ручной поиск:  `scripts/lab1_7_search_bm25.py "запрос" --top-k 10` .
Тесты:  `tests/test_bm25.py` .
Отчёт:  `data/processed/lab1_7_bm25_report.json` ; лог:  `data/processed/lab1_7_bm25.log` .
1.8b Плотный поиск (Лаб 1.8)
Реализация:  `src/retrieval/dense_search.py`  — класс  `DenseSearcher` : эмбеддинг запроса BAAI/bge-m3 ( `normalize_embeddings=True` , без префиксов) + поиск через Qdrant REST  `POST /collections/{collection}/points/search`  (не зависит от версии qdrant-client).
Точка входа:  `DenseSearcher.search(query, top_k)`  → список  `DenseHit`  (rank, chunk_id, doc_id, title, text, score, chunk_index, start_char, end_char) + latency в мс.
Скрипт batch-прогона:  `scripts/lab1_8_dense_search.py`  ( `--queries` ,  `--query` ,  `--out` ,  `--report` ,  `--top-k` ,  `--limit` ).
Скрипт подбора тем по SQLite:  `scripts/lab1_8_find_titles.py`  (LIKE-поиск по  `documents.title` ).
Запросы:  `data/processed/lab1_8_queries.jsonl`  — 20 самостоятельно составленных запросов (5 factual, 5 paraphrase, 5 exact_fact, 4 ambiguous + 1 coverage_gap); темы проверены по корпусу через  `lab1_8_find_titles.py` .
Результаты:  `data/processed/lab1_8_dense_results.jsonl`  (20 строк × топ-10),  `data/processed/lab1_8_dense_report.json` .
Наблюдения:  `docs/lab1_8_observations.md`  — ручной просмотр топ-10, шкала релевантности 2/1/0, типы ошибок, подробные кейсы.
Семантика скора: Cosine в Qdrant, выше score = ближе вектор; высокий score не гарантирует наличи е ответа в чанке.
Ключевые выводы Лаб 1.8:
фактографические запросы и перефразы без лексических совпадений: релевантный документ в рангах 1–3;
короткие однословные запросы (q16–q18 «Волга»/«Марс»/«Пифагор»): ошибка дизамбигуации сущности, поиск выбирает «семантически близкое», а не нужную сущность;
узкий запрос против широкой статьи (q19 «Ленин в Париже»): общая статья вытесняет узкую (`precision_noise`);
q20 («Конституция Российской Федерации»): статьи нет в корпусе — `coverage_gap`, а не ошибка поиска;
сверхкороткие «хвостовые» чанки без сущности получают завышенный косинус (смоук-кейс: запрос «Пушкин» → ранг 1 чанк « Достоевский» из статьи о музее Достоевского);
решение для Лаб 1.9: top-k первичного поиска = 20 (факты закрываются топ-10, неоднозначным запросам нужен запас).
1.9 Retrieval параметры
Top-k для первичного поиска: 20 (определён в Лаб 1.8: фактографические запросы закрываются топ-10, неоднозначным нужен запас; ручной просмотр топ-10 выполнен в Лаб 1.8)
Top-k после реранкинга: [определится в Лаб 1.10]
Метод гибридного поиска: RRF (Reciprocal Rank Fusion)
RRF k параметр: 60 (подтверждён в Лаб 1.9; смешиваются только ранги, сырые скоры BM25 и dense не нормализуются)
1.9b Гибридный поиск (Лаб 1.9)
Реализация: `src/retrieval/hybrid_search.py` — `rrf_scores()` / `fuse_rrf()`; идентификатор слияния `chunk_id`; сырые скоры не смешиваются (BM25 отрицательный, dense cosine), используются только ранги.
Скрипты: `scripts/lab1_9_hybrid_search.py` (прогон: BM25 top-20 + dense top-20 → RRF top-20), `scripts/lab1_9_fill_manual.py` (простановка relevance из разметки), `scripts/lab1_9_eval_manual.py` (P@5/P@10/MRR по ручной разметке).
Тесты: `tests/test_hybrid_rrf.py` (4 теста).
Параметры: RRF k = 60 (подтверждён), top-k первичного поиска = 20, eval top-k = 10.
Артефакты: `data/processed/lab1_9_hybrid_results.jsonl`, `lab1_9_hybrid_report.json`, `lab1_9_comparison_summary.csv`, `lab1_9_comparison_details.csv`, `lab1_9_manual_template.csv`, `lab1_9_manual_scores.csv`, `lab1_9_metrics.csv`, `lab1_9_metrics_by_query.csv`, `lab1_9_metrics.md`; наблюдения: `docs/lab1_9_observations.md`.
Результат (20 запросов, ручная разметка топ-10 трёх методов, шкала 2/1/0, релевантно >= 1): bm25 P@5 0.660 / P@10 0.620 / MRR 0.879; dense P@5 0.900 / P@10 0.805 / MRR 0.917; hybrid P@5 0.860 / P@10 0.745 / MRR 0.975.
Ключевые кейсы: q16/q17 — hybrid снимает ошибку dense на ранге 1 (короткие чанки «Герб»/«Бестиарий»); q12 — цена RRF: чанк из средних рангов обоих списков обошёл одиночный топ-1; q07/q15 — когда один метод идеален, смешивание снижает P@10.
1.10 Реранкинг
Модель: [кросс-энкодер — определится в Лаб 1.10]
1.11 LLM для генерации
Провайдер: [Groq/Ollama/OpenAI — определится в Лаб 1.11]
Модель: [определится]
Temperature: [определится, обычно 0.1-0.3 для RAG]
Max tokens: [определится]
📁 Структура проекта
Весь курс живёт в одном репозитории. В нём есть тренировочные лабораторные (`lab01`–`lab03`) и основные проекты (на данный момент `Project1`).
Общие для всего репозитория: `.venv`, `.gitignore`, `README.md`.
Все пути в этом файле дальше считаются относительно папки `Project1/`.
ai-playground/
├── .venv/                      # общее виртуальное окружение для всех лаб (в Git не хранится)
├── .gitignore                  # общие правила игнорирования
├── README.md                   # общий README
│
├── lab01/                      # тренировочная лаба 1
├── lab02/                      # тренировочная лаба 2
├── lab03/                      # тренировочная лаба 3
│
└── Project1/                   # Основной проект 1
  ├── project_state.md        # этот файл, состояние проекта (хранится в Git)
  ├── .env                       # API-ключи (появится в Лаб 1.6/1.11; в Git не хранится)
  │
  ├── models/                   # локальные веса моделей (bge-m3); в Git не хранится (правило models/)
  ├── data/                       # ВСЯ папка не хранится в Git (правило data/ в .gitignore)
│   ├── raw/                # сырые документы
│   │   └── ru_wikipedia_5000.jsonl                # Лаб 1 .1 ✅
│   │
│   └── processed/          # обработанные данные и статистика
│       ├── lab1_1_corpus_stats.json               # Лаб 1.1 ✅
│       ├── ru_wikipedia_5000_parsed.jsonl          # Лаб 1.2 ✅
│       ├── lab1_2_parse_errors.jsonl              # Лаб 1.2 ✅ (пустой)
│       ├── lab1_2_parse_stats.json                # Лаб 1.2 ✅
│       ├── lab1_2_parse. log                       # Лаб 1.2 ✅
│       ├── ru_wikipedia_5000_normalized.sqlite3   # Лаб 1.3, 1.4, 1.5, 1.7 ✅ (documents + chunks + chunks_structural + chunks_fts)
│       ├─ ─ lab1_3_dedup_report.json               # Лаб 1.3 ✅
│       ├── lab1_3_duplicates.jsonl                # Лаб 1.3 ✅
│       ├── lab1_3_disambig.jsonl                  # Лаб 1.3 ✅
        ├── lab1_3_normalize.log                   # Лаб 1.3 ✅
│       ├── lab1_4_chunking.log                    # Лаб 1.4 ✅
│       ├── lab1_5_chunking.log                    # Ла б 1.5 ✅
│       ├── lab1_5_structural_stats.json           # Лаб 1.5 ✅
│       ├── lab1_5_length_comparison.json          # Лаб 1.5 ✅
│       ├── lab1_5_length_histogram.csv             # Лаб 1.5 ✅
│       ├── lab1_6_embedding.log                   # Лаб 1.6 ✅
│       ├── lab1_6_embedding_report.json           # Лаб 1.6 ✅
│       ├── lab1_7_bm25_report.json                 # Лаб 1.7 ✅
│       ├── lab1_7_bm25.log                        # Лаб 1.7 ✅
│       ├── lab1_8_queries.jsonl                   # Лаб 1.8 ✅
│       ├── lab1_8_dense_res ults.jsonl             # Лаб 1.8 ✅
│       └── lab1_8_dense_report.json               # Лаб 1.8 ✅
│       ├── lab1_9_hybrid_results.jsonl            # Лаб 1.9 ✅
│       ├── lab1_9_hybrid_report.json              # Лаб 1.9 ✅
│       ├── lab1_9_comparison_summary.csv          # Лаб 1.9 ✅
│       ├── lab1_9_comparison_details.csv          # Лаб 1.9 ✅
│       ├── lab1_9_manual_template.csv             # Лаб 1.9 ✅
│       ├── lab1_9_manual_scores.csv               # Лаб 1.9 ✅
│       ├── lab1_9_analys.json                     # Лаб 1.9 ✅ (исходник экспертных оценок)
│       ├── lab1_9_metrics.csv                     # Лаб 1.9 ✅
│       ├── lab1_9_metrics_by_query.csv            # Лаб 1.9 ✅
│       └── lab1_9_metrics.md                      # Лаб 1.9 ✅
│
├── notebooks/              # ноутбуки лабораторных
│   ├── lab1_1_corpus_explor ation.ipynb            # Лаб 1.1 ✅
│   ├── lab1_8_search_analysis.ipynb               # Лаб 1.8 (позже, опционально)
│   └── lab1_14_comparison.ipynb                   # Лаб 1.14 ( позже)
│
├── src/                    # исходный код (хранится в Git)
│   ├──  init .py                              # Лаб 1.2 ✅
│   ├── ingestion/
│   │   ├──  init .py                          # Лаб 1.2 ✅
│   │   ├── parser.py                            # Лаб 1.2 ✅
│   │   └── normalize.py                         # Лаб 1.3 ✅
│   ├── chunking/             # fixed_size.py, structural.py, parent_child.py (Лаб 1.4-1.5, 1.13)
│   │   ├──  init .py                          # Лаб 1.4 ✅
│   │   ├── fixed_size.py                        # Лаб 1.4 ✅
│   │   └── structural.py                        # Лаб 1.5 ✅
│   ├── indexing/             # embeddings.py, qdrant_index.py, bm25_index.py (Лаб 1.6-1.7)
│   │   ├──  init .py                          # Лаб 1.6 ✅
│   │   ├── embeddings.py                        # Лаб 1.6 ✅
│   │   ├── qdrant_index.py                      # Лаб 1.6 ✅
│   │   └── bm25_ index.py                        # Лаб 1.7 ✅
│   ├── retrieval/           # dense_search.py, hybrid_search.py, reranker.py (Лаб 1.8-1.10)
│   │   ├──  init .py                          # Лаб 1.8 ✅
│   │   └── dense_search.py                      # Лаб 1.8 ✅
│   │   └── hybrid_search.py                     # Лаб 1.9 ✅
│   ├── generation/         # llm_generator.py (Лаб 1.11)
│   └── api/                  # main.py (FastAPI, Лаб 1.15)
│
├── scripts/                # хранится в Git
│   ├── lab1_2_parse_corpus.py                   # Лаб 1.2 ✅
│   ├── lab1_2_check_quality.py                   # Лаб 1.2 ✅
│   ├── lab1_3_normalize_dedup.py                # Лаб 1.3 ✅
│   ├── lab1_3_check_db.py                       # Лаб 1.3 ✅
│   ├── lab1_4_chunk_corpus.py                    # Лаб 1.4 ✅
│   ├── lab1_4_check_db.py                       # Лаб 1.4 ✅
│   ├── lab1_5_chunk_structural.py               # Лаб 1.5 ✅
│   ├── lab1_5_check_db.py                       # Лаб 1.5 ✅
│   ├── lab1_5_compare_chunks.py                 # Лаб 1.5 ✅
│   ├── lab1_6_embed_qdrant.py                   # Лаб 1.6 ✅
│   ├── lab1_6_check_qdrant.py                   # Лаб 1.6 ✅
│   ├── lab1_7_build_bm25.py                     # Лаб 1.7 ✅
│   ├── lab1_7_check_fts5.py                     # Лаб 1.7 ✅
│   ├── lab1_7_check_bm25.py                     # Лаб 1.7 ✅
│   ├── lab1_7_search_bm25.py                    # Лаб 1.7 ✅
│   ├── lab1_8_dense_search.py                   # Лаб 1.8 ✅
│   └── lab1_8_find_titles.py                    # Лаб 1.8 ✅
│   ├── lab1_9_hybrid_search.py                  # Лаб 1.9 ✅
│   ├── lab1_9_fill_manual.py                    # Лаб 1.9 ✅
│   └── lab1_9_eval_manual.py                    # Лаб 1.9 ✅
│
├── tests/                  # хранится в Git
│   ├── test_parser.py                            # Лаб 1.2 ✅ (8 тестов)
│   ├── test_norm alize.py                         # Лаб 1.3 ✅ (6 тестов)
│   ├── test_chunking.py                          # Лаб 1.4 ✅ (4 теста)
│   ├── test_chunking_structural.py               #  Лаб 1.5 ✅
│   ├── test_indexing_helpers.py                  # Лаб 1.6 ✅ (5 тестов)
│   └── test_bm25.py                              # Лаб 1.7 ✅
│   └── test_hybrid_rrf.py                        # Лаб 1.9 ✅
│
└── docs/                   # док ументация и схема архитектуры (Лаб 1.15)
└── lab1_8_observations.md                    # Лаб 1.8 ✅ (наблюдения: где ошибается плотный поиск)
└── lab1_9_observations.md                    # Лаб 1.9 ✅ (hybrid vs bm25 vs dense: метрики и кейсы)
📦 Установленные библиотеки
Core
 Python: 3.14
 FastAPI: [версия] — для API
 Uvicorn: [версия] — ASGI сервер
ML & NLP
 sentence-transformers: 6.1.0 — для эмбеддингов (использована в Лаб 1.6 и Лаб 1.8)
 rank-bm25: [версия] — для текстового поиска
 transformers: [версия] — для реранкера
 torch: 2.14.0+cu126 — PyTorch backend (сборка CUDA 12.6, torch.cuda.is_available()=True, Лаб 1.6)
Vector DB
 qdrant-client: 1.19.1 — клиент Qdrant (Лаб 1.6; метод search() в этой версии удалён, проверка поиска выполнена через REST)
 Data Processing
 datasets: [версия] — загрузка HuggingFace datasets (использовалась в Лаб 1.1)
 pandas: [версия] — обработка данных (использовалась в Лаб 1.1)
 numpy: [версия] — численные операции
 pyarrow: [версия] — бэкенд для pandas/datasets
Standard Library
 Для Лаб 1.3 новые внешние зависимости не добавлялись.
 Использованы стандартные модули:
 json, sqlite3, hashlib, re, unicodedata, pathlib, datetime
 Для Лаб 1.4 новые внешние зависимости не добавлялись.
 Использованы стандартные модули:
 sqlite3, json, logging, pathlib, typing
 Для Лаб 1.5 новые внешние зависимости не добавлялись.
 Использованы стандартные модули:
 re, sqlite3, json, logging, pathlib, statistics, csv, datetime, typing, dataclasses
 Для Лаб 1.7 новые внешние зависимости не добавлялись.
 BM25 реализован средствами SQLite FTS5; библиотека rank-bm25 не использовалась.
 Использованы стандартные модули: sqlite3, re, os, json, logging, pathlib, datetime, typing, argparse.
 Для Лаб 1.8 новые внешние зависимости не добавлялись.
 Dense-поиск реализован через Qdrant REST стандартными модулями:
 urllib.request, urllib.error, json, time, os, logging, pathlib, argparse, dataclasses, typing
 Плюс уже установленные: python-dotenv (чтение .env), sentence-transformers (эмбеддинг запроса).
Utilities
 python-dotenv: [версия] — переменные окружения
 tqdm: [версия] — прогресс-бары (использовалась в Лаб 1.1, Лаб 1.4 и Лаб 1.6)
 modelscope: [версия] — загрузка весов bge-m3 с ModelScope в локальную папку models/bge-m3 (Лаб 1.6)
 matplotlib/seaborn: [версия] — визуализация
 pydantic: [версия] — валидация данных
 jupyter: [версия] — для работы с notebooks
 Testing
 pytest: [версия] — юнит-тесты (добавлена в Лаб 1.2)
🔐 Переменные окружения (.env)
 ```env
 # Qdrant
 QDRANT_MODE=server
 QDRANT_HOST=localhost
 QDRANT_PORT=6333
 QDRANT_COLLECTION=rag_documents
 # LLM Provider (Groq/Ollama/OpenAI)
 LLM_PROVIDER=groq
 LLM_API_KEY=your_api_key_here
 LLM_MODEL=llama-3.1-70b-versatile
 # Embedding Model
 EMBEDDING_MODEL=models/bge-m3
 EMBEDDING_DEVICE=cuda
 EMBEDDING_BATCH_SIZE=32
 # Paths
 DATA_DIR=./data
 MODELS_DIR=./models
 DB_PATH=data/processed/ru_wikipedia_5000_normalized.sqlite3
 CHUNKS_TABLE=chunks
📊 Схемы данных
Document Schema (Лаб 1.1-1.2, сырой распарсенный JSONL)
Реализована в Лаб 1.2: документы в `data/processed/ru_wikipedia_5000_parsed.jsonl` соответствуют этой схеме.
Особенности:
`date` часто null (особенность среза);
в `metadata` добавлен блок `parser`: `{"lab", "version", "text_chars"}`.
{
  "doc_id": "str",
  "title": "str",
  "text": "str",
  "source": "str",
  "date": "str | null",
  "metadata": {}
}
Normalized Document Schema (Лаб 1.3, SQLite)
Нормализованный корпус хранится в: `data/processed/ru_wikipedia_5000_normalized.sqlite3`
Таблица: `documents`
SQL-схема:
CREATE TABLE documents (
    doc_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    text TEXT NOT NULL,
    source TEXT,
    date TEXT,
    text_chars INTEGER NOT NULL,
    text_words INTEGER NOT NULL,
    title_norm_hash TEXT NOT NULL,
    text_norm_hash TEXT NOT NULL,
    full_hash TEXT NOT NULL,
    is_disambig INTEGER NOT NULL DEFAULT 0,
    metadata_json TEXT NOT NULL
);
Дополнительные индексы:
CREATE INDEX idx_documents_title ON documents(title);
CREATE INDEX idx_documents_full_hash ON documents(full_hash);
Поле `metadata_json` содержит исходные метаданные документа и блок `normalization`:
{
  "normalization": {
    "lab": "1.3",
    "normalized_at": "timestamp",
    "title_norm_hash": "sha256",
    "text_norm_hash": "sha256",
    "full_hash": "sha256",
    "is_disambig": false
  }
}
Chunk Schema (Лаб 1.4-1.5)
Реализовано в Лаб 1.4 (Стратегия A) и Лаб 1.5 (Стратегия B): чанки хранятся в таблицах `chunks` и `chunks_structural` в той же SQLite-базе, что и документы.
SQL-схема:
CREATE TABLE chunks (
    chunk_id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    chunk_index INTEGER NOT NULL,
    text TEXT NOT NULL,
    start_char INTEGER NOT NULL,
    end_char INTEGER NOT NULL,
    metadata_json TEXT NOT NULL,
    FOREIGN KEY (doc_id) REFERENCES documents(doc_id)
);
Дополнительный индекс:
CREATE INDEX idx_chunks_doc_id ON chunks(doc_id);
Поле `metadata_json` чанка содержит параметры стратегии:
{
  "chunking_strategy": "fixed_size",
  "chunk_size": 500,
  "overlap": 50
}
JSON-схема чанка:
{
  "chunk_id": "str",
  "doc_id": "str",
  "text": "str",
  "chunk_index": 0,
  "start_char": 0,
  "end_char": 0,
  "metadata": {}
}
Для таблицы  `chunks_structural`  обязательными являются поля  `chunk_id` ,  `doc_id` ,  `chunk_index` ,  `text` ,  `start_char` ,  `end_char` , а также метаданные структурного чанкования (например,  `heading_path`  и параметры  `max_chars`  /  `overlap` ).
BM25/FTS5 Schema (Лаб 1.7)
Виртуальная таблица полнотекстового поиска в той же SQLite-базе:
CREATE VIRTUAL TABLE chunks_fts
USING fts5(
    text,
    chunk_id UNINDEXED,
    doc_id UNINDEXED,
    tokenize='unicode61'
);
Колонки заполняются из `chunks` при сборке индекса; источник текста и координат при поиске — таблица `chunks` (JOIN по `chunk_id`).
Parent-Child Schema (Лаб 1.13)
{
  "parent_chunk_id": "str",
  "child_chunk_ids": [],
  "parent_text": "str",
  "child_texts": []
}
📈 Метрики и измерения
Retrieval Quality (Лаб 1.8-1.10)
Precision@k: измерена вручную в Лаб 1.8 (топ-10, 20 запросов, шкала 2/1/0) — значения в docs/lab1_8_observations.md; автоматически — в Лаб 1.14
Recall@k: [измерится]
MRR (Mean Reciprocal Rank): измерен вручную в Лаб 1.8 (ранг первого релевантного результата по каждому запросу) — значения в docs/lab1_8_observations.md
Lab 1.9 (hybrid search, manual markup of top-10 for three methods, 20 queries, scale 2/1/0, relevant >= 1): bm25 P@5 0.660 / P@10 0.620 / MRR 0.879; dense P@5 0.900 / P@10 0.805 / MRR 0.917; hybrid P@5 0.860 / P@10 0.745 / MRR 0.975; summary table — data/processed/lab1_9_metrics.md, per-query — data/processed/lab1_9_metrics_by_query.csv
Generation Quality (Лаб 1.11)
Faithfulness: [оценка — ответы только по контексту]
Answer Relevance: [оценка — релевантность ответа вопросу]
Context Relevance: [оценка — релевантность контекста]
Performance
Latency (search): dense-поиск ~40–60 мс/запрос (REST, RTX 3060 Laptop GPU) — см. data/processed/lab1_8_dense_report.json
Latency (generation): [мс]
Cost per query: [$]
⚠️ Известные проблемы и ограничения
Поле  `date`  в текущем срезе Википедии пустое, так как в снапшоте  `20231101.ru`  не хранятся даты публикации/редактирования конкретных статей.
Подсчёт слов выполнен простым методом  `.split()` , что даёт приблизительную оценку. Для точной токенизации потребуется отдельная библиотека ( `tiktoken`  /  `huggingface tokenizers` ) в следующих лабораторных.
В корпусе присутствовали страницы-неоднозначности («Волга может означать: …»). В Лаб 1.3 они фильтруются эвристически и по умолчанию удаляются из финаль ного корпуса. Список удалённых страниц сохраняется в  `data/processed/lab1_3_disambig.jsonl` .
Эвристики для страниц-неоднозначностей могут давать как ложные срабатывания, так и пропуски. При необходимости правила можно уточнить в  `src/ingestion/normalize.py` .
Очистка wiki-разметки выполнена регулярными выражениями с fallback-проходами для вложенных конструкций; остаточные маркеры по отчёту равны 0, но теоретически особо сложная вложен ность может вычищаться с потерей окружающего текста — контролируется тестами и  `scripts/lab1_2_check_quality.py` .
В Лаб 1.3 выполняется точная дедупликация по  `doc_id`  и  `full_hash` . Near-duplicate-документы с незначительными текстовыми отличиями на этом этапе не выявляются.
Статистики лабораторных и артефакты в  `data/`  не хранятся в Git из-за правила  `data/`  в  `.gitignore` ; при потере локальных файлов они пересоздаются повторным запуском соответствующих скриптов.
Итоговый корпус хранится в SQLite. Файл  `*.sqlite3`  не коммитится в Git, но воспроизводится командой:  `python scripts/lab1_3_normalize_dedup.py`
Чанкинг Лаб 1.4 выполнен в символах, а не в токенах: границы чанков не совпадают с границами токенов эмбеддинг-модели. При необходимости переход на токен-окна планируется в Лаб 1. 6.
Фиксированный размер чанка может разрывать предложения и смысловые блоки на границах; перекрытие 50 символов частично компенсирует это. Структурное чанкование реализовано в Лаб  1.5 как альтернатива; его влияние оценивается по распределению длин и дальнейшему поиску.
Структурный чанкер может не находить явные заголовки, если они были удалены парсером; в эт ом случае текст разбивается по абзацам и предложениям.
Анонимные загрузки с Hugging Face троттлились до ~0.2–0.7 МБ/с; веса bge-m3 загружены с ModelScope в локальную папку models/b ge-m3, в .gitignore добавлено правило models/.
qdrant-client 1.19.1: метод search() удалён, вызов query_points() с именованным collection_name в этой сборке нестабилен; проверочный  поиск в scripts/lab1_6_check_qdrant.py выполнен через REST POST /collections/{name}/points/search, что не зависит от версии клиента.
Кеш Hugging Face на Windows без Developer Mode  работает без symlinks (degraded-режим) — влияет только на расход места на диске, на результат не влияет.
BM25 (Лаб 1.7): токенизатор unicode61 не лемматизирует русский текст, запр осы объединяются через OR; индекс пересоздаётся полностью при каждом запуске scripts/lab1_7_build_bm25 (инкрементальность — задача Лаб 1.12); доступность FTS5 зависит от сборки SQL ite и проверяется scripts/lab1_7_check_fts5.py.
Лаб 1.8: сверхкороткие «хвостовые» чанки (десятки символов, например « Достоевский») получают завышенное косинусное сходство с общим и запросами и могут вытеснять целевую статью из топ-10; кандидаты на решение: фильтр минимальной длины чанка, реранкер (Лаб 1.10), добавление title в эмбеддинг.
Лаб 1.8: в текстах  чанков (payload) встречаются остаточные неразрывные пробелы  `\xa0`  и следы очистки wiki-разметки (например, «(Москва — , Санкт-Петербург)»); на dense-поиск влияет не критично, зафиксировано в наблюдениях как артефакт качества данных.
🎓 Ключевые инсайты
Загрузка больших датасетов через  `streaming=True`  позволяет работать с корпусами без полного скачивания их на диск.
Дедупликация по  `doc_id`  и  `title`  на этапе загрузки критична: в дампах Википедии часто встречаются страницы-редиректы и дубликаты.
Фильтрация по минимальной длине ( `MIN_CHARS = 300` ) отсекает служебные страницы и слишком короткие заготовки.
После удаления wiki-ссылок и шаблонов в тексте остаются «пустые» скобки вида  `( , , , )` ; добавлена пост-очистка пустых скобок и fallback для вложенных конструкций, после чего все маркеры разметки в отчёте качества равны 0.
Паттерн  `safe_parse()`  с возвратом  `(result, error)`  позволяет не ронять весь прогон корпуса из-за одного битого документа и копить все ошибки в отдельный JSONL для разбора.
Автоматический отчёт маркеров разметки ( `scripts/lab1_2_check_quality.py` ) находит артефакты парсера, которые легко пропустить при ручном просмотре файла.
Для нормализации важно разделять два представления: читаемый нормализованный текст для хранения и  нижнеуровневый нормализованный текст для дедупликации.
Дедупликация по  `full_hash`  даёт детерминированный и быстрый способ удалить полные дубликаты документов.
Страницы-неоднозначности лучше удалять до этапа чанкинга и индексации, чтобы не загрязнять поиск корот кими перечислениями значений.
Для корпуса из 5000+ документов SQLite является достаточно простым и удобным форматом хранения: не требует внешней инфраструктуры и позволяет легко пр оверять целостность таблицы через SQL.
Перекрытие (overlap) между соседними чанками сохраняет контекст на границах: проверка по  `start_char`  /  `end_char`  подтвердила ровно 50 символов пересечения между соседними чанками.
Хранение  `start_char`  /  `end_char`  в чанке позволяет детерминированно проверять перекрытие и позже восстанавливать точную позицию найденного фрагмента в исходном документе (пригодится для цитат в Лаб 1.11).
Пакетна я вставка через  `executemany`  значительно ускоряет запись десятков тысяч чанков в SQLite по сравнению с построчным  `execute` .
Хранение чанков в той же SQLite-базе, что и документы (с внешним ключом по  `doc_id` ), сохраняет связность «документ → чанки» без дополнительной инфраструктуры.
Структурное чанкование лучше сохраняет границы абзацев и заголовков, но распределение длин становится м енее равномерным; это нормально и требует сравнения с фиксированной стратегией.
Детерминированный point id (uuid5 от chunk_id) делает перезагрузку коллекции идемпотентной: повторны й прогон обновляет те же точки, а не создаёт дубли.
Узкое место пакетной загрузки при малых батчах — не GPU, а накладные расходы upsert: при batch 32 throughput ~47 чанков/с, укруп нение батча до 128 кратно ускоряет полный прогон.
Локальная копия весов модели (models/bge-m3) полностью убирает сетевую зависимость конвейера: все последующие запуски стартуют без  обращений к Hugging Face.
Проверка поиска через REST-эндпоинт Qdrant вместо клиентского метода защищает лабораторные от смены API qdrant-client между версиями.
Хранение BM25-индек са виртуальной таблицей FTS5 в той же SQLite-базе убирает отдельный индекс-файл и сохраняет воспроизводимость одним скриптом.
bm25() в FTS5 отрицательный и «меньше = лучше» — эту и нверсию легко потерять при слиянии рангов в гибридном поиске.
Ценность dense-поиска подтверждена на перефразах: релевантность держится на смысле, а не на совпадении словоформ (Лаб  1.8).
Главный предел dense-поиска — не качество векторов, а неоднозначность запроса и отсутствие сущности в коротком чанке; это лечится реранкером (Лаб 1.10) и parent-child (Лаб 1. 13), а не переэмбеддингом (Лаб 1.8).
При ручном просмотре топ-10 важно отделять coverage_gap (статьи нет в корпусе) от retrieval-ошибок, иначе качество поиска занижается из-за дыр  в корпусе (Лаб 1.8).
Проверка тем запросов по корпусу до прогона (LIKE по titles, scripts/lab1_8_find_titles.py) экономит бюджет ручного просмотра на «пустых» темах (Лаб 1.8).
RRF по рангам снимает проблему разных шкал в гибридном поиске: отрицательный bm25() FTS5 и cosine Qdrant не нужно нормализовать, важны только ранги (Лаб 1.9).
RRF сильно усиливает чанки, присутствующие в обоих списках: средние ранги в BM25 и dense могут обойти сильный одиночный топ-1 — это системная цена слияния, а не баг (q12, Лаб 1.9).
Гибрид через RRF — это страховка ранга 1 (MRR 0.975 против 0.917 у dense), а не прирост плотности топ-10 (P@10 0.745 против 0.805 у dense); плотность топ-10 — зона реранкера Лаб 1.10 (Лаб 1.9).
📝 Заметки для следующих сессий
Лаб 1.2 выполнена: парсер `src/ingestion/parser.py`, тесты `tests/test_parser.py` зелёные (8 тестов), корпус распарсен 5000/5000, `failed = 0`.
Лаб 1.3 выполнена: нормализация, дедупликация и сохранение корпуса в SQLite реализованы.
Модуль нормализации:  `src/ingestion/normalize.py` .
Основной скрипт Лаб 1.3:  `scripts/lab1_3_normalize_dedup.py` .
Проверка результата:  `scripts/lab1_3_check_db.py` .
Тесты Лаб 1.3:  `tests/test_normalize.py`  зелёные (6 тестов).
Итоговая таблица документов:  `data/processed/ru_wikipedia_5000_normalized.sqlite3` , таблица  `documents` .
Отчёт о дедупликации:  `data/processed/lab1_3_dedup_report.json` .
Аудит удалённых дубликатов:  `data/processed/lab1_3_duplicates.jsonl` .
Аудит удалённых страниц-неоднозначностей:  `data/processed/lab1_3_disambig.jsonl` .
Быстрый перезапуск Лаб 1.3
Из папки `Project1` с активированным виртуальным окружением:
python -m pytest tests/test_normalize.py -q
python scripts/lab1_3_normalize_dedup.py
python scripts/lab1_3_check_db.py
Ожидаемый результат:
тесты проходят;
создаётся/пересоздаётся `data/processed/ru_wikipedia_5000_normalized.sqlite3`;
создаётся `data/processed/lab1_3_dedup_report.json`;
проверка базы показывает количество документов, отсутствие дубликатов по `full_hash` и отсутствие `is_disambig = 1` при настройке `REMOVE_DISAMBIG = True`.
Лаб 1.4 выполнена: чанкинг фиксированного размера с перекрытием реализован.
Параметры: chunk_size=500 символов, overlap=50 символов (шаг 450).
Результат: таблица  `chunks`  в  `data/processed/ru_wikipedia_5000_normalized.sqlite3` ; 138 785 чанков из 4910 документов; среднее 28.27 чанков/документ.
Модуль чанкинга:  `src/chunking/fixed_size.py` , функция  `chunk_text_fixed_size()` .
Скрипт Лаб 1.4:  `scripts/lab1_4_chunk_corpus.py` ; проверка:  `scripts/lab1_4_check_db.py`  (все проверки зелёные).
Тесты Лаб 1.4:  `tests/test_chunking.py`  зелёные (4 теста).
Решение по хранению статистик в Git: оставляем  `data/`  полностью игнорируемой; все артефакты воспроизводимы скриптами.
Быстрый перезапуск Лаб 1.4
Из папки `Project1` с активированным виртуальным окружением:
python -m pytest tests/test_chunking.py -q
python -m scripts.lab1_4_chunk_corpus
python scripts/lab1_4_check_db.py
Примечание: если при запуске скрипта возникает `ModuleNotFoundError: No module named 'src'`, запускать именно как модуль (`python -m scripts.lab1_4_chunk_corpus`) либо добавить корень проекта в `sys.path` внутри скрипта.
Ожидаемый результат:
тесты проходят (4 теста);
таблица `chunks` пересоздаётся: 138 785 чанков из 4910 документов;
проверка показывает количество чанков, среднее число чанков на документ и перекрытие 50 символов между соседними чанками.
Лаб 1.5 выполнена: структурное чанкование реализовано.
Параметры: max_chars=500 символов, overlap=0; разбиение по заголовкам/абзацам, длинные блоки режутся по предложениям/пробелам .
Результат: таблица  `chunks_structural`  в  `data/processed/ru_wikipedia_5000_normalized.sqlite3` ; выполнено сравнение распределения длин со стратегией A.
Модуль чанкинга:  `src/chunking/structural.py` , функция  `chunk_text_structural()` .
Скрипт Лаб 1.5:  `scripts/lab1_5_chunk_structural.py` ; проверка:  `scripts/lab1_5_check_db.py` ; сравнение:  `scripts/lab1_5_compare_chunks.py` .
Тесты Лаб 1.5:  `tests/test_chunking_structural.py`  зелёные.
Быстрый перезапуск Лаб 1.5
Из папки `Project1` с активированным виртуальным окружением:
python -m pytest tests/test_chunking_structural.py -q
python -m scripts.lab1_5_chunk_structural
python -m scripts.lab1_5_check_db
python -m scripts.lab1_5_compare_chunks
Примечание: если при запуске скрипта возникает `ModuleNotFoundError: No module named 'src'`, запускать именно как модуль (`python -m scripts.lab1_5_chunk_structural`) либо добавить корень проекта в `sys.path` внутри скрипта.
Ожидаемый результат:
тесты проходят;
таблица `chunks_structural` пересоздаётся;
проверка показывает отсутствие пустых чанков, дублей `chunk_id`, дублей `doc_id + chunk_index` и корректность `start_char` / `end_char`;
скрипт сравнения создаёт отчёты распределения длин стратегии A и стратегии B.
Лаб 1.6 выполнена: эмбеддинги и загрузка векторов в Qdrant реализованы.
Модель: BAAI/bge-m3, локальная копия models/bge-m3 (ModelScope); размерность вектора 1024; устройство cuda.
Qdrant: Docker, контейнер qdrant, том qdrant_storage; коллекция rag_documents; метрика Cosine; 138 785 точек из таблицы chunks.
Модули: src/indexing/embeddings.py, src/indexing/qdrant_index.py.
Скрипты: scripts/lab1_6_embed_qdrant.py (загрузка), scripts/lab1_6_check_qdrant.py (проверка коллекции и тестовый поиск).
Тесты: tests/test_indexing_helpers.py зелёные (5 тестов).
Отчёт: data/processed/lab1_6_embedding_report.json; лог: data/processed/lab1_6_embedding.log.
Быстрый перезапуск Лаб 1.6
Из папки Project1 с активированным виртуальным окружением:
docker start qdrant
python -m pytest tests/test_indexing_helpers.py -q
python -m scripts.lab1_6_embed_qdrant --limit 100 --recreate
python -m scripts.lab1_6_check_qdrant
python -m scripts.lab1_6_embed_qdrant --recreate --batch-size 128
python -m scripts.lab1_6_check_qdrant
Ожидаемый результат:
тесты проходят (5 тестов);
коллекция rag_documents пересоздаётся с размерностью 1024;
после полного прогона Points count: 138785;
тестовый поиск возвращает релевантные чанки с payload (title, doc_id, chunk_id, text).
Лаб 1.8 выполнена: плотный поиск реализован и вручную оценён на 20 запросах.
Реализация: src/retrieval/dense_search.py (DenseSearcher), scripts/lab1_8_dense_search.py, scripts/lab1_8_find_titles.py.
Артефакты: data/processed/lab1_8_queries.jsonl (20 запросов), lab1_8_dense_results.jsonl (20 × топ-10), lab1_8_dense_report.json; наблюдения: docs/lab1_8_observations.md.
Решение: top-k первичного поиска = 20 для Лаб 1.9 (см. раздел 1.9).
Быстрый перезапуск Лаб 1.8
Из папки Project1 с активированным виртуальным окружением:
docker start qdrant
python -m scripts.lab1_6_check_qdrant
python -m scripts.lab1_8_dense_search --queries data/processed/lab1_8_queries.jsonl --out data/processed/lab1_8_dense_results.jsonl --report data/processed/lab1_8_dense_report.json --top-k 10
Ожидаемый результат:
проверка Qdrant показывает Points count: 138785;
в lab1_8_dense_results.jsonl ровно 20 строк, по ~10 хитов на запрос;
latency десятки мс на запрос;
файлы lab1_8_dense_results.jsonl и lab1_8_dense_report.json пересозданы.
Лаб 1.9 выполнена: гибридный поиск через RRF реализован и оценён.
Модуль: src/retrieval/hybrid_search.py (rrf_scores/fuse_rrf).
Скрипты: scripts/lab1_9_hybrid_search.py, scripts/lab1_9_fill_manual.py, scripts/lab1_9_eval_manual.py.
Тесты: tests/test_hybrid_rrf.py зелёные (4 теста).
Параметры: BM25 top-k 20, dense top-k 20, RRF k 60, eval top-k 10; слияние по chunk_id, только ранги.
Метрики (20 запросов, ручная разметка топ-10): bm25 P@10 0.620 / MRR 0.879; dense P@10 0.805 / MRR 0.917; hybrid P@10 0.745 / MRR 0.975.
Быстрый перезапуск Лаб 1.9
Из папки Project1 с активированным виртуальным окружением:
docker start qdrant
python -m pytest tests/test_hybrid_rrf.py -q
python -m scripts.lab1_7_check_bm25
python -m scripts.lab1_6_check_qdrant
python -m scripts.lab1_9_hybrid_search
python -m scripts.lab1_9_fill_manual
python -m scripts.lab1_9_eval_manual --input data/processed/lab1_9_manual_scores.csv
Ожидаемый результат:
тесты проходят (4 теста);
в lab1_9_hybrid_results.jsonl и lab1_9_comparison_summary.csv по 20 строк;
таблица метрик в консоли совпадает с data/processed/lab1_9_metrics.md (bm25 0.660/0.620/0.879; dense 0.900/0.805/0.917; hybrid 0.860/0.745/0.975).