# Araştırma: hangi gösterge/veri gerçekten tahmin gücü katıyor?

Bu klasör **üretim kodu değil**, karar kanıtı üretir. Her script tek bir soruya cevap verir.
Sonuçların yorumu `TASARIM.md`'de.

| Script | Soru | Ölçüm |
|---|---|---|
| `gostergeler.py` | — | 15+ göstergenin sızıntısız ortak kütüphanesi (ATR, RSI, KDJ, WR, StochRSI, CCI, MACD, BOLL, SAR, SuperTrend, OBV, VWAP, MFI, CMF, ADX) + taker alanları |
| `gostergeler_analiz.py` | "35 gösterge kaç bağımsız bilgi taşıyor?" | Korelasyon kümeleme, PCA etkin boyut, aile içi korelasyon |
| `sinyal_testi.py` | "Yöntem gerçek bir sinyali yakalıyor mu?" | Sinyali tek kanaldan enjekte et, kontrol grubuyla karşılaştır |
| `gurultu_testi.py` | "Gösterge sayısı neye mal olur?" | Saf gürültü hedefinde eğitim/test AUC ayrışması |
| `ablasyon.py` | "Hangi aile ne kadar katkı veriyor?" | 11 özellik seti × AUC/BSS/top-10/EV, zaman sıralı bölme |

## Çalıştırma

```bash
cd arastirma
python gostergeler_analiz.py
python sinyal_testi.py
python gurultu_testi.py
python ablasyon.py            # sentetik piyasa, ağ gerekmez
python ablasyon.py --real     # Binance'ten 12 parite, 3 aylık mum (ağ gerekir)
```

## Bulgular (özet)

1. **Momentum ailesi tekrar:** RSI/CCI/WR/StochRSI/KDJ-J/bb_pos/vwap_dev ortalama ρ≈0,79–0,97 → 1 bilginin 6 kopyası.
2. **Yöntem doğru çalışıyor:** kontrol senaryosu AUC 0,50; enjekte sinyal doğru ailede 0,985.
3. **Gösterge eklemek zarar veriyor:** sinyalsiz veride 5→60 özellikte eğitim AUC 0,73→0,87, test 0,51→0,50.
4. **Tam set en kötü:** 35 gösterge (AUC 0,452) < 6 gösterge (0,510).

> Bu sonuçlar **sentetik** piyasada alındı (sandbox'ta dış ağ kapalı). Kanıtladıkları şey yöntemin ve
> uyarıların geçerliliği; gerçek edge büyüklüğü değil. Kararları `ablasyon.py --real` çıktısına göre verin.

## Sızıntı notu (yaşanmış)

İlk sürümde fitiller ve hacim `np.gradient` (merkezi fark = gelecek bilgisi) ile üretiliyordu.
Sonuç: saf gürültüde bile "AUC 0,66 momentum sinyali" göründü. Nedensel fitile geçildi → 0,50.
Bu yüzden `center=True`, `np.gradient`, `.shift(-n)` üçlüsünü her yeni özellikte arayın.
