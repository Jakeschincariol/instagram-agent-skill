# Metin düzenleme

> Türkçe kullanım rehberi. Bu katkı yalnızca dokümantasyondur; Python betiklerinin davranışını değiştirmez. Betikler İngilizce sözcük listeleri ve yer yer ASCII karakter kuralları kullanır. Türkçe açılış/üslup puanlarını geçerli sayma; Türkçe konuşma süresini sesli prova ile doğrula. Türkçe metinlerde anlam, açıklık ve marka sesini elle değerlendir. Betik komutları yalnızca mevcut İngilizce araçların kullanımını gösterir; `--lang` seçeneği bu kaynak sürümde yoktur.

## Ortak bağlam

Varsa `~/.claude/instagram/voice.md`, `swipe.md`, `plan.md` ve `log.md` içinden yalnızca görevle ilgili dosyaları oku. Marka sesi yoksa `templates/voice.tr.md` şablonunu öner; verilen bağlamla ilerle. Kişisel/müşteri verilerini herkese açık Git deposuna ekleme. Diğer becerileri `/ig-reel` gibi çağır veya ilgili `SKILL.md` dosyasını oku.

Veri, müşteri sonucu ve alıntı uydurma. Bilinmeyen değeri `{{doğrulanacak bilgi}}` ile işaretle. İçerik ve yanıt taslakları hazırla; Instagram'a gönderi/yorum/DM gönderme. Platform sayılarını değişmez kural gibi sunma; güncel iddia gerekiyorsa resmî kaynaktan doğrula.


Amaç anlamı ve marka sesini koruyup gereksiz kalıpları sadeleştirmektir. Noktalama, görünmez karakterler veya puanlar bir metnin AI tarafından yazıldığını kanıtlamaz. Tespit aracını atlatma veya görünmez filigran kaldırma garantisi verme.

`slop.json` sözlüğü İngilizcedir; Türkçe metni bu sözlükle otomatik puanlama. Marka diline ait yerinde terimleri sırf listede diye silme; gerekirse özel sözlük kullan.

1. Metni gereksiz girişler, genel sıfatlar ve anlamı zayıflatan tekrarlar için elle düzenle.
2. URL, e-posta, özel isim, rakam, Türkçe ekler ve emoji anlamını özgün metinle karşılaştır.
3. Yapısal kalıpları bağlama göre değerlendir; her üçlü liste veya düzenli cümle kusur değildir.
4. Kaynak `humanize.py` ve `detect.py` araçları İngilizce odaklıdır. Türkçe metne İngilizce sözlük veya AI yazarlığı puanı uygulama. İki turdan fazla sırf puan için metni bozma.

Çıktı: düzenlenmiş metin, önemli değişiklikler, kalan uyarılar. İstenirse editoryal puanı ve sınırlılığını açıkla. JSON alan adları ve bazı teknik tanı mesajları İngilizce kalır. Tek başına puan teslim etme.
