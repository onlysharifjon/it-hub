# Ota-ona iOS ilovasi: versiya va texnik ko'rik

CRM'da faqat `admin` roli uchun **Tizim → Mobil ilova** sahifasi. Sozlamalar bitta
`parent_release_config` DB qatorida saqlanadi; `audit_logs` har o'zgarishni xodim
IDsi va eski/yangi qiymatlar bilan qayd etadi. API ishchi nusxalari bir xil DB
holatini har parent so'rovda o'qiydi.

## Mobil ilova shartnomasi

`GET /api/parent/release-config` — loginsiz, `Cache-Control: no-store`:

```json
{
  "maintenance_enabled": false,
  "maintenance_title": "Texnik xizmat davom etmoqda",
  "maintenance_message": "Ilova ustida qisqa texnik ishlar olib borilmoqda. Birozdan so‘ng qayta urinib ko‘ring.",
  "min_supported_build": 1,
  "latest_build": 5,
  "app_store_url": "https://apps.apple.com/uz/app/minar-parents/id6820518218"
}
```

Ilova start/foreground'da va 426/503 javobidan so'ng qayta o'qiydi. Har parent API
so'roviga `X-Minar-App-Build: <CFBundleVersion>` yuboradi. `build <
min_supported_build` bo'lsa yangilash ekrani, aks holda
`maintenance_enabled=true` bo'lsa texnik ko'rik ekrani ko'rinadi. Bu ustuvorlik
server gate'da ham bir xil.

Eski App Store mijozlari build header yubormaydi; ular build **5** deb hisoblanadi.
Shuning uchun `min_supported_build=6` qo'yilsa ular 426 oladi; `5` qo'yilsa
header yo'q mijozning haqiqiy buildi 1–4 ekanini server ajrata olmaydi.

Server parent API va eski `/auth/phone/*` OTP endpointlariga:

* `426 {"code":"upgrade_required", ...}` — build minimaldan past;
* `503 {"code":"maintenance", ...}` va `Retry-After: 120` — texnik ko'rik;

javobini beradi. Har ikkisi `Cache-Control: no-store`, `X-Request-ID` bilan.
To'lov provayderining `/payment-callbacks/*` webhooklari, CRM admin API,
public privacy va release-config ochiq qoladi; `DELETE /parent/account` ham
akkauntni o'chirish huquqi uchun ochiq qoladi. Oldi ilova 426/503 javobini
maxsus ekran sifatida ko'rsatmasligi mumkin, ammo parent API so'rovlari
serverda to'xtatiladi.

## CRM admin API

`GET /api/admin/parent-release-config` va `PUT /api/admin/parent-release-config`
faqat CRM `admin` Bearer tokeni bilan ishlaydi. PUT barcha 6 ommaviy maydonni
birgalikda qabul qiladi. `updated_at` va `updated_by_id` admin javobida bor.
Buildlar musbat butun, `latest_build >= min_supported_build`; App Store URL faqat
HTTPS `apps.apple.com/.../id6820518218` ko'rinishida bo'lishi mumkin.

## Chiqarish tartibi

1. `alembic upgrade head` migratsiyasini API image almashishidan oldin bajaring.
   Migration sozlamalarni xavfsiz boshlaydi: maintenance **false**, minimal
   build **1**, so'nggi build **5**. Hech kim darhol bloklanmaydi.
2. API + CRM web bir xil commitdan deploy qilinadi. Production stack:
   `/var/www/minar-stack`; `deploy.sh` ga commit `--ref` sifatida uzatiladi.
3. Public GET, CRM admin GET, login, Payme webhook routingi va xayoliy review
   akkauntini smoke-test qiling. Flaglarni yoqish shart emas.
4. Yangi build App Store'da haqiqatan chiqqachgina minimal buildni oshiring.
   CRM tasdiqlash oynasi ta'sir doirasini ko'rsatadi; bekor qilish uchun
   minimumni avvalgi qiymatga qaytaring yoki texnik ko'rikni o'chiring.

Release sozlamalari parent login-parol migratsiyasidan mustaqil; boshqa
branchdagi parol o'zgarishlari bu branchga qo'shilmagan.
