# Profil değerlendirmesi

> Türkçe kullanım rehberi. Bu katkı yalnızca dokümantasyondur; Python betiklerinin davranışını değiştirmez. Betikler İngilizce sözcük listeleri ve yer yer ASCII karakter kuralları kullanır. Türkçe açılış/üslup puanlarını geçerli sayma; Türkçe konuşma süresini sesli prova ile doğrula. Türkçe metinlerde anlam, açıklık ve marka sesini elle değerlendir. Betik komutları yalnızca mevcut İngilizce araçların kullanımını gösterir; `--lang` seçeneği bu kaynak sürümde yoktur.

## Ortak bağlam

Varsa `~/.claude/instagram/voice.md`, `swipe.md`, `plan.md` ve `log.md` içinden yalnızca görevle ilgili dosyaları oku. Marka sesi yoksa `templates/voice.tr.md` şablonunu öner; verilen bağlamla ilerle. Kişisel/müşteri verilerini herkese açık Git deposuna ekleme. Diğer becerileri `/ig-reel` gibi çağır veya ilgili `SKILL.md` dosyasını oku.

Veri, müşteri sonucu ve alıntı uydurma. Bilinmeyen değeri `{{doğrulanacak bilgi}}` ile işaretle. İçerik ve yanıt taslakları hazırla; Instagram'a gönderi/yorum/DM gönderme. Platform sayılarını değişmez kural gibi sunma; güncel iddia gerekiyorsa resmî kaynaktan doğrula.


Kullanıcının verdiği profil görüntüsü veya metninden isim, kullanıcı adı, biyografi, bağlantı, öne çıkanlar, sabit gönderiler ve ilk dokuz kapağı incele. Görünmeyen öğeye sıfır verme; bilinmiyor olarak işaretle.

`rubric.json` ölçütlerini oku ve Türkçe açıkla. 12 ölçütü ayrı puanla. Eksik veri varsa gözlenen puanı değerlendirilebilen toplam üzerinden göster; tam profil incelenmiş gibi 100 üzerinden sonuç uydurma.

Kaybedilen puana göre düzelt: üç isim alanı seçeneği, hedef kitleyi ve teklifi anlatan biyografi, kanıt/teklif/tanışma görevleri farklı üç sabit gönderi, alıcının sorularına göre öne çıkanlar, vaade uyan bağlantı ve okunaklı kapaklar. Karakter sınırını güncel uygulamada doğrulamadan kesinleştirme.

Kurumsal hesapta logo kullanımını kişisel hesap ölçütüyle cezalandırma. Mevcut gönderi ve kanıt gerektiren puanı yalnızca metin yeniden yazıldı diye yükseltme.

Çıktı: kanıta bağlı puan tablosu, eksik veriler, öncelikli düzeltmeler ve kopyalanabilir metinler. Önerilen profille mevcut profilin puanını ayrı göster; Instagram profilinde değişiklik yapma.
