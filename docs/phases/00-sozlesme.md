# Aşama 0 — Sistem sözleşmesi

**Proje:** Evidra (`evidra-autonomous-data-analyst`)  
**Önceki:** yok  
**Sonraki:** [01-synthetic-capability.md](01-synthetic-capability.md)

Kod yok veya yalnızca dokümanlar. Amaç: ajanın ne yaptığı / ne yapmadığı ve V1 kapısının nerede bittiğinin kilitlenmesi.

Kaynak: [PLAN.md](../../PLAN.md), [SCHEMAS.md](../SCHEMAS.md), [DESIGN_REVIEW.md](../DESIGN_REVIEW.md), [README.md](../../README.md).

---

## Amaç

Evidra V1’in davranışını, sınırını ve başarı ölçütünü sabitlemek. Sonraki aşamalar bu sözleşmeyi bozamaz; bozmak için bu dosya, SCHEMAS ve DESIGN_REVIEW birlikte güncellenir.

README tepesi ile hizalama: Evidra bir LLM’in veri analiz etmesi değildir. Investigation policy (LLM veya heuristic) neyin test edileceğine karar verir; kayıtlı tool’lar hesaplar; evidence katmanı neyin iddia edilebileceğine karar verir.

---

## Agent ne yapar? (8 davranış)

Kullanıcı bir tablo yükler (CSV/Excel) ve doğal dille sorar.

1. Dataset’i inceler ve kolon **rollerini** çıkarır (`time | metric | dimension | id | ignore`).  
2. Şemadan **capability** üretir; soru ile kesiştirir; kesişim boşsa **abstain** eder, hipotez üretmez.  
3. Kapalı template kümesinden hipotezleri **rank / bind / skip** eder (yeni operatör uydurmaz).  
4. Her bağlı hipotezi kayıtlı tool ile dener; **research budget** içinde kalır.  
5. Engine çıktısını **evidence** nesnesi olarak (append-only) kaydeder; strength scorer’dan gelir.  
6. Claim’leri validator’dan geçirir: her olgusal claim’in `evidence_id`’si vardır.  
7. Durur: `strong_evidence | space_exhausted | budget | abstain`.  
8. Yalnızca geçer claim’lerden rapor üretir; grafik varsa `evidence_ids` taşır.

---

## Agent ne yapmaz? (V1)

- Multi-agent orkestrasyon  
- RAG / vector DB / fine-tune / “autonomous retraining”  
- Postgres, MLflow, LangSmith  
- `run_python` (AST tek başına sandbox sayılmaz)  
- Sahte “89% confidence”  
- Nedensel dil (`cause`, `because`, `sebep`, `root cause`)  
- Capability yokken hipotez uydurma  
- Olist’i V1 correctness seti sayma  
- Core kapısı olarak zengin 5 panelli UI  

---

## Görevler

- [ ] Ürün / repo adı net (Evidra / `evidra-autonomous-data-analyst`)
- [ ] README, PLAN, SCHEMAS, DESIGN_REVIEW çelişkisiz
- [ ] 8 davranış ve V1 yasak listesi yazılı
- [ ] V1 core = Aşama 6 (UI’sız) yazılı
- [ ] Dataset sırası: sentetik (4 fixture) → Superstore → Olist (Aşama 9)
- [ ] Kapalı hipotez uzayı + evidence-first + association dili yazılı

---

## Çıkış kriteri

İK veya mühendis yalnızca bu aşama + README okuyunca ürünün “modele CSV verip analiz ettirmek” olmadığını anlar. SCHEMAS’taki loop ve yasak dil ile çelişki yoktur.

**Bitti sayılır:** Kutular işaretli; Aşama 1’e geçiş onayı var.

---

## Bilinçli olarak yok

Uygulama kodu, klasör ormanı, FastAPI, LangGraph, Olist indirme, frontend.
