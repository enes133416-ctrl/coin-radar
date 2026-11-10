# Coin Radar v2 — Veri, Gösterge ve Tahmin Mimarisi

**Sorulan:** Geçmiş veriyi Binance'ten çeken ve geçmişten ders alan bir site: ne eklemeli, nelere dikkat etmeli, hangi veriler çekilmeli, ve listedeki göstergelerden (MA, EMA, BOLL, SAR, AVL/VWAP, SuperTrend, VOL, MACD, RSI, KDJ, OBV, WR, StochRSI, ATR, CCI) hangileri ölçüt olmalı?

**Bu dokümanın farkı:** Tavsiye vermeden önce **ölçtüm**. `arastirma/` klasöründe 4 deney var, hepsi bu repoda çalışır durumda. Sonuçların bir kısmı sezgiye aykırı: **15 gösterge eklemek tahmin gücünü artırmıyor; çoğu zaman azaltıyor.**

---

## 0. Otuz saniyelik cevap

1. **Gösterge ≠ bilgi.** Listendeki 15 göstergenin tamamı fiyat ve hacmin türevidir. Birbirleriyle ortalama %79 korelasyona sahip 5 momentum göstergesi, 5 ayrı bilgi değil **1 bilginin 5 kopyasıdır**.
2. **Tahmin gücünü artıran şey yeni gösterge değil, yeni BİLGİ KAYNAĞI**: taker tarafı (alıcı/satıcı agresifliği), emir defteri değişimi, funding/basis, açık pozisyon, tasfiye akışı, zincir üstü transferler, kesitsel sıralama.
3. **Ölçüt olarak kullanılacak göstergeler az ve nettir:** ATR (ölçek/bariyer), Bollinger genişliği + squeeze (rejim), göreli hacim (V), taker dengesizliği (VOL/OBV'nin gerçek hâli), MA/EMA **sadece eğim + ATR-normalize** olarak, ve **tek bir** momentum osilatörü (RSI). KDJ, WR, StochRSI, CCI → aynı bilgi; birini seç.
4. **Göstergeleri ham değer olarak modele sokmayın.** RSI 71, fiyat 0,42 $ iken bir şey ifade etmez; `(RSI-50)/ATR%` ya da `kesitsel yüzdelik sıra` olarak anlamlıdır.
5. **En büyük risk aşırı uyum.** Sinyalsiz gürültüde 5 göstergeden 60'a çıkınca **eğitim AUC'si 0,73 → 0,87** oldu, test AUC'si **0,51 → 0,50**. Gösterge sayısı arttıkça "geçmişte mükemmel, gelecekte çöp" olursunuz.
6. **Hedef ve maliyet, göstergeden önemli.** Hangi göstergeyi eklerseniz ekleyin, ±%10 bariyer + %0,2 maliyetle başabaş %51'dir; göstergeler bunu değiştirmez (bkz. `ANALIZ.md` §9).

---

## 1. Ölçüm sonuçları (bu repoda çalıştırıldı)

### Deney 1 — Göstergelerin korelasyon yapısı
`arastirma/gostergeler_analiz.py`

```
35 gösterge, 25 varlık, 149.400 satır (sentetik piyasa)

En yüksek çiftler (|Spearman|):
  0.97  cci      ↔ bb_pos        ← neredeyse aynı
  0.97  rsi      ↔ vwap_dev      ← neredeyse aynı
  0.94  bb_pos   ↔ vwap_dev
  0.92  rsi      ↔ bb_pos
  0.91  wr       ↔ bb_pos
  0.91  rsi      ↔ cci
  0.90  ma_slope ↔ rsi

PCA: 35 göstergede bilginin %80'i 9 boyutta, %95'i 18 boyutta
Aile içi ortalama |ρ|:  momentum 0.79 · trend 0.56 · konum 0.62
                       oynaklık 0.38 · hacim 0.30 · emir akışı 0.33
```

**Okuma:** "momentum" ailesi kendi içinde neredeyse tam tekrar. RSI, CCI, WR, StochRSI, KDJ-J, Bollinger pozisyonu ve VWAP sapması **fiilen aynı sayı**. Bunların hepsini eklemek modelin bilgisini artırmıyor, sadece **gürültülü kopyaların sayısını** artırıyor — ki ağaç modelleri bu kopyalardan birini rastgele seçip önem atfeder, yorum da bozulur.

### Deney 2 — Yöntem gerçekten sinyal yakalıyor mu?
`arastirma/sinyal_testi.py` — sinyali **tek kanaldan** enjekte edip hangi ailenin yakaladığına bakıyoruz.

| Senaryo | trend | momentum | bant | hacim | emir akışı |
|---|---|---|---|---|---|
| Kontrol (sinyal yok) | 0,497 | 0,503 | 0,500 | 0,504 | 0,494 |
| Sinyal **sadece emir akışında** | 0,501 | 0,502 | 0,501 | 0,493 | **0,985** |
| Sinyal **sadece momentumda** | 0,508 | **0,549** | 0,520 | 0,523 | 0,504 |

**Okuma:** Yöntem çalışıyor (kontrol 0,50'de kalıyor; enjekte edilen sinyali doğru aile yakalıyor). Dikkat çeken: momentum sinyali zayıf yakalanıyor (%54,9) çünkü RSI gibi osilatörler **sinyali gecikmeli ve sönümlü** taşır. Aynı bilgi ham getiri serisinde çok daha net → "gösterge, bilgiyi kaybettirir".

### Deney 3 — Ablasyon: hangi aile gerçekten katkı veriyor?
`arastirma/ablasyon.py` — ilk-temas etiketi (3×ATR↑ / 1×ATR↓, 24s), zaman sıralı bölme, 24s seyreltme.

| Özellik seti | AUC | BSS | top-10 isabet | top-10 EV |
|---|---|---|---|---|
| 0 · taban (volatilite + konum) | 0,438 | −0,01 | %27,0 | −0,02R |
| 1 · + trend (MA/EMA/SAR/ST/MACD) | 0,453 | −0,01 | %26,4 | −0,05R |
| 2 · + momentum (RSI/KDJ/WR/StochRSI/CCI) | 0,434 | −0,02 | %28,6 | +0,05R |
| 3 · + bant | 0,455 | −0,01 | %27,0 | −0,02R |
| 4 · + hacim (OBV/VWAP/MFI/CMF) | 0,434 | −0,01 | %25,7 | −0,07R |
| 5 · + emir akışı | 0,433 | −0,02 | %25,5 | −0,08R |
| 6 · + ADX | 0,443 | −0,01 | %25,9 | −0,06R |
| **7 · HER ŞEY (35 gösterge)** | **0,452** | −0,01 | %26,6 | −0,04R |
| 8 · sadece momentum | 0,504 | −0,00 | %26,8 | −0,03R |
| 9 · sadece emir akışı | 0,499 | −0,00 | %28,6 | +0,05R |
| 10 · sadece trend | 0,510 | −0,00 | %29,1 | +0,06R |

**Okuma:** Piyasada öğrenilebilir sürüklenme yokken **hiçbir aile** AUC 0,51'i geçmiyor ve **35 göstergenin tamamı, 6 göstergeden daha kötü** (0,452 vs 0,510). Yani "hepsini ekleyelim" stratejisi ölçülebilir biçimde zararlı. (Baz oran ≈ %26 olduğu için top-10 EV'ler ±0,1R bandında gürültü; anlamlı fark yok.)

> ⚠️ Sınır: Bu ablasyon **sentetik** piyasada. Bu sandbox'ta Binance erişimi yok (`curl` → 000), o yüzden `--real` modu burada çalıştırılamadı. Gerçek veri modu hazır: `python arastirma/ablasyon.py --real` (12 majör parite, 3 aylık mum). GitHub Actions'ta veya lokalde çalıştırıp aynı tabloyu gerçek veriyle üretmelisiniz — **kararları o tabloya göre verin**, buradaki sayılar yöntemin doğruluğunu kanıtlar, gerçek edge büyüklüğünü değil.

### Deney 4 — Gösterge sayısının bedeli (en çarpıcı sonuç)
`arastirma/gurultu_testi.py` — hedef **saf gürültü** (tahmin edilecek hiçbir şey yok).

| Özellik sayısı | Eğitim AUC | Test AUC | Aşırı uyum farkı |
|---|---|---|---|
| 5 | 0,728 | 0,512 | 0,216 |
| 10 | 0,748 | 0,513 | 0,235 |
| 20 | 0,798 | 0,509 | 0,289 |
| 35 | 0,835 | 0,503 | 0,332 |
| 60 | 0,866 | 0,505 | 0,361 |

**Okuma:** Gösterge ekledikçe **eğitim başarısı fırlıyor** (0,73 → 0,87), **test başarısı düşüyor** (0,51 → 0,50). Sitede "geçmişte %87 doğruluk" yazarsanız tam olarak bu tuzağı sergilersiniz. Çözüm: özellik seçimi + düzenlileştirme + **sadece test metriği yayınlama** + taban çizgisi karşılaştırması.

---

## 2. Temel ilke: bilgi kaynakları hiyerarşisi

Tahmin gücü, kullandığınız **bilgi kaynağının** ne kadar "fiyatın henüz sindirmediği" olduğuna bağlıdır:

| Katman | Örnek | Kripto'da bilgi değeri | Neden |
|---|---|---|---|
| **1. Fiyat türevleri** | MA, EMA, MACD, RSI, KDJ, WR, CCI, SAR, ST | **Düşük** | Herkes görüyor, fiyatın içinde zaten var, gecikmeli |
| **2. Hacim türevleri** | VOL, OBV, VWAP, MFI, CMF | **Orta** | Fiyatla uyumsuzluğu (divergence) bilgi taşır; tek başına zayıf |
| **3. Emir akışı** | taker buy/sell, CVD, emir defteri dengesizliği, büyük işlemler | **Yüksek** | Kimin agresif olduğunu gösterir; 1–60 dk ufukta en güçlü |
| **4. Pozisyonlanma** | funding, basis, OI, top trader oranları, tasfiye | **Yüksek** | Sıkışma/tasfiye yakıtı; 4–72 saat ufukta en güçlü |
| **5. Dış bilgi** | zincir üstü akış, stablecoin arzı, ETF akışı, makro, haber/listeleme | **Yüksek ama gürültülü** | Fiyatın nedeni; entegrasyon zor, gecikme riski |

**Kural:** 1. katmandan 10 gösterge eklemek, 5. katmandan 1 veri eklemekten daha az şey kazandırır. Senin listenin **tamamı 1. ve 2. katmanda** — bu yüzden asıl kazanç listede değil.

---

## 3. Listendeki 15 gösterge: tek tek karar

Her biri için: **ölçüt mü · nasıl kullanılmalı · ne zaman zararlı**.

| Gösterge | Karar | Nasıl kullanılmalı | Uyarı |
|---|---|---|---|
| **ATR** | ✅ **Çekirdek — vazgeçilmez** | Bariyer ölçeği (hedef 3×ATR, stop 1×ATR), tüm özellikleri normalize etme paydası, likidite/risk filtresi | Ham ATR $ değeri işe yaramaz; **ATR% ve ATR oranı (kısa/uzun)** kullan |
| **VOL (hacim)** | ✅ **Çekirdek** | Göreli hacim `v / v_ort24`, hacim z-skoru, `v/ATR` (hacim başına hareket) | Mutlak hacim coin büyüklüğüyle karışır; **kesitsel yüzdelik sıra** daha iyi |
| **Bollinger (BOLL)** | ✅ **Ölçüt (genişlik)** | `bb_width` = rejim (sıkışma → patlama), `squeeze = width/width_ort`, pozisyon `bb_pos` | `bb_pos` RSI ile 0,92 korelasyona sahip → ayrı özellik saymayın; kanal içinde al/sat sinyali olarak kullanmayın |
| **MA / EMA** | 🟡 **Sadece eğim ve mesafe** | `EMA20 eğimi / ATR%`, `(EMA12/EMA48-1)/ATR%`, fiyatın EMA200'e ATR cinsinden uzaklığı | Kesişim (golden cross) sinyali değersiz; 3 ayrı periyot = 3 kopya. **Ham fiyat/EMA oranı ölçek taşır, normalize edin** |
| **VWAP (AVL)** | 🟡 **Orta** | 24s VWAP'tan ATR cinsinden sapma; hacim ağırlıklı ortalama fiyat ≈ gün içi "adil değer" | RSI ile 0,97 korelasyon → tek başına yeni bilgi değil; **intraday ufukta** (1–8 saat) daha anlamlı |
| **MACD** | 🟡 **1 tanesi yeter** | `histogram / fiyat / ATR%` (normalize) | MACD = iki EMA farkı → trend ailesinin kopyası; sinyal çizgisi kesişimi geç ve gürültülü |
| **RSI** | ✅ **Tek momentum ölçütü** | **Divergence** (fiyat yeni zirve, RSI değil) ve aşırı bölge *rejim bağlamında*; normalize: `(RSI-50)/ATR%` | "30 altı al, 70 üstü sat" **kripto'da çalışmaz** (trendde 80'de kalır). Ham RSI'yı modele sokmayın, sıra/z-score kullanın |
| **KDJ** | ❌ **Gereksiz** | — | Stokastik'in yumuşatılmış hâli; RSI/WR ile aynı bilgi. Ekstrapole eden `J` bileşeni gürültü üretir |
| **WR (Williams %R)** | ❌ **Gereksiz** | — | Tanım gereği RSI'ın **ters çevrilmiş** hâli (ρ ≈ −0,95). Kopya |
| **StochRSI** | ❌ **Gereksiz** | — | RSI'ın üzerine bir osilatör daha; bilgi eklemez, gecikme ekler |
| **CCI** | ❌ **Gereksiz** | — | Bollinger pozisyonu ile 0,97 korelasyon; aşırı bölge eşikleri (-100/+100) keyfî |
| **OBV** | 🟡 **Vekil — daha iyisi var** | Hacim-fiyat uyumsuzluğu: fiyat yükselirken OBV düşüyor → zayıflık | OBV, **taker tarafını bilmez**: satıcının agresif mi pasif mi olduğunu ayırt edemez. Gerçek veri: `taker buy volume` |
| **SAR** | 🟡 **1 trend-dönüş ölçütü** | Trend yönü (±1) ve "bar sayısı" (trend yaşı) | Sürekli değer olarak modele sokmayın; sadece yön. ATR ile normalize edilmiş mesafe anlamlı |
| **SuperTrend** | 🟡 **SAR'ın alternatifi (ikisinden BİRİ)** | Yön + ATR cinsinden bant mesafesi; trend dönüşünde yaş | SAR ile aynı bilgiyi taşır. İkisini birlikte eklemek = çoklu bağlantı |
| **ADX** | ✅ **Rejim kapısı** | Trend gücü > 25 → momentum stratejisi, < 20 → yatay/mean-reversion stratejisi | Yön vermez, sadece güç. Özellik olarak değil **rejim ayrımı** olarak kullanın |

