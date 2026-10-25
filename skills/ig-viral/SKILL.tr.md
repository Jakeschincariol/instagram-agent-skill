# Örnek içerik araştırması

> Türkçe kullanım rehberi. Bu katkı yalnızca dokümantasyondur; Python betiklerinin davranışını değiştirmez. Betikler İngilizce sözcük listeleri ve yer yer ASCII karakter kuralları kullanır. Türkçe açılış/üslup puanlarını geçerli sayma; Türkçe konuşma süresini sesli prova ile doğrula. Türkçe metinlerde anlam, açıklık ve marka sesini elle değerlendir. Betik komutları yalnızca mevcut İngilizce araçların kullanımını gösterir; `--lang` seçeneği bu kaynak sürümde yoktur.

## Ortak bağlam

Varsa `~/.claude/instagram/voice.md`, `swipe.md`, `plan.md` ve `log.md` içinden yalnızca görevle ilgili dosyaları oku. Marka sesi yoksa `templates/voice.tr.md` şablonunu öner; verilen bağlamla ilerle. Kişisel/müşteri verilerini herkese açık Git deposuna ekleme. Diğer becerileri `/ig-reel` gibi çağır veya ilgili `SKILL.md` dosyasını oku.

Veri, müşteri sonucu ve alıntı uydurma. Bilinmeyen değeri `{{doğrulanacak bilgi}}` ile işaretle. İçerik ve yanıt taslakları hazırla; Instagram'a gönderi/yorum/DM gönderme. Platform sayılarını değişmez kural gibi sunma; güncel iddia gerekiyorsa resmî kaynaktan doğrula.


Amaç benzer hesapların kendi normaline göre iyi çalışan içerik yapısını anlamaktır. Ham izlenmeyi başarı garantisi veya kopyalanacak senaryo gibi sunma.

1. Kullanıcının hedef nişini ve kitleyi belirle. Kullanıcının verdiği veri, herkese açık erişilebilir sayfa veya ayrıca yetkilendirilmiş okuma aracı kullan. Bu paket Instagram veri toplayıcısı içermez; parola veya toplu tarama kurma.
2. Makul başlangıç örneği olarak on hesaptan yakın dönemdeki yaklaşık 12 Reels'i incele. Görünmeyen sayı ve medyanı uydurma. Her satıra kaynak URL ve gözlem tarihi ekle; aynı tarih aralığından kıyasla.
3. TSV başlığı: `account	followers	median	views	hook	url	observed_at`. Sayıları tam tamsayı yaz (4500); `4.5K`, `4,5 bin` gibi kısaltmaları doğrudan betiğe geçirme. Medyan yoksa boş bırak; takipçi tabanı aynı ölçüt değildir.
4. `python3 swipe.py captured.tsv --json` çalıştır. Otomatik formül sınıflandırması İngilizce kalıplara dayanır; Türkçe açılış yapısını elle adlandır. Girdi tabanı (medyan veya takipçi) farklı olan satırları ayrı değerlendir; medyan katı ile takipçi oranını aynı sıralamada yorumlama.
5. Üst/alt grubun yapı farklarını, formül sayımlarını ve sınıflandırılamayanları bildir. Örnek sayısını ve belirsizliği açıkla; küçük örnekten kesin algoritma sonucu çıkarma.
6. Başarılı yapıların kullanıcının gerçek deneyimine uygun üç yeni versiyonunu öner; başka yaratıcının metnini veya sesini kopyalama. Senaryolar için `ig-reel` kullan.

Dosya istendiğinde `--out` ile `~/.claude/instagram/swipe.md` yolunu kullan. Kaynak betik çıktıları İngilizcedir; sonuçları Türkçe açıkla. Araştırmayı tamamladığını söylemek için gerçek veri ve kaynaklar gerekir; yalnızca şablon doldurulduysa bunu belirt.
