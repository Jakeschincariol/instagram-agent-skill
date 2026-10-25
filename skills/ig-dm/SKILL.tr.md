# DM taslakları

> Türkçe kullanım rehberi. Bu katkı yalnızca dokümantasyondur; Python betiklerinin davranışını değiştirmez. Betikler İngilizce sözcük listeleri ve yer yer ASCII karakter kuralları kullanır. Türkçe açılış/üslup puanlarını geçerli sayma; Türkçe konuşma süresini sesli prova ile doğrula. Türkçe metinlerde anlam, açıklık ve marka sesini elle değerlendir. Betik komutları yalnızca mevcut İngilizce araçların kullanımını gösterir; `--lang` seçeneği bu kaynak sürümde yoktur.

## Ortak bağlam

Varsa `~/.claude/instagram/voice.md`, `swipe.md`, `plan.md` ve `log.md` içinden yalnızca görevle ilgili dosyaları oku. Marka sesi yoksa `templates/voice.tr.md` şablonunu öner; verilen bağlamla ilerle. Kişisel/müşteri verilerini herkese açık Git deposuna ekleme. Diğer becerileri `/ig-reel` gibi çağır veya ilgili `SKILL.md` dosyasını oku.

Veri, müşteri sonucu ve alıntı uydurma. Bilinmeyen değeri `{{doğrulanacak bilgi}}` ile işaretle. İçerik ve yanıt taslakları hazırla; Instagram'a gönderi/yorum/DM gönderme. Platform sayılarını değişmez kural gibi sunma; güncel iddia gerekiyorsa resmî kaynaktan doğrula.


Alıcıyı, mesajın gerçek tetikleyicisini ve kullanıcının amacını mevcut bağlamdan belirle. İzlemediğin içerikleri izlemiş veya tanışmadığın kişiyi tanıyormuş gibi yazma.

- Anahtar kelime/kaynak talebi: vaat edilen içerik veya bağlantıyı ilk mesajda ver. Kaynağı almak için sonradan sürpriz koşul ekleme. Sonuna kısa, isteğe bağlı soru eklenebilir.
- Mevcut ilişki: belirli etkileşime atıf yapan iki-dört cümle, önce yarar, ardından küçük tek istek.
- İş birliği: gözlenen iş, somut fikir, karşı tarafa yarar, beklenen katkı.
- Soğuk yaklaşım istenirse kişiselleştirilmiş, dürüst ve kısa taslak yaz; kitlesel gönderim veya otomatik takibe dönüştürme.

Takip istenirse başlangıç önerisi olarak +4 ve +10 güne iki farklı taslak hazırla. Yeni bir değer yoksa takip üretme; olumsuz yanıt veya vazgeçme varsa dur. Bunlar plan önerileridir, otomatik mesaj veya hatırlatma oluşturma.

`ig-human` ile düzenle. Çıktı: ana mesaj, karakter sayısı ve istenen takip taslakları. Kullanıcının izin verdiği kanal ve bağlam dışında gönderim yapma; bu paket yalnızca metin üretir.