**Sonuç tablosu:**

- **Eklenecek (5):** ATR% · göreli hacim · Bollinger genişliği/squeeze · tek trend ölçütü (EMA eğimi + ATR normalize) · tek momentum ölçütü (RSI, normalize/sıra)
- **Şartlı (3):** VWAP sapması (intraday), ADX (rejim), SAR **veya** SuperTrend (ikisinden biri)
- **Reddedilecek (4):** KDJ, WR, StochRSI, CCI — aynı bilgi, sadece kalabalık ve yanıltıcı önem yorumu
- **Vekil (1):** OBV → taker buy hacmi ile değiştir

> Not: "Reddedilecek" demek "kaldırın" değil, **"modele özellik olarak koymayın"** demek. Arayüzde bilgi amaçlı gösterebilirsiniz; ama modelin 41 sütununda yer kaplarlarsa hem gürültü hem de yanlış "neden bu skor?" açıklaması üretirsiniz (mevcut sitede tam olarak bu oluyor).

---

## 4. Binance'ten hangi veriler çekilmeli

### 4.1 Şu an çekilen (ve sorunları)
| Endpoint | Durum | Sorun |
|---|---|---|
| `/api/v3/klines` | ✅ çalışıyor (`data-api.binance.vision`) | Sadece OHLCV+quoteVolume kullanılıyor; **`takerBuyBaseVolume` alanı atılıyor** — oysa ücretsiz ve en değerli sinyal orada |
| `/api/v3/depth` | ⚠️ tek anlık görüntü | Sadece filtre için kullanılıyor; zaman serisi yok, modele girmiyor |
| `/api/v3/ticker/24hr` | ✅ | Evren seçimi |
| `fapi/*` (funding, OI, long/short) | ❌ **451 (ABD bloğu)** | Tüm futures özellikleri ölü |

