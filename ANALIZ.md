# Coin Radar — Kripto Analist Değerlendirmesi

**Tarih:** 10 Kasım 2026 · **İncelenen commit:** `b679de8` ("veri güncellendi") · **Üretilen veri:** `docs/data.json` (2026-11-10 00:57 UTC), `docs/report.json`

> **Ekran taslağı:** Önerdiğim arayüzün çalışan hali `docs/oneri/index.html` dosyasında — sayfa repodaki **gerçek** `docs/data.json` ile besleniyor, eşik oynatıcı ile EV tablosunu canlı hesaplıyor.

Bu rapor repoyu satır satır okumakla yetinmiyor; repo içindeki **gerçek çıktı dosyaları üzerinden** ölçüm yaptım (olasılık dağılımı, kalibrasyon eğrisi, eşik bağları, kayıt defteri tutarlılığı, maliyet sonrası beklenen değer, volatilite-varlık sınıfı kırılımı). Tüm sayılar `docs/data.json` ve `docs/report.json`'dan hesaplandı; hangi sayının nereden geldiği ilgili bölümde yazıyor.

---

## 1. Yönetici özeti

Site "ilkeli" değil, aslında **mühendislik disiplini yüksek ama hedefi yanlış seçilmiş** bir sistem. Kod kalitesi, sızıntı kontrolleri, testler ve dürüst uyarı metinleri Türkiye'deki benzerlerinin çok üstünde. Buna karşın proje şu üç sorundan dolayı **tahmin "tutma" oranını anlamlı biçimde artıramaz**:

| # | Sorun | Ölçüm |
|---|---|---|
| 1 | **Hedef iktisaden kaybediyor.** ±%10 bariyer + %0,1 komisyon → başabaş isabet **%51**. Evrendeki en yüksek olasılık **%50,0**; hiçbir coin pozitif beklenen değer üretmiyor. | Top-10 ortalama p=%18,8 → işlem başına **−%6,5 EV** |
| 2 | **Olasılıklar aşırı özgüvenli ve kaba.** Kalibrasyon eğrisinin en üst kovası: tahmin %50, gerçekleşen **%11,7** (n=443). 125 coin için yalnızca **13 farklı olasılık değeri** var; 10. sıradaki değerde **10 coin eşit** → top-10 listesi fiilen hacme göre kesiliyor. | `p_up` ∈ {0, 0.0029, 0.0185, 0.0211, 0.0256, 0.0271, 0.0286, 0.0293, 0.0986, 0.1159, 0.1538, 0.2222, 0.5} |
| 3 | **Modelin volatilite dışında öğrendiği bilgi çok az.** Olasılık sıralaması ile "sadece son 24s volatilite" sıralaması arasında Spearman **0,851**; top-10 listelerinin **7/10**'u aynı. Volatilite sabit tutulduğunda ATR ile kalan kısmi korelasyon yalnızca **0,18**. | `spearman(p_up, vol24)=0.85`, `spearman(p_up, atr14)=0.80` |

Ayrıca **tüm vadeli işlem (futures) verisi her taramada ölü**: 125 coinin 125'inde funding, OI, long/short endpointleri `451` dönüyor (GitHub Actions IP'leri ABD'de, Binance futures ABD'yi bloke ediyor). Yani 13 özellik (funding, OI değişimi, global/top trader long-short) modelde **hiç yok** — `report.json` bunu "sabit veya eksik" diye zaten yazıyor. Oysa 24 saatlik squeeze/tasfiye hareketlerini en iyi önceden haber veren sinyaller tam olarak bunlar.

Özet yargı: **sorun arayüzün "ilkel" olması değil, ürünün ölçtüğü şeyin ticarete uygun olmaması.** Arayüz bu yüzden ilkel görünüyor, çünkü arkasında raporlanabilir tek bir dürüst sayı (maliyet sonrası net beklenti) yok.

---

## 2. Gerçekten iyi yapılanlar (bunları koruyun)

- **İlk-temas etiketi** (`labels()`): "24 saatte %10 gördü mü" değil, "hangi bariyere önce değdi" — doğru tanım. Aynı saatlik mumda iki bariyer de aşılırsa örneği `belirsiz` sayıp dışlıyor. Bu, çoğu ticari sinyal sitesinde olmayan bir dürüstlük.
- **Purge/embargo** (`assert_no_leakage`): eğitim–kalibrasyon–test arasında hedef ufku kadar boşluk zorunlu ve assert ediliyor. Sızıntı testi (`test_future_features_do_not_look_ahead`) gerçekten 700. saatten sonrasını bozup ilk kısmın değişmediğini doğruluyor.
- **Snapshot'un geçmişe yapıştırılmaması**: emir defteri ve güncel OI eğitime girmiyor; futures verileri ihtiyatlı gecikmeyle hizalanıyor (`add_futures` +1 saat). Bu, en sık yapılan backtest hatasının engellenmesi.
- **Isotonic kalibrasyon + walk-forward**, ayarların `config.json`'da olması, testlerin (10/10 geçiyor) ve GitHub Actions'ın olması, hiçbir sırrın repoda olmaması, statik hosting ile sıfır maliyet.
- **Dürüst uyarı metinleri**: "yatırım tavsiyesi değildir", "seçim/sağkalım yanlılığı", "güven göstergesi istatistiksel güven aralığı değildir". Bu metinler sorunları **gizlemiyor, itiraf ediyor** — iyi bir temel.

---

## 3. Ölçülen sorunlar

### 3.1 Hedef ve iktisat (en kritik)

**Bariyer matematiği.** ±%10 simetrik bariyerde kazanç %10, kayıp %10. %0,1 gidiş-dönüş maliyetle kazanç %9,8, kayıp %10,2 olur:

```
başabaş p = 10,2 / (9,8 + 10,2) = %51,0
```

Gerçekleşen en yüksek olasılık (SOXSB) **%50,0**. Yani **tüm evrende EV ≤ 0**. Top-10'un ortalama p'si %18,8 → işlem başına **−%6,5**. Walk-forward'da gerçekleşen top-10 isabeti %13,5 (up) / %16,5 (dn) → **−%7,5 / −%6,9**.

Bu, "model kötü" demek değil; **kurgu matematiksel olarak kaybediyor**. İsabet oranını %13'ten %35'e çıkarsanız bile ±%10/%10 bariyerde para kaybedersiniz. Site şu an "yüzde kaç kazanılıp kaybedileceğini yazıyor" iddiasında ama **maliyet sonrası beklenen değeri hiç hesaplamıyor**; kullanıcı %13 isabeti "%13 kazanç" sanabilir.

**Çözüm üç yol:**
1. **Asimetrik bariyer**: hedef 3×ATR yukarı, stop 1×ATR aşağı → başabaş p = **%25**. ⚠️ Bu, kâr yaratmaz: sürüklenmesiz fiyatta P(üst bariyere önce değme) = stop/(hedef+stop) = başabaşın ta kendisi. Faydası **ulaşılabilir bir hedef, daha az belirsiz örnek ve dürüst R raporlaması** (bkz. Bölüm 9).
2. **Daha yüksek baz oranlı hedef**: ±%10/24s baz oranı %4,2 (up) — çok nadir. ±%5/24s baz oranı simülasyonda **%27**; 3×ATR/24s **%35**. Baz oranı yükselince hem örnek sayısı hem öğrenilebilirlik artar.
3. **Volatiliteye göre ölçeklenmiş bariyer** (`atr_target_enabled` zaten kodda var ama kapalı) → coin başına farklı eşik, aynı "R" biriminde karşılaştırılabilir sonuç.

