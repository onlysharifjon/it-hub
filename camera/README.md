# Camera — Yuz orqali keldi/ketdi bildirishnoma servisi

RTSP kamerasiga ulanib, o'quvchilarning yuzini tanib oladi va ular markazga
**keldi** yoki markazdan **ketdi** bo'lganida Telegram orqali xabar yuboradi.

## Qanday ishlaydi

1. `service.py` RTSP oqimiga ulanadi (ulanish uzilsa avtomatik qayta ulanadi).
2. Har `FRAME_SKIP` kadrda yuzlarni topadi va `faces/` dagi ma'lum yuzlar bilan solishtiradi.
3. Tanilgan o'quvchi birinchi marta ko'rinsa → **keldi** xabari.
4. `ABSENCE_TIMEOUT` soniya davomida ko'rinmasa → **ketdi** xabari.
5. Ism/telegram_id backend bazasidan (`students` jadvali) olinadi.

## O'rnatish

```bash
cd camera
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt        # face_recognition uchun cmake/dlib kerak bo'ladi
cp .env.example .env                    # va qiymatlarni to'ldiring
```

> macOS: `brew install cmake` — `dlib` kompilyatsiyasi uchun zarur.

## O'quvchi yuzlarini qo'shish

Har bir o'quvchi uchun katalog nomi `students.id` bilan boshlanadi:

```
faces/
  42/            # yoki  42_Ali_Valiyev
    1.jpg
    2.jpg
  57/
    front.jpg
```

Bir nechta rasm (turli burchak/yorug'lik) aniqlikni oshiradi.
Yangi rasm qo'shsangiz, keshni yangilash uchun `encodings.pkl` ni o'chiring.

## Ishga tushirish

```bash
python service.py
```

## Sozlamalar (.env)

| O'zgaruvchi | Izoh |
|---|---|
| `RTSP_URL` | Kamera oqimi manzili |
| `FRAME_SKIP` | Har nechinchi kadr tahlil qilinadi (tezlik) |
| `DETECTION_MODEL` | `hog` (CPU) yoki `cnn` (GPU, aniqroq) |
| `RECOGNITION_TOLERANCE` | Tanish qat'iyligi (kichik = qat'iy) |
| `ABSENCE_TIMEOUT` | Necha soniyadan keyin "ketdi" hisoblanadi |
| `NOTIFY_COOLDOWN` | Bir o'quvchi bo'yicha xabarlar orasidagi min. vaqt |
| `TELEGRAM_TOKEN` | Bot tokeni |
| `NOTIFY_CHAT_ID` | Ma'muriyat guruhi/chat id |
| `NOTIFY_STUDENT` | `true` bo'lsa o'quvchining shaxsiy chatiga ham |
| `DATABASE_URL` | Backend bilan bir xil baza |

Telegram sozlanmagan bo'lsa (`TELEGRAM_TOKEN` bo'sh), xabarlar faqat logga chiqadi —
kamerani test qilish uchun qulay.
```