### 4.2 Çekilmesi gerekenler (öncelik sırasıyla)

**P0 — ücretsiz, hemen, en yüksek getiri**
| Veri | Kaynak | Kullanım |
|---|---|---|
| **Taker buy/sell hacmi** | `klines` alanları 9–11 (`takerBuyBaseAssetVolume`, `takerBuyQuoteAssetVolume`, `numberOfTrades`) — **zaten indirdiğiniz veride var** | `taker_ratio = tb/v - 0.5`, z-skoru, 3/12/24 saatlik kümülatif (CVD yaklaşımı) |
| **Ortalama işlem büyüklüğü** | aynı alanlar: `quoteVolume / trades` | Balina/parçalı işlem ayrımı: bilet büyüklüğü artıyorsa kurumsal akış |
| **Basis (perp−spot)** | `fapi/v1/premiumIndex` (engellenirse spot+perp fiyat farkı ayrı kaynaklardan) | Aşırı pozitif basis = aşırı long; negatif = korku |
| **Funding oranı + tahmini** | `fapi/v1/fundingRate`, `premiumIndex` | 24s ufkun **en güçlü** adayı: ekstrem funding → squeeze/tasfiye |
| **Açık pozisyon (OI)** | `futures/data/openInterestHist` | `OI değişimi × fiyat yönü`: OI↑+fiyat↑ = yeni long (kırılgan), OI↑+fiyat↓ = yeni short (squeeze yakıtı) |
| **Top trader long/short** | `topLongShortPositionRatio`, `globalLongShortAccountRatio`, `takerlongshortRatio` | Kalabalığın konumu; kontra sinyal olabilir |