> **Ölçülmüş uyarı:** Bu üç maddenin hiçbiri tek başına **pozitif beklenti yaratmaz**; sadece ölçümü dürüstleştirir ve hedefi ulaşılabilir kılar. Opsiyonel durdurma teoremi gereği sürüklenmesiz fiyatta hangi bariyer oranı seçilirse seçilsin EV = 0 − maliyet. Gerçek avantaj yalnızca **modelin kalibrasyonu + sürüklenme tahmini** varsa doğar.

> Somut öneri: **hedefi ve stopu ATR cinsinden tanımlayın, sonucu R (risk birimi) olarak raporlayın, maliyeti düşün.** "Silver" gösterge %10 değil, "1,5R'ye ulaşma olasılığı" olmalı.

### 3.2 Olasılıklar neden 13 adımda?

`docs/data.json`'daki 125 coinin `p_up` değerleri yalnızca 13 farklı sayıdan oluşuyor ve bu sayılar kesirli olarak çok küçük paydalara sahip:

| p_up | yaklaşık kesir | yorum |
|---|---|---|
| 0,500000 | 1/2 | 2 olay |
| 0,222222 | 2/9 | 2 olay |
| 0,153846 | 2/13 | 2 olay |
| 0,115942 | 8/69 | 8 olay |
| 0,098592 | 7/71 | 7 olay |
| 0,029340 | 11/375 | 11 olay |

Bu, **isotonic regresyonun kaç basamaklı olduğunu** doğrudan gösteriyor. Kaynağı:

- `sample_stride_hours = 24` → eğitim **yalnızca 00:00 UTC'de açılan mumlarda** örnekleniyor (`thin()`: `hours % 24 == 0`).
- Kalibrasyon kümesi = son zamanların %10'u, o da 24'e bölünüyor → **~300 saatlik pencere / 24 ≈ 12–13 farklı saat** × 125 coin ≈ 1.500 satır, ~65 olay.
- Isotonic bu ~13 zaman kümesine oturtuluyor → çıktı **13 basamaklı** bir merdiven.

Sonuçları:
- **Eşitlik kırılamıyor**: 10. sıradaki `p_up = 0,115942` değerinde **10 coin birden** var. Top-10 seçimi pratikte "hangi coin önce geldiyse" (yani hacim sırası) ile yapılıyor. Aynı skorla listeye giren/girmeyen coin arasında hiçbir istatistiksel fark yok.
- **İç-gün mevsimselliği asla öğrenilemiyor**: `utc_hour` ve `hours_to_funding` "sabit veya eksik" diye düşürülmüş (`report.json → feature_selection.up.dropped`). Sebep tam olarak stride'ın sabit fazı. Funding saatleri (00/08/16 UTC) 24 saatlik kripto piyasasında gerçek bir etkiye sahiptir; model bunu göremiyor.
- **Kalibrasyonun en üst basamağı "2 olay" ile kuruluyor.** %50 olasılık, 2 gözlemin ortalaması. Aşağıdaki tabloda bunun bedeli görülüyor.

### 3.3 Kalibrasyon: en üst kova feci özgüvenli

`metrics.up.calibration_curve` (kalibre edilmiş olasılıklar üzerinde):

| Tahmin ort. | Gerçekleşen | Örnek |
|---|---|---|
| %3,0 | %2,6 | 84.457 |
| %12,9 | %10,2 | 20.182 |
| %20,4 | %14,0 | 515 |
| **%37,0** | **%12,0** | 1.272 |
| **%50,0** | **%11,7** | 443 |

Kalibrasyon eğrisi düz olması gerekirken **üst kuyrukta tamamen çöküyor**. Yani sitenin en üstte gösterdiği coinlerde olasılık **4 katına kadar şişirilmiş**. Düşüş tarafı daha kötü: %44 tahmin → %37 gerçekleşen ama n=54.

**Bu tek bulgu, "p" değerinin ekranda tek başına gösterilmemesi gerektiğinin kanıtı.**

### 3.4 Değerlendirme metrikleri yanıltıcı (fold karıştırma + örtüşme)

- **Pooled AUC bozuk.** Düşüş modeli: fold bazında AUC **0,700 / 0,751 / 0,698** ama `metrics.dn.auc` = **0,560**. Sebep: her fold kendi isotonic eğrisini kullanıyor, sonra test tahminleri tek havuzda birleştiriliyor. Farklı ölçeklenmiş olasılıklar aynı AUC'ye girince sıralama bilgisi kayboluyor. **Raporlanan 0,560 gerçek performans değil; birleştirme hatası.** (Doğrusu: fold içi AUC'lerin ortalaması veya ham skorların havuzlanması.)
- **Brier kötü, kimse fark etmiyor.** Up Brier 0,04063, iklimsel tahmin (hep baz oranı) Brier 0,04044 → **Beceri Skoru BSS = −%0,5**. Düşüşte −%5,9. Yani model, "herkese sabit %4,2 de" diyen bir tablodan **daha kötü** kalibre. AUC 0,75 ile Brier'ın bu kadar kötü olması, sıralamanın iyi ama **ölçeğin bozuk** olduğunun klasik işaretidir.
- **Test satırlarının %95'i birbirinin kopyası.** Test 106.875 satır; ufuk 24 saat ve saatlik örnekleme → bağımsız blok sayısı ≈ 855/24 ≈ **36**. Top-10 metrikleri 8.550 satırdan geliyor ama etkin örnek 356 blok. Güven aralığı:
  - Naif (8.550 saat): %13,5 → **[%12,8 – %14,3]**
  - Blok düzeyi (356 blok): %13,5 → **[%10,3 – %17,4]**
  
  Yani "istatistiksel olarak anlamlı fark" sandığınız her şey aslında gürültü olabilir. Ayrıca **eğitim 24'e seyreltilmiş (~15 bin satır), test seyreltilmemiş** — eğitim ve test aynı bilgi yoğunluğunda değil.
- Karşılaştırma tabanı yok: raporda **"sadece volatilite sıralaması"** veya **"rastgele"** satırı yok. 0,751 AUC tek başına bir şey ifade etmez; vol-only taban çizgisi 0,74 ise model hiçbir şey eklemiyor demektir — ki bu repoda durum buna çok yakın (bkz. 3.5).

### 3.5 Modelin öğrendiği nedir? (volatilite, başka az şey)

125 coinin güncel özellikleriyle yaptığım kontroller:

| İlişki | Spearman |
|---|---|
| `p_up` ↔ `vol24` | **0,850** |
| `p_up` ↔ `atr14` | 0,803 |
| `p_up` ↔ `vol_zscore` | 0,165 |
| `p_up` ↔ `ret24` | 0,087 |
| `p_dn` ↔ `ret24` | 0,505 |
| `p_up` ↔ `atr14` (**vol24 sabitken kısmi**) | **0,18** |

Ve bağımsız bir kontrol olarak: her coinin son 24s saatlik volatilitesini alıp, ±%10 bariyerine 24 saatte ilk-temas olasılığını GBM ile 6.000 yol üzerinden simüle ettim:

- Evren medyanı: **%3,8** (baz oran %4,2 ile tutarlı — iyi işaret)
- **Volatiliteye göre ilk 10 coin**: medyan **%33,6**, 90. yüzdelik %18,3
- Modelin top-10'unda gerçekleşen **%13,5**
- İki listenin örtüşmesi: **7/10**

İki çıkarım:
1. Model pratikte **"en oynak 10 coin"** listesinin pürüzsüzleştirilmiş hâli. Volatilite dışındaki katkı marjinal.
2. Gerçekleşen %13,5, GBM'nin %33,6 beklentisinin çok altında → **vol24 kalıcı değil** (oynaklık kümeleniyor ama ortalamaya dönüyor). Model "dün çok oynadı" diyen coinleri seçiyor; bugün oynaklık düşüyor. Bu, volatilite özelliklerine **ortalamaya dönüş / kalıcılık** boyutu eklenmesi gerektiğini gösteriyor (`vol24/vol168`, `vol_zscore` var ama ağırlık kazanmamış; `vol24` tek başına baskın).

