# Gönderi açıklaması

> Türkçe kullanım rehberi. Bu katkı yalnızca dokümantasyondur; Python betiklerinin davranışını değiştirmez. Betikler İngilizce sözcük listeleri ve yer yer ASCII karakter kuralları kullanır. Türkçe açılış/üslup puanlarını geçerli sayma; Türkçe konuşma süresini sesli prova ile doğrula. Türkçe metinlerde anlam, açıklık ve marka sesini elle değerlendir. Betik komutları yalnızca mevcut İngilizce araçların kullanımını gösterir; `--lang` seçeneği bu kaynak sürümde yoktur.

## Ortak bağlam

Varsa `~/.claude/instagram/voice.md`, `swipe.md`, `plan.md` ve `log.md` içinden yalnızca görevle ilgili dosyaları oku. Marka sesi yoksa `templates/voice.tr.md` şablonunu öner; verilen bağlamla ilerle. Kişisel/müşteri verilerini herkese açık Git deposuna ekleme. Diğer becerileri `/ig-reel` gibi çağır veya ilgili `SKILL.md` dosyasını oku.

Veri, müşteri sonucu ve alıntı uydurma. Bilinmeyen değeri `{{doğrulanacak bilgi}}` ile işaretle. İçerik ve yanıt taslakları hazırla; Instagram'a gönderi/yorum/DM gönderme. Platform sayılarını değişmez kural gibi sunma; güncel iddia gerekiyorsa resmî kaynaktan doğrula.


Önce görevi seç: A) Reels zaten dikkat çekiyorsa açıklama bağlamı ve çağrıyı tamamlasın. B) Fotoğraf veya carousel metni taşıyorsa ilk satır açılış olsun.

1. İlk satırı kısa ve somut yaz. Selamlaşma veya hashtag ile başlama. Ardından kısa paragraflar, tek eylem çağrısı ve gerekiyorsa ilgili hashtagler ekle.
2. Kullanıcının bulunmak istediği iki-üç arama ifadesini doğal cümlelere yerleştir. Hashtagleri erişim garantisi olarak sunma.
3. `ig-human` ile düzenle; ardından `python3 caption.py caption.txt --keywords "satış otomasyonu,teklif hazırlama" --json` çalıştır.
4. İlk 125 karakterlik görünümü yaklaşık önizleme olarak ele al. Ekran ve arayüze göre değişir; `--truncate` ile değiştirilebilir. Kaynak betikteki hashtag sınırını güncel platform limiti diye sunma; bu dokümantasyon katkısı betik ayarlarını değiştirmez.
5. FAIL sonuçlarını düzelt; WARN sonuçlarını anlamı koruyarak değerlendir. Teknik denetleyici her Türkçe çağrı biçimini tanıyamaz; elle de kontrol et.

Çıktı: kopyalanabilir açıklama, yaklaşık ilk görünüm, tek CTA, arama ifadeleri, denetim özeti. Fotoğraf/carousel için alt metin ekle. Açıklamadaki bağlantının tıklanabildiğini varsayma; uygun hedefi profil veya yetkili mesaj akışı olarak öner.
