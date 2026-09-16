from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct


# Подключение к Qdrant в Docker
client = QdrantClient(
    host="127.0.0.1",
    port=16333,
    grpc_port=16334,
    prefer_grpc=True,
    timeout=60
)

collection_name = "demo_collection"

# Пересоздаём коллекцию, чтобы скрипт можно было запускать повторно
if client.collection_exists(collection_name):
    client.delete_collection(collection_name)

client.create_collection(
    collection_name=collection_name,
    vectors_config=VectorParams(size=4, distance=Distance.COSINE)
)
print("Коллекция создана")

# Две тестовые записи: вектор из 4 чисел + полезные данные в payload
points = [
    PointStruct(
        id=1,
        vector=[0.1, 0.2, 0.3, 0.4],
        payload={"title": "Docker",
                 "text": "Docker позволяет запускать приложения в контейнерах"}
    ),
    PointStruct(
        id=2,
        vector=[0.9, 0.1, 0.2, 0.0],
        payload={"title": "Python",
                 "text": "Python — язык программирования"}
    )
]

client.upsert(collection_name=collection_name, points=points)
print("Записи добавлены")

# Вектор запроса, похожий на вектор записи id=1
query_vector = [0.11, 0.19, 0.31, 0.39]

result = client.query_points(
    collection_name=collection_name,
    query=query_vector,
    limit=1
).points

print("Результат поиска:")
print(result)