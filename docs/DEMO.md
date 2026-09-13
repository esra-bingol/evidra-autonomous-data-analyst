# Evidra demo

Yerel, auth yok, port **8765**.

```bash
uv sync --extra dev
uv run python -m analysis.api
```

Aç: `http://127.0.0.1:8765/chat?fixture=clear_driver`

## 5 dakika

1. **Bağla** — `clear_driver` veya `taxi_trips`. İstersen CSV yükle.
2. **Sor** — `Satış neden değişti?` / `Ücret neden değişti?`
3. **Kanıt** — sağ panelde karar, bulgular, grafik. Chip’lerde motor jargonu yok.
4. **Rapor** — `Detaylı raporu aç`. Çizgi / sütun / şelale evidence’a bağlı.
5. **Follow-up** — `Peki West'te durum nasıl?` (yeni run yok) veya `West'i daha detaylı incele.` (scoped run).
6. **Dashboard** — `/dashboard` son incelemenin değişim %, dilim, hacim/sepet değerlerini gösterir. Grafik sayısı KPI değildir.

Teslimat sorusu (`Teslimat gecikmesi puanı nasıl etkiler?`) capability yoksa abstain eder; hipotez uydurulmaz.

## Eval

```bash
uv run python -m analysis.eval
uv run pytest
```

V1 golden değişmez. Product sorular: `evals/product.json` (taxi zorunlu; Superstore/Olist dosya varsa).

## Screenshot checklist

Dosyalar `docs/screenshots/` altına (git’e büyük PNG koymak isteğe bağlı):

| Dosya | Sahne |
| --- | --- |
| `01-chat-question.png` | Soru + Türkçe cevap |
| `02-chat-preview.png` | Sağ panel KPI + grafik |
| `03-report.png` | Rapor: özet, şelale, sınırlama |
| `04-dashboard.png` | Dashboard inceleme KPI’ları |
| `05-abstain.png` | Teslimat abstain |

Çekimden önce `?fixture=clear_driver` ile aynı sahneyi üret.
