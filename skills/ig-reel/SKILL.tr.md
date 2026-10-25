# Reels senaryosu

> Türkçe kullanım rehberi. Bu katkı yalnızca dokümantasyondur; Python betiklerinin davranışını değiştirmez. Betikler İngilizce sözcük listeleri ve yer yer ASCII karakter kuralları kullanır. Türkçe açılış/üslup puanlarını geçerli sayma; Türkçe konuşma süresini sesli prova ile doğrula. Türkçe metinlerde anlam, açıklık ve marka sesini elle değerlendir. Betik komutları yalnızca mevcut İngilizce araçların kullanımını gösterir; `--lang` seçeneği bu kaynak sürümde yoktur.

## Ortak bağlam

Varsa `~/.claude/instagram/voice.md`, `swipe.md`, `plan.md` ve `log.md` içinden yalnızca görevle ilgili dosyaları oku. Marka sesi yoksa `templates/voice.tr.md` şablonunu öner; verilen bağlamla ilerle. Kişisel/müşteri verilerini herkese açık Git deposuna ekleme. Diğer becerileri `/ig-reel` gibi çağır veya ilgili `SKILL.md` dosyasını oku.

Veri, müşteri sonucu ve alıntı uydurma. Bilinmeyen değeri `{{doğrulanacak bilgi}}` ile işaretle. İçerik ve yanıt taslakları hazırla; Instagram'a gönderi/yorum/DM gönderme. Platform sayılarını değişmez kural gibi sunma; güncel iddia gerekiyorsa resmî kaynaktan doğrula.


1. Konuyu, hedef izleyiciyi, tek somut sorunu, doğrulanmış örneği ve istenen süreyi belirle. Tek videoya tek fikir koy.
2. `hooks.json` içindeki İngilizce formülleri oku ve Türkçe anlatıma uyarla. Varsa `swipe.md` içindeki kullanıcı verisini genel önerilerin önüne koy.
3. Birbirinden farklı üç formülle üç açılış yaz. Her biri için konuşulan cümleyi ve en fazla altı sözcüklük ekran metnini ayrı ver.
4. Üç Türkçe açılışı kısalık, somutluk, açıklık ve izleyiciye uygunluk açısından elle karşılaştır. Kaynak `hookscore.py` İngilizce odaklıdır; Türkçe için sayısal puan uydurma veya İngilizce puanı geçerli sayma.
5. Seçilen açılışla senaryoyu satır başına bir sahne olacak biçimde yaz: açılış, sorunun önemi, açıklama, karşılık ve tek eylem çağrısı. Son satır uygunsa ilk satırdaki fikre bağlansın.
6. Hedef süreyi talebe göre ayarla. Türkçe metni sesli oku ve gerçek süreyi ölç. İlk cümleyi kısa tut, uzun durağan sahneleri böl. Kaynak `beats.py` ASCII sözcük sayımı Türkçe karakterleri bölebilir; Türkçe süreyi bu araçla doğrulanmış sayma.
7. Metni `ig-human` ile düzenle. İki düzeltme turundan sonra puanı zorlamak yerine kalan sorunu açıkla.

Çıktı: üç açılış ve araç puanları, seçimin nedeni, kopyalanabilir konuşma metni, zamanlı ekran metinleri, sahne/görüntü önerileri ve tek CTA. 1080×1920 tasarımda metni arayüz alanlarından uzak tut; önizlemede doğrula. Bu iş akışı video render etmez.

Kullanıcı içerik kaydı isterse tarih, formül ve açılışı `log.md` dosyasına ekle. Yayınlanmamış taslağı yayınlanmış gibi kaydetme.
