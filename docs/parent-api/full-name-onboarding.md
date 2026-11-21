# Minar Parents — kirgandan keyin to'liq ism-familiya so'rash

CRM'da ko'pincha ota-onaning **faqat ismi** yozilgan (talaba kartasidagi `mother_name` / `father_name`).
Hunter akkaunt ochadi: login = telefon, avto parol = **ism + telefonning oxirgi 4 raqami** (`Nodira2233`).
Ota-ona birinchi kirganda ilova to'liq ism-familiyani so'raydi.

**API yoki JSON o'zgarmaydi.** Yangi endpoint yo'q, mavjud ikkitasi ishlatiladi.

## iOS oqimi

1. `POST /api/parent/auth/login` → tokenlar (o'zgarmagan).
2. `GET /api/parent/profile` → `{display_name, full_name, phone}` (o'zgarmagan).
3. Agar `full_name.trimmingCharacters(in: .whitespaces).split(separator: " ").count < 2` bo'lsa,
   **«To'liq ism-familiyangizni kiriting»** ekrani ko'rsatiladi (yopib bo'lmaydi, asosiy ekranga o'tilmaydi).
   * Bitta maydon, masalan placeholder `Nodira Karimova`. Kamida 2 so'z bo'lmasa «Saqlash» tugmasi faol bo'lmaydi.
   * Kichik harf bilan yozilsa ham bo'ladi, server o'zi to'g'rilaydi.
4. `PATCH /api/parent/profile` `{"display_name": "<kiritilgan matn>"}` → `204` (o'zgarmagan shartnoma).
5. `GET /api/parent/profile` qayta chaqiriladi. Endi `full_name` ham, `display_name` ham formatlangan holatda
   keladi (`"nodira karimova"` → `"Nodira Karimova"`). Ilova shu qiymatni ko'rsatadi va asosiy ekranni ochadi.

Xatolar: `422 validation_error` (bo'sh yoki 100 belgidan uzun) — `errors.display_name[0]` ko'rsatiladi.

## Server xatti-harakati (`PATCH /parent/profile`, `display_name`)

* Ism formatlanadi: bo'shliqlar bittaga, har so'z (va chiziqcha bilan ajratilgan qism) bosh harfi katta, qolgani
  kichik. Apostrofdan keyingi harf kichik qoladi (`o'g'iloy` → `O'g'iloy`); `o'g'li` / `qizi` kichik harfda qoladi.
* Kiritilgan ism **2+ so'z** bo'lsa va CRM'dagi `full_name` **bitta so'z** bo'lsa → `full_name` ham shu qiymatga
  yangilanadi (CRM'da ham to'liq ism ko'rinadi). CRM'da allaqachon to'liq ism bo'lsa, u ustidan yozilmaydi,
  faqat `display_name` o'zgaradi. Shuning uchun ekran bir marta chiqadi.
* Parol, login va farzandlar o'zgarmaydi.

## Eski ilova versiyalari

Eski build bu ekranni ko'rsatmaydi va odatdagidek ishlayveradi. Profil tahrirlashda ism endi bosh harflari katta
qilib saqlanadi — boshqa farq yo'q.