### 3.6 Veri ve evren sorunları

**a) Futures tamamen ölü (P0).** `data.json`'daki her coinde:
```
funding: 451 Client Error ... fapi/v1/fundingRate
oi: 451 ... futures/data/openInterestHist
global_ls: 451 ... globalLongShortAccountRatio
top_ls: 451 ... topLongShortAccountRatio
current_oi: 451 ... fapi/v1/openInterest
```
125/125 coin, 5/5 endpoint. Sebep: GitHub Actions runner'ları ABD'de, `fapi.binance.com` ABD IP'lerine **451 (Unavailable For Legal Reasons)** dönüyor. Spot için `data-api.binance.vision` kullanıldığı için kripto fiyat verisi sorunsuz; vadeli kısım tamamen çökmüş.
- 13 özellik (funding_rate, funding_mean24, funding_change24, OI ve değişimleri, global_ls, top_ls) **hiç hesaplanmıyor** → `report.json` "sabit veya eksik" diyor.
- Bunlar 24 saatlik hareketlerin **en bilgilendirici** ailesidir: funding ekstremleri, OI patlaması + fiyat düşüşü (short squeeze yakıtı), top trader konumu.
- Aynı şeyi `futures_errors` alanının **her coinde tekrar tekrar** yazılması gösteriyor: arayüzde hiç görünmüyor, `data.json`'a ~60 KB çöp ekliyor.
- **Çözüm:** (i) ABD dışı runner (self-hosted EU) veya (ii) OKX/Bybit public funding+OI (aynı bilgi, engel yok) ile çapraz kaynak, veya (iii) en azından bir "veri sağlığı" bandı ve `model_mode: spot_only` etiketi. Şu an site, modelin yarısı ölüyken bunu hiç söylemiyor.

**b) Tokenize hisse senetleri evreni ele geçirmiş (P0).** 125 coinin **49'u** (SNDKB, NVDAB, SOXLB, MUB, INTCB, TQQQB, AAPLB, MSFTB…):

| | Tokenize hisse (49) | Kripto (76) |
|---|---|---|
| Medyan \|24s değişim\| | **%5,51** | %1,31 |
| Medyan ATR | %1,48 | %1,34 |
| Medyan `p_dn` | **%14,5** | %2,7 |
| Hacim payı | %13,6 | %86,4 |

- **Top-20 yükseliş adayının 17'si, top-10 düşüş adayının 10'u hisse.** Liste "en oynak" listesi olduğu için otomatik olarak hisse senedi listesine dönüşüyor.
- Bunlar 24 saat kesintisiz işlem görmüyor: ABD seansı dışında fiyat donuyor, açılışta **gap** oluşuyor. Bariyer modelinin temel varsayımı (yol sürekliliği, ilk temas sırası) seans gaplarında çöküyor — bir gap iki bariyeri de aynı mumda aşabilir, o örnek `belirsiz` diye atılıyor. Yani model bu varlıklarda **sistematik olarak ölçemediği** örnekleri dışlıyor.
- Kripto ve hisse aynı modelde, aynı özellik uzayında: dağılımlar farklı, saat dilimi etkisi farklı, haber kaynağı farklı.
- **Çözüm:** varsayılan olarak **ayrı evren / ayrı model** ya da en azından `asset_class` özelliği + arayüzde sınıf filtresi ve hisselerde kesinlikle **seans farkındalıklı** etiketleme (sadece seans içi saatleri say) ve gap uyarısı.

**c) Sabit coin ve para birimleri hâlâ içeride (P1).** `BFUSD` (fiyat 0,9999, ATR %0,009) ve `EURI` (EUR stablecoin) evrende. `skip_assets` listesi elle tutuluyor ve kaçırıyor. Kural tabanlı filtre ekleyin: **son 30 günde ATR < %0,2 veya |90 günlük getiri| < %2 olan varlıkları otomatik çıkar** (stablecoin, wrapped, para birimi hepsini yakalar).

**d) Evrenin %61'i eleniyor.** 322 adaydan **194'ü "spread/derinlik filtresi"**, 3'ü "kesintisiz geçmiş yok" diye atılmış; 125 coin kalmış. Sorun: filtre **tek bir anlık görüntüye** dayanıyor (`depth?limit=500`), ve README "emir defteri modele girmez" dese de **evreni belirlediği için örnek seçimine giriyor**. Ayrıca %0,5 spread eşiği altcoinlerde çok sıkı → likit olmayan ama hareketli coinler sistematik olarak dışlanıyor, yani model **sadece "kolay" coinlerde** eğitiliyor ve canlıda da sadece onları görüyor. Bu bir **seçim yanlılığı** ve raporda yalnızca tek satırlık bir uyarı.
- **Çözüm:** spread/derinliği **birkaç saatlik ortalamayla** ölçün (ör. son 24 saatin 6 örneklemi), eşiği gevşetin (spread ≤ %1, derinlik ≥ 25 bin $) ve filtrelenen coinleri raporda **gerekçe dağılımıyla** gösterin. Alternatif: iki katmanlı evren — "işlem yapılabilir" (likit) ve "izlenen" (likit değil ama skorlanır, arayüzde gri).

**e) Geçmiş kısa.** `kline_pages: 3` → 3.000 saat ≈ 4,2 ay. `min_history_hours: 720` (30 gün). 4 ayda 24 saatlik etiketlerle coin başına ~5 bağımsız olay var. Walk-forward 3 fold + kalibrasyon için bu **çok az**; ayrıca piyasa rejimi (tek bir boğa/ayı dönemi) öğreniliyor. **En az 12 ay** (9 kline sayfası) hedefleyin; coin başına değil, **kesitsel** öğrenme yaptığınız için toplam örnek artar ama rejim çeşitliliği kritik.

**f) İzleme/delist alanı ölü.** `monitoring.status` her zaman `unknown` (spot `exchangeInfo` etiket alanı vermiyor). Arayüzde 125 coin için "bilinmiyor" yazıyor — bilgi değeri sıfır, güveni düşürüyor. Ya Binance duyuru API'si ile gerçekten doldurun ya da alanı kaldırın.

**g) ASCII olmayan sembol.** `牛来` evrende. URL, CSV, arama ve `symbol + 'USDT'` birleştirmelerinde kırılgan. Sembollerin `baseAsset` kimliğini ayrı tutun, görünen adı ayrı.

### 3.7 Boru hattı ve kayıt defteri hataları

Bunlar "tahmin tutma oranını" **doğrudan bozan** hatalar olduğu için ayrı bölüm:

1. **Aynı saatte iki tarama → çift kayıt.** `pending` içinde `2026-11-10T01:00` için **32 kayıt** var (15 up + 17 dn), oysa `top_k=10` → 20 olmalı. İlk 10 kayıt eski olasılıklarla (0,233), sonrakiler yeni olasılıklarla (0,222/0,154). Sebep: `t0 = now.floor('h') + 1h` aynı saate düşüyor ve `seen` kümesi yeni eklenenlerden önce kurulmuş; manuel tetikleme + zamanlanmış çalışma aynı saate denk gelince liste şişiyor. Aynı saatte iki farklı model sürümünün tahmini tek bir "zaman" altında karışıyor → isabet istatistiği bozuluyor.
   - **Düzeltme:** `(t, sym, side)` anahtarını **ekleme sırasında** kontrol et; bir zaman damgası için tek tarama kabul et (`scan_id` ekle, aynı saatte yeni tarama varsa eskisini `superseded` işaretle ve isabet hesabından çıkar).

