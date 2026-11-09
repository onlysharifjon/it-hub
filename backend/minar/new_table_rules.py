"""Authoritative rules for eight multiplayer games, with explicit private views.

State is persisted in existing table rooms. No client supplies scores, random rolls,
answers, or winners. Every public projection is assembled from a whitelist.
"""
import copy
import math
import random
import re
import secrets
import unicodedata

from .errors import MinarError
from .new_table_content import DRAW_WORDS, CODE_WORDS, COUNTRIES, LANDMARKS, SHAPES

GAMES = {'draw': (3, 8), 'fleet': (2, 2), 'quest': (2, 4), 'domino': (2, 4),
         'connect4': (2, 2), 'ludo': (2, 4), 'codenames': (4, 8), 'geography': (2, 8)}
RNG = random.SystemRandom()
PALETTE = ('#17243b', '#e14b67', '#ed9c40', '#f5cf58', '#36ad8b', '#4394e7', '#9468d7', '#ffffff')
LUDO_SAFE = [0, 8, 13, 21, 26, 34, 39, 47]


def require(ok, message='Bu harakatni hozir bajarib bo‘lmaydi.'):
    if not ok:
        raise MinarError(400, message)


def integer(value, low, high):
    require(type(value) is int and low <= value <= high, 'Raqam belgilangan oraliqda bo‘lishi kerak.')
    return value


def text(value, limit=120):
    require(isinstance(value, str) and 0 < len(value) <= limit, 'Matn uzunligini tekshiring.')
    value = ''.join(c for c in value if not unicodedata.category(c).startswith('C')).strip()
    require(bool(value), 'Matn kiriting.')
    return value


def normalize(value):
    # Uzbek apostrophe variants are equivalent; punctuation and spacing are not clues.
    return ''.join(c for c in unicodedata.normalize('NFKC', value).casefold() if c.isalnum())


def finish(s, winners, reason='completed'):
    s.update(finished=True, winners=winners[:], reason=reason)


def phase_key(s):
    return f"{s['rulesVersion']}:{s['phaseSerial']}"


def transition(s, phase=None):
    s['phaseSerial'] += 1
    if phase is not None:
        s['phase'] = phase


def next_turn(s):
    s['turn'] = (s['turn'] + 1) % len(s['players'])
    transition(s)


def phase_actions(game, kind):
    return ((game == 'draw' and kind in ('stroke', 'clear', 'guess')) or
            (game == 'fleet' and kind == 'deploy') or
            (game == 'quest' and kind in ('toggle', 'rotate', 'code', 'chat')) or
            (game == 'codenames' and kind in ('clue', 'guess', 'end')) or
            (game == 'geography' and kind == 'answer'))


def phase_seconds(game, s):
    if game == 'draw':
        return 75 if s['phase'] == 'drawing' else 8
    if game == 'fleet':
        return 180 if s['phase'] == 'placement' else 60
    if game == 'quest':
        return 180
    if game == 'codenames':
        return 75 if s['phase'] == 'clue' else 60
    if game == 'geography':
        return 25 if s['phase'] == 'question' else 6
    return 60


def scored_finish(s):
    top = max(s['scores'].values(), default=0)
    finish(s, [p for p in s['players'] if top > 0 and s['scores'][p] == top], 'completed' if top > 0 else 'draw')


def draw_round(s):
    s['drawer'] = s['players'][s['round'] - 1]
    s['turn'] = s['round'] - 1
    s['word'] = s['words'][s['round'] - 1]
    s.update(strokes=[], guessed=[], messages=[])
    transition(s, 'drawing')


def geo_round(s):
    s.update(answers={}, question=copy.deepcopy(s['questions'][s['round'] - 1]))
    transition(s, 'question')


def geo_reveal(s):
    for p, choice in s['answers'].items():
        if choice == s['question']['answer']:
            s['scores'][p] += 100
    transition(s, 'reveal')