> ABD bloğu (451) sorunu: GitHub Actions runner'ları ABD'de. Çözüm: **EU runner** (self-hosted) veya **OKX/Bybit public API** (funding+OI aynı bilgi, blok yok). İki kaynağı karşılaştırıp tutarsızlığı raporlayın.

**P1 — ek maliyet/emek ama gerçek bilgi**
| Veri | Kaynak | Kullanım |
|---|---|---|
| **Emir defteri anlık görüntüleri (dakikalık)** | `depth?limit=100` → kendi arşiviniz | `bid/ask derinlik oranı`, ±%0,5 bant derinliği, **defter çekilmesi** (liquidity pull) hareketin öncüsü olabilir. Geriye dönük verilmediği için **bugünden arşivlemeye başlayın** |
| **Agresif işlem akışı (CVD)** | `aggTrades` (sayfalama) | Gerçek alıcı-satıcı agresifliği; taker hacminden daha hassas, ama pahalı. Sadece ilk 20 coin için |
| **Tasfiye akışı** | Resmî geçmiş endpoint yok; **OI düşüşü + funding ekstremi + hızlı fitil** ile vekil üretin | Tasfiye kaskadları en büyük 24s hareketlerini açıklar |
| **Emir sayısı / iptal oranı** | `aggTrades` + `depth` | Spoofing/pull tespiti (deneysel) |
| **Tick size / min notional** | `exchangeInfo` | Gerçekçi işlem simülasyonu, yuvarlama maliyeti |
| **Listeleme / delist duyuruları** | Binance CMS/announcement | En yüksek getirili "olay" sinyali; takvim özelliği olarak eklenir |