2. **`track` boş → sitenin en önemli sayısı yok.** Ana sayfadaki "canlı isabet (N tahmin)" alanı boş çünkü hiçbir tahmin sonuçlanmamış. `pending` 92 kayıt, 4 farklı zaman (05:00, 15:00, 23:00, 01:00). 6 saatlik cron'a rağmen 05/15/23 aralıkları düzensiz → taramalar arası boşluklar var ve hiçbiri 24 saatini doldurmamış. Ürün için kritik: **hiçbir zaman sonuç üretmeyen bir takip paneli**, sistemin kendi doğruluğunu kanıtlayamaması demek.
   - **Düzeltme:** tahminleri **bağımsız bloklar** olarak yönetin (coin+yon başına aynı anda tek açık tahmin); sonuçlanınca `track`'e taşıyın; 24 saatlik ufuk tamamlanmadan yeni tahmin açmayın. Panelde "açık pozisyon" ve "sonuçlanmış" ayrımı net olsun.

3. **Sessiz budama = hayatta kalma yanlılığı.** `resolve()`: coin evrenden çıkarsa (`dfs` içinde yok) veya 72 saatten eski tahmin çözülemezse kayıt **hiçbir iz bırakmadan atılıyor** (`if now - t0 < h*3: keep.append`) . Yani delist olan / likiditesi düşen / veri gelmeyen coinlerin tahminleri "tutmadı" olarak değil, **yok** olarak sayılıyor → canlı isabet oranı yukarı yanlı. Mum eksikse de `continue` ile aynı şekilde kayboluyor.
   - **Düzeltme:** `result: 'veri_yok'` / `'evrenden_cikti'` durumları ekleyin ve **paydada tutun**, ayrı gösterin.

