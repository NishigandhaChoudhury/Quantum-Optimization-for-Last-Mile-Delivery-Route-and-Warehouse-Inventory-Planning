# build_joint.py
import numpy as np, pandas as pd
rng = np.random.default_rng(42)

inv = pd.read_csv("Grocery_Inventory new v1.csv")
print("columns:", list(inv.columns))
inv["Date_Received"] = pd.to_datetime(inv["Date_Received"], errors="coerce")
inv["Expiration_Date"] = pd.to_datetime(inv["Expiration_Date"], errors="coerce")
inv = inv.dropna(subset=["Date_Received", "Expiration_Date"])

REF = inv["Date_Received"].median()          # simulated "today"
alive = inv[(inv.Date_Received <= REF) & (inv.Expiration_Date > REF)].copy()
prods = alive["Product_Name"].value_counts().head(5).index.tolist()
alive = alive[alive.Product_Name.isin(prods)].copy()
alive["wid"] = rng.choice(list("ABC"), len(alive))   # synthetic batch -> warehouse

g = alive.groupby(["wid", "Product_Name"]).agg(
    qty=("Stock_Quantity", "sum"), exp=("Expiration_Date", "min")).reset_index()
g["stock"] = np.ceil(g.qty / 50).astype(int).clip(1, 3)   # scaled down so orders compete
g["remaining_days"] = (g.exp - REF).dt.days
g[["wid", "Product_Name", "stock", "remaining_days"]].to_csv("inventory.csv", index=False)

o = pd.read_csv("orders.csv")
o["product"] = rng.choice(prods, len(o))              # synthetic order -> product
o["min_shelf_days"] = rng.choice([7, 14, 30], len(o))
o.to_csv("orders_full.csv", index=False)

print("REF:", REF.date(), "| batches kept:", len(alive), "| products:", prods)
print(g[["wid", "Product_Name", "stock", "remaining_days"]].to_string(index=False))