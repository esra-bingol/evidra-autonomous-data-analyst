# Aşama 9 — Olist (yapısal benchmark)

**Proje:** Evidra  
**Önceki:** [08-optional-python.md](08-optional-python.md)  
**Sonraki:** [10-v2.md](10-v2.md)

V1 core (Aşama 6) yeşil olmadan başlanmaz. Olist **V1 dataset’i değildir**; generalization / structure sınavıdır. Ürün demosu buradadır.

---

## Amaç

Olist Brazilian E-Commerce (~2016–2018, ilişkili tablolar) ile ajanın join, teslimat süresi (engine’de türetilmiş), review ve çok boyutlu soruları **engine + SQL** ile araştırması.

Tek golden şehir yoktur. Ölçüm **süreç rubriği**dir.

---

## Dataset

Kaynak: Olist Brazilian E-Commerce Public Dataset. Ham dosyalar repoda yok.

Tablolar (tipik): orders, order_items, customers, products, payments, reviews, sellers, geolocation, category translation.

**Sözleşme:** tablo rolleri + join anahtarları (`order_id`, `customer_id`, `product_id`, `seller_id`).

`inspect` çok tablo özeti verir. Capability: `multi_table_join`, `delivery_analysis`, `retention_analysis` şema uygunsa true.

Hipotez aileleri genişler ama **kapalı template seti** aynıdır; yeni operatör uydurulmaz. Teslimat gecikmesi engine feature’ıdır, LLM hesabı değil.

Olist’te **kâr kolonu yoktur.** Margin uydurulmaz; insufficient evidence / abstain.

---

## Case’ler (en az ikisi join’siz çözülemez)

1. Teslimat gecikmesi ile review score **association**  
2. Yüksek ciro, düşük puan kategorileri  
3. Eyalet/bölge lojistik association  
4. Ciro lideri = “en iyi”? kanıt yoksa iddia etme  
5. Tekrar alım ile teslimat/puan association  

**Rubrik (eval 3–5 madde):** kullanılan tablolar, join anahtarları, türetilmiş delay kolonu, review bağlama, evidence nesnesi, nedensel dil yok.

---

## Görevler

- [x] `data/README` Olist indirme + tablo haritası
- [x] Çok dosya / zip yükleme
- [x] DuckDB tüm tablolar; join’li SELECT
- [x] Teslimat süresi engine’de
- [x] ≥2 join case uçtan uca (CLI veya UI)
- [x] Olist rubrik eval
- [x] README demo senaryosu Olist
- [x] V1 (Aşama 6) eval regresyonu yeşil

---

## Çıkış kriteri

Gösterilecek akış Olist case’idir (ör. gecikme × puan association). Evidence birden fazla tablodan gelir. Causal fiil yoktur.

**Bitti sayılır:** İki join case + rubrik eval + lisans/indirme notu.

---

## Bilinçli olarak yok

UCI Retail ve NYC Taxi (Aşama 10, XOR). Multi-agent Reviewer. Fine-tune. Olist’i tek doğru sürücü golden’ı yapmak.
