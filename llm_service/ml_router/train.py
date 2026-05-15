import joblib
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report


model = SentenceTransformer("intfloat/multilingual-e5-small")

df = pd.read_csv('data/dataset.csv')


X = [model.encode(t) for t in df['text']]
y = df['label']

X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

clf = LogisticRegression(class_weight='balanced', max_iter=1000)
clf.fit(X_train, y_train)

print(classification_report(y_test, clf.predict(X_test)))

joblib.dump(clf, 'intent_model_small.pkl')