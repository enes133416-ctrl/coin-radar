# Coin Radar

Binance USDT spot pariteleri için, önümüzdeki 24 saatte +%10 veya -%10 eşiğine **ters eşiğe ulaşmadan önce** ulaşma olasılığını iki LightGBM modeliyle tahmin eder. Model oynaklığı tahmin etmede yönden daha iyidir. **Yatırım tavsiyesi değildir.**

## Windows'ta çalıştırma

Python 3.11 veya üzerini kurun; PowerShell'de proje klasöründe:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m unittest discover -s tests -v
python scanner.py
cd docs
python -m http.server 8000
```

Tarayıcıda `http://localhost:8000` adresini açın. PowerShell etkinleştirmeyi engellerse aktivasyon yerine `.\.venv\Scripts\python.exe` ile komutları çalıştırın. Tarama Binance spot ve Futures API'lerine ağ erişimi gerektirir ve 150 coin için zaman alabilir. Bazı coğrafyalarda API'ler engellenebilir veya Futures verileri belirli pariteler için bulunmayabilir; eksik veriler ve atlanan coinler rapora yazılır. Spot/BTC erişimi veya yeterli eğitim verisi yoksa işlem hata verir; eski çıktı güncellenmez.

## Ayarlar ve dosyalar

Tüm çalışma parametreleri `config.json` içindedir. Varsayılanlar: en yüksek hacimli 150 USDT paritesi, en az 5 milyon USDT günlük hacim, 720 saat kesintisiz geçmiş, %0,5 azami spread ve orta fiyatın ±%1'inde her yönde en az 50.000 USDT derinlik. Spread, orta fiyata bölünmüş alış-satış farkıdır. Emir defteri limiti derinlik bandını kapsamıyorsa ölçüm alt sınırdır; filtre yine de ölçülen miktarı kullanır. Kitap alınamazsa coin elenir. Stable/fiat/wrapped dışlama listesi yapılandırmadadır ve kapsamlı bir varlık sınıflandırması değildir.

- `radar/data.py`: spot mumlar ve defter, Futures funding, OI, global/top trader long-short, izleme etiketi kontrolü.
- `radar/features.py`: geçmişe dönük özellikler, BTC rejimi, UTC zamanı, ATR, Bollinger, 7/30 günlük zirve/dip ve oynaklık z-skoru; ilk temas etiketleri.
- `radar/model.py`: sızıntı kontrolü, korelasyon/önem seçimi, walk-forward, isotonic kalibrasyon, değerlendirme.
- `scanner.py`: iş akışı ve tahmin takibi; `docs/data.json`: web verileri; `docs/report.json`: bölme metrikleri, kalibrasyon eğrileri, korelasyon matrisi, özellik seçimleri ve atlamalar. Dosyalar başarılı taramada üretilir.
- `docs/index.html`: web arayüzü; `tests/test_radar.py`: testler.

Örneğin `top_n`, `max_spread_pct`, `min_depth_usdt_per_side`, `correlation_threshold` ve `min_importance_pct` yapılandırmadan değiştirilebilir. `atr_target_enabled: true` ile sabit %10 hedefi yanında ATR% × `atr_multiplier` (belirtilen alt/üst sınırlar içinde) için ikinci bir walk-forward karşılaştırması rapora eklenir; arayüzdeki tahminler yine sabit %10 hedefidir. Funding saatine kalan süre varsayılan 8 saatlik UTC çizelgesini kullanır; sözleşmeye özel funding sıklığı değişikliklerini yansıtmayabilir.

## Yöntem ve kısıtlar

- Özellikler yalnızca kapanmış saatlik mumdan hesaplanır. Futures verileri yayın zamanından önce kullanılmaz: funding için zaman damgası, OI ve oranlar için ihtiyatlı bir saatlik gecikme uygulanır. Geçmiş OI/oran endpointleri sınırlı geçmiş sunar (istekte en fazla 500 saatlik kayıt); diğer satırlar eksiktir, gelecekteki değerlerle doldurulmaz. Futures'ı olmayan coinler eksik özelliklerle değerlendirilebilir. Güncel OI ayrıca gösterilmek üzere anlık alınır.
- Emir defteri yalnızca güncel bir anlık görüntüdür, geçmişteki örneklere yapıştırılmaz ve modelin eğitim girdisi değildir; likidite filtresi ve gösterimde kullanılır. Kamuya açık güvenilir tarihsel likidasyon serisi mevcut olmadığından likidasyon özelliği yoktur. Binance spot `exchangeInfo` izleme/delist etiketini sunmadığında sonuç **bilinmiyor** gösterilir; bu, güvenli olduğu anlamına gelmez ve duyuru takibinin yerini tutmaz.
- Etiket ilk eşik temasını ölçer. Aynı saatlik mumda iki eşik de aşılırsa sıralama bilinmediğinden örnek değerlendirme ve eğitimden çıkarılır. Dolayısıyla sonuçlar bu belirsiz örnekler dışındaki olaylara koşulludur. Son ufuk kadar saat etiketsizdir. 30 günlük zirve/dip, yeni coinin o tarihe kadar mevcut geçmişini kullanabilir; ATH kullanılmaz.
- Walk-forward bölmelerinde eğitim, kalibrasyon ve test kronolojiktir; her sınırda en az hedef ufku kadar boşluk vardır ve kontrol otomatik yapılır. Eğitim ve kalibrasyon, aynı coin için örtüşen etiketleri önlemek üzere varsayılan 24 saatte bir örneklenir. Korelasyon elemesi ve ön önem modeli sadece ilgili eğitim bölmesinde kurulur; nihai model ayrı bir geçmiş kalibrasyon kümesi kullanır. Son testler öğrenmeye veya kalibrasyona katılmaz.
- Brier skoru ve kalibrasyon eğrisi, test örneklerinin kalibre edilmiş olasılıklarıyla hesaplanır. Precision@10/isabet, her test saatindeki en yüksek 10 coinin birleştirilmiş gerçekleşme oranıdır; baz oran tüm test satırları üzerinden hesaplanır. Ölçümler saatler arasında örtüşen test etiketleri içerebilir, bağımsız gözlem gibi yorumlanmamalıdır.
- Coin evreni, güncel hacim, listeleme ve likiditeye göre seçilir. Geçmiş walk-forward sonuçları bu nedenle sağkalım/seçim yanlılığı içerir; tarihsel olarak işlem yapılabilir bir evren simülasyonu değildir. Özellik katkıları kalibrasyon öncesi ham model skoruna aittir. Güven göstergesi yalnızca eksik özellik ve kalibrasyondaki olay sayısına dayalı kaba bir veri yeterliliği etiketidir, güven aralığı veya garanti değildir.
- Canlı takip, tahmin yayınlandıktan sonraki ilk tam mumun açılışını referans alır; bu fiyat modelin kullandığı son kapanıştan farklı olabilir. Aynı mumdaki belirsiz temaslar isabet hesabı dışında kalır. Eski hedef tanımına ait takip kayıtları karıştırılmaz.

GitHub Pages için Settings → Pages altında `main` / `/docs` seçin ve Actions → `update-data` iş akışını çalıştırın. İş akışı testleri çalıştırır ve ardından veri ve raporu üretir. Repodaki önceki `docs/data.json` yeni tarama başarıyla çalışana kadar eski model sonucudur; arayüz bunu belirtir.
