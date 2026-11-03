"""Additional student questions matched to the existing 24 CRM Foundation lessons.

Each tuple is (question, correct choice, two distractors, explanation). These
questions do not use confidential lesson guides or generate questions at runtime.
"""
CHECKS = {
1: [
('Papka nima uchun kerak?', 'Fayllarni tartiblash uchun', 'Ekran yorqinligini oshirish uchun', 'Internet tezligini oshirish uchun', 'Papka fayllarni mavzu yoki loyiha bo‘yicha yig‘adi.'),
('Natijani ekranda qaysi qurilma ko‘rsatadi?', 'Monitor', 'Klaviatura', 'Sichqoncha', 'Monitor chiqarish qurilmasidir.'),
('Ishni keyin topish uchun qaysi nom qulay?', 'Tabiat-loyihasi', 'Yangi fayl 999', 'aaaaa', 'Mazmunli nom kerakli ishni topishni osonlashtiradi.'),
('Dasturdagi ishni yopishdan oldin nima qilish kerak?', 'Ish saqlanganini tekshirish', 'Faylni o‘chirish', 'Kompyuterni tokdan uzish', 'Saqlanmagan o‘zgarishlar yo‘qolishi mumkin.')],
2: [
('Brauzerning vazifasi nima?', 'Veb-sahifalarni ochish', 'Monitorni ta’mirlash', 'Klaviaturani almashtirish', 'Brauzer internetdagi sahifalarni ko‘rsatadi.'),
('Qidiruv natijasining ishonchliligini qanday tekshiramiz?', 'Manba, muallif va sanani tekshirib', 'Faqat birinchi natijani olib', 'Faqat rangiga qarab', 'Manba va sana ma’lumotni baholashga yordam beradi.'),
('Begona sayt parolingizni so‘radi. Nima qilasiz?', 'Kiritmayman va kattadan yordam so‘rayman', 'Hamma parollarimni kiritaman', 'Do‘stimning parolini yozaman', 'Parol shaxsiy ma’lumotdir.'),
('Qidiruvda qanday so‘zlar foydaliroq?', 'Mavzuga mos aniq kalit so‘zlar', 'Tasodifiy harflar', 'Faqat undov belgisi', 'Aniq kalit so‘zlar mos natijalarni topadi.')],
3: [
('Drive nimaga xizmat qiladi?', 'Fayllarni saqlash va ulashishga', 'Monitorni boshqarishga', 'Faqat musiqa eshitishga', 'Drive fayllarni bulutda saqlaydi.'),
('Tasdiqlash kodini kimga berish mumkin?', 'Hech kimga bermaslik kerak', 'Har qanday yozgan odamga', 'Ochiq guruhga', 'Tasdiqlash kodi akkauntga kirish huquqini beradi.'),
('Xatning mavzu qatori qanday bo‘lishi kerak?', 'Xat maqsadini qisqa bildirsin', 'Ma’nosiz belgilar bo‘lsin', 'Parol yozilsin', 'Aniq mavzu xat nima haqida ekanini ko‘rsatadi.'),
('Faylni kimlar o‘zgartirishi kerak?', 'Faqat tahrirlash vazifasi bor odamlar', 'Havolani olgan hamma doim', 'Begona foydalanuvchilar', 'Ulashishda eng zarur huquq beriladi.')],
4: [
('Bir paragraf nimani yoritgani yaxshi?', 'Bitta asosiy fikrni', 'Bir-biriga aloqasiz o‘nta mavzuni', 'Faqat belgilarni', 'Paragraflar fikrlarni ajratadi.'),
('Matn o‘qilishini nima yaxshilaydi?', 'Mos shrift va yetarli oraliq', 'Juda kichik harflar', 'Har so‘zda boshqa shrift', 'Bir xil uslub va oraliq o‘qishni osonlashtiradi.'),
('Boshqa odam matnidan foydalanishdan oldin nima tekshiriladi?', 'Foydalanishga ruxsat borligi', 'Faqat harflar soni', 'Ekran hajmi', 'Muallif huquqini hurmat qilish kerak.'),
('Hujjatni nimadan boshlash qulay?', 'Mazmunli sarlavhadan', 'Tasodifiy rasmdan', 'Yashirin paroldan', 'Sarlavha mavzuni tanishtiradi.')],
5: [
('Ketma-ket bajariladigan ishlar uchun nima qulay?', 'Raqamlangan ro‘yxat', 'Aralash rasmlar', 'Bo‘sh sahifa', 'Raqamlar qadamlar tartibini ko‘rsatadi.'),
('Sarlavha uslublari nima beradi?', 'Hujjatga izchil tuzilish', 'Internet tezligini', 'Avtomatik to‘g‘ri mazmun', 'Uslublar bo‘limlarning darajasini ajratadi.'),
('Topshirishdan oldin nimani tekshiramiz?', 'Imlo, havola va sahifa chegaralarini', 'Faqat fayl hajmini', 'Faqat ekran rangini', 'Yakuniy tekshiruv hujjat sifatini oshiradi.'),
('Rasm yonidagi izoh nima qiladi?', 'Rasm mazmunini tushuntiradi', 'Parolni oshkor qiladi', 'Sahifani o‘chiradi', 'Mazmunli izoh rasmni tushunishga yordam beradi.')],
6: [
('Taqdimotdagi yozuv qanday bo‘lishi kerak?', 'Uzoqdan ham o‘qiladigan', 'Iloji boricha mayda', 'Fonga bir xil rangda', 'Auditoriya matnni bemalol ko‘rishi kerak.'),
('Slaydga qanday rasm tanlanadi?', 'Asosiy fikrga mos rasm', 'Mavzuga aloqasiz rasm', 'Eng katta fayl', 'Rasm fikrni tushuntirishga xizmat qiladi.'),
('Taqdimotchi qanday tushuntirgani yaxshi?', 'O‘z so‘zlari bilan izohlab', 'Hamma matnni jim ko‘rsatib', 'Auditoriyaga orqa o‘girib', 'Slayd nutqni qo‘llab-quvvatlaydi.'),
('Muammo va yechimni qanday joylashtirish qulay?', 'Mantiqiy ketma-ketlikdagi slaydlarda', 'Hammasini bitta mayda matnda', 'Tasodifiy tartibda', 'Ketma-ketlik hikoyani tushunarli qiladi.')],
7: [
('A1 qaysi katak?', 'A ustun va 1-qator kesishmasi', 'B ustundagi katak', 'Birinchi fayl', 'Katak manzili ustun harfi va qator raqamidan tuziladi.'),
('Ustun sarlavhasi nima uchun kerak?', 'Qiymatlar ma’nosini ko‘rsatish uchun', 'Jadvalni yashirish uchun', 'Faqat bezak uchun', 'Sarlavha ustundagi ma’lumot turini tushuntiradi.'),
('Daqiqalar va ismlarni qanday joylashtiramiz?', 'Alohida ma’noli ustunlarda', 'Bitta aralash katakda', 'Faqat rasm shaklida', 'Bir xil turdagi ma’lumot bir ustunda turadi.'),
('Hisoblanadigan miqdor qanday kiritiladi?', 'Son qiymati sifatida', 'Faqat rasm sifatida', 'Tasodifiy harflar bilan', 'Son qiymatlari bilan hisoblash mumkin.')],
8: [
('Formula qaysi belgi bilan boshlanadi?', '=', '#', '?', 'Jadval formulasi tenglik belgisi bilan boshlanadi.'),
('Yig‘indini hisoblashga qaysi funksiya mos?', 'SUM', 'Rasm', 'Sarlavha', 'SUM berilgan sonlarni qo‘shadi.'),
('Diagramma nima uchun kerak?', 'Ma’lumotdagi farq va o‘zgarishni ko‘rish uchun', 'Ma’lumotni yashirish uchun', 'Kataklarni o‘chirish uchun', 'Diagramma sonlarni ko‘rgazmali taqqoslaydi.'),
('Hisob natijasi g‘alati chiqsa nima tekshiriladi?', 'Formula va katak manzillari', 'Faqat monitor rangi', 'Klaviatura markasi', 'Noto‘g‘ri manzil boshqa qiymatni hisobga olishi mumkin.')],
9: [
('So‘rovnoma yig‘ish uchun qaysi vosita mos?', 'Google Forms', 'Faqat kalkulyator', 'Monitor sozlamasi', 'Forms savollar va javoblarni yig‘adi.'),
('Oddiy veb-sahifa tuzishga qaysi vosita mos?', 'Google Sites', 'Fayl nomini o‘zgartirish', 'Klaviatura sozlamasi', 'Sites sahifalarni tuzish va nashr qilish uchun ishlatiladi.'),
('So‘rovnomada qanday savol yaxshi?', 'Qisqa va tushunarli', 'Bir savolda beshta alohida masala', 'Mavzusiz savol', 'Aniq savolga javob berish osonroq.'),
('So‘rovnomada nima yig‘ilmasligi kerak?', 'Keraksiz maxfiy ma’lumotlar', 'Mavzuga mos fikrlar', 'Ruxsat etilgan javoblar', 'Faqat zarur ma’lumotni so‘rash kerak.')],
10: [
('Shablon bilan ishlaganda nima qilish kerak?', 'Uni o‘z maqsadiga moslashtirish', 'Mazmunini tekshirmaslik', 'Har bir qismini tasodifiy almashtirish', 'Shablon boshlang‘ich tuzilma beradi.'),
('Dizayndagi matn qanday bo‘lsin?', 'O‘qilishi oson', 'Fonda ko‘rinmas', 'Doim juda mayda', 'Dizayn mazmunni yetkazishi kerak.'),
('Bir ishda ranglarni qanday tanlaymiz?', 'Bir-biriga mos cheklangan palitra', 'Har element uchun tasodifiy rang', 'Faqat ko‘rinmas ranglar', 'Izchil palitra yaxlitlik beradi.'),
('Rasmni cho‘zib yuborish qanday ta’sir qiladi?', 'Uning nisbatlari buziladi', 'Sifati doim oshadi', 'Ma’nosi avtomatik aniqlashadi', 'Rasmning tomonlar nisbatini saqlash kerak.')],
11: [
('Posterda eng asosiy xabar qanday ajratiladi?', 'Ko‘zga tashlanadigan sarlavha bilan', 'Eng mayda matn bilan', 'Barcha joyni to‘ldirib', 'Vizual tartib asosiy xabarga e’tiborni yo‘naltiradi.'),
('Bo‘sh joy dizaynga nima beradi?', 'Elementlar orasida nafas va aniqlik', 'Faqat xato', 'Majburiy ravishda ma’lumot yo‘qolishi', 'Bo‘sh joy elementlarni ajratadi.'),
('Tadbir posterida qaysi ma’lumot zarur?', 'Nomi, sanasi va joyi', 'Muallifning paroli', 'Tasodifiy raqamlar', 'Tomoshabin qachon va qayerga borishni bilishi kerak.'),
('Matn va fon kontrasti nima uchun kerak?', 'Matn o‘qilishi uchun', 'Faylni yashirish uchun', 'Sarlavhani yo‘qotish uchun', 'Yetarli kontrast mazmunni aniq ko‘rsatadi.')],
12: [
('Videoda sahnalar tartibi qanday bo‘lishi kerak?', 'Fikrni tushunarli davom ettiradigan', 'Doim tasodifiy', 'Faqat bir xil takror', 'Sahnalar mantiqiy hikoya hosil qiladi.'),
('Ovoz va musiqa qanday muvozanat qilinadi?', 'Nutq aniq eshitiladigan qilib', 'Musiqa nutqni butunlay bosib', 'Hamma ovoz eng baland qilib', 'Asosiy xabarni eshitish muhim.'),
('Taqdimotda animatsiya nima uchun ishlatiladi?', 'Fikrga e’tiborni yo‘naltirish uchun', 'Mazmunni yashirish uchun', 'Har bir elementni doim qimirlatish uchun', 'Animatsiya maqsadga xizmat qilishi kerak.'),
('Tayyor videoni ulashishdan oldin nima qilinadi?', 'Boshidan oxirigacha tekshiriladi', 'Hech ko‘rilmaydi', 'Tasodifiy fayl yuboriladi', 'Ko‘rib chiqish tovush va tasvir xatolarini topadi.')],
13: [
('Figma’da frame nima uchun kerak?', 'Ekran yoki dizayn hududini ajratish uchun', 'Internet tezligini oshirish uchun', 'Parolni saqlash uchun', 'Frame ekran maketini tartiblaydi.'),
('Qatlamlarga nom berish nima uchun foydali?', 'Kerakli elementni topish osonlashadi', 'Rasm o‘z-o‘zidan yoziladi', 'Fayl o‘chadi', 'Mazmunli nom katta loyihada yo‘l topishga yordam beradi.'),
('Elementlarni tekislash nimani yaxshilaydi?', 'Tartib va o‘qilishni', 'Faqat internetni', 'Tasodifiylikni', 'Tekis joylashish izchil maket beradi.'),
('Takrorlanadigan tugmalar qanday bo‘lishi kerak?', 'Bir xil uslubda', 'Har biri mutlaqo boshqa', 'Matnsiz va ko‘rinmas', 'Izchil tugmalar interfeysni tushunarli qiladi.')],
14: [
('Tugma matni nimani bildirishi kerak?', 'Bosilganda nima bo‘lishini', 'Tasodifiy harflarni', 'Foydalanuvchi parolini', 'Aniq nom harakat natijasini oldindan bildiradi.'),
('Interfeysdagi asosiy amal qanday ajratiladi?', 'Ko‘rinadigan joy va mos urg‘u bilan', 'Yashirin joyga qo‘yib', 'Hamma elementni bir xil kattalashtirib', 'Vizual tartib eng muhim amalni topishga yordam beradi.'),
('Xato xabari qanday bo‘lishi kerak?', 'Muammoni va keyingi qadamni tushuntirsin', 'Foydalanuvchini ayblasin', 'Faqat noma’lum kod bo‘lsin', 'Tushunarli xabar xatoni tuzatishga yordam beradi.'),
('Telefon ekranidagi tugma qanday bo‘lishi kerak?', 'Barmoq bilan qulay bosiladigan', 'Juda mayda', 'Boshqa tugma ustida', 'Bosish maydoni va oraliq qulaylikni oshiradi.')],
15: [
('Prototip nimani sinashga yordam beradi?', 'Ekranlar o‘rtasidagi o‘tishlarni', 'Kompyuter tokini', 'Fayl parolini', 'Prototip foydalanuvchi yo‘lini sinaydi.'),
('Tugma bosilganda qayerga o‘tishini nima belgilaydi?', 'Prototipdagi bog‘lanish', 'Faylning rangi', 'Monitor hajmi', 'Interaksiya elementni keyingi ekran bilan bog‘laydi.'),
('Prototipni kim bilan sinash foydali?', 'Maqsadli foydalanuvchi bilan', 'Hech kim bilan emas', 'Faqat tasodifiy fayl bilan', 'Foydalanuvchi fikri tushunarsiz joylarni ko‘rsatadi.'),
('Sinovda foydalanuvchi adashsa nima qilamiz?', 'Sababini topib maketni yaxshilaymiz', 'Uni ayblaymiz', 'Muammoni yashiramiz', 'Sinovning maqsadi dizaynni yaxshilashdir.')],
16: [
('Scratch’dagi sprite nima?', 'Sahnadagi boshqariladigan obyekt', 'Kompyuter simi', 'Fayl paroli', 'Sprite buyruqlar bilan boshqariladi.'),
('Bloklar tartibi nimaga ta’sir qiladi?', 'Buyruqlarning bajarilish tartibiga', 'Monitor hajmiga', 'Internet narxiga', 'Kompyuter ko‘rsatmalarni belgilangan tartibda bajaradi.'),
('Yashil bayroq ko‘pincha nima qiladi?', 'Loyihani ishga tushiradi', 'Faylni o‘chiradi', 'Monitorni o‘chiradi', 'Yashil bayroq bosilishi boshlash hodisasi bo‘la oladi.'),
('Takrorlash bloki nima uchun kerak?', 'Bir amalni bir necha marta bajarish uchun', 'Faqat rasm chizish uchun', 'Parol qo‘yish uchun', 'Sikl takroriy buyruqlarni qisqartiradi.')],
17: [
('O‘yin maqsadi qanday bo‘lishi kerak?', 'O‘yinchiga tushunarli', 'Doim yashirin', 'Hech qachon tekshirilmaydigan', 'Aniq maqsad o‘yinchiga yo‘l ko‘rsatadi.'),
('Ochkoni nimada saqlash mumkin?', 'O‘zgaruvchida', 'Faqat fon rangida', 'Fayl nomida', 'O‘zgaruvchi o‘zgaradigan qiymatni saqlaydi.'),
('Qahramon to‘siqqa tegsa nima ishlatilishi mumkin?', 'Tegishni tekshiruvchi shart', 'Tasodifiy matnni o‘chirish', 'Monitorni almashtirish', 'Shart vaziyatga mos javobni ishga tushiradi.'),
('Yangi o‘yin boshlanganda ochko nima bo‘lishi kerak?', 'Boshlang‘ich qiymatga qaytishi', 'Eski natija tasodifan qolishi', 'Doim cheksiz bo‘lishi', 'Boshlang‘ich holat takroriy o‘yinni to‘g‘ri boshlaydi.')],
18: [
('Shart bloki nimani tekshiradi?', 'Vaziyat rost yoki yolg‘onligini', 'Faqat shriftni', 'Kompyuter markasini', 'Shart natijasiga qarab turli amallar bajariladi.'),
('O‘zgaruvchi nima saqlaydi?', 'O‘zgarishi mumkin bo‘lgan qiymatni', 'Faqat monitorni', 'Faqat fayl ikonkasini', 'Masalan, ochko va hayot soni o‘zgaruvchida turadi.'),
('Hayot soni nol bo‘lsa qaysi amal mos?', 'O‘yinni yakunlash', 'Tekshirmay davom etish', 'Parolni e’lon qilish', 'Shart o‘yin tugashini belgilashi mumkin.'),
('Ochko 5 bo‘lib, unga 2 qo‘shilsa nechchi bo‘ladi?', '7', '52', '3', 'Son qiymatiga 2 qo‘shilsa 7 hosil bo‘ladi.')],
19: [
('Interaktiv hikoyada o‘quvchi nima qila oladi?', 'Tanlov qilib voqeaga ta’sir qiladi', 'Faqat faylni o‘chiradi', 'Hech qanday amal qilolmaydi', 'Interaktivlik foydalanuvchining ishtirokini bildiradi.'),
('Voqealar tartibi qanday bo‘lishi kerak?', 'Sabab va natijasi tushunarli', 'Faqat tasodifiy', 'Doim bir-biriga zid', 'Izchil hikoya voqealarni anglashga yordam beradi.'),
('Qahramonlar navbat bilan gapirishi uchun nima kerak?', 'Vaqt yoki hodisalarni muvofiqlashtirish', 'Hammasini bir vaqtda yozish', 'Barcha blokni o‘chirish', 'Hodisalar dialog ketma-ketligini boshqaradi.'),
('Tanlov tugmasi nimani tushuntirsin?', 'Tanlov mazmunini', 'Yashirin parolni', 'Tasodifiy sonni', 'Aniq tanlov nomi foydalanuvchiga qaror qilishga yordam beradi.')],
20: [
('O‘yindagi xatoni topishning yaxshi yo‘li qaysi?', 'Bir vaziyatni bosqichma-bosqich qayta sinash', 'Hammasini birdan tasodifan o‘zgartirish', 'Xatoni yashirish', 'Takrorlanadigan sinov sababni ajratishga yordam beradi.'),
('O‘yin qiyinligi qanday oshirilishi mumkin?', 'Bosqichma-bosqich', 'Birinchi soniyada imkonsiz qilib', 'Maqsadni yashirib', 'Bosqichli qiyinlik o‘rganish imkonini beradi.'),
('Qayta boshlash tugmasi nimani tiklashi kerak?', 'Ochko, joylashuv va boshlang‘ich holatni', 'Faqat rangni', 'Faqat fayl nomini', 'Barcha muhim holatlar qayta o‘rnatiladi.'),
('O‘yinni boshqaga sinatish nima beradi?', 'Yangi xato va takliflarni', 'Avtomatik mukammallikni', 'Faqat fayl hajmini', 'Boshqa foydalanuvchi kutilmagan vaziyatlarni topishi mumkin.')],
21: [
('Kreativ topshiriqni nimadan boshlaymiz?', 'Maqsad va cheklovlarni tushunishdan', 'Tasodifiy nusxa ko‘chirishdan', 'Ishni yashirishdan', 'Maqsad yechim yo‘nalishini belgilaydi.'),
('Bir nechta g‘oyani qanday taqqoslaymiz?', 'Maqsadga mosligi va bajarish imkoniga qarab', 'Faqat nomining uzunligiga qarab', 'Faqat tasodifan', 'Mezonlar asosli tanlov qilishga yordam beradi.'),
('Vaqt oz bo‘lsa nima muhim?', 'Asosiy ishlaydigan qismni tugatish', 'Cheksiz bezak qo‘shish', 'Barcha ishni qayta boshlash', 'Ustuvor vazifa mahsulotning asosiy maqsadidir.'),
('Olingan fikr-mulohaza bilan nima qilamiz?', 'Foydali takliflarni sinab ko‘ramiz', 'Hamma fikrni o‘chiramiz', 'Muallifni ayblaymiz', 'Fikr-mulohaza ishni takomillashtirishga xizmat qiladi.')],
22: [
('Loyiha g‘oyasi nimani aytishi kerak?', 'Kimning qaysi muammosini hal qilishini', 'Faqat fayl rangini', 'Muallif parolini', 'Aniq muammo loyiha maqsadini belgilaydi.'),
('Katta vazifani qanday rejalash qulay?', 'Kichik bajariladigan qadamlarga bo‘lib', 'Hammasini bir vaqtga qoldirib', 'Faqat nom berib', 'Kichik vazifalarni kuzatish va bajarish oson.'),
('Muvaffaqiyat mezoni nima?', 'Natijani baholaydigan aniq shart', 'Tasodifiy bezak', 'Faqat fayl nomi', 'Mezon maqsad bajarilganini tekshiradi.'),
('Jamoada mas’ullar nima uchun belgilanadi?', 'Har kim vazifasini bilishi uchun', 'Hamma bir ishni bilmay takrorlashi uchun', 'Ishlarni yashirish uchun', 'Mas’uliyatlar kelishilgan ishni osonlashtiradi.')],
23: [
('Loyihaning dastlabki ishlaydigan versiyasi nima uchun kerak?', 'Asosiy g‘oyani erta sinash uchun', 'Hamma xatoni yashirish uchun', 'Ishni o‘chirish uchun', 'Kichik ishlaydigan versiya muammoni erta ko‘rsatadi.'),
('Sinovda topilgan xatolar qanday yuritiladi?', 'Ro‘yxat qilib ustuvorlik bilan tuzatiladi', 'Faqat eslab qolishga uriniladi', 'Hech qachon yozilmaydi', 'Ro‘yxat tekshiruv va tuzatishni kuzatishga yordam beradi.'),
('O‘zgarishdan keyin nima kerak?', 'Asosiy funksiyalarni qayta sinash', 'Oldingi sinovga ko‘r-ko‘rona ishonish', 'Faylni yashirish', 'Yangi o‘zgarish boshqa qismga ta’sir qilishi mumkin.'),
('Ishni yo‘qotmaslik uchun nima foydali?', 'Muntazam saqlash va zaxira nusxa', 'Faqat ochiq oynada qoldirish', 'Fayllarni tasodifan o‘chirish', 'Saqlash va zaxira nusxa mehnatni asraydi.')],
24: [
('Loyihani tanishtirishda avval nima aytiladi?', 'Muammo va loyiha maqsadi', 'Faqat fayl hajmi', 'Shaxsiy parollar', 'Tinglovchi loyiha nima uchun yaratilganini tushunsin.'),
('Namoyish uchun nima tayyorlash kerak?', 'Ishlaydigan versiya va qisqa reja', 'Faqat nom', 'Tekshirilmagan fayl', 'Oldindan sinov ishonchli namoyishga yordam beradi.'),
('Savolga javobni bilmasangiz nima qilasiz?', 'Bilmasligingizni aytib tekshirishni taklif qilasiz', 'Noto‘g‘ri ma’lumot to‘qiysiz', 'Savol berganni ayblaysiz', 'Halol javob va tekshirish ishonchni saqlaydi.'),
('Namoyishdan keyin nimani belgilash foydali?', 'Keyingi yaxshilash qadamlarini', 'Barcha ishni o‘chirishni', 'Fikrlarni yashirishni', 'Yakuniy mulohaza keyingi rivojlanishni rejalaydi.')],
}


def additions(number):
    return [{'q':q, 'options':[correct, wrong1, wrong2], 'answer':0, 'explain':explain}
            for q, correct, wrong1, wrong2, explain in CHECKS[number]]
