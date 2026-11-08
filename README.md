# Coin Radar

Binance geçmiş mum verisinden (1 saatlik) öğrenip, her coin için **önümüzdeki 24 saatte en az +%10 yükselme** ve **en az -%10 düşme** olasılığını hesaplayan, sonucu web sayfasında gösteren sistem.

- `scanner.py`: veriyi çeker, LightGBM modellerini eğitir, `docs/data.json` üretir
- `docs/index.html`: arayüz (GitHub Pages ile yayınlanır)
- `.github/workflows/update.yml`: 6 saatte bir otomatik günceller

## Windows'ta çalıştırma
```
pip install -r requirements.txt
python scanner.py
cd docs
python -m http.server 8000
```
Tarayıcıda `http://localhost:8000` aç.

## GitHub'da yayınlama
1. Repoyu GitHub'a yükle.
2. Settings > Pages > Branch: `main`, klasör: `/docs`.
3. Actions sekmesinden `update-data` iş akışını bir kez elle çalıştır. Sonrası otomatik.

## Ayarlar (ortam değişkeni)
`TOP_N` (80), `MIN_VOLUME_USDT` (5000000), `PAGES` (3), `HORIZON_H` (24), `THRESHOLD` (0.10)

## Önemli
Çıktı bir olasılık tahminidir, yatırım tavsiyesi değildir. Arayüzdeki "test" rakamları modelin eğitimde görmediği son %20 zaman diliminde ölçülmüştür; geçmiş performans gelecekte tekrarlanmayabilir. %10 hareket nadir bir olaydır, yüksek olasılık bile çoğu zaman gerçekleşmeme demektir.
