# data/

Large raw tables are not committed (`data/raw/**`).

| Path | Role |
| --- | --- |
| `fixtures/` | Synthetic + UCI-schema retail line items (committed) |
| `raw/superstore.csv` | Local Superstore (optional) |
| `raw/olist_*.csv` | Local Olist (optional) |
| `raw/online_retail_ii.xlsx` | Optional UCI Online Retail II workbook |

UCI source: UCI / Kaggle “Online Retail II”. Place locally if you want the full file; CI uses `fixtures/retail_line_items.csv`.
