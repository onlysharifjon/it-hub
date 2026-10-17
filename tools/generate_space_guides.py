"""Build the versioned, offline-readable SPACE manuals served only to superadmin."""
from pathlib import Path
from html import escape
from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,PageBreak,KeepTogether,ListFlowable,ListItem
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import json
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'backend/minar/docs'
FONT=Path('/usr/share/fonts/truetype/dejavu')
pdfmetrics.registerFont(TTFont('Guide',str(FONT/'DejaVuSans.ttf')))
pdfmetrics.registerFont(TTFont('GuideBold',str(FONT/'DejaVuSans-Bold.ttf')))
pdfmetrics.registerFontFamily('Guide',normal='Guide',bold='GuideBold',italic='Guide',boldItalic='GuideBold')
styles=getSampleStyleSheet()
for name in ('BodyText','Normal','Title','Heading1','Heading2','Heading3'):
 styles[name].fontName='Guide';styles[name].leading=16;styles[name].textColor=colors.HexColor('#263348')
styles['BodyText'].fontSize=10;styles['BodyText'].spaceAfter=9
styles['Title'].fontName='GuideBold';styles['Title'].fontSize=27;styles['Title'].leading=36
styles['Heading1'].fontName='GuideBold';styles['Heading1'].fontSize=18;styles['Heading1'].leading=24;styles['Heading1'].spaceBefore=18;styles['Heading1'].spaceAfter=12
styles['Heading2'].fontName='GuideBold';styles['Heading2'].fontSize=13;styles['Heading2'].leading=18;styles['Heading2'].spaceBefore=12
DATE='18.10.2026'
GUIDE=[
('Kirish va bo‘limlar',[
('Superadmin yo‘li','CRM: https://crm.minaracademy.uz. Admin akkaunti bilan kiring → chap menyu → Tizim → Yo‘riqnomalar → kerakli hujjatda Yuklab olish. PDF internet bo‘lmasa ham o‘qiladi. HTML nusxani brauzerda ochish yoki chop etish mumkin. Faqat admin roli hujjatni yuklab oladi; havolani boshqa rolga berish ruxsat bermaydi.'),
('Yangi ish joylari','Ta’lim menyusidagi SPACE ta’lim bo‘limida dars materiallari, uy vazifalari, loyihalar va savollar boshqariladi. SPACE buyurtmalari bo‘limida sovg‘a buyurtmalari va ombor qoldig‘i yuritiladi. Minar Space bo‘limida akkaunt, QR, parol, kurs va ixtiyoriy yosh toifasi boshqariladi.'),
('Rollar','Admin: barcha SPACE boshqaruvi va yo‘riqnomalar. Support teacher: akkauntlar, kurslar, materiallar, o‘quv ishlarini tekshirish va buyurtmalar. Ustoz: o‘z guruhidagi uy vazifalari, loyihalar va o‘ziga biriktirilgan savollar. O‘quvchi: o‘z kabineti, fayllari, javoblari va loyihalari. Ota-ona: faqat o‘ziga bog‘langan farzand ma’lumotlari.')]),
('Birinchi sozlash',[
('Guruhlar','SPACE ta’lim → Guruhlar va nazorat. Har guruh uchun o‘yin/kodlash kursini tanlang. HTML, CSS va JavaScript o‘yin kurslaridir; CRMdagi Foundation dasturi bilan bog‘langan darslar alohida ko‘rinadi. O‘quvchi boshqa faol guruhga o‘tganda kurs yangilanadi; oldingi yechim va mukofot tarixi saqlanadi. Bir nechta guruhdagi o‘quvchi Bugungi o‘qish kartasida faol guruhni tanlaydi.'),
('Akkaunt va yosh toifasi','Minar Space jadvalida alohida o‘quvchining kursini o‘zgartirish mumkin. Ixtiyoriy yosh toifalari: 7–9, 10–12, 13–16 va 17+. Aniq tug‘ilgan sana talab qilinmaydi. Toifa berilmagan bo‘lsa, yosh bo‘yicha taqqoslash ko‘rinmaydi. Parol tiklanganda yoki akkaunt bloklanganda eski sessiyalar va QR tokenlari bekor qilinadi; yangi QR chiqaring.'),
('Haqiqiy ombor qoldig‘i','SPACE buyurtmalari → Ombordagi bo‘sh sovg‘alar. Buyurtmaga band qilinmagan real sonni kiriting. Yangilanish boshlanganda qoldiq 0: inventar soni taxmin qilinmagan. Qoldiq kiritilmaguncha haqiqiy sovg‘a xaridi yopiq. Eski pending/ready buyurtmalarini alohida sanab, ularga band sovg‘alarni bo‘sh qoldiqqa qo‘shmang.')]),
('Dars materiallarini nashr qilish',[
('Tayyor materiallar','48 ta boshlang‘ich modul tayyorlangan: Foundation bo‘yicha 24 ta o‘quvchi materiali va HTML/CSS/JavaScript bo‘yicha 24 ta kodlash moduli. Foundation mavzulari kompyuter, xavfsiz internet, Google vositalari, dizayn, Scratch va yakuniy loyihani qamrab oladi. Ustozning ichki metodika matni o‘quvchiga yuborilmaydi.'),
('Yaratish va tahrirlash','SPACE ta’lim → Dars materiallari → Yangi dars materiali yoki Tahrirlash. Nom, kurs, mavzu guruhi, tartib raqami va o‘quvchi matnini kiriting. Zarur bo‘lsa CRM darsini tanlang. Video hamda fayl havolalarini kiriting; havola o‘quvchilarga ochilishini tekshiring. Mustaqil mashqni yozing.'),
('Mini-test','Har material uchun 1–10 ta savol, har savol uchun 2–6 variant kiriting. To‘g‘ri javobni doira bilan belgilang; xatodan o‘rganish uchun izoh yozing. Nashr qilish belgisini yoqing va Saqlashni bosing. Belgi o‘chirilsa material qoralama bo‘lib qoladi. Mavjud ustoz qo‘llanmasi bundan o‘zgarmaydi.'),
('O‘quvchi qanday bajaradi','SPACE → Kurslarim → Darsni ochish. Materialni o‘qiydi, mustaqil mashqni bajaradi va mini-testni topshiradi. Kamida 80% natija mavzuni o‘zlashtirilgan deb belgilaydi. Birinchi muvaffaqiyat uchun 5 coin va 30 XP beriladi. Muddati kelgan takrorlash 1, 3, 7, 14 kunlik jadvalga ko‘ra taklif qilinadi; bir kunda bitta takrorlash mukofoti 2 coin. Bir xil so‘rov mukofotni qayta bermaydi.')]),
('Bugungi o‘qish va bilim xaritasi',[
('Bosh sahifa','Bugungi o‘qish kartasi navbatdagi dars vaqti, guruhi, ustozi va xonasini ko‘rsatadi. Bajarilmagan vazifalar soni barcha faol guruhlar bo‘yicha hisoblanadi. Oxirgi ustoz fikri hamda davom ettiriladigan mavzu bir joyda turadi. Jadval kiritilmagan bo‘lsa, bu ochiq yoziladi.'),
('Bilim xaritasi','SPACE → Bilim xaritasi. Mavzular bo‘yicha test natijalari, bajarilgan darslar, qayta ko‘rib chiqish kerak bo‘lgan savollar va takrorlash tugmasi mavjud. XP faollik ko‘rsatkichi, test natijasi esa shu mavzu bo‘yicha ko‘rsatkich: ular bir-birining o‘rnini bosmaydi.'),
('Kunlik vazifa','Dars topshirig‘i yangi dars, Kod maydonidagi yangi yechim yoki muddati kelgan takrorlash bilan bajariladi. Barcha mavjud material tugagandan keyin, takrorlash muddati kelmagan kunlarda ham tavsiya qilingan mavzuni 80% natija bilan qayta ishlash kunlik dars missiyasini bajaradi. Takrorlash coini kuniga bir marta, XP esa faqat birinchi o‘zlashtirishda beriladi. Kurs dasturining navbatdagi darsi hali kiritilmagan bo‘lsa, Dastur yakunlandi deb ko‘rsatilmaydi.')]),
('Uy vazifasi: o‘quvchi',[
('Qoralama','Uy vazifalarim → Bajarish kerak. Javob va ixtiyoriy havolani yozing. Qoralama shu akkaunt nomi bilan qurilmada va internet bo‘lsa serverda saqlanadi. Internet uzilsa matn yo‘qolmaydi; qayta ulanganda sinxronlanadi. Birgalikda ishlatiladigan qurilmada ish tugagach akkauntdan chiqing: chiqish mahalliy shaxsiy qoralamalarni tozalaydi.'),
('Fayl biriktirish','PDF, JPG yoki PNG fayl tanlang. Har fayl 5 MB gacha, bitta javobga 5 tagacha fayl; akkaunt uchun umumiy 100 MB limit bor. Fayllar umumiy ochiq manzil orqali tarqatilmaydi. Yuklash internet talab qiladi. Dastur kodi yoki loyiha uchun matn/havola maydonidan foydalaning.'),
('Yuborish va qaytarish','Ustozga yuborish tugmasini bosing va tasdiqni kuting. Tekshirilayotgan javobni yangilash mumkin. Ustoz tuzatishga qaytarsa izohni o‘qing, javobni to‘ldiring va Qayta topshirishni bosing. Baholangan ishni o‘zgartirib bo‘lmaydi; ustoz qaytarishi kerak. Javoblar va baholash tarixi ochiladigan panelda saqlanadi.'),
('Eski vazifalar','Holat filtri: bajarish kerak, tekshirilmoqda, baholangan, barchasi. Oldingi vazifalarni ko‘rsatish tugmasi keyingi sahifani ochadi. 30 tadan eski vazifa ham hisobdan tushib qolmaydi.')]),
('Uy vazifasi: ustoz va admin',[
('Tekshirish','CRM → SPACE ta’lim → Uy vazifalari. O‘quvchi javobi, havolasi, fayllari va barcha qayta topshirishlarni ko‘ring. Har mezonni 0–5 ball bilan belgilang: to‘g‘rilik, tushuntirish, mustaqillik. Jami natija avtomatik 100 ballga o‘tkaziladi.'),
('Fikr va rag‘bat','Aniq fikr yozing: nima to‘g‘ri, qaysi joyni qanday tuzatish kerak. 0–20 coin rag‘bat berish mumkin; mavjud ustoz budjeti va bir martalik mukofot qoidasi ishlaydi. Baholash javobni yakunlaydi. Tuzatishga qaytarish uchun sabab yozish shart. Qayta baholash allaqachon berilgan coinni takrorlamaydi.')]),
('Portfolio, sertifikat va yordam',[
('Portfolio','SPACE → Portfoliom. Loyiha nomi, tavsifi va havolasini kiriting → Ustozga yuborish. CRM → SPACE ta’lim → Loyihalar orqali ustoz Tasdiqlash yoki Tuzatish so‘rashni tanlaydi. Loyiha o‘zgartirilsa yana tekshirishga boradi.'),
('Umumiy havola','Faqat tasdiqlangan loyiha uchun o‘quvchi Umumiy havolani yoqish tugmasini bosishi mumkin. Havola o‘z-o‘zidan ochilmaydi. O‘quvchi uni yopishi mumkin; ustoz tasdiqni qaytarsa yoki loyiha tahrirlansa eski havola ham yopiladi. Ochiq sahifa o‘quvchining to‘liq ismi va aloqa ma’lumotlarini bermaydi. Loyiha tavsifi va tashqi loyiha ichida ham shaxsiy ma’lumot bo‘lmasin.'),
('Sertifikat','CRMda o‘quvchiga biriktirilgan mavjud sertifikatlar Portfoliom → Sertifikatlarim bo‘limida yuklab olinadi. Sertifikat yaratilmagan bo‘lsa bo‘lim bo‘sh holatni tushuntiradi.'),
('Ustozga savol','SPACE → Ustozdan yordam. Savol mavzusi, matni, ixtiyoriy vazifa raqami va skrinshotni yuboring. Savol faol guruh ustoziga biriktiriladi. CRM → SPACE ta’lim → Ustozga savollar orqali javob yoziladi. Holatlar: javob kutilmoqda, javob berildi, yopilgan. Keyingi savol shu suhbatda davom ettiriladi.')]),
('Coin, sovg‘a va adolatli motivatsiya',[
('Yagona balans','CRM, SPACE va ota-ona kabineti bir xil balansni ko‘rsatadi. Xarid va yechish bir xil talaba hisobini bazada qulflab bajariladi. Sarflangan coinni bekor qilish balansni manfiy qilib yuborishi mumkin bo‘lsa amal rad etiladi. Coin yozuvini bekor qilish eski yozuvni o‘chirmaydi: tarixga qarama-qarshi yozuv qo‘shiladi.'),
('Buyurtma oqimi','O‘quvchi Minar shopdan omborda bor sovg‘ani tanlaydi va tasdiqlaydi. Qoldiq birga kamayadi, coin yechiladi, buyurtma Yangi holatida turadi. CRM → SPACE buyurtmalari: Yangi → Tayyor → Topshirildi. Tayyor bo‘lganda o‘quvchiga ilova ichida bildirishnoma keladi. Buyurtma raqami va o‘quvchini tekshirib sovg‘ani topshiring.'),
('Bekor qilish','Yangi yoki Tayyor buyurtmani bekor qilish mumkin. Coin bir marta qaytariladi va bo‘sh ombor qoldig‘i tiklanadi. Topshirilgan buyurtmani bu tugma bilan qaytarib bo‘lmaydi. Bir xil xaridni tarmoq xatosidan keyin qayta yuborish ikkinchi buyurtma yaratmaydi.'),
('Mukofotlar','Har o‘yin turida kuniga 3 ta coin mukofoti va 10 ta XP beriladigan urinish chegarasi bor. Robo bilan mashq coin/XP bermaydi. Haqiqiy Battle serverdagi yakunlangan o‘yin bilan tekshiriladi; bitta bellashuv qayta mukofotlanmaydi. ZType urilgan so‘zlarni serverga yuboradi. Kod maydoni javobi haqiqiy server bajarish natijasi bilan tekshiriladi.'),
('Turnir','Guruh turniri haftalik mukofotining qoidasi saqlanadi: kamida 50 ochko; 1–3-o‘rinlarga 50/30/20 coin. Teng ochkoda akkauntning barqaror tartibi ishlatiladi; ekran va sovrin bir xil hisoblaydi. Yosh va daraja bo‘yicha qo‘shimcha taqqoslashlar alohida sovrin bermaydi. Test akkauntlari reytingdan chiqarilgan. Guruhlar va nazoratda haddan tashqari ko‘p o‘yin urinishlari ko‘rsatiladi.')]),
('Tarix, davomat va ota-ona',[
('To‘liq tarix','Coin tarixi oy filtri va sahifalash bilan barcha operatsiyalarni qamrab oladi. Oylik kirim/chiqim faqat yuklangan qatorlar emas, butun bazadan hisoblanadi. O‘yin natijalarini ham oy bo‘yicha ko‘rish mumkin. Davomatda bir kunda ikki guruh bo‘lsa, ikkala dars alohida qayd etiladi.'),
('Ota-ona','Mavjud ota-ona kabinetining coin bo‘limi SPACE xaridi va mukofotlarini ham hisobga oladi. Haftalik hisobotga yangi o‘zlashtirilgan mavzular hamda hozirgi balans qo‘shilgan. API orqali bilim xaritasi va bajarilmagan vazifalar soni ham mavjud. Ota-ona mobil ilovasining yangi ekranlarini chiqarish alohida mobil reliz talab qiladi; bu server yangilanishida mavjud ekranlarning hisoblari tuzatilgan.')]),
('Yordamchi, monitoring va nosozliklar',[
('Yordamchi rejimi','AI API kaliti bo‘lmasa yoki provayder vaqtida javob bermasa, tayyor o‘quv javobi qaytariladi va javobda bu yoziladi. Serverda hozir kalit sozlanmagan. Shaxsiy ma’lumot aniqlangan xabarlar suhbat tarixining barcha qismlarida tashqi modelga yuborilishidan oldin yashiriladi. Kalitni chatga yubormang; serverning maxfiy sozlamasida saqlang.'),
('Monitoring','Yo‘riqnomalar sahifasidagi Tizim holati ma’lumotlar bazasi, Redis, xizmatlar, disk va oxirgi zaxira nusxa holatini ko‘rsatadi. Eski monitoring ma’lumoti alohida belgilanadi. HTTP 404 yoki 401 sog‘lom xizmat deb olinmaydi. Telegram manzili hozir sozlanmagan: ogohlantirishlar admin paneli va server jurnalida mavjud.'),
('Sessiya tugasa','Ilova kirish ekraniga qaytaradi. O‘sha akkauntga qayta kirib qoralamani oching. Boshqa akkauntning qoralamasi ko‘rinmaydi. Akkaunt bloklangan yoki CRM talabasi faol bo‘lmasa support teacher bilan tekshiring.'),
('Xarid javobi kelmasa','Sahifani ochib buyurtmalar holatini ko‘ring yoki shu xaridni qayta yuboring. Ilova bir xil niyat identifikatorini saqlab turadi. Yangi tasdiqlangan xarid muvaffaqiyatli tugagach keyingi xarid uchun yangi identifikator ishlatiladi.'),
('Kod vaqt limiti','Cheksiz sikl yoki juda katta xotira talab qiladigan kod to‘xtatiladi. JavaScript serverdagi cheklangan jarayonda bajariladi; tarmoq, fayl va operatsion tizim APIlariga kira olmaydi. HTML ko‘rinishida skriptlar ishlamaydi. JavaScript uchun konsol natijasi alohida ko‘rsatiladi.'),
('Yangilash va qaytish','Texnik administrator har relizdan oldin PostgreSQL va fayllar zaxirasini oladi. Ushbu reliz ma’lumotni saqlovchi qo‘shimcha migratsiyadir. Zarur bo‘lsa oldingi ilova image’lariga qaytiladi; o‘quvchi ishlari bor yangi jadvallar o‘chirilmaydi. Ishlab turgan Battle tugamasdan SPACE API qayta ishga tushirilmaydi.')])]
FIXES=[
('A01','Yagona coin hisobi','Umumiy balans, ko‘p jarayonli tranzaksiya qulfi, o‘chirish o‘rniga qaytaruvchi yozuv; ota-ona va CRM moslashtirildi.'),
('A02–A03','Battle natijasi va takroriy mukofot','Faqat serverdagi ishtirokchi va tugagan match qabul qilinadi; match bo‘yicha bir martalik mukofot, mashqqa XP yo‘q.'),
('A04','ZType natijasi','Har so‘z serverga yuboriladi; so‘z, paydo bo‘lish vaqti va yozish tezligi tekshiriladi; soxta indekslar rad etiladi.'),
('A05','JavaScript tekshirish','Mijoz yuborgan konsol matni mukofot uchun ishlatilmaydi. QuickJS-NG cheklangan alohida jarayonda kodni bajaradi; qo‘shimcha semantik tekshiruvlar bor.'),
('A06','QR tokenlar','Parol tiklash, almashtirish va bloklash eski QR tokenlarini ham bekor qiladi.'),
('A07','Eski uy vazifalari','To‘liq pending hisob, status filtri va sahifalash.'),
('A08','Davomat','Bir kundagi turli guruh darslari alohida ko‘rsatiladi.'),
('A09','Teng ochkoli turnir','Ekran reytingi va mukofot bir xil barqaror tartibdan foydalanadi.'),
('A10','AI maxfiyligi','Suhbat tarixidagi barcha xabarlar shaxsiy ma’lumot bo‘yicha tozalanadi; xatolar jurnaliga matn yoki kalit yozilmaydi.'),
('A11','Test akkauntlari','Umumiy reyting va turnirda is_test akkauntlar qatnashmaydi.'),
('A12','Dastur holati','Yuklash xatosi qayta urinish bilan ko‘rsatiladi; kiritilmagan dars yakunlangan deb aytilmaydi.'),
('A13','Bildirishnomalar','Faqat ko‘rsatilgan IDlar o‘qilgan bo‘ladi; qolganlar sahifalab ochiladi.'),
('A14','Haqiqiy o‘rin','Server rank va total qaytaradi; 50-o‘rindan past shaxsiy o‘rin saqlanadi; dashboard shu rankni ishlatadi.'),
('C01–C02','Buyurtma va ombor','CRM ish jarayoni, qoldiq band qilish, nazoratli o‘tishlar, qaytarim va audit; xarid niyati tarmoq qayta urinishida saqlanadi.'),
('C03','Kurslar integratsiyasi','Guruh-kurs xaritasi, faol guruh tanlash va akkaunt kursini boshqarish; avvalgi tarix saqlanadi.'),
('C04','Yangilanish va sessiya','Fokus, internet qaytishi va 30 soniyalik yangilash; 401 da login, akkauntga ajratilgan qoralama.'),
('C05','AI rejimi','Aniq AI/tayyor javob rejimi, 10 soniyalik provayder limiti, xavfsiz xato va kechikish jurnali. Ishlaydigan tashqi AI uchun kalit kerak.'),
('C06–C07','Qoralama va brauzer xavfsizligi','Akkaunt bo‘yicha kod qoralamasi; chiqishda tozalash; HTML skriptsiz, JS esa vaqt/xotira/tarmoq/fayl cheklovi ostida serverda bajariladi.'),
('C08','Kontent va takrorlash','48 boshlang‘ich material, CMS, mini-test, bilim xaritasi va 1/3/7/14 kunlik takrorlash.'),
('C09','Tarix chegaralari','Coin, o‘yin va davomat tarixiga sahifalash va oy filtri; yig‘indilar serverdagi to‘liq davr bo‘yicha.'),
('C10','Monitoring','Liveness va DB/Redis readiness ajratildi; kutilgan HTTP 200 va JSON tekshiriladi; superadmin status hisoboti.'),
('C11','Yuklama','Umumiy Python qulfi olib tashlanib talaba/akkaunt bazaviy qulfi qo‘yildi. Bootstrap cheklangan ro‘yxatlar qaytaradi; yutuq ko‘rsatkichlari jamlangan so‘rovda hisoblanadi.'),
('C12','Battle quiz','Savollar va javob variantlari har match uchun serverda tanlanadi; to‘g‘ri javob frontend boshlang‘ich ma’lumotida yo‘q.')]