def geography_questions():
    countries = [c[0] for c in COUNTRIES]
    capitals = [c[2] for c in COUNTRIES]
    pool = []
    def add(kind, prompt, answer, choices, explanation, **visual):
        options = RNG.sample([c for c in choices if c != answer], 3) + [answer]
        RNG.shuffle(options)
        pool.append({'kind': kind, 'prompt': prompt, 'options': options,
                     'answer': options.index(answer), 'explanation': explanation, **visual})
    for country, iso, capital in COUNTRIES:
        add('flag', 'Bu qaysi mamlakat bayrog‘i?', country, countries,
            f'Bu — {country} bayrog‘i. Poytaxti: {capital}.', flag=iso)
        add('capital', f'{country} poytaxtini toping.', capital, capitals,
            f'{country} poytaxti — {capital}.')
    for prompt, landmark, answer, explanation in LANDMARKS:
        add('landmark', prompt, answer, countries, explanation, landmark=landmark)
    for country, shape in SHAPES:
        add('shape', 'Soddalashtirilgan shakl qaysi mamlakatga tegishli?', country,
            countries, f'Bu {country}ning soddalashtirilgan geografik shakli.', map=shape)
    # Every match includes all four kinds, with no repeated question.
    chosen = [RNG.choice([q for q in pool if q['kind'] == kind]) for kind in ('flag', 'capital', 'landmark', 'shape')]
    chosen += RNG.sample([q for q in pool if q not in chosen], 4)
    RNG.shuffle(chosen)
    return chosen


def lights_toggle(cells, cell):
    row, col = divmod(cell, 3)
    for r, c in ((row, col), (row-1, col), (row+1, col), (row, col-1), (row, col+1)):
        if 0 <= r < 3 and 0 <= c < 3:
            cells[r*3+c] = not cells[r*3+c]


