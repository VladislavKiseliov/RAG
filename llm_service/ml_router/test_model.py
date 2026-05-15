import time

import joblib
from sentence_transformers import SentenceTransformer




MODEL_NAME = "intfloat/multilingual-e5-large"
CLF_PATH = r"C:\Users\rgg1\Desktop\EmbededLearn\intent_model.pkl"

embedder = SentenceTransformer(MODEL_NAME)
clf = joblib.load(CLF_PATH)

embedder.encode(["warmup"], normalize_embeddings=True)  # прогрев


started = time.perf_counter()
query = "Объясни подробно как работает редуктор давления газа"
start_encode = time.perf_counter()
vec = embedder.encode([query], normalize_embeddings=True)
print(f"stop_encode {int((time.perf_counter() - start_encode) * 1000)=}")

proba = clf.predict_proba(vec)[0]
confidence = proba.max()
label = clf.classes_[proba.argmax()]

print(f"Класс:       {label}")
print(f"Уверенность: {confidence:.3f}")
print(f"Все вероятности: {dict(zip(clf.classes_, proba.round(3)))}")
print(int((time.perf_counter() - started) * 1000))