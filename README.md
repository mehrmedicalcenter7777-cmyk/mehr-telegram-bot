# Mehr Medical: Telegram kanal uchun avtomatik postlar

Har kuni **8:00** va **12:00** da (Toshkent vaqti) [@mehr_medical7](https://t.me/mehr_medical7) kanaliga
rasm va audio bilan tibbiy maslahat posti chiqaradi.

## Qanday ishlaydi

| Qadam | Agent | Nima qiladi |
|---|---|---|
| 1 | Izlovchi (`agents/researcher.py`) | Rubrika bo'yicha internetdan dolzarb mavzular topadi, avvalgilarini takrorlamaydi |
| 2 | Muallif (`agents/writer.py`) | Ishonchli manbalardan maslahatni topib, `config/style.md` uslubida post yozadi va mos shifokorni tavsiya qiladi |
| 3 | Rassom (`agents/illustrator.py`) | Gemini "Nano Banana" bilan rasm chizadi |
| 4 | Diktor (`agents/narrator.py`) | ElevenLabs orqali maslahatni ovozda o'qiydi |
| 5 | Nazoratchi (`agents/reviewer.py`) | Tibbiy aniqlik, imlo, lotin yozuvi, uzunlik va formatni tekshiradi; xato bo'lsa qayta yozdiradi |
| 6 | Nashr (`main.py`) | 10 daqiqa oldin adminga yuboradi, keyin kanalga chiqaradi |

Vaqt jadvali (GitHub Actions, `.github/workflows/post.yml`):

- **7:35 / 11:35** ishga tushadi va postni tayyorlaydi.
- **7:50 / 11:50** postni adminga **🔄 Qayta ishlash** tugmasi bilan yuboradi.
  Tugma bosilsa, boshqa mavzuda yangi variant tayyorlanib, yana yuboriladi.
- **8:00 / 12:00** oxirgi variant kanalga chiqadi.
- Xato bo'lsa, admin botdan "⚠️" xabarini oladi.

## Sozlash (bir marta)

GitHub'da: **Settings → Secrets and variables → Actions → New repository secret**.
Quyidagi 5 ta secret qo'shiladi:

| Nomi | Qayerdan olinadi |
|---|---|
| `TELEGRAM_BOT_TOKEN` | @BotFather bergan token |
| `GEMINI_API_KEY` | https://aistudio.google.com/apikey |
| `ELEVENLABS_API_KEY` | elevenlabs.io → Profile → API Keys |
| `ELEVENLABS_VOICE_ID` | elevenlabs.io → Voices → ovoz → "Copy voice ID" |
| `ADMIN_CHAT_ID` | Pastdagi "chat_id" ishga tushirish orqali |

`ADMIN_CHAT_ID` ni topish: botni oching va **/start** bosing. Keyin **Actions → Kanalga post →
Run workflow**, `mode = chat_id` ni tanlang. Natijada `ADMIN_CHAT_ID = 123456789` yozuvi chiqadi.

## Qo'lda ishga tushirish

**Actions → Kanalga post → Run workflow**:

- `test`: post tayyorlab, faqat adminga yuboradi (kanalga chiqmaydi)
- `now`: darhol kanalga chiqaradi
- `chat_id`: botga yozganlarning ID sini ko'rsatadi

## O'zgartirish

- Shifokorlar: `config/doctors.yaml`
- Rubrika, kanal, telefon, vaqtlar, modellar: `config/settings.yaml`
  (vaqtni o'zgartirsangiz, `post.yml` dagi `cron` ni ham 25 daqiqa oldinga moslang, UTC = Toshkent − 5 soat)
- Post uslubi: `config/style.md`
- Chiqqan mavzular tarixi: `data/history.json` (avtomatik yangilanadi)

## Eslatma

- Shaxsiy (private) repozitoriyada GitHub Actions oyiga 2000 daqiqa bepul.
  Bu dastur kuniga taxminan 2 × 25 daqiqa, ya'ni oyiga ~1500 daqiqa sarflaydi.
- GitHub jadvali ba'zan bir necha daqiqa kechikadi. Kechiksa ham admin postni
  kamida 5 daqiqa oldin oladi.
