"""Server-owned vocabulary and geography questions; answers never enter client bundles."""
DRAW_WORDS = (
    'raketa', 'sayyora', 'quyosh', 'oy', 'yulduz', 'kitob', 'qalam', 'daraxt',
    'kapalak', 'mushuk', 'baliq', 'qush', 'velosiped', 'samolyot', 'kema', 'uy',
    'ko‘prik', 'soat', 'ko‘zoynak', 'soyabon', 'poyezd', 'toj', 'kalit', 'robot',
    'gitara', 'baraban', 'tog‘', 'vulqon', 'kamalak', 'bulut', 'qor', 'olma',
    'gul', 'delfin', 'sher', 'fil', 'toshbaqa', 'kompyuter', 'telefon', 'qal’a',
    'chiroq', 'yurak', 'narvon', 'qayiq', 'pingvin', 'quyon', 'ari', 'muzqaymoq',
    'shaxmat', 'koptok', 'raketka', 'sumka', 'stul', 'eshik', 'oyna', 'chashka',
)
CODE_WORDS = (
    'OY', 'YULDUZ', 'RAKETA', 'KO‘PRIK', 'KITOB', 'KALIT', 'TOJ', 'DARAXT',
    'OLMA', 'QALAM', 'TOG‘', 'DENGIZ', 'QUM', 'MUZ', 'SHAMOL', 'OLOV', 'SOAT',
    'QUSH', 'BULUT', 'KEMA', 'QAL’A', 'OT', 'ARI', 'GUL', 'CHIROQ', 'KO‘Z',
    'YO‘L', 'OYNA', 'QO‘NG‘IROQ', 'BOG‘', 'SANDIQ', 'TANGA', 'QALQON', 'IP',
    'NON', 'TUZ', 'SUV', 'BO‘RI', 'SHER', 'BALIQ', 'TERAK', 'DAFTAR', 'XAT',
    'QANOT', 'KOPTOK', 'G‘OR', 'KAMALAK', 'QOR', 'DARYO', 'MARVARID', 'KUMUSH',
    'OLTIN', 'QUMSOAT', 'MINORA', 'XARITA', 'KOMPAS', 'OROL', 'QUYOSH', 'MAKTAB',
)
# (country Uzbek, ISO2, capital). Values are stable basic geographical facts.
COUNTRIES = (
    ('O‘zbekiston', 'UZ', 'Toshkent'), ('Yaponiya', 'JP', 'Tokio'),
    ('Fransiya', 'FR', 'Parij'), ('Braziliya', 'BR', 'Brazilia'),
    ('Kanada', 'CA', 'Ottava'), ('Avstraliya', 'AU', 'Kanberra'),
    ('Turkiya', 'TR', 'Anqara'), ('Italiya', 'IT', 'Rim'),
    ('Hindiston', 'IN', 'Nyu-Dehli'), ('Buyuk Britaniya', 'GB', 'London'),
    ('Misr', 'EG', 'Qohira'), ('Xitoy', 'CN', 'Pekin'),
    ('Janubiy Koreya', 'KR', 'Seul'), ('Germaniya', 'DE', 'Berlin'),
    ('AQSh', 'US', 'Vashington'),
)
LANDMARKS = (
    ('Eyfel minorasi qaysi mamlakatda?', 'eiffel', 'Fransiya', 'Eyfel minorasi Fransiyaning Parij shahrida joylashgan.'),
    ('Toj Mahal qaysi mamlakatda?', 'taj-mahal', 'Hindiston', 'Toj Mahal Hindistonning Agra shahrida joylashgan.'),
    ('Giza piramidalari qaysi mamlakatda?', 'pyramids', 'Misr', 'Giza piramidalari Misrda, Qohira yaqinida joylashgan.'),
    ('Kolizey qaysi mamlakatda?', 'colosseum', 'Italiya', 'Kolizey Italiya poytaxti Rimda joylashgan.'),
    ('Registon maydoni qaysi mamlakatda?', 'registan', 'O‘zbekiston', 'Registon O‘zbekistonning Samarqand shahrida joylashgan.'),
    ('Sidney opera teatri qaysi mamlakatda?', 'sydney', 'Avstraliya', 'Sidney opera teatri Avstraliyaning Sidney shahrida joylashgan.'),
)
# Simplified teaching silhouettes, normalized for an SVG viewBox. Not border maps.
SHAPES = (
    ('Italiya', [[.12,.08],[.32,.05],[.52,.13],[.50,.25],[.62,.40],[.69,.53],[.84,.61],[.90,.69],[.82,.73],[.77,.68],[.69,.68],[.77,.79],[.74,.90],[.66,.91],[.64,.77],[.55,.64],[.44,.54],[.35,.37],[.30,.26],[.18,.27],[.08,.19]]),
    ('Avstraliya', [[.08,.45],[.14,.31],[.29,.27],[.35,.13],[.46,.20],[.53,.12],[.60,.22],[.71,.18],[.75,.07],[.83,.25],[.91,.42],[.87,.59],[.79,.75],[.68,.86],[.56,.79],[.46,.75],[.34,.75],[.26,.68],[.12,.70],[.06,.57]]),
    ('Fransiya', [[.28,.10],[.53,.05],[.63,.21],[.80,.29],[.77,.44],[.88,.59],[.73,.77],[.65,.85],[.41,.79],[.31,.85],[.19,.62],[.17,.46],[.04,.38],[.07,.29],[.27,.28]]),
)