def quest_stage(s):
    s['world'] = ('verdora', 'glacia', 'pyron')[s['stage'] // 2]
    kind = ('lights', 'rotors', 'vault')[s['stage'] % 3]
    if kind == 'lights':
        cells = [False]*9
        for cell in RNG.sample(range(9), 4 + s['stage']//3):
            lights_toggle(cells, cell)
        if not any(cells):
            lights_toggle(cells, 4)
        puzzle = {'kind': kind, 'cells': cells, 'title': 'Energiya tugunlari',
                  'instruction': 'Tugunga tegish uning o‘zi va yonidagi tugunlarni almashtiradi. Barcha chiroqlarni o‘chiring.'}
    elif kind == 'rotors':
        target = [RNG.randrange(4) for _ in range(3)]
        values = [(n + RNG.choice((1, 2, 3))) % 4 for n in target]
        puzzle = {'kind': kind, 'values': values, 'target': target,
                  'title': 'Quvvat kanallari', 'instruction': 'Uch halqani aylantirib, ko‘rsatilgan quvvat yo‘nalishlariga moslang.'}
    else:
        code = ''.join(str(RNG.randrange(10)) for _ in range(3))
        clues = {}
        for i, pid in enumerate(s['players']):
            positions = [n for n in range(3) if n % len(s['players']) == i]
            if not positions:
                positions = [i % 3]
            clues[pid] = ' · '.join(f'{n+1}-raqam: {code[n]}' for n in positions)
        puzzle = {'kind': kind, 'length': 3, 'code': code, 'clues': clues,
                  'title': 'Sirli darvoza', 'instruction': 'Har biringizda kodning bir qismi bor. Xabarlarda maslahatlashib, uch raqamni to‘g‘ri kiriting.'}
    s['puzzle'] = puzzle
    s['stageActions'] = 0
    s['events'] = (s['events'] + [f'{s["stage"]+1}-bekat: {puzzle["title"]}'])[-16:]
    transition(s, 'puzzle')


def quest_complete(s):
    s['events'] = (s['events'] + ['Bekat muvaffaqiyatli tiklandi!'])[-16:]
    s['stage'] += 1
    if s['stage'] == s['totalStages']:
        finish(s, s['players'])
    else:
        quest_stage(s)


def new_game(game, ids):
    require(game in GAMES and GAMES[game][0] <= len(ids) <= GAMES[game][1] and len(set(ids)) == len(ids))
    s = {'players': ids[:], 'turn': 0, 'plies': 0, 'finished': False, 'winners': [], 'log': [],
         'rulesVersion': 'space-eight-v1', 'phaseSerial': 0, 'phase': 'playing'}
    if game == 'draw':
        s.update(round=1, totalRounds=len(ids), scores={p: 0 for p in ids}, words=RNG.sample(DRAW_WORDS, len(ids)))
        draw_round(s)
    elif game == 'fleet':
        s.update(phase='placement', size=8, shipLengths=[4, 3, 2], fleets={}, fired={p: [] for p in ids}, lastShot=None)
    elif game == 'quest':
        s.update(stage=0, totalStages=6, energy=12, contributors=[], messages=[], events=[])
        quest_stage(s)
    elif game == 'domino':
        deck = [{'id': f'{a}-{b}', 'a': a, 'b': b} for a in range(7) for b in range(a, 7)]
        RNG.shuffle(deck)
        s.update(hands={p: [deck.pop() for _ in range(7)] for p in ids}, deck=deck, chain=[], passes=0, lastMove=None)
    elif game == 'connect4':
        s.update(board=[0]*42, winningCells=[], lastMove=None)
    elif game == 'ludo':
        s.update(tokens={p: [-1]*4 for p in ids}, rolled=None, sixes=0, safe=LUDO_SAFE[:],
                 starts={p: i*13 for i, p in enumerate(ids)}, colors=dict(zip(ids, ('red', 'green', 'yellow', 'blue'))), lastMove=None)
    elif game == 'codenames':
        keys = [0]*9 + [1]*8 + ['neutral']*7 + ['trap']
        RNG.shuffle(keys)
        s.update(teams={p: i % 2 for i, p in enumerate(ids)}, captains=[ids[0], ids[1]], teamTurn=0,
                 phase='clue', words=RNG.sample(CODE_WORDS, 25), keys=keys, revealed=[False]*25,
                 clue=None, guessesLeft=0, history=[], idlePhases=0)
    elif game == 'geography':
        s.update(round=1, totalRounds=8, scores={p: 0 for p in ids}, questions=geography_questions())
        geo_round(s)
    return s


def domino_legal(s, pid):
    if s['finished'] or s['players'][s['turn']] != pid:
        return []
    legal = []
    for tile in s['hands'][pid]:
        if not s['chain']:
            legal.append({'id': tile['id'], 'side': 'right'})
        else:
            if s['chain'][0]['a'] in (tile['a'], tile['b']):
                legal.append({'id': tile['id'], 'side': 'left'})
            if s['chain'][-1]['b'] in (tile['a'], tile['b']):
                legal.append({'id': tile['id'], 'side': 'right'})
    return legal


def ludo_legal(s, pid):
    if s['finished'] or s['players'][s['turn']] != pid or s['rolled'] is None:
        return []
    return [i for i, n in enumerate(s['tokens'][pid]) if (n == -1 and s['rolled'] == 6) or (0 <= n < 57 and n + s['rolled'] <= 57)]


def code_remaining(s):
    return [sum(not seen and key == team for key, seen in zip(s['keys'], s['revealed'])) for team in (0, 1)]


def code_next(s):
    s['teamTurn'] = 1 - s['teamTurn']
    s['turn'] = s['players'].index(s['captains'][s['teamTurn']])
    s.update(clue=None, guessesLeft=0)
    transition(s, 'clue')


def code_finish(s, team):
    s['winningTeam'] = team
    finish(s, [p for p in s['players'] if s['teams'][p] == team])


def advance(game, s):
    """Called only after the server-owned deadline; clients cannot fast-forward."""
    if s['finished']:
        return
    if game == 'draw':
        if s['phase'] == 'drawing':
            transition(s, 'reveal')
        elif s['round'] == s['totalRounds']:
            scored_finish(s)
        else:
            s['round'] += 1
            draw_round(s)
    elif game == 'geography':
        if s['phase'] == 'question':
            geo_reveal(s)
        elif s['round'] == s['totalRounds']:
            scored_finish(s)
        else:
            s['round'] += 1
            geo_round(s)
    elif game == 'codenames':
        s['idlePhases'] += 1
        if s['idlePhases'] >= 6:
            finish(s, [], 'timeout')
        else:
            code_next(s)
    else:
        finish(s, [], 'timeout')


def move(game, s, pid, action):
    require(pid in s['players'] and not s['finished'], 'O‘yin yakunlangan yoki siz xona ishtirokchisi emassiz.')
    kind = action.get('type')
    if game == 'draw':
        _draw(s, pid, kind, action)
    elif game == 'fleet':
        _fleet(s, pid, kind, action)
    elif game == 'quest':
        _quest(s, pid, kind, action)
    elif game == 'codenames':
        _codenames(s, pid, kind, action)
    elif game == 'geography':
        require(kind == 'answer' and s['phase'] == 'question' and pid not in s['answers'], 'Javob allaqachon berilgan yoki vaqt tugagan.')
        s['answers'][pid] = integer(action.get('choice'), 0, len(s['question']['options'])-1)
        if len(s['answers']) == len(s['players']):
            geo_reveal(s)
    else:
        require(s['players'][s['turn']] == pid, 'Hozir raqibning navbati.')
        if game == 'domino':
            _domino(s, pid, kind, action)
        elif game == 'connect4':
            _connect4(s, pid, kind, action)
        elif game == 'ludo':
            _ludo(s, pid, kind, action)
        else:
            require(False)
    s['plies'] += 1


def _draw(s, pid, kind, action):
    require(s['phase'] == 'drawing', 'Yangi davr boshlanishini kuting.')
    if kind in ('stroke', 'clear'):
        require(pid == s['drawer'], 'Faqat rassom chizishi mumkin.')
        if kind == 'clear':
            s['strokes'] = []
            return
        require(len(s['strokes']) < 220, 'Chiziqlar limiti to‘ldi. Doskani tozalab davom eting.')
        points, color = action.get('points'), action.get('color')
        require(isinstance(color, str) and color.lower() in PALETTE, 'Palitradagi rangni tanlang.')
        width = integer(action.get('width'), 2, 18)
        require(isinstance(points, list) and 1 <= len(points) <= 120, 'Chiziq nuqtalari noto‘g‘ri.')
        clean = []
        for point in points:
            require(isinstance(point, list) and len(point) == 2)
            require(all(type(n) in (int, float) and math.isfinite(n) and 0 <= n <= 1 for n in point))
            clean.append([round(n, 4) for n in point])
        s['strokes'].append({'id': secrets.token_hex(6), 'color': color.lower(), 'width': width, 'points': clean})
    elif kind == 'guess':
        require(pid != s['drawer'] and pid not in s['guessed'], 'Hozir so‘zni topish navbati sizda emas.')
        guess = text(action.get('text'), 50)
        correct = normalize(guess) == normalize(s['word'])
        if correct:
            s['guessed'].append(pid)
            s['scores'][pid] += 100
            s['scores'][s['drawer']] += 30
        s['messages'] = (s['messages'] + [{'player': pid, 'text': 'So‘zni topdi!' if correct else guess, 'correct': correct}])[-32:]
        if len(s['guessed']) == len(s['players']) - 1:
            transition(s, 'reveal')
    else:
        require(False)


def _fleet(s, pid, kind, action):
    if kind == 'deploy':
        require(s['phase'] == 'placement' and pid not in s['fleets'], 'Flot allaqachon joylashtirilgan.')
        ships = action.get('ships')
        require(isinstance(ships, list) and len(ships) == len(s['shipLengths']))
        clean, occupied = [], set()
        for ship, length in zip(ships, s['shipLengths']):
            require(isinstance(ship, list) and len(ship) == length)
            cells = sorted(integer(cell, 0, 63) for cell in ship)
            require(len(set(cells)) == length and not occupied.intersection(cells), 'Kemalar ustma-ust tushmasin.')
            horizontal = len({c//8 for c in cells}) == 1 and all(b-a == 1 for a, b in zip(cells, cells[1:]))
            vertical = len({c % 8 for c in cells}) == 1 and all(b-a == 8 for a, b in zip(cells, cells[1:]))
            require(horizontal or vertical, 'Kema bitta tekis qatorda bo‘lishi kerak.')
            clean.append(cells)
            occupied.update(cells)
        s['fleets'][pid] = clean
        if len(s['fleets']) == 2:
            transition(s, 'battle')
    elif kind == 'fire':
        require(s['phase'] == 'battle' and s['players'][s['turn']] == pid, 'Hozir raqibning navbati.')
        cell = integer(action.get('cell'), 0, 63)
        require(cell not in s['fired'][pid], 'Bu katak tekshirilgan.')
        opponent = next(p for p in s['players'] if p != pid)
        targets = {c for ship in s['fleets'][opponent] for c in ship}
        s['fired'][pid].append(cell)
        s['lastShot'] = {'player': pid, 'cell': cell, 'hit': cell in targets}
        if targets.issubset(s['fired'][pid]):
            finish(s, [pid])
        else:
            next_turn(s)
    else:
        require(False)


def _quest(s, pid, kind, action):
    if kind == 'chat':
        s['messages'] = (s['messages'] + [{'player': pid, 'text': text(action.get('text'), 180)}])[-40:]
        return
    p = s['puzzle']
    solved = False
    if kind == 'toggle' and p['kind'] == 'lights':
        lights_toggle(p['cells'], integer(action.get('cell'), 0, 8))
        solved = not any(p['cells'])
    elif kind == 'rotate' and p['kind'] == 'rotors':
        i = integer(action.get('index'), 0, 2)
        p['values'][i] = (p['values'][i] + 1) % 4
        solved = p['values'] == p['target']
    elif kind == 'code' and p['kind'] == 'vault':
        code = action.get('code')
        require(isinstance(code, str) and re.fullmatch(r'[0-9]{3}', code), 'Uchta raqam kiriting.')
        solved = code == p['code']
        if not solved:
            s['energy'] -= 1
            s['events'] = (s['events'] + ['Kod mos kelmadi. Jamoa maslahatlarini yana tekshiring.'])[-16:]
    else:
        require(False, 'Bu bekatda boshqa mexanizm ishlaydi.')
    s['stageActions'] += 1
    if pid not in s['contributors']:
        s['contributors'].append(pid)
    if s['energy'] <= 0:
        finish(s, [], 'energy')
    elif solved:
        quest_complete(s)
    # Prevent a single puzzle being spammed indefinitely while retaining solvability.
    elif s['stageActions'] >= 160:
        finish(s, [], 'energy')


def _domino(s, pid, kind, action):
    legal = domino_legal(s, pid)
    if kind == 'draw':
        require(not legal and bool(s['deck']), 'Yurish mavjud yoki zaxira tugagan.')
        s['hands'][pid].append(s['deck'].pop())
        s['passes'] = 0
        s['lastMove'] = {'player': pid, 'type': 'draw'}
        return
    if kind == 'pass':
        require(not legal and not s['deck'], 'Avval yurish yoki tosh olish kerak.')
        s['passes'] += 1
        s['lastMove'] = {'player': pid, 'type': 'pass'}
        if s['passes'] >= len(s['players']):
            pips = {p: sum(t['a']+t['b'] for t in hand) for p, hand in s['hands'].items()}
            winners = [p for p in s['players'] if pips[p] == min(pips.values())]
            finish(s, winners if len(winners) == 1 else [], 'completed' if len(winners) == 1 else 'draw')
            return
        next_turn(s)
        return
    require(kind == 'play')
    tile_id, side = action.get('tile'), action.get('side')
    require(any(m['id'] == tile_id and m['side'] == side for m in legal), 'Tosh ochiq uchga mos emas.')
    tile = next(t for t in s['hands'][pid] if t['id'] == tile_id)
    s['hands'][pid].remove(tile)
    tile = tile.copy()
    if s['chain']:
        if side == 'left' and tile['b'] != s['chain'][0]['a'] or side == 'right' and tile['a'] != s['chain'][-1]['b']:
            tile['a'], tile['b'] = tile['b'], tile['a']
    if side == 'left':
        s['chain'].insert(0, tile)
    else:
        s['chain'].append(tile)
    s['lastMove'] = {'player': pid, 'type': 'play', 'tile': tile, 'side': side}
    s['passes'] = 0
    if not s['hands'][pid]:
        finish(s, [pid])
    else:
        next_turn(s)


def _connect4(s, pid, kind, action):
    require(kind == 'drop')
    column = integer(action.get('column'), 0, 6)
    rows = [r for r in range(6) if s['board'][r*7+column] == 0]
    require(bool(rows), 'Bu ustun to‘lgan.')
    row = max(rows)
    value = s['turn']+1
    s['board'][row*7+column] = value
    s['lastMove'] = {'row': row, 'col': column, 'player': pid}
    for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
        line = [row*7+column]
        for direction in (-1, 1):
            r, c = row+dy*direction, column+dx*direction
            while 0 <= r < 6 and 0 <= c < 7 and s['board'][r*7+c] == value:
                line.append(r*7+c)
                r, c = r+dy*direction, c+dx*direction
        if len(line) >= 4:
            s['winningCells'] = sorted(line)
            finish(s, [pid])
            return
    if all(s['board']):
        finish(s, [], 'draw')
    else:
        next_turn(s)


def _ludo(s, pid, kind, action):
    if kind == 'roll':
        require(s['rolled'] is None, 'Avval tushgan raqam bilan yuring.')
        s['rolled'] = RNG.randint(1, 6)
        s['sixes'] = s['sixes']+1 if s['rolled'] == 6 else 0
        if s['sixes'] >= 3 or not ludo_legal(s, pid):
            s['lastRoll'] = {'player': pid, 'value': s['rolled'], 'forfeited': s['sixes'] >= 3, 'noMove': s['sixes'] < 3}
            s.update(rolled=None, sixes=0)
            next_turn(s)
        return
    require(kind == 'move')
    token = integer(action.get('token'), 0, 3)
    require(token in ludo_legal(s, pid), 'Bu dona bilan yurib bo‘lmaydi.')
    old = s['tokens'][pid][token]
    target = 0 if old == -1 else old+s['rolled']
    s['tokens'][pid][token] = target
    captures = []
    if target < 52:
        absolute = (s['starts'][pid]+target) % 52
        if absolute not in LUDO_SAFE:
            for other in s['players']:
                if other == pid:
                    continue
                for i, n in enumerate(s['tokens'][other]):
                    if 0 <= n < 52 and (s['starts'][other]+n) % 52 == absolute:
                        s['tokens'][other][i] = -1
                        captures.append({'player': other, 'token': i})
    s['lastMove'] = {'player': pid, 'token': token, 'from': old, 'to': target, 'captured': captures}
    s['lastRoll'] = {'player': pid, 'value': s['rolled'], 'forfeited': False, 'noMove': False}
    extra = s['rolled'] == 6
    s['rolled'] = None
    if all(n == 57 for n in s['tokens'][pid]):
        finish(s, [pid])
    elif not extra:
        s['sixes'] = 0
        next_turn(s)
    else:
        # Extra turns get a fresh clock; rolling without moving never does.
        transition(s)


def _codenames(s, pid, kind, action):
    team = s['teamTurn']
    require(s['teams'][pid] == team, 'Hozir boshqa jamoaning navbati.')
    if kind == 'clue':
        require(s['phase'] == 'clue' and pid == s['captains'][team], 'Ishorani jamoa sardori beradi.')
        clue = text(action.get('word'), 32)
        require(len(clue.split()) == 1 and any(c.isalpha() for c in clue), 'Bitta so‘zdan iborat ishora yozing.')
        require(normalize(clue) not in {normalize(w) for w in s['words']}, 'Doska so‘zini ishora sifatida ishlatmang.')
        count = integer(action.get('count'), 1, 9)
        s['clue'] = {'word': clue, 'count': count}
        s['guessesLeft'] = count + 1
        s['history'] = (s['history'] + [{'team': team, 'word': clue, 'count': count}])[-30:]
        s['idlePhases'] = 0
        transition(s, 'guess')
        return
    require(s['phase'] == 'guess' and pid != s['captains'][team], 'So‘zlarni jamoa izlovchilari tanlaydi.')
    if kind == 'end':
        code_next(s)
        return
    require(kind == 'guess')
    cell = integer(action.get('cell'), 0, 24)
    require(not s['revealed'][cell], 'Bu so‘z allaqachon ochilgan.')
    s['revealed'][cell] = True
    s['idlePhases'] = 0
    color = s['keys'][cell]
    if color == 'trap':
        code_finish(s, 1-team)
        return
    remaining = code_remaining(s)
    for winner in (0, 1):
        if remaining[winner] == 0:
            code_finish(s, winner)
            return
    s['guessesLeft'] -= 1
    if color != team or s['guessesLeft'] <= 0:
        code_next(s)


def view(game, s, pid):
    require(pid in s['players'])
    out = {k: copy.deepcopy(s.get(k)) for k in ('players', 'turn', 'plies', 'finished', 'winners', 'reason', 'log', 'phase')}
    out.update(phaseKey=phase_key(s), phaseSeconds=0 if s['finished'] else phase_seconds(game, s), rulesVersion=s['rulesVersion'])
    if game == 'draw':
        for k in ('round', 'totalRounds', 'drawer', 'scores', 'strokes', 'guessed', 'messages'):
            out[k] = copy.deepcopy(s[k])
        out.update(wordLength=len(s['word']), word=s['word'] if pid == s['drawer'] or s['phase'] == 'reveal' or s['finished'] else None)
    elif game == 'fleet':
        other = next(p for p in s['players'] if p != pid)
        ships = s['fleets'].get(pid, [])
        enemy = s['fleets'].get(other, [])
        mine = {c for ship in ships for c in ship}
        targets = {c for ship in enemy for c in ship}
        shots, incoming = s['fired'][pid], s['fired'][other]
        out.update(size=8, shipLengths=[4, 3, 2], ships=copy.deepcopy(ships), deployed=list(s['fleets']),
                   shots=shots[:], incoming=incoming[:], hits=[c for c in shots if c in targets],
                   incomingHits=[c for c in incoming if c in mine],
                   sunk=[ship[:] for ship in enemy if set(ship).issubset(shots)], lastShot=copy.deepcopy(s['lastShot']))
    elif game == 'quest':
        for k in ('stage', 'totalStages', 'world', 'energy', 'contributors', 'messages', 'events'):
            out[k] = copy.deepcopy(s[k])
        out['puzzle'] = {k: copy.deepcopy(v) for k, v in s['puzzle'].items() if k not in ('code', 'clues')}
        if s['puzzle']['kind'] == 'vault':
            out['puzzle']['clue'] = s['puzzle']['clues'][pid]
    elif game == 'domino':
        legal = domino_legal(s, pid)
        mine = s['players'][s['turn']] == pid and not s['finished']
        out.update(hand=copy.deepcopy(s['hands'][pid]), chain=copy.deepcopy(s['chain']),
                   counts={p: len(h) for p, h in s['hands'].items()}, deckCount=len(s['deck']), legal=legal,
                   canDraw=mine and not legal and bool(s['deck']), canPass=mine and not legal and not s['deck'], lastMove=copy.deepcopy(s['lastMove']))
    elif game == 'connect4':
        out.update(board=s['board'][:], legal=[c for c in range(7) if s['board'][c] == 0] if not s['finished'] else [],
                   winningCells=s['winningCells'][:], lastMove=copy.deepcopy(s['lastMove']))
    elif game == 'ludo':
        for k in ('tokens', 'rolled', 'colors', 'starts', 'safe', 'lastMove'):
            out[k] = copy.deepcopy(s[k])
        out.update(legal=ludo_legal(s, pid), lastRoll=copy.deepcopy(s.get('lastRoll')))
    elif game == 'codenames':
        for k in ('teams', 'captains', 'teamTurn', 'words', 'revealed', 'clue', 'guessesLeft', 'history'):
            out[k] = copy.deepcopy(s[k])
        out.update(colors=[color if pid in s['captains'] or seen or s['finished'] else None for color, seen in zip(s['keys'], s['revealed'])], remaining=code_remaining(s), winningTeam=s.get('winningTeam'))
    elif game == 'geography':
        out.update(round=s['round'], totalRounds=s['totalRounds'], scores=s['scores'].copy(),
                   answered=list(s['answers']), myAnswer=s['answers'].get(pid),
                   question={k: copy.deepcopy(v) for k, v in s['question'].items() if k not in ('answer', 'explanation')})
        if s['phase'] == 'reveal' or s['finished']:
            out.update(answer=s['question']['answer'], explanation=s['question']['explanation'])
    return out
