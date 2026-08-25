# Aşama 8 — İsteğe bağlı izole Python

**Proje:** Evidra  
**Önceki:** [07-minimal-ui.md](07-minimal-ui.md)  
**Sonraki:** [09-olist.md](09-olist.md)

**V1 DEĞİL.** Bu aşamayı **atlamak geçerlidir.** V1 core Aşama 6’da biter; Python yürütme iddianın parçası değildir.

---

## Amaç

Yalnızca bilinçli bir ürün kararıyla `run_python` açılacaksa: AST validator **ve** izole container. Host’ta RestrictedPython / “AST sandbox” **yetmez**.

---

## Zorunlu izolasyon (eğer açılırsa)

```text
kod taslağı → AST allowlist → isolated container → sonuç → Evidence
```

Container:

- Ağ yok  
- Dosya sistemi read-only (dataset mount hariç, yazma yok)  
- CPU / bellek / timeout limit  
- İzinli import: pandas, numpy, math, datetime; kayıtlı `df`  

Yasak: `os`, `subprocess`, `socket`, `eval`/`exec`/`compile`, dunder kaçışları, dış yol.

Başarısız veya reddedilen kod → tool hata kaydı; ajan sayı uydurmaz.

`run_sql` ayrı kalır: yalnızca SELECT.

Negatif testler: zararlı kod reddi; meşru `groupby` geçer.

---

## Görevler (yalnızca bu dilim seçilirse)

- [ ] AST validator + container runtime
- [ ] Negatif güvenlik testleri
- [ ] Çıktı → Evidence map
- [ ] Aşama 6 eval regresyonu yeşil
- [ ] Atlandıysa: PLAN/README’de “Phase 8 skipped” notu

---

## Çıkış kriteri

Açıldıysa: zararlı kod reddedilir, meşru analiz Evidence üretir, host kaçışı yoktur.

Atlandıysa: dosyada skip kararı yazılıdır; Aşama 9’a geçiş bloklanmaz.

**Bitti sayılır:** Ya izole Python yeşil, ya resmi skip.

---

## Bilinçli olarak yok (skip veya sonra)

RestrictedPython’u sandbox saymak, Olist, multi-agent, efficiency gate.