def paragraph(txt,style='BodyText'):
 return Paragraph(escape(txt).replace('\n','<br/>'),styles[style])
def page(canvas,doc):
 canvas.setStrokeColor(colors.HexColor('#dfe3ec'));canvas.line(42,43,A4[0]-42,43)
 canvas.setFont('Guide',8);canvas.setFillColor(colors.HexColor('#677187'))
 canvas.drawString(42,30,'MINAR ACADEMY · SPACE · '+DATE);canvas.drawRightString(A4[0]-42,30,str(doc.page))
def pdf(path,title,subtitle,sections):
 story=[Spacer(1,58),paragraph('MINAR ACADEMY','Heading2'),paragraph(title,'Title'),Spacer(1,15),paragraph(subtitle),paragraph('Versiya: '+DATE),Spacer(1,20)]
 story.append(paragraph('Superadmin → CRM → Tizim → Yo‘riqnomalar','Heading2'))
 story.append(PageBreak())
 for heading,blocks in sections:
  story.append(paragraph(heading,'Heading1'))
  for name,body in blocks:
   story.extend([paragraph(name,'Heading2'),paragraph(body)])
 doc=SimpleDocTemplate(str(path),pagesize=A4,rightMargin=44,leftMargin=44,topMargin=44,bottomMargin=57,title=title,author='Minar Academy')
 doc.build(story,onFirstPage=page,onLaterPages=page)

