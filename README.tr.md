# Instagram Agent Skill — Türkçe Kullanım Rehberi

[English](README.md)

[Jake Schincariol](https://opusjake.ai) tarafından geliştirilen Instagram içerik becerileri için Türkçe dokümantasyon. Özgün proje, yazar ve MIT lisansı korunur. Türkçe kullanım uyarlaması: ASAYTECH / Asay60.

Bu katkı İngilizce varsayılan iş akışlarını değiştirmeden Türkçe talimatlar ekler. 13 becerinin her birinde `SKILL.tr.md` bulunur; ana `SKILL.md` dosyası Türkçe isteklerde bu dosyayı okumayı belirtir.

## Kurulum

Git ve yerel araçlar için Python gerekir. Python betikleri üçüncü taraf paket gerektirmez. Kullandığınız ajanın/modelin hesap koşulları ayrıca geçerlidir.

```bash
git clone https://github.com/Jakeschincariol/instagram-agent-skill.git
cp -r instagram-agent-skill/skills/ig-* ~/.claude/skills/
```

Claude Code marketplace:

```text
/plugin marketplace add Jakeschincariol/instagram-agent-skill
/plugin install instagram-agent
```

Bu değişiklik kaynak projeye birleştirilene kadar yukarıdaki kaynak depo kurulumu Türkçe dosyaları içermez; PR dalını kullanmak gerekir. Bu rehber yeni bir Codex kurucusu veya yayınlama entegrasyonu eklemez.

## Kullanım

```text
/ig-reel Teklif sonrası takip aramasını unutan işletmeler için Türkçe
30 saniyelik Reels taslağı hazırla. Sonuç veya müşteri rakamı uydurma.
```

Marka sesini `templates/voice.tr.md` şablonundan oluşturup `~/.claude/instagram/voice.md` konumuna kaydedin. Hedef kitleyi, tonu, gerçek kanıtları ve tek eylem çağrısını tanımlayın. Özel bilgileri herkese açık depoya eklemeyin.

## 13 beceri

| Komut | Görevi |
| --- | --- |
| `/ig-reel` | Açılış seçenekleri, Reels metni ve çekim planı |
| `/ig-viral` | Sağlanan veya yetkili örneklerden içerik araştırması |
| `/ig-caption` | Gönderi açıklaması ve çağrı taslağı |
| `/ig-carousel` | Kaydırmalı gönderi metinleri ve görsel planı |
| `/ig-story` | Story kareleri ve çıkartma önerileri |
| `/ig-profile` | Profil ve biyografi değerlendirmesi |
| `/ig-plan` | Haftalık içerik takvimi |
| `/ig-human` | Anlamı koruyan sadeleştirme |
| `/ig-comment` | Başka gönderiler için yorum taslakları |
| `/ig-reply` | Kendi yorumlarına yanıt taslakları |
| `/ig-dm` | Mesaj ve takip taslakları |
| `/ig-repurpose` | Uzun içerikten bağımsız kısa içerikler |
| `/ig-audit` | Verilen performans verilerinin analizi |

## Türkçe desteğin sınırları

- Bu PR **dokümantasyon katkısıdır**. Python betikleri, JSON sözlükleri ve İngilizce varsayılanlar değiştirilmez.
- Betiklerin İngilizce sözcük listeleri ve ASCII odaklı sözcük kuralları Türkçe açılış/üslup puanlarını yanıltabilir. Türkçe puanları doğrulanmış ölçüm gibi kullanmayın.
- Türkçe konuşma süresini sesli prova ile ölçün; kaynak `beats.py` Türkçe karakterleri sözcük hesabında bölebilir.
- Kaynak araçlarda `--lang tr` seçeneği yoktur. Betik çıktıları İngilizcedir. Türkçe dil işleme desteği ayrı bir kod değişikliği gerektirir.
- `humanize.py` görünmez biçim karakterlerini kaldırırken emoji birleşimlerini bozabilir; özgün emoji ve bağlantıları elle kontrol edin.
- `swipe.py` girdisinde 4500 gibi tam tamsayı kullanın. K/M/bin biçimindeki kısaltmalar yanlış yorumlanabilir. Hesap medyanı ile takipçi sayısını eşdeğer taban saymayın.
- Açılış ve üslup puanları viral olma veya AI yazarlığı olasılığı değildir. Özgün projenin İngilizce ölçümleri Türkçe metinleri doğrulamaz.
- Platform sınırları ve arayüz ayrıntıları değişebilir; canlı iddia için güncel resmî kaynağı doğrulayın.
- Beceriler taslak üretir; Instagram'a giriş, otomatik gönderi/yorum/DM, toplu veri toplama veya video render etme özelliği eklemez.

## Lisans

MIT. Copyright (c) 2026 Jake Schincariol. Ayrıntılar [LICENSE](LICENSE) dosyasındadır. Türkçe kullanım uyarlaması kaynak projeye katkı olarak sunulur; özgün ürünün sahipliği iddia edilmez.