**P2 — kripto'ya özgü dış bilgi (site büyüdükçe)**
| Veri | Kullanım |
|---|---|
| Borsa net akışı (exchange inflow/outflow) | Büyük transfer → satış baskısı olasılığı |
| Stablecoin arzı (USDT/USDC) | Piyasa likiditesi yönü |
| BTC dominansı, toplam piyasa hacmi, "coin'lerin %X'i 20g MA üstünde" | **Piyasa genişliği = rejim kapısı** |
| ETF akışları, CME basis | Kurumsal talep; haftalık ufuk |
| Options skew / IV (Deribit) | Korku ölçüsü; 24s–7g |
| Makro takvim (FOMC, CPI) | Yüksek oynaklık pencereleri — **işlem açmama** kuralı olarak kullanılabilir |

### 4.3 Veri kalitesi kuralları (bunlar atlanırsa tüm edge kaybolur)
1. **Kapanmış mumdan başka bir şey kullanmayın.** Kapanmamış mumun `h/l/c`'si yanıltıcıdır.
2. **Her serinin yayın gecikmesi farklı.** Funding 8 saatte bir açıklanır, OI 1 saatte bir, long/short oranları gecikmeli. Hepsini **kendi yayın zamanına** hizalayın (mevcut `add_futures`'daki +1 saat ihtiyatı doğru bir başlangıç).
3. **Anlık görüntüyü (snapshot) geçmişe yapıştırmayın.** Emir defteri bugünün verisidir; dünün özelliği değildir. (Mevcut kod bunu doğru yapıyor — koruyun.)
4. **Merkezi fark kullanmayın.** `np.gradient`, `rolling(...).mean().shift(-1)`, `center=True` → **gelecek sızıntısı**. Bu deneylerde bunu bir kez ben de yaptım ve AUC 0,66'lık sahte bir "sinyal" üretti; fitilleri nedensel hale getirince 0,50'ye düştü. Sızıntı testini her özellik için otomatikleştirin (mevcut `test_future_features_do_not_look_ahead` iyi bir başlangıç, tüm yeni özelliklere genişletin).
5. **Hayatta kalma yanlılığı:** Evreni **geçmişte de** o gün var olan coinlerle kurun. Delist olan coinleri geriye dönük ekleyin; yoksa model sadece kazananları görür.
6. **Sembol birleştirme:** `BTC` + `USDT` yerine `baseAsset` kimliği + `exchangeInfo` filtresi kullanın (ASCII olmayan semboller, 1000PEPE tipi çarpanlar).

---

## 5. Tahmin gücünü gerçekten ne artırır (etki sırasıyla)

| # | Eklenen şey | Neden en güçlü | Ufuk | Ölçüm yolu |
|---|---|---|---|---|
| 1 | **Kalibrasyon + dürüst değerlendirme** (mevcut sitede üst kova %50→%11,7) | Söylenen sayı doğru olmadan hiçbir model işe yaramaz | anında | Kalibrasyon eğrisi + BSS + blok CI |
| 2 | **Taker akışı / CVD** | Fiyatın **nedeni**, fiyat değil; 1–24s ufukta en güçlü | 1–24 saat | Ablasyon: akış ailesi tek başına |
| 3 | **Funding + OI + tasfiye vekili** | Sıkışma ve kaskadları önceden gösterir; 24s ufkun doğal ufku | 4–72 saat | Ablasyon: pozisyonlanma ailesi |
| 4 | **Kesitsel (cross-sectional) sıralama** | "Hangi coin diğerlerinden daha iyi" sorusu, "bu coin yükselir mi"den daha öğrenilebilir; piyasa betası arındırılır | tümü | Per-timestamp LambdaRank; top-k lift |
| 5 | **Rejim kapısı** (BTC trendi, piyasa genişliği, volatilite rejimi) | Model rejime göre farklı davranmalı; 4 aylık veride tek rejim öğreniliyor | günler | Rejim bazında ayrı metrikler |
| 6 | **ATR ölçekli bariyer + R raporlaması** | Ölçülebilir, ulaşılabilir hedef; örnek sayısı ve netlik artar | — | Başabaş/EV tablosu |
| 7 | **Emir defteri zaman serisi** (arşivlemeye bugün başla) | Likidite çekilmesi hareketin öncüsü olabilir; geriye dönük alınamaz | 5–60 dk | 6 ay sonra ablasyon |
| 8 | **Olay takvimi** (listeleme, delist, unlock, makro) | En büyük hareketler olay kaynaklı | 1–72 saat | Olay günlerinde ayrı metrik |
| 9 | **Çoklu ufuk** (4s / 24s / 72s) | Kullanıcı 24 saat beklemez; 4s hem sık geri bildirim hem çok örnek | — | Ufuk başına ayrı model |
| 10 | **Daha uzun ve daha temiz geçmiş** (12 ay, delist dahil) | Rejim çeşitliliği; aşırı uyumu azaltır | — | Fold sayısı/CI genişliği |

> Bu listenin **hiçbiri** "bir gösterge daha ekle" değil. Hepsi **yeni veri, yeni hedef veya daha dürüst ölçüm**.

---

## 6. Mimari: 41 özellik yerine 12 özellik + disiplin

### 6.1 Özellik katmanları (önerilen)
```
KATMAN A — Çekirdek (6):        atr_pct · atr_ratio(14/56) · rel_volume · bb_width_squeeze ·
                                 trend_slope_ATRnorm (EMA20) · rsi_rank
KATMAN B — Bilgi (4):           taker_ratio_z · cvd_3h/24h · funding_z · oi_change_x_price
KATMAN C — Rejim (3):           btc_trend · breadth(% coins > MA20) · vol_regime
KATMAN D — Konum (2):           pos_7d · pos_30d (0–1 normalize)
KATMAN E — Etkileşim (2–3):     taker_ratio_z × atr_ratio · funding_z × oi_change · squeeze × breadth
```
Toplam **~17**; 35'ten az, 12'den fazla — ablasyonla her katmanın katkısı **kanıtlanmadan** eklenmemeli.

### 6.2 Normalizasyon kuralları (en sık yapılan hata)
1. Her fiyat/indikatör özelliğini **ATR% ile böl** (coin boyutu ve rejim farkını sil).
2. Momentum/osilatörleri **kesitsel yüzdelik sıraya** çevir (aynı saatte 125 coin arasında).
3. Hacim, OI, funding gibi farklı ölçekli serileri **kendi 30 günlük z-skoruna** çevir.
4. **Kural:** bir özellik, birimini kaybetmiyorsa (RSI=71 gibi) modele girmemeli.

### 6.3 Değerlendirme disiplini
- Yalnızca **zaman sıralı** bölme + purge/embargo (mevcut kod doğru).
- **Her metrik için taban çizgisi:** rastgele · vol-only · BTC-beta · "5 göstergeli basit model". Model bunları geçmiyorsa yayınlanmaz.
- **Ablasyon zorunlu:** her yeni aile, top-k metrikte blok CI'ları örtüşmeyen iyileşme göstermeli (bkz. `arastirma/ablasyon.py`).
- **Sadece test metriği** gösterilir; eğitim/AUC şişmesi ekrana çıkmaz (Deney 4).
- **Özellik sayısı tavanı:** tavanı koyun (ör. 20). Yeni özellik girecekse eskisi çıkacak.

### 6.4 Anti-pattern listesi (sitede asla olmamalı)
| Anti-pattern | Neden yanlış |
|---|---|
| "RSI 30 altı = al" | Trendde RSI 80'de kalır; kripto'da aşırı bölge = güçlü trend işareti olabilir |
| "Golden cross / MACD kesişimi" | Sinyal gecikmeli; backtest'te işlem maliyetiyle kaybeder |
| "5 gösterge onay verirse gir" | Korelasyonlu 5 sinyal ≈ 1 sinyal; sahte güven yaratır |
| Eğitim/backtest doğruluğu göstermek | Deney 4: %87 "doğruluk", %50 gerçek |
| Tek coin backtest | Örneklem yanlılığı; kesitsel doğrulama yok |
| Kapanmamış mumun fitilini kullanmak | Sızıntı; aynı mumda kapanışa göre karar verilemez |
| "Tüm göstergeler yeşil" panosu | Bilgi yok, ekran kalabalığı; karar kalitesini düşürür |
| Ham gösterge değerini model girdisi yapmak | Ölçek/birim karışır, model coin büyüklüğünü öğrenir |

---

## 7. 90 günlük plan

**Hafta 1–2 · Ölçüm altyapısı**
- `arastirma/ablasyon.py --real` gerçek veriyle çalıştır; gerçek AUC/BSS tablosunu çıkar.
- Kline'lardan **taker hacmi + işlem sayısı** özelliklerini üret (ekstra istek yok, aynı dosyada var).
- Sızıntı testini tüm yeni özelliklere genişlet.

**Hafta 3–4 · Pozisyonlanma verisi**
- EU runner veya OKX/Bybit ile funding + OI + long/short; 12 ay geçmiş.
- `funding_z`, `oi_change × price`, `basis` özellikleri; ablasyonda katkı ölç.

**Hafta 5–6 · Hedef ve değerlendirme**
- ATR ölçekli asimetrik bariyer + R raporlaması.
- Kesitsel sıralama hedefi (LambdaRank/softmax), top-k lift ile değerlendirme.
- Taban çizgileri + blok CI + BSS arayüzde.

**Hafta 7–8 · Rejim ve çoklu ufuk**
- BTC trendi, piyasa genişliği, vol rejimi kapıları; 4s/24s/72s modelleri.
- Rejim bazında ayrı metrikler.

**Hafta 9–12 · Arşivleme ve dış veri**
- Emir defteri dakikalık arşivi (bugün başlamazsa 3 ay sonra veri yok).
- Olay takvimi (listeleme/delist/makro), zincir üstü akış.
- 6 ay sonra defter verisiyle ilk ablasyon; sonuç yoksa **kaldır**.

**Başarı kriteri (bunlar sağlanmadan yeni gösterge eklenmez):**
1. Kalibrasyon üst kovasında |tahmin − gerçekleşen| < 5 puan.
2. BSS > 0 ve vol-only taban çizgisini **blok CI'ları örtüşmeyecek** şekilde geçmek.
3. Top-10 lift'te ablasyonla kanıtlanmış artış.
4. Kâğıt portföyde net (komisyon+spread) pozitif beklenti, ≥30 bağımsız işlem.

---

## 8. Deneyleri kendin çalıştır

```bash
cd arastirma
python gostergeler_analiz.py        # korelasyon + PCA: kaç bağımsız bilgi var
python sinyal_testi.py              # yöntem gerçek sinyali yakalıyor mu (kontrol grubu ile)
python gurultu_testi.py             # gösterge sayısı ↔ aşırı uyum
python ablasyon.py                  # aile bazında AUC/BSS/top-10 katkısı (sentetik)
python ablasyon.py --real           # aynı tablo, Binance'ten gerçek mumlarla (ağ gerekir)
```

Gereksinimler: `numpy pandas lightgbm scikit-learn` (repodaki `requirements.txt` ile aynı). Bu sandbox'ta dış ağ kapalı olduğu için `--real` modu çalıştırılamadı; kod hazır.

---

## 9. Sınırlar ve dürüst notlar

- **Sentetik piyasa** kullanıldı: gerçekçi (ortak faktör, oynaklık kümelenmesi, taker akışı) ama **uydurma**. Buradaki AUC'ler "gerçek kripto verisinde şu kadar kazanırız" demek değil. Kanıtladıkları şey **yöntemin ve uyarıların doğruluğu**: kontrol grubu 0,50'de kalıyor, enjekte edilen sinyal doğru ailede yakalanıyor, gösterge sayısı arttıkça aşırı uyum artıyor.
- **Bir kez kendi deneyimde sızıntı yaptım**: `np.gradient` ile üretilen fitiller gelecek bilgisi taşıdı ve sahte AUC 0,66 üretti. Nedensel fitile geçince 0,50'ye düştü. Bu, Bölüm 4.3'teki 4. kuralın neden hayati olduğunun canlı kanıtı.
- **Gerçek edge büyüklüğü bilinmiyor.** Bu doküman "şu verileri ekle, şu kadar kazanırsın" demiyor; "şu verileri ekle, **şu yöntemle ölç**, kazanç yoksa ekleme" diyor.
- Her şey `ANALIZ.md`'deki temel kısıtla sınırlı: **bariyer/maliyet matematiği göstergelerden bağımsızdır.** ±%10 hedefte başabaş %51'dir; göstergeler bunu değiştirmez, sadece olasılığı biraz daha isabetli tahmin etmenizi sağlar.

---

## 10. Hazır kod: özellik üretimi (sızıntısız, normalize edilmiş)

`arastirma/gostergeler.py` içindeki `feature_frame()` bu mimarinin çalışan referansıdır.
Aşağıdaki blok, üretime alınacak **minimum** özellik setini gösterir; her satırda sızıntı yorumu var.

```python
import numpy as np, pandas as pd

def safe_log_ret(c, n=1):
    """Kapanmış mumlardan; gelecek bilgisi yok."""
    return np.log(c / c.shift(n))

def core_features(df, btc, cfg):
    c, h, l, v = df.c, df.h, df.l, df.v
    r1 = safe_log_ret(c, 1)
    f = pd.DataFrame(index=df.index)

    # --- A. çekirdek: ölçek ve rejim --------------------------------------
    tr = pd.concat([h - l, (h - c.shift()).abs(), (l - c.shift()).abs()], axis=1).max(axis=1)
    atr14 = tr.ewm(alpha=1/14, adjust=False, min_periods=14).mean()
    atr56 = tr.ewm(alpha=1/56, adjust=False, min_periods=56).mean()
    f['atr_pct'] = atr14 / c                  # birim yok
    f['atr_ratio'] = atr14 / atr56            # oynaklık rejimi
    f['rel_volume'] = v / v.rolling(24, min_periods=12).mean()
    f['vol_z'] = (f.rel_volume - f.rel_volume.rolling(168, min_periods=72).mean()) / \
                 (f.rel_volume.rolling(168, min_periods=72).std() + 1e-12)
    ma20 = c.rolling(20).mean(); sd20 = c.rolling(20).std()
    f['bb_width'] = 4 * sd20 / ma20
    f['squeeze'] = f.bb_width / f.bb_width.rolling(168, min_periods=72).mean()

    # --- A. trend: SADECE normalize eğim (kesişim yok) --------------------
    ema20 = c.ewm(span=20, adjust=False).mean()
    f['trend_slope'] = ema20.pct_change(6) / f.atr_pct
    f['ema_gap'] = (c.ewm(span=12, adjust=False).mean() /
                    c.ewm(span=48, adjust=False).mean() - 1) / f.atr_pct

    # --- A. momentum: TEK osilatör, sıralanmış ---------------------------
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    dn = (-d).clip(lower=0).ewm(alpha=1/14, adjust=False).mean()
    rsi = 100 - 100 / (1 + up / (dn + 1e-12))
    f['rsi_norm'] = (rsi - 50) / 50            # -1..1, birimsiz
    # KESİTSEL sıra: aynı saatteki tüm coinler arasında yüzdelik (scanner'da uygulanır)
    # f['rsi_rank'] = f.groupby(level=0).rsi_norm.rank(pct=True)

    # --- B. emir akışı: ücretsiz, kline içinde hazır ---------------------
    if 'tb' in df:                              # takerBuyBaseAssetVolume
        ratio = df.tb / (v + 1e-12) - 0.5       # -0.5..+0.5
        f['taker_z'] = (ratio - ratio.rolling(72, min_periods=24).mean()) / \
                       (ratio.rolling(72, min_periods=24).std() + 1e-12)
        f['cvd_3h'] = (df.tb - (v - df.tb)).rolling(3).sum() / v.rolling(24).sum()
        f['cvd_24h'] = (df.tb - (v - df.tb)).rolling(24).sum() / v.rolling(24).sum()
        f['ticket_z'] = (np.log((df.qv if 'qv' in df else v * c) / (df.ntrades + 1e-12))
                         .pipe(lambda s: (s - s.rolling(72, min_periods=24).mean()) /
                                         (s.rolling(72, min_periods=24).std() + 1e-12)))
    # --- B. pozisyonlanma (futures erişimi varsa) -----------------------
    # f['funding_z'], f['oi_x_price']  → radar/features.py'deki as-of join ile

    # --- C. rejim --------------------------------------------------------
    br = btc.c.pct_change()
    f['btc_trend'] = btc.c.rolling(48).mean() / btc.c.rolling(168).mean() - 1
    f['btc_vol'] = br.rolling(24).std()
    f['beta'] = r1.rolling(168).cov(br)
    f['beta'] /= (br.rolling(168).var() + 1e-12)

    # --- D. konum (0-1, birimsiz) ----------------------------------------
    lo168, hi168 = l.rolling(168, min_periods=72).min(), h.rolling(168, min_periods=72).max()
    f['pos_7d'] = (c - lo168) / (hi168 - lo168 + 1e-12)
    lo720, hi720 = l.rolling(720, min_periods=168).min(), h.rolling(720, min_periods=168).max()
    f['pos_30d'] = (c - lo720) / (hi720 - lo720 + 1e-12)

    return f.replace([np.inf, -np.inf], np.nan)
```

**Kline alanlarını artık atmayın.** `radar/data.py` şu an ilk 6 alanı alıyor
(`df.iloc[:, :6]`). Taker verisi için:

```python
df = pd.DataFrame(out)
df.columns = ['t', 'o', 'h', 'l', 'c', 'v', '_ct', 'qv', 'ntrades',
              'tb', '_tbq', '_ignore']
df = df[['t', 'o', 'h', 'l', 'c', 'v', 'qv', 'ntrades', 'tb']].astype(float)
```
Bu, **tek satırlık bir değişiklikle** modele 4 yeni ve gerçek bilgi kaynağı ekler
(taker buy hacmi, quote hacmi, işlem sayısı, ortalama bilet). Mevcut 41 özellikten
daha değerlidir ve ek istek maliyeti **sıfırdır**.

---

## 11. Tek sayfalık özet

| Soru | Cevap |
|---|---|
| Hangi göstergeler ölçüt olmalı? | **ATR (zorunlu), göreli hacim, Bollinger genişliği, EMA eğimi, RSI (tek), ADX (rejim), VWAP (intraday), SAR veya SuperTrend (biri)** |
| Hangileri gereksiz? | **KDJ, WR, StochRSI, CCI** — aynı bilgi; OBV yerine **taker hacmi** |
| Kaç gösterge? | **~17 özellik, tavan 20.** 35 gösterge ablasyonda daha kötü (0,452 vs 0,510) |
| Ham değer mi? | **Hayır.** Hepsi ATR'ye bölünmüş, z-skorlanmış veya kesitsel sıralanmış olmalı |
| Hangi veriler çekilmeli? | **Taker buy/sell + işlem sayısı (ücretsiz, kline içinde), funding, basis, OI, long/short, emir defteri arşivi, olay takvimi** |
| En büyük risk? | **Aşırı uyum:** 5→60 gösterge eğitim AUC 0,73→0,87, test 0,51→0,50 |
| Tahmin gücünü en çok ne artırır? | **Kalibrasyon + yeni bilgi kaynağı (akış, pozisyonlanma) + kesitsel sıralama + rejim**; yeni gösterge değil |
| Nasıl ölçülür? | **Ablasyon + taban çizgileri + blok güven aralığı + sadece test metriği** |