4. **Fiyat kayıtları yanlış şeyi ölçüyor.** Kullanıcı "o fiyattan alınırsa 24 saat sonra yüzde kaç kazanılır/kaybedilir" bekliyor. Kod ise 24 saat içindeki **en yüksek ve en düşük** fiyatı yazıyor. Bu bir **oynaklık ölçümü**, bir strateji sonucu değil:
   - Giriş → 24 saat sonraki **çıkış fiyatı** (gerçek getiri) yok.
   - **Hedef mi stop mu önce değdi** (path) yok.
   - **Komisyon, spread, kayma** yok (README'de "teorik" deniyor ama tabloda "+%8,4" görünen sayı kâr sanılıyor).
   - **MFE/MAE** (maksimum lehte/aleyhte hareket) ayrı ayrı var ama "hedefe ulaştı mı" bilgisi yok.
   - **Aynı coin 15 dakika arayla iki kez kaydedilmiş** (00:42 ve 00:57 batch'leri, 20 satır = 10 coin × 2). Her taramada koşulsuz yeni kayıt açılıyor.
   - `status: 'complete'` "24 saat doldu" demek; "hedefe ulaştı" değil. Arayüzde "24 saat tamamlandı" yazıyor, kullanıcı "tuttu" sanabilir.
   - Hata durumunda eski değerler korunup `status` yine `pending` bırakılıyor → tabloda eski rakamla yeni satır karışıyor.

5. **`resolve()` saatlik mumla dakika hassasiyetinde karar veriyor.** Giriş fiyatı "ilk tam mumun açılışı"; aynı mumda iki bariyer de görülürse `belirsiz`. Doğru, ama bu, **yüksek volatiliteli coinlerde olayların büyük kısmının atılması** demek (ve tam olarak modelin sevdiği coinler bunlar). 1 dakikalık mumlarla (zaten `price_history` için çekiliyor) sıralama çözülebilir → belirsiz oranı düşer, değerlendirme daha adil olur.

6. **Model her 6 saatte sıfırdan eğitiliyor ve son 3 haftayı hiç görmüyor.** Nihai model `split_at` ile: kalibrasyon son %10, eğitim ondan 24 saat öncesine kadar → **son ~1 ay eğitime girmiyor**. Yeni listeleme/trend bilgisi modele ulaşmıyor. Ayrıca her çalıştırmada 2 yön × 3 fold × 300 ağaç → gereksiz maliyet; model versiyonlanmıyor (`model_hash` yok), yani aynı girdi için farklı çıktı üretildiğinde kimse fark etmiyor.

7. **`features()` içinde `vol_zscore` tanımı: paydada `vol24.rolling(168)` var**, yani z-skorun kendisi de gecikmeli; olması gereken "bugünkü oynaklık / geçmiş oynaklık dağılımı". Küçük ama önemli: ekranda "Normalden sapma: 0,25 z" yazıyor, bu sayı sıralamayla 0,165 korelasyona sahip — yani neredeyse bilgi taşımıyor. Daha iyi: `log(vol24) - log(vol168)` ve yüzdelik sıra.

8. **Testler yeşil ama kritik şeyleri test etmiyor.** 10/10 geçiyor (doğruladım). Eksikler: aynı saatte çift tarama, eşitlik (tie) kırma, CI hesabı, `resolve` budama davranışı, kayıt tekrarı, `thin()` fazı. Bunlar bu repodaki gerçek hataların tam listesi — her biri için bir test yazılmalı.

---

## 4. Ne eklenmeli, ne çıkarılmalı

Öncelik: **P0 = tahmin kalitesini doğrudan belirler**, P1 = güvenilirlik, P2 = cila. "Etki" tahminleri bu repo için gerçekçi.

### 4.1 ÇIKARIN / kapatın

| Ne | Neden | Aksiyon |
|---|---|---|
| **±%10 simetrik bariyer varsayımı** | Başabaş %51 → yapısal olarak EV<0 | Asimetrik veya ATR ölçekli bariyere geç; R cinsinden raporla |
| **%50/39/15 gibi 2–13 olaylı olasılık basamakları** | Kalibrasyon güvenilmez, tie kırılamıyor | Min. olay/basamak kuralı; altında "rank only" göster |
| **"Güven: yüksek" etiketi** | 125/125 coin "düşüş yönünde yüksek" — hiçbir ayrım yok | Kaldır; yerine "kalibrasyon basamağında kaç olay var" yaz (2 olay = güven yok) |
| **Tek başına "p" yüzdesi** (özellikle üst kuyrukta) | Kalibrasyon eğrisi üst kovada %50→%11,7 | Yüzdelik sıra + blok CI + tek bir dürüst sayı (maliyet sonrası EV/R) |
| **"Güven: orta/yüksek" alanı** | 125/125 coin "orta" veya "yüksek"; hiçbir ayrım yok | Kaldır veya "kaç bağımsız olay" sayısıyla değiştir |
| **İzleme/delist: bilinmiyor** | Her coin için aynı, bilgi sıfır | Gerçek kaynak bağlanana kadar kaldır |
| **`futures_errors` (coinde tekrar)** | 125×5 satır çöp, UI'da görünmüyor | Tek bir veri sağlığı bandına taşı |
| **Tokenize hisseleri kripto ile aynı listede karıştırmak** | Farklı dağılım/gap/seans; listeyi ele geçiriyor | Ayrı sınıf, ayrı model veya varsayılan kapalı |
| **`utc_hour` benzeri özelliklerin stride yüzünden ölmesi** | İç-gün/funding mevsimselliği kayıp | Fazı coin başına döndür (aşağıda tek satır) |
| **24e seyreltilmiş eğitim / seyreltilmemiş test** | Tutarsız örnekleme, örtüşen test | İkisini de aynı kurala bağla + purge |
| **`total_volume` benzeri yalnızca gösterim amaçlı 20+ özellik** | `ind` 41 alan ×125 coin = 416 KB, çoğu karar vermiyor | Modelde tut, UI'ya yalnızca 6–8 anlamlı alan |
| **"Normalden sapma" (vol_zscore) satırı** | korelasyon 0,165; kullanıcıyı yanıltıyor | Yerine "24s oynaklık yüzdelik sırası" |

### 4.2 EKLEYİN

**P0 — tahmin gücü**

1. **Futures verisini geri getirin.** ABD dışı runner **veya** OKX/Bybit funding + OI + long-short. Bu 13 özellik, 24 saatlik hareketlerin en güçlü öncü ailesidir; şu an tamamen kayıp. Ek olarak: `basis` (perp-spot farkı), `funding_zscore`, `oi_change_h` × `price_change_h` etkileşimi, `liq` yaklaşımı (OI artışı + funding ekstremi + fiyat düşüşü).
2. **Sıralama (ranking) hedefi.** Metrik top-k precision; o zaman modeli de sıralama olarak eğitin: her zaman damgasında kesitsel **LambdaRank / softmax** veya "aynı saatteki coinler arasında en iyi" ikili karşılaştırma. Bağımsız ikili sınıflandırma, kesitsel karşılaştırmayı optimize etmiyor.
3. **Yardımcı regresyon başlığı: MFE.** "24 saatte en fazla %X yukarı gider" tahmini, "±%10'a değer mi" ikili hedefinden **çok daha kolay** ve daha kararlı. Arayüzde "beklenen tepe %4,2 (belirsizlik %2,8–%6,1)" gibi gösterin.
4. **Taban çizgileri (baseline).** Raporda ve arayüzde her metrik için üç satır: **rastgele**, **volatilite-only**, **BTC-only (beta)**. Model bunları yenmiyorsa gösterilmemeli. Bu tek ekleme, projenin gerçekçiliğini bir anda artırır.
5. **Örnekleme düzeltmesi (tek satırlık, yüksek etki):**
   ```python
   def thin(frame, stride):
       # coin başına sabit faz, ama coinler arasında farklı faz → iç-gün bilgisi korunur
       phase = frame.groupby('sym').ngroup() % stride if 'sym' in frame else 0
       hours = frame.index.as_unit('ns').asi8 // (3600 * 10**9)
       return frame[(hours - phase) % stride == 0]
   ```
   Böylece her coin hâlâ örtüşmeyen 24 saatlik bloklarda örneklenir ama `utc_hour`, `hours_to_funding`, `utc_weekday` **sabit kalmaz**. (Alternatif: tüm saatleri tutup `sample_weight` ile örtüşmeyi cezalandırmak.)
6. **Rejim kapısı.** BTC trendi/volatilitesi ve piyasa genişliği (`% of coins above 20d MA`, toplam hacim değişimi, funding dağılımı) → ya özellik olarak ekleyin ya da rejim başına ayrı model. 4 aylık veride tek rejim öğreniliyor; rejim etiketi bunu görünür kılar.
7. **Volatilite kalıcılığı.** `vol24` yerine `vol72`, `vol24/vol168`, `log(atr14/atr56)`, "oynaklığın yüzdelik sırası" — çünkü gerçekleşen %13,5, vol-only beklentinin çok altında.
8. **Emir defteri dengesizliği** (bid/ask notional oranı, ±%1 derinlik eğimi) — geçmişi yok, o yüzden modelde kullanılamaz; ama **filtre ve gösterim** olarak değerli: "bu coin bu likiditede 10 bin $ ile girilir mi?"

**P1 — güvenilirlik / dürüstlük**

9. **Bloklu (block bootstrap) güven aralıkları** ve **bağımsız blok sayısının ekranda yazılması** ("36 bağımsız 24s blok; ±%3,5").
10. **Kimlik doğrulama paneli**: `Brier`, `BSS` (iklimsele karşı), `log-loss`, `top-k lift`, fold bazlı tablo, kalibrasyon eğrisi + binom CI, **her eğitimde saklanan model hash'i ve özellik listesi**.
11. **Adil kayıt defteri**: tek açık pozisyon/kural; `veri_yok`/`evrenden_cikti` durumları paydada; 1 dakikalık mumlarla belirsizlik çözümü; **kümülatif net R eğrisi** (komisyon ve spread düşülmüş).
12. **Veri sağlığı bandı** (arayüzün en üstünde): son tarama, taranan/elenen coin, hangi veri ailesi çalışıyor (spot ✓ / futures ✗), model sürümü.
13. **Çoklu ufuk**: 4s / 24s / 72s. Kullanıcı pratikte 24 saat beklemez; 4 saatlik kart hem daha sık geri bildirim hem daha çok eğitim örneği demek.
14. **Varlık sınıfı ayrımı** + seans/gap farkındalıklı etiketleme.
15. **Delist/izleme** için gerçek kaynak (Binance duyuru/CMS) veya alanı kaldırma.

**P2 — ürün**

16. Alarm/e-posta/Telegram: "sadece EV>0 ve likidite yeterli olduğunda" — günde 1–2 bildirim, 125 coin listesi değil.
17. Model versiyonlama + `data.json` şema sürümü (`schema_version`), `docs/` dışında arşiv (her 6 saatte 400 KB commit → repo şişiyor).
18. Kâğıt portföy (paper trading) modu: sabit risk (ör. %1), komisyon, kayma, gerçek giriş/çıkış → "yüzde kaç kazandım" sorusunun tek dürüst cevabı.

---

## 5. Arayüz nasıl olmalı

Mevcut arayüz iki büyük sütuna ("Yükseliş adayları" / "Düşüş adayları") dayanıyor. Sorun: **iki sütun, "bir şey yap" mesajı veriyor**; oysa doğru mesaj çoğu zaman **"bugün yapılacak bir şey yok"**. Ayrıca sayfanın en önemli sayısı (canlı isabet) boş, en yanıltıcı sayısı (tek başına %) en büyük puntoda.

### 5.1 Bilgi mimarisi (yukarıdan aşağıya)

```
┌──────────────────────────────────────────────────────────────────────┐
│ COIN RADAR            [Veri sağlığı: ● spot ✓  ● futures ✗]         │
│ 10 Kas 03:00 UTC · 125/322 coin · model v3 · 36 bağımsız blok        │
├──────────────────────────────────────────────────────────────────────┤
│ BUGÜNÜN KARARI                                                       │
│  ⛔ Ticaret yok — hiçbir adayda maliyet sonrası EV > 0                │
│  En iyi aday %18,8 · başabaş gereken %51,0 · maliyet %0,20           │
│  [Eşiği değiştir: 3×ATR↑ / 1×ATR↓ → başabaş %25]  ← canlı hesap      │
├──────────────────────────────────────────────────────────────────────┤
│ SIRALAMA (tek tablo, iki sütun değil)                                │
│ # coin     sınıf   p̂    %90 CI    EV(R)  likidite  neden      ivme  │
│ 1 SOXSB   hisse   .50  .31–.68   −0,35R  iyi      oynak↑    ▁▂▅▇   │
│ 2 SOXLB   hisse   .15  .09–.24   −0,71R  iyi      oynak↑    ▁▃▂▅   │
│ …   [gri = EV<0 → "izleme listesi", renkli = işlem adayı]            │
├──────────────────────────────────────────────────────────────────────┤
│ DOĞRULAMA (site kendi kendini denetler)                              │
│  Top-10 isabet %13,5 [%10,3–%17,4] · vol-only %33* · rastgele %4,2   │
│  Beceri skoru (BSS) −%0,5 · Kalibrasyon: üst kova %50→%11,7 ⚠        │
│  Son 30 gün kâğıt portföy: −2,1R (net, komisyon dahil)   [grafik]    │
├──────────────────────────────────────────────────────────────────────┤
│ KAYIT DEFTERİ                                                        │
│  açık 8 · sonuçlanmış 34 · veri yok 2 · ortalama süre 24s            │
└──────────────────────────────────────────────────────────────────────┘
```

### 5.2 Bileşen bazında kurallar

| Bölge | Kural | Neden |
|---|---|---|
| **Veri sağlığı bandı** | Her zaman en üstte, renkli noktalarla; futures ölüyse "model spot-only" etiketi | Bugün kullanıcı modelin yarısının çalışmadığını bilmiyor |
| **Karar kutusu** | Tek cümle: "ticaret var / yok" + gerekçe (EV, başabaş, maliyet) | Mevcut sayfa hiçbir zaman "yok" demiyor |
| **Tek tablo** | Yönü bir **kolon** yapın (`↑/↓`), iki sütunu kaldırın; varsayılan sıralama **EV**, olasılık değil | İki sütun, aynı coinin iki yönde de üstte olmasına yol açıyor (bugün SOXSB: ↑%50 **ve** ↓%39,5 — toplam %89,5; bu bir çelişki, kullanıcı göremiyor) |
| **p̂ gösterimi** | Sayı + **%90 güven bandı** + yanında "top %8" yüzdelik; üst kuyrukta bant genişse sayıyı soluklaştır | Kalibrasyon üst kovada çöküyor; bant bunu dürüstçe gösterir |
| **EV(R) kolonu** | Hedef/stop seçilebilir; `EV = p·kazanç − (1−p)·kayıp − maliyet`, R cinsinden | "Yüzde kaç kazanç" sorusunun tek doğru cevabı |
| **Likidite kolonu** | Spread + ±%1 derinliğin **seçili işlem büyüklüğüne** oranı; yetersizse "girilemez" | Derinlik bilgisi var ama kullanılmıyor |
| **Neden kolonu** | 3 işaretli etiket (↑ oynaklık, ↓ BTC korelasyonu, ↑ dibe yakınlık); tıklayınca ayrıntı | Mevcut "why" çubukları ham skor katkısı; özetlenince anlaşılır olur |
| **Gri "izleme" durumu** | EV<0 veya likidite yetersiz → satır gri, sıralamada altta; yine de görünür | "İlkel site" hissinin kaynağı: her satır aynı görsel ağırlıkta |
| **Eşik oynatıcı** | Kullanıcı hedef/stopu değiştirince **tablo yeniden hesaplanır** (p aynı, EV değişir) | Ürünü bir oyuncak olmaktan çıkarır: karar aracı olur |
| **Doğrulama paneli** | Fold metrikleri, BSS, kalibrasyon eğrisi + CI, **taban çizgileri**, kâğıt portföy eğrisi | Sitenin tek gerçek reklamı kendi kanıtıdır |
| **Kayıt defteri** | Durumlar: açık / tuttu / tutmadı / belirsiz / veri yok / evrenden çıktı; **hepsi paydada** | Bugün `track` boş, `pending` 92; "veri yok" durumu yok |
| **Mobil** | Tablo yerine kart: sembol, EV rozeti, p̂ bandı, 5 kelimelik gerekçe | Mevcut tablolar yatay kaydırma istiyor |
| **Tipografi/renk** | Olasılık için yeşil/kırmızı **değil**, nötr mavi-gri skala + yalnızca EV işaretinde renk | Yeşil her zaman "al" diye okunuyor |

### 5.3 Kaldırılacak ekran öğeleri
- "Güven: orta / yüksek" (tüm evrende aynı)
- "İzleme/delist: bilinmiyor" (125/125 aynı)
- "Genel baz oran %4,2" her satırda tekrar (üstte bir kez)
- "Normalden sapma 0,25 z" (sıralamayla 0,165 korelasyon)
- İki sütunlu yön yerleşimi
- Detay penceresindeki 41 satırlık gösterge tablosu → 6 anlamlı gösterge + "tümünü göster" katlaması

### 5.4 Ekran metinleri (öneri)
- Bugün: *"Önümüzdeki 24 saatte %10 yükselme olasılığı"* → **"Bu coin 24 saatte %10 yukarı gitme eşiğine değer mi? Model: %15 (belirsizlik %9–24). Maliyet sonrası beklenti: −0,7R."**
- İsabet: *"canlı isabet"* → **"kâğıt portföy, net: −2,1R · 34 işlem · komisyon dahil"**
- Boş durum: *"Henüz sonuçlanmış tahmin yok"* → **"İlk sonuç 24 saat sonra: 11 Kas 03:00 UTC. Şu an 8 açık tahmin var."**

---

## 6. Yol haritası

**Hafta 1 — dürüstlük (düşük efor, en yüksek güven kazancı)**
1. `thin()` faz düzeltmesi (coin başına farklı faz) → iç-gün/funding özellikleri geri gelir.
2. Kayıt defteri: çift kayıt engeli (`scan_id`, aynı saat tek tarama), `veri_yok`/`evrenden_cikti` durumları, budama yok.
3. Fiyat kayıtları: giriş → 24s **çıkış getirisi**, MFE/MAE, hedef/stop sırası, komisyon; aynı coin için günde tek kayıt.
4. Metrik düzeltmesi: pooled AUC yerine fold ortalaması, **BSS**, bağımsız blok sayısı, blok bootstrap CI. Rapor ve arayüzde **vol-only + rastgele taban çizgileri**.
5. Veri sağlığı bandı + `model_mode: spot_only`.
6. Kalibrasyon eğrisinin üst kovası için minimum olay kuralı; altındaysa olasılığı gösterme, yalnızca yüzdelik göster.

**Hafta 2–4 — hedefi düzeltme**
7. Asimetrik/ATR ölçekli bariyer + R raporlaması; `atr_target_enabled` varsayılan açık.
8. Kesitsel sıralama hedefi (LambdaRank) veya per-timestamp softmax.
9. MFE regresyonu ikinci çıktı.
10. Varlık sınıfı ayrımı (kripto / hisse / emtia / stable), seans farkındalıklı etiket.
11. Stabilcoin otomatik filtresi (ATR < %0,2), 12 aylık geçmiş.

**Ay 2 — arayüzü yeniden kurma**
12. Tek tablo + EV kolonu + eşik oynatıcı + gri izleme durumu.
13. Doğrulama paneli ve kâğıt portföy eğrisi.
14. Mobil kart görünümü, 4s/24s/72s sekmeleri.

**Ay 2–3 — sinyal derinliği**
15. Futures verisi (ABD dışı runner veya OKX/Bybit).
16. Rejim kapısı, piyasa genişliği, funding dağılımı, basis.
17. Model versiyonlama, şema sürümü, veri arşivi.

**Başarı kriteri (definition of done)** — bunlar sağlanmadan liste yayınlanmasın:
- Vol-only taban çizgisine karşı top-10 precision'da **istatistiksel olarak anlamlı** üstünlük (blok CI'ları örtüşmüyor).
- BSS > 0 (iklimsel tahminden iyi).
- Kalibrasyon üst kovasında |tahmin − gerçekleşen| < 5 puan.
- Kâğıt portföyde **net** (komisyon + spread) pozitif beklenti, en az 30 bağımsız işlem.
- "Ticaret yok" durumu üretimde en az bir kez doğru şekilde gösterilebilmiş.

---

## 7. Bu raporun yöntemi ve sınırları

- Sayılar `docs/data.json` (125 coin, 41 özellik, `generated` 2026-11-10T00:57Z) ve `docs/report.json`'dan hesaplandı; kod okumasıyla çapraz kontrol edildi.
- **Beklenen değer** hesabı: simetrik ±%10 bariyer, %0,1 gidiş-dönüş komisyon (`win=0.098`, `loss=0.102`). Spread/kayma dahil değil; dahil edilirse başabaş daha da yükselir.
- **GBM simülasyonu** (6.000 yol, saatlik σ = `vol24`, sürüklenme yok, lognormal) yalnızca "büyüklük mertebesi" içindir: gerçek kripto getirileri kalın kuyruklu olduğu için gerçek temas olasılığı GBM'ninkinden **yüksek** olma eğilimindedir; bu, "modelin üst kuyruğu düşük tahmin ediyor" yönündeki bulguyu zayıflatmaz, aksine güçlendirir.
- **Kısmi korelasyon** sıra (rank) uzayında, `vol24` doğrusal olarak arındırılarak hesaplandı.
- Testler: `.venv` içinde `python -m unittest discover -s tests` → **10/10 geçti**; `node --test` → 3/3.
- Bu rapor **yatırım tavsiyesi değildir**. Amaç, ürünün kendi iddiasını kanıtlayabilir hale gelmesi.

---

### Tek cümlelik teşhis

Site iyi mühendislikle **ticarete uygun olmayan bir soruyu** ("24 saatte ±%10'a değer mi?") yüksek özgüvenle cevaplıyor; soruyu **ATR ölçekli, asimetrik, maliyet sonrası EV** sorusuna çevirip yanına **vol-only taban çizgisi, blok güven aralığı ve net kâğıt portföy** koyduğunuz anda hem tahminler tutmaya başlar hem arayüz kendiliğinden sadeleşir.

---

## 8. Somut kod yamaları (kopyala-yapıştır)

### 8.1 Örnekleme fazı — iç-gün ve funding bilgisini geri kazandırır
`radar/model.py`, `thin()`:
```python
def thin(frame, stride):
    # Coin başına sabit faz (örtüşme yok) ama coinler arasında farklı faz:
    # utc_hour / hours_to_funding / utc_weekday artık sabit kalmaz.
    sym = frame['sym'] if 'sym' in frame else pd.Series('all', index=frame.index)
    phase = pd.Series(sym, index=frame.index).astype('category').cat.codes % stride
    hours = frame.index.as_unit('ns').asi8 // (3600 * 10**9)
    return frame[(hours - phase) % stride == 0]
```
> Not: `train_model()` çağrısından önce `train = train.assign(sym=train.sym)` olduğundan emin olun (scanner zaten `frame['sym']` ekliyor; `evaluate` öncesi `data.reset_index().set_index('t')` benzeri bir dönüşüm gerekirse uyarlayın).

### 8.2 Metrikler: fold karıştırma + beceri skoru + blok CI
`radar/model.py`, `metrics()`:
```python
from sklearn.metrics import log_loss

def metrics(test, probs, target, cfg):
    y = test[target].astype(int).to_numpy()
    base = float(y.mean())
    brier = float(brier_score_loss(y, probs))
    # Beceri skoru: iklimsel (sabit baz oran) tahmine karşı. Negatifse model yayınlanmamalı.
    brier_ref = base * (1 - base)
    # Bloklu belirsizlik: ufuk kadar saatlik bloklardan bootstrap.
    work = pd.DataFrame({'p': probs, 'y': y}, index=test.index)
    blocks = work.index.floor(f'{cfg["horizon_hours"]}h')
    rng = np.random.default_rng(42)
    ids = blocks.unique()
    boots = []
    for _ in range(500):
        pick = rng.choice(ids, len(ids), replace=True)
        sample = pd.concat([work[blocks == b] for b in pick])
        boots.append(brier_score_loss(sample.y, sample.p))
    top = work.sort_values('p', ascending=False).groupby(level=0, sort=False).head(cfg['top_k'])
    return {'auc': ..., 'brier': brier, 'brier_ref': brier_ref,
            'bss': 1 - brier / brier_ref if brier_ref else None,
            'brier_ci90': [float(np.percentile(boots, 5)), float(np.percentile(boots, 95))],
            'independent_blocks': int(len(ids)),
            'base_rate': base, 'precision_top10': float(top.y.mean()), ...}
```
Ve `evaluate()` içinde **fold AUC'lerini havuzlamak yerine** fold bazlı değerleri de rapora yazın:
```python
result['auc_folds'] = [f['metrics']['auc'] for f in folds]
result['auc_mean'] = float(np.nanmean(result['auc_folds']))
# havuzlanmış AUC'yi yalnızca ham (kalibre edilmemiş) skorla hesaplayın
```

### 8.3 Aynı saatte çift tarama / çift kayıt engeli
`scanner.py`:
```python
scan_id = now.isoformat(timespec='seconds')
seen = {(e['t'], e['sym'], e['side']) for e in keep + track}
for side in ('up', 'dn'):
    for coin in sorted(coins, key=lambda c: -c['p_' + side])[:cfg['top_k']]:
        t0 = (now.floor('h') + pd.Timedelta(hours=1)).isoformat()
        key = (t0, coin['symbol'], side)
        if key in seen:
            continue                      # aynı saat, aynı coin, aynı yön → tekrar yazma
        seen.add(key)                     # ← eksik olan satır buydu
        keep.append({'t': t0, 'sym': coin['symbol'], 'side': side, 'p': coin['p_' + side],
                     'price': None, 'reference_price': coin['price'],
                     'threshold': cfg['threshold'], 'scan_id': scan_id})
```
Ayrıca `resolve()` içindeki iki sessiz `continue`'yu durum kaydına çevirin:
```python
if df is None:
    done.append({**e, 'result': 'evrenden_cikti', 'hit': None}); continue
if now - t0 >= pd.Timedelta(hours=h * 3):
    done.append({**e, 'result': 'veri_yok', 'hit': None}); continue
keep.append(e)
```
Böylece canlı isabet oranı "kaybolan" tahminlerle şişmez.

### 8.4 Tie kırma (eşit olasılıklar)
```python
def rank_key(c, side, cfg):
    # Önce olasılık, eşitlikte likidite ve oynaklıkla ayrıştır (belgelenmiş kural).
    depth = min(c['book']['bid_depth_usdt'], c['book']['ask_depth_usdt']) if c['book'] else 0
    return (c['p_' + side], depth, c['vol_zscore'] or 0)
selected = sorted(coins, key=lambda c: rank_key(c, side, cfg), reverse=True)[:cfg['top_k']]
```
Ve arayüzde eşitlik varsa gösterin: "10. sırada 10 coin eşit → liste alfabetik/hacme göre kesiliyor".

### 8.5 Fiyat kayıtlarında gerçek strateji sonucu
`radar/price_history.py` — 1 dakikalık mumlardan hem MFE/MAE hem **hedef/stop sırası** hem de 24 saatlik **çıkış getirisi**:
```python
rows = ...  # mevcut 1m mum döngüsü: (t, high, low, close)
up_bar, dn_bar = price * (1 + target), price * (1 - stop)
hit = next((i for i, (_, h, l, _) in enumerate(rows) if h >= up_bar or l <= dn_bar), None)
if hit is not None:
    first_up = rows[hit][1] >= up_bar
    # aynı dakikada ikisi de olabilir → belirsiz
    outcome = 'belirsiz' if rows[hit][1] >= up_bar and rows[hit][2] <= dn_bar else ('hedef' if first_up else 'stop')
result.update(mfe=max(r[1] for r in rows) / price - 1,
              mae=min(r[2] for r in rows) / price - 1,
              close_return=rows[-1][3] / price - 1,
              exit_price=rows[-1][3], outcome=outcome,
              net_r=(target - 2 * fee) / stop if outcome == 'hedef'
                    else (-1 - 2 * fee / stop) if outcome == 'stop' else None)
```
Aynı coin için 15 dakika arayla kayıt açılmasını da engelleyin: `(symbol, date)` başına tek kayıt.

### 8.6 Kabul testleri (her biri mevcut bir hatayı kilitler)
```python
def test_thin_keeps_intraday_variation():        # 8.1
    ...
def test_metrics_reports_skill_and_blocks():      # 8.2: bss anahtarı var, independent_blocks > 0
    ...
def test_same_hour_scan_does_not_duplicate():     # 8.3
    ...
def test_resolve_marks_missing_data_not_drops():  # 8.3
    ...
def test_tie_break_is_deterministic():            # 8.4
    ...
def test_price_history_tracks_target_before_stop():  # 8.5
    ...
```

---

## 9. Düzeltme ve net cevap: "Bunlar tahmin tutma ihtimalini artırır mı?"

Bu soru iki farklı şeyi karıştırıyor; ayrıştırmak gerekiyor:

- **(A) Bir coinin hedefe ulaşma sıklığı** (isabet oranı) — bariyer ve piyasa belirler.
- **(B) Modelin söylediği olasılığın doğru çıkması** (kalibrasyon) — veri ve yöntem belirler.

### 9.1 Ayrı simülasyonla ölçülen etkiler

Sürüklenmesiz GBM, 3.000–6.000 yol, evrenin gerçek `vol24` değerleri:

| Ayar | Evren medyanı isabet | En iyi 10 coin | Başabaş gereken |
|---|---|---|---|
| ±%10 (mevcut) | %4,0 | **%32,9** | %50,0 |
| +%7,5 / −%2,5 | %10,5 | %29,8 | %25,0 |
| +%2,5 / −%7,5 | %53,2 | %68,3 | %75,0 |

**"Mükemmel model" üst sınırı:** sadece coin seçimi kusursuz olsa (gelecekteki volatiliteyi tam bilse), ±%10/24s hedefinde en iyi 10 coinin isabeti **≈%33**, en iyi 3 coinin **≈%46,5**. Model şu an **%13,5**.

### 9.2 İsabet oranını yükseltme tuzağı

Tipik bir coin için (saatlik σ = %1,0) bariyeri değiştirmenin isabet ve beklentiye etkisi:

| Hedef | Stop | "İsabet" | Başabaş | İşlem başına EV |
|---|---|---|---|---|
| +%0,5 | −%10 | %82,8 | %95,2 | **−1,3%** |
| +%1,0 | −%10 | %74,1 | %90,9 | **−1,9%** |
| +%2,0 | −%10 | %60,1 | %83,3 | **−2,8%** |
| +%5,0 | −%5 | %26,8 | %50,0 | −2,3% |
| +%7,5 | −%2,5 | %10,7 | %25,0 | −1,4% |
| +%10 | −%10 | %4,2 | %50,0 | −9,2% |

Matematik: sürüklenmesiz fiyatta **P(üst bariyere önce değme) = stop / (hedef + stop)** — yani başabaş oranının ta kendisi. Hangi bariyer oranını seçerseniz seçin, maliyet öncesi beklenen değer **tam olarak sıfırdır**. Bariyer oranı kâr yaratmaz; yalnızca gerçekleşme sıklığını, ölçülebilirliği ve kullanıcının yanılma biçimini değiştirir.

> **Kendi raporumdaki düzeltme:** Bölüm 4.1'deki "3:1 asimetrik → 9 adayda pozitif EV" ifadesi, modelin **şişkin** olasılıklarıyla yapılmış bir hesaptı ve yanıltıcı. Gerçekçi (kalibre edilmiş) olasılıklarla, hangi bariyer seçilirse seçilsin EV ≈ 0 − maliyet olur. Asimetrik bariyerin gerçek faydası **kâr değil**, şu üçüdür:
> 1. Hedef **ulaşılabilir** olur (24s'de 3×ATR, 10%'dan çok daha sık) → örnek sayısı ve dolayısıyla öğrenilebilirlik artar.
> 2. Aynı saatlik mumda iki bariyerin çakışma (belirsiz örnek) oranı düşer → değerlendirme daha az yanlı olur.
> 3. "İsabet %50" gibi yanıltıcı bir sayı yerine "1R başına beklenti" gibi dürüst bir sayı üretir.

### 9.3 Tavsiyelerin sınıflandırması

**A. Tahmin kalitesini (B) gerçekten artırır — evet, ölçülebilir:**

| Tavsiye | Etki | Neden eminim |
|---|---|---|
| Aynı saatte çift kayıt engeli + sessiz budamanın kaldırılması | Canlı isabet oranı **doğru** ölçülür (bugün yukarı yanlı) | 01:00 için 32 kayıt var, olması gereken 20 |
| Fold karıştırma hatasının düzeltilmesi | Düşüş modeli AUC'si 0,560 → ~0,72 | Fold AUC'leri 0,700/0,751/0,698 |
| Kalibrasyon üst kovasının düzeltilmesi | %50 diyen yer %12 der → karar doğru olur | Kalibrasyon tablosu, n=443 |
| Eşitlik (tie) kırma | Top-10 seçimi rastgelelikten kurtulur | 10. sırada 10 coin eşit |
| Örnekleme fazı (`thin`) | İç-gün + funding özellikleri geri gelir | `utc_hour`/`hours_to_funding` "sabit" diye düştü |
| Taban çizgisi (vol-only) | Modelin gerçekten bir şey eklediği görülür | vol-only ile Spearman 0,851 |
| Futures verisinin geri getirilmesi | Modelin en güçlü özellik ailesi açılır | 125/125 coinde 451 hatası |
| Tokenize hisselerin ayrılması | Farklı dağılım/gap karışması biter | 49/125 coin, |24s| medyanı 4 kat |
| Ranking hedefi | Top-10 optimizasyonu doğru yapılır | Metrik zaten top-k |
| Stabilcoin otomatik filtresi | Evren temizlenir | BFUSD ATR %0,009 |

**B. İsabet oranını artırır ama para kazandırmaz — dikkat:**
- Bariyeri daraltmak (ör. +%2/−%10 → isabet %60). Yukarıdaki tablo: EV hâlâ negatif. **Bu bir iyileşme değil, yanıltıcı bir kozmetik.**

**C. Tahmin kalitesini artırmaz, ama siteyi güvenilir yapar (yine de gerekli):**
- Blok güven aralıkları, BSS, kâğıt portföy, veri sağlığı bandı, model versiyonlama, şema sürümü, `veri_yok`/`evrenden_cikti` durumları, arayüzün tek tabloya indirilmesi, mobil kartlar, alarm.

**D. Gereksiz kalabalık — kaldırılmalı:**
- "Güven: yüksek/orta" (125/125 aynı), "İzleme/delist: bilinmiyor" (125/125 aynı), her coinde tekrarlanan `futures_errors` (125×5 satır), `vol_zscore` satırı (sıralamayla 0,165 korelasyon), çift sütunlu yön yerleşimi, detay penceresindeki 41 satırlık gösterge tablosu, olasılığın %2 hassasiyetle gösterilmesi (gerçek çözünürlük 13 basamak).

### 9.4 Tek cümlelik cevap

> Hayır — **hiçbir tavsiye isabet oranını %13'ten %51'e çıkarmaz**; o hedefin ulaşılabilir tavanı kusursuz bir modelde bile ≈%33'tür. Tavsiyelerin **büyük kısmı tahmin kalitesini artırmaz; yalan söylemeyi bırakmasını sağlar** (kalibrasyon, tie, çift kayıt, taban çizgisi). Tahmin kalitesini gerçekten artıran kısım az ve nettir: **kalibrasyon düzeltmesi, örnekleme fazı, futures verisi, hisse/kripto ayrımı, ranking hedefi, tie kırma.** Kalabalık olan kısım ise arayüz ve ölçüm katmanıdır — ama tam da bugün modelin **kendini kanıtlayamamasının** sebebi o katman.
