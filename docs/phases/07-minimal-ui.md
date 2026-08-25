# Aşama 7 — Minimal UI

**Proje:** Evidra  
**Önceki:** [06-eval-abstention-budget.md](06-eval-abstention-budget.md)  
**Sonraki:** [08-optional-python.md](08-optional-python.md)

Ajan davranışını **değiştirmez**. Aşama 6 core’unun ince yüzeyi. 5. bağımsız viz paneli backlog.

---

## Amaç

Upload, soru, plan, findings+nested charts, evidence. Chat balonu değil; araştırma konsolu. Core CLI/API aynı kalır.

---

## 4 blok

1. **Upload / dataset** — CSV/Excel; gömülü fixture seçici (sentetik + Superstore).  
2. **Question** — soru kutusu; örnek sorular (abstain örneği dahil).  
3. **Plan** — adım, tool, durum, süre (tool log).  
4. **Findings + Evidence** — claim’ler, strength etiketi (`weak|moderate|strong|inconclusive`), evidence tabloları; **grafikler findings altında nested** (`evidence_ids`).

Boş / yükleniyor / hata: dosya yok, soru yok, tool hatası, tek dönem, abstain.

Dil: arayüz Türkçe olabilir; AOV, hypothesis, strength İngilizce kalabilir. Nedensel slogan yok.

---

## API (ince)

FastAPI, aynı core:

- `POST /datasets` — upload  
- `GET /datasets/{id}` — overview / capabilities  
- `POST /datasets/{id}/analyze` — soru → run (senkron V1 kabul)  
- `GET /runs/{id}` — plan, claims, evidence, charts, traces, stop_reason  

Auth yok. Tek kullanıcı, yerel. Portlar: 3000 / 5173 / 8080 dışında.

---

## Görevler

- [x] Upload + fixture seçici
- [x] 4 blok bağlama; nested charts
- [x] Strength enum görünür; yüzde güven yok
- [x] Abstain ve hata halleri kırılmaz
- [x] Mobil: alt alta; masaüstü: grid
- [x] README: API + UI port
- [x] Aşama 6 eval hâlâ yeşil (regresyon)

---

## Çıkış kriteri

Ekranda chatbot değil **evidence tablosu** ve strength etiketi görünür. Sentetik `clear_driver` UI’da doğru association claim’i gösterir. Ajan grafı/tool seti değişmemiştir.

**Bitti sayılır:** Upload → soru → 4 blok. 5. viz paneli yok.

---

## Bilinçli olarak yok

Beşinci bağımsız Visualizations paneli, kullanıcı sistemi, Postgres, LangSmith UI, Olist çoklu yükleme, `run_python`.