def main():
 OUT.mkdir(exist_ok=True)
 subtitle='Admin, ustoz va o‘quvchi uchun amaliy foydalanish yo‘riqnomasi.'
 pdf(OUT/'space-guide.pdf','SPACE foydalanish yo‘riqnomasi',subtitle,GUIDE)
 html='<!doctype html><html lang="uz"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>SPACE yo‘riqnomasi</title><style>body{max-width:920px;margin:40px auto;padding:20px;font:16px/1.75 system-ui;color:#263348}h1,h2,h3{line-height:1.3}h1{font-size:36px}h2{color:#6553bb;border-top:1px solid #ddd;padding-top:28px;margin-top:40px}nav{background:#f5f3ff;padding:20px;border-radius:15px}a{color:#5546aa}@media print{nav{break-after:page}h2,h3{break-after:avoid}body{font-size:11pt;margin:0}}</style><h1>SPACE foydalanish yo‘riqnomasi</h1><p>'+escape(subtitle)+' · '+DATE+'</p><nav><strong>Mundarija</strong><ol>'
 html+=''.join(f'<li><a href="#s{i}">{escape(h)}</a></li>' for i,(h,_) in enumerate(GUIDE))+'</ol></nav>'
 for i,(h,blocks) in enumerate(GUIDE):
  html+=f'<section id="s{i}"><h2>{escape(h)}</h2>'+''.join(f'<h3>{escape(n)}</h3><p>{escape(b)}</p>' for n,b in blocks)+'</section>'
 (OUT/'space-guide.html').write_text(html+'</html>')
 verification=ROOT/'backend/minar/docs/verification.json'
 checks=json.loads(verification.read_text()) if verification.exists() else {'Holat':'Reliz sinovlari yakunlangach yangilanadi.'}
 sections=[('Audit tuzatishlari',[(f'{code} · {title}',body) for code,title,body in FIXES]),
 ('Yangi imkoniyatlar',[(h,'; '.join(n for n,_ in blocks)) for h,blocks in GUIDE[2:9]]),
 ('Tekshirish natijalari',list(checks.items())),
 ('Zaxiradan tiklashda qo‘shimcha tuzatish',[('Tarixiy xodim bog‘lanishlari','Tiklash sinovida oldin o‘chirilgan 3 ta xodim identifikatoriga bog‘langan 29 ta audit va 2 ta ogohlantirish yozuvi aniqlandi. Tarix o‘chirilmadi. Ushbu identifikatorlar uchun Arxiv yozuvi nomli, shaxsiy ma’lumotsiz, faol bo‘lmagan akkauntlar qo‘shildi. Asl shaxs va roli noma’lum; ularni faollashtirmang. Login paroli tasodifiy va hech kimga berilmagan; ish haqi hisoblanmaydi.')]),
 ('Operator kiritadigan ma’lumotlar',[('Ombor','Haqiqiy qoldiq admin tomonidan sanab kiritiladi; boshlang‘ich qiymat 0.'),('AI va Telegram','AI kaliti va Telegram kanal sozlamasi mavjud emas. Tayyor yordamchi hamda superadmin ichidagi monitoring ishlaydi. Maxfiy kalitlar hujjatda saqlanmaydi.'),('Kontent va mobil ilova','Materiallarni ustoz o‘quv dasturiga moslab nashr qiladi. Ota-ona API/hisoblari yangilandi; yangi mobil ekranlarni ilova do‘koniga chiqarish ushbu server relizining qismi emas.')])]
 pdf(OUT/'space-changes.pdf','SPACE audit: bajarilgan ishlar','Aniqlangan 26 band bo‘yicha o‘zgarishlar, yangi imkoniyatlar va tekshirish dalillari.',sections)
 print('Generated:', ', '.join(p.name for p in OUT.glob('*') if p.suffix in ('.pdf','.html')))
if __name__=='__main__':main()
