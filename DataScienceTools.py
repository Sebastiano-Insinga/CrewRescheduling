import numpy as np
import matplotlib.pyplot as plt
from sklearn.datasets import make_moons
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score
import pandas as pd

df = pd.DataFrame({"name":["Alice", "Bob", "Manuel", "Hannah", "Clemens"],
                   "age": [23, 45, 25, 27, 36],
                   "city": ["Vienna", "Linz", "Munich", "Munich", "Vienna"]})

df.head()

df.info()

print(df)

filtered_df = df[df["age"] > 30]

print(filtered_df)

austrian_members = df[df["city"].isin(["Linz", "Vienna"])]

print(austrian_members)

df["age_plus_5"] = df["age"] + 5

print(df)

print(df.isna())

print(df.groupby("city").agg(count=("age", "count"), mean_age=("age", "mean"), max_age=("age", "max")))

print(df.groupby("city")["age"].mean())
"""
# 1. Generate nonlinear dataset
X, y = make_moons(n_samples=400, noise=0.25, random_state=42)
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.3, random_state=42)

# 2. Fit models
log_reg = LogisticRegression()
rf = RandomForestClassifier(n_estimators=100, random_state=42)

log_reg.fit(X_train, y_train)
rf.fit(X_train, y_train)

# 3. Predictions and accuracy
y_pred_log = log_reg.predict(X_test)
y_pred_rf = rf.predict(X_test)

print("Logistic Regression Accuracy:", accuracy_score(y_test, y_pred_log))
print("Random Forest Accuracy:", accuracy_score(y_test, y_pred_rf))

# 4. Visualize decision boundaries
xx, yy = np.meshgrid(np.linspace(X[:,0].min()-0.5, X[:,0].max()+0.5, 200),
                     np.linspace(X[:,1].min()-0.5, X[:,1].max()+0.5, 200))

Z_log = log_reg.predict(np.c_[xx.ravel(), yy.ravel()]).reshape(xx.shape)
Z_rf = rf.predict(np.c_[xx.ravel(), yy.ravel()]).reshape(xx.shape)

plt.figure(figsize=(12,5))

# Logistic Regression boundary
plt.subplot(1, 2, 1)
plt.contourf(xx, yy, Z_log, alpha=0.3, cmap='coolwarm')
plt.scatter(X_test[:,0], X_test[:,1], c=y_test, cmap='coolwarm', edgecolor='k')
plt.title("Logistic Regression")

# Random Forest boundary
plt.subplot(1, 2, 2)
plt.contourf(xx, yy, Z_rf, alpha=0.3, cmap='coolwarm')
plt.scatter(X_test[:,0], X_test[:,1], c=y_test, cmap='coolwarm', edgecolor='k')
plt.title("Random Forest")

plt.show()
"""