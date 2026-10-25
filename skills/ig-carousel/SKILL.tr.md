# Kaydırmalı gönderi

> Türkçe kullanım rehberi. Bu katkı yalnızca dokümantasyondur; Python betiklerinin davranışını değiştirmez. Betikler İngilizce sözcük listeleri ve yer yer ASCII karakter kuralları kullanır. Türkçe açılış/üslup puanlarını geçerli sayma; Türkçe konuşma süresini sesli prova ile doğrula. Türkçe metinlerde anlam, açıklık ve marka sesini elle değerlendir. Betik komutları yalnızca mevcut İngilizce araçların kullanımını gösterir; `--lang` seçeneği bu kaynak sürümde yoktur.

## Ortak bağlam

Varsa `~/.claude/instagram/voice.md`, `swipe.md`, `plan.md` ve `log.md` içinden yalnızca görevle ilgili dosyaları oku. Marka sesi yoksa `templates/voice.tr.md` şablonunu öner; verilen bağlamla ilerle. Kişisel/müşteri verilerini herkese açık Git deposuna ekleme. Diğer becerileri `/ig-reel` gibi çağır veya ilgili `SKILL.md` dosyasını oku.

Veri, müşteri sonucu ve alıntı uydurma. Bilinmeyen değeri `{{doğrulanacak bilgi}}` ile işaretle. İçerik ve yanıt taslakları hazırla; Instagram'a gönderi/yorum/DM gönderme. Platform sayılarını değişmez kural gibi sunma; güncel iddia gerekiyorsa resmî kaynaktan doğrula.


Sıralama, karşılaştırma veya tekrar okunacak adımlar için carousel seç. Tek somut fikri altı-on slayta böl; bu aralık öneridir.

1. Kapak: en fazla altı sözcük ve açık vaat.
2. İkinci slayt: sorun ve neden önemli olduğu; kendi başına da anlaşılmalı.
3. Gövde: slayt başına tek fikir, üç-yedi sözcüklük başlık, yaklaşık 25 sözcüğü geçmeyen açıklama.
4. Sona doğru tek başına paylaşılabilir özet; son slaytta tek CTA.
5. Metni `ig-human`, açıklamayı `ig-caption` ile kontrol et. Her slayta alt metin yaz.

Çıktıda önce numaralı slayt metinlerini ve açıklamayı göster. Kullanıcı görsel üretimini zaten istediyse ayrıca onay bekleme. Görsel üretimi istenmediyse metin teslimi yeterlidir.

Dosya istenirse mevcut tasarım/render aracını kullan. Varsayılan 1080×1350 (4:5), okunaklı yazı, markanın renkleri ve tutarlı boşluklarla çalış; farklı oran istenirse uygula. PNG/JPEG oluştuğunu gerçekten doğrula, oluşturulmamış dosyaya indirme bağlantısı uydurma. Yalnızca HTML veya PDF üretilebildiyse bunu açıkça söyle; PDF'yi doğrudan Instagram görseli gibi sunma. Bu pakette hazır render motoru yoktur.
