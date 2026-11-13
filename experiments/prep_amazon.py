# prep_amazon.py  (pip install pandas numpy scikit-learn)
import numpy as np, pandas as pd
from sklearn.cluster import KMeans

df = pd.read_csv("amazon_delivery.csv")
print("total rows:", len(df))
df = df[(df.Store_Latitude != 0) & (df.Store_Longitude != 0)]
df = df[df.Category.isin(["Grocery", "Snacks", "Cosmetics"])].copy()
print("after category filter:", len(df))

def hav(a, b, c, d):
    a, b, c, d = map(np.radians, (a, b, c, d))
    h = np.sin((c-a)/2)**2 + np.cos(a)*np.cos(c)*np.sin((d-b)/2)**2
    return 6371 * 2 * np.arcsin(np.sqrt(h))

# 1) busiest city = most common 1-degree grid cell of store locations
cell = pd.Series(list(zip(df.Store_Latitude.round(0), df.Store_Longitude.round(0))), index=df.index)
df = df[cell == cell.mode()[0]].copy()
print("after city filter:", len(df))

# 2) keep drops within 15 km of their own store
d = hav(df.Store_Latitude, df.Store_Longitude, df.Drop_Latitude, df.Drop_Longitude)
df = df[d < 15].copy()
print("after distance filter:", len(df))

# 3) 3 warehouses = clusters of store points
S = df[["Store_Latitude", "Store_Longitude"]].values
km = KMeans(3, n_init=10, random_state=42).fit(S)
wh = pd.DataFrame(km.cluster_centers_, columns=["lat", "lon"])
wh["wid"] = ["A", "B", "C"]

orders = df[["Order_ID", "Category", "Drop_Latitude", "Drop_Longitude"]].reset_index(drop=True)
for w in wh.itertuples():
    orders[f"dist_{w.wid}"] = hav(w.lat, w.lon, orders.Drop_Latitude, orders.Drop_Longitude).round(2)

orders.to_csv("orders.csv", index=False)
wh.to_csv("warehouses.csv", index=False)
print(len(orders), "orders"); print(wh); print(orders.Category.value_counts())
print(orders.filter(like="dist_").describe().loc[["min", "mean", "max"]])