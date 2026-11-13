"""Bounded computer opponents for the existing authoritative table rules.

The policy boundary is table_rules.view: opponents never inspect another hand,
fleet, role, answer or unrevealed operative key. Persist the small ``memory``
dictionary per practice room and apply returned actions through table_rules.move.
Scheduling, phase deadlines, membership and reward exclusion belong to tables.py.
"""
from collections import Counter
import hashlib
import json
import math
import random

import chess

from . import table_rules as rules
from . import new_table_rules as expanded
from .new_table_content import CODE_WORDS, COUNTRIES, DRAW_WORDS, LANDMARKS, SHAPES
from .practice_drawing import drawing_strokes


BOT_COUNTS = {'chess': 1, 'checkers': 1, 'uno': 3, 'mafia': 11, 'draw': 2,
              'fleet': 1, 'quest': 1, 'domino': 1, 'connect4': 1, 'ludo': 3,
              'codenames': 3, 'geography': 2}
BOT_NAMES = ('Ziyo', 'Zukko', 'Bilimdon', 'Orion', 'Atlas', 'Sirius',
             'Vega', 'Navo', 'Zafar', 'Umid', 'Olim')


def make_bots(game, human_id):
    """Virtual participants only; no database accounts or rewards are created."""
    if game not in BOT_COUNTS:
        return []
    bots = []
    for i in range(1, BOT_COUNTS[game]+1):
        bot_id = f'bot:{i}'
        if bot_id == str(human_id):
            bot_id = f'bot:practice:{i}'
        bots.append({'id': bot_id, 'name': f'Kompyuter · {BOT_NAMES[i-1]}',
                     'character': 'foxy', 'ready': True, 'isBot': True})
    return bots


def _eligible(game, v, pid):
    if v.get('finished') or pid not in v.get('players', []):
        return False
    if game == 'mafia':
        return pid in v['alive'] and (
            v['phase'] == 'discussion' and pid not in v['discussionReady']
            or v['phase'] == 'vote' and not v['choiceReceived']
            or v['phase'] == 'night' and v['role'] != 'citizen' and not v['choiceReceived'])
    if game == 'draw':
        return v['phase'] == 'drawing' and (pid == v['drawer'] or pid not in v['guessed'])
    if game == 'geography':
        return v['phase'] == 'question' and pid not in v['answered']
    if game == 'quest':
        return True
    if game == 'fleet' and v['phase'] == 'placement':
        return pid not in v['deployed']
    if game == 'codenames':
        return v['teams'][pid] == v['teamTurn'] and (
            v['phase'] == 'clue' and pid == v['captains'][v['teamTurn']]
            or v['phase'] == 'guess' and pid != v['captains'][v['teamTurn']])
    return v['players'][v['turn']] == pid


def eligible_bot_ids(game, state, bots):
    """Candidates, in stable order. A social bot may still elect to wait.

    The tick wrapper should try the next candidate when choose returns None, but
    apply at most one action per tick. This avoids one waiting sketch guesser
    starving the computer artist or another simultaneous participant.
    """
    if game not in BOT_COUNTS or state.get('finished'):
        return []
    ids = [b['id'] if isinstance(b, dict) else b for b in bots]
    return [pid for pid in ids if pid in state.get('players', [])
            and _eligible(game, rules.view(game, state, pid), pid)]


def _rng(*parts):
    raw = json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
    return random.Random(int.from_bytes(hashlib.sha256(raw.encode()).digest()[:8], 'big'))


def choose_bot_action(game, full_game_state, bot_id, memory):
    """Return one legal intent, without mutating game state or reading secrets.

    Policies get exactly the projection delivered to an equivalent player.
    Memory is JSON serializable, bot-scoped and bounded across arbitrarily long
    games. A None result means wait for another participant or the server clock.
    """
    if game not in BOT_COUNTS or full_game_state.get('finished'):
        return None
    if bot_id not in full_game_state.get('players', []):
        return None
    v = rules.view(game, full_game_state, bot_id)
    if not _eligible(game, v, bot_id):
        return None
    own = memory.setdefault(bot_id, {})
    if own.get('game') != game:
        own.clear()
        own['game'] = game
    rng = _rng(game, bot_id, v.get('plies'), v.get('phaseKey'), v.get('round'))
    policy = {'chess': _chess, 'checkers': _checkers, 'uno': _uno,
              'mafia': _mafia, 'draw': _draw, 'fleet': _fleet, 'quest': _quest,
              'domino': _domino, 'connect4': _connect4, 'ludo': _ludo,
              'codenames': _codenames, 'geography': _geography}[game]
    action = policy(v, bot_id, own, rng)
    if action is not None and v.get('phaseKey'):
        action['phaseKey'] = v['phaseKey']
    return action


PIECE_VALUES = {chess.PAWN: 100, chess.KNIGHT: 320, chess.BISHOP: 335,
                chess.ROOK: 500, chess.QUEEN: 900, chess.KING: 0}


def _chess_score(board, color):
    if board.is_checkmate():
        return -100000 if board.turn == color else 100000
    if board.is_stalemate() or board.is_insufficient_material():
        return 0
    value = 0
    for square, piece in board.piece_map().items():
        row, col = chess.square_rank(square), chess.square_file(square)
        advance = row if piece.color else 7-row
        center = 3.5-abs(col-3.5) + 3.5-abs(row-3.5)
        positional = center * (6 if piece.piece_type in (chess.KNIGHT, chess.BISHOP) else 1)
        if piece.piece_type == chess.PAWN:
            positional += advance*7
        if piece.piece_type == chess.KING and len(board.piece_map()) > 12:
            positional = -center*4
        value += (PIECE_VALUES[piece.piece_type]+positional) * (1 if piece.color == color else -1)
    return value


def _chess(v, pid, memory, rng):
    board = chess.Board(v['fen'])
    color = board.turn
    candidates = list(board.legal_moves)
    if not candidates:
        return None
    # Order cheap first, then evaluate up to 24 root choices and 24 replies.
    # The bounded 576 leaves keep every API tick responsive on small servers.
    def priority(move):
        victim = board.piece_at(move.to_square)
        return (10000 if board.gives_check(move) else 0) + (PIECE_VALUES.get(victim.piece_type, 0) if victim else 0) + (900 if move.promotion else 0)
    rng.shuffle(candidates)
    candidates.sort(key=priority, reverse=True)
    best, score = candidates[0], -math.inf
    recent = memory.get('recent', [])
    for move in candidates[:24]:
        board.push(move)
        evaluation = _chess_score(board, color)
        if not board.is_game_over():
            replies = list(board.legal_moves)
            replies.sort(key=priority, reverse=True)
            evaluation = math.inf
            for reply in replies[:24]:
                board.push(reply)
                evaluation = min(evaluation, _chess_score(board, color))
                board.pop()
        board.pop()
        evaluation -= recent.count(move.uci())*18
        evaluation += rng.random()*2
        if evaluation > score:
            best, score = move, evaluation
    memory['recent'] = (recent+[best.uci()])[-10:]
    return {'type': 'move', 'move': best.uci()}


def _checkers(v, pid, memory, rng):
    def score(move):
        piece = v['board'][move['from']]
        row, col = divmod(move['to'], 8)
        promotion = abs(piece) == 1 and row == (7 if piece > 0 else 0)
        return (100 if 'capture' in move else 0) + promotion*75 + (row if piece > 0 else 7-row)*2 + (3.5-abs(col-3.5)) + rng.random()
    if not v['legal']:
        return None
    move = max(v['legal'], key=score)
    return {'type': 'move', 'from': move['from'], 'to': move['to']}


def _uno(v, pid, memory, rng):
    cards = [card for card in v['hand'] if card['id'] in v['legal']]
    if not cards:
        return {'type': 'pass' if v['drawn'] else 'draw'}
    colors = Counter(card['color'] for card in v['hand'] if card['color'] != 'W')
    next_id = v['players'][(v['turn']+v['direction']) % len(v['players'])]
    pressure = v['counts'][next_id] <= 2
    def score(card):
        value = card['value']
        return (25 if pressure and value in ('+2', '+4', 'skip', 'reverse') else 0) + colors[card['color']]*2 + (5 if value in ('+2','skip','reverse') else 0) - (8 if card['color'] == 'W' else 0) + rng.random()
    card = max(cards, key=score)
    color = max('RGBY', key=lambda c: colors[c])
    return {'type': 'play', 'card': card['id'], 'color': color, 'uno': True}


def _mafia(v, pid, memory, rng):
    alive = v['alive']
    role = v['role']
    if v['phase'] == 'discussion':
        if memory.get('spoken') != v['phaseKey']:
            memory['spoken'] = v['phaseKey']
            positive = any(flag and target in alive for target, flag in v['investigations'].items())
            if role == 'detective' and positive:
                text = 'Tekshiruvimda mafiya aniqlandi. Ovoz berishda tekshirgan gumondorimni tanlayman.'
            elif v['lastNight']:
                text = rng.choice(('Kechasi bir ishtirokchini yo‘qotdik. Dalilsiz shoshilmaylik.',
                                   'Tun xavfli o‘tdi. Kimning fikri o‘zgardi? Sababini eshitaylik.'))
            elif v['round'] > 1:
                text = 'Bu tun hech kim chiqib ketmadi. Oldingi ovozlar va gaplarni solishtiraylik.'
            else:
                text = rng.choice(('Men ovoz berishdan oldin boshqalarning fikrini eshitmoqchiman.',
                                   'Hamma fikrini aytsin. Hozircha aniq dalil yo‘q.',
                                   'Faqat jim turgani uchun gumon qilmaylik. Ovozlar ham muhim.'))
            return {'type': 'chat', 'text': text}
        return {'type': 'discussion_ready', 'ready': True}
    options = [p for p in alive if p != pid]
    if v['phase'] == 'night':
        if role == 'mafia':
            options = [p for p in alive if p not in v.get('team', [])]
            # Teammates know one another and can coordinate; no citizen roles.
            rng = _rng('mafia-team', v['round'], options)
        elif role == 'doctor':
            options = [pid] if v['round'] % 2 else alive[:]
        elif role == 'detective':
            options = [p for p in options if p not in v['investigations']] or options
        else:
            return None
    else:
        confirmed = [p for p in options if v['investigations'].get(p) is True]
        if confirmed:
            options = confirmed
        elif role == 'mafia':
            options = [p for p in options if p not in v.get('team', [])]
            rng = _rng('mafia-vote', v['round'], options)
        else:
            innocents = {p for p, flag in v['investigations'].items() if flag is False}
            options = [p for p in options if p not in innocents] or options
            tally = (v.get('lastVote') or {}).get('tally', {})
            if tally and options:
                weights = [1+min(3, tally.get(p, 0)) for p in options]
                return {'type': 'choose', 'target': rng.choices(options, weights)[0]}
    return {'type': 'choose', 'target': rng.choice(options)} if options else None


def _stroke_signature(stroke):
    pts = stroke['points']
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    return [min(xs), max(xs), min(ys), max(ys), sum(xs)/len(xs), sum(ys)/len(ys)]


def _drawing_guess(v, memory):
    """Recognize public geometry only, including rough human-drawn sketches."""
    strokes = v['strokes']
    count = len(strokes)
    if count < 3 or memory.get('guessCount', 0) >= 2 or count < memory.get('lastGuessStrokes', -4)+4:
        return None
    # An unchanged/ambiguous drawing need not be recognized every poll. The
    # final stroke ID also distinguishes clear-and-redraw at the same count.
    revision = f'{count}:{strokes[-1].get("id", "")}'
    if memory.get('examined') == revision:
        return None
    memory['examined'] = revision
    candidates = [word for word in DRAW_WORDS if len(word) == v['wordLength'] and word not in memory.get('guesses', [])]
    if not candidates:
        return None
    actual = [_stroke_signature(s) for s in strokes[:40]]
    def distance(word):
        template = drawing_strokes(word)
        expected = [_stroke_signature(s) for s in template]
        # Prefix alignment recognizes the computer's still-growing sketches;
        # nearest-stroke comparison tolerates humans drawing in another order.
        aligned = sum(sum(abs(a-b) for a,b in zip(actual[i], expected[i])) for i in range(min(len(actual),len(expected)))) / min(len(actual),len(expected))
        nearest = sum(min(sum(abs(a-b) for a,b in zip(s,t)) for t in expected) for s in actual)/len(actual)
        return min(aligned, nearest+.08) + max(0,len(actual)-len(expected))*.02
    ranked = sorted((distance(word), word) for word in candidates)
    # Ambiguous early sketches remain unguessed until another visible stroke.
    if ranked[0][0] > .7 or (len(ranked)>1 and ranked[1][0]-ranked[0][0] < .035 and count < 8):
        return None
    word = ranked[0][1]
    memory['lastGuessStrokes'] = count
    memory['guessCount'] = memory.get('guessCount',0)+1
    memory['guesses'] = (memory.get('guesses',[])+[word])[-2:]
    return {'type': 'guess', 'text': word}


def _draw(v, pid, memory, rng):
    if memory.get('round') != v['round']:
        memory.clear()
        memory.update(game='draw', round=v['round'])
    if pid == v['drawer']:
        strokes = drawing_strokes(v['word'])
        index = len(v['strokes'])
        return strokes[index] if index < len(strokes) else None
    return _drawing_guess(v, memory)


def _fleet(v, pid, memory, rng):
    if v['phase'] == 'placement':
        occupied, ships = set(), []
        for length in v['shipLengths']:
            options = []
            for start in range(64):
                for step in (1, 8):
                    cells = [start+i*step for i in range(length)]
                    if cells[-1]<64 and (step == 8 or cells[-1]//8 == start//8) and not occupied.intersection(cells):
                        options.append(cells)
            chosen = rng.choice(options)
            ships.append(chosen)
            occupied.update(chosen)
        return {'type': 'deploy', 'ships': ships}
    shots = set(v['shots'])
    sunk = {cell for ship in v['sunk'] for cell in ship}
    hits = set(v['hits'])-sunk
    misses = shots-set(v['hits'])
    score = Counter()
    remaining_lengths = v['shipLengths'][:]
    for ship in v['sunk']:
        if len(ship) in remaining_lengths:
            remaining_lengths.remove(len(ship))
    for length in remaining_lengths:
        for start in range(64):
            for step in (1, 8):
                cells = [start+i*step for i in range(length)]
                if cells[-1] >= 64 or step == 1 and cells[-1]//8 != start//8:
                    continue
                if set(cells) & (misses | sunk):
                    continue
                weight = 1+15*len(set(cells)&hits)
                for cell in cells:
                    if cell not in shots:
                        score[cell] += weight
    options = [cell for cell in range(64) if cell not in shots]
    return {'type': 'fire', 'cell': max(options, key=lambda c: score[c]+rng.random())} if options else None


def _lights_solution(cells):
    # Nine switches: exhaustive GF(2) search is only 512 small candidates.
    for mask in sorted(range(512), key=int.bit_count):
        result = cells[:]
        switches = [i for i in range(9) if mask & (1 << i)]
        for cell in switches:
            expanded.lights_toggle(result, cell)
        if not any(result):
            return switches
    return []


def _quest(v, pid, memory, rng):
    if memory.get('stage') != v['stage']:
        memory.clear()
        memory.update(game='quest', stage=v['stage'], budget=1, observed=v['plies'], human=False)
    elif v['plies'] > memory.get('observed', v['plies']):
        memory['budget'] = 1
        memory['human'] = True
    puzzle = v['puzzle']
    if not memory.get('hint'):
        memory['hint'] = True
        memory['observed'] = v['plies']+1
        if puzzle['kind'] == 'vault':
            text = f'Mendagi maslahat: {puzzle["clue"]}. Qolgan raqamlarni sening maslahatingdan topamiz; kodni sen kirit.'
        elif puzzle['kind'] == 'lights':
            solution = _lights_solution(puzzle['cells'])
            text = f'Bir tugma yonidagi chiroqlarni ham o‘zgartiradi. {solution[0]+1}-tugunni tekshirib ko‘r. Birgalikda yechamiz.' if solution else 'Chiroqlarni birgalikda o‘chiramiz.'
        else:
            text = 'Halqalarni yuqoridagi namunaga moslaymiz. Men yordam beraman, keyingi yurish seniki.'
        return {'type':'chat', 'text':text}
    if not memory['budget'] or puzzle['kind'] == 'vault':
        return None
    if puzzle['kind'] == 'lights':
        solution = _lights_solution(puzzle['cells'])
        if not solution or len(solution) == 1 and not memory['human']:
            return None
        action = {'type':'toggle', 'cell':solution[0]}
    else:
        needed = sum((b-a)%4 for a,b in zip(puzzle['values'],puzzle['target']))
        if not needed or needed == 1 and not memory['human']:
            return None
        index = next(i for i,(a,b) in enumerate(zip(puzzle['values'],puzzle['target'])) if a != b)
        action = {'type':'rotate', 'index':index}
    memory['budget'] = 0
    memory['observed'] = v['plies']+1
    return action


def _domino(v, pid, memory, rng):
    if v['legal']:
        hand = {tile['id']: tile for tile in v['hand']}
        choice = max(v['legal'], key=lambda m: hand[m['id']]['a']+hand[m['id']]['b']+(2 if hand[m['id']]['a']==hand[m['id']]['b'] else 0)+rng.random())
        return {'type':'play', 'tile':choice['id'], 'side':choice['side']}
    return {'type':'draw' if v['canDraw'] else 'pass'} if v['canDraw'] or v['canPass'] else None


def _four(board, side):
    for row in range(6):
        for col in range(7):
            for dy,dx in ((0,1),(1,0),(1,1),(1,-1)):
                if 0 <= row+3*dy < 6 and 0 <= col+3*dx < 7 and all(board[(row+i*dy)*7+col+i*dx] == side for i in range(4)):
                    return True
    return False


def _drop(board, col, side):
    result = board[:]
    for row in range(5,-1,-1):
        if result[row*7+col] == 0:
            result[row*7+col] = side
            return result
    return result


def _connect4(v, pid, memory, rng):
    side = v['turn']+1
    enemy = 3-side
    legal = v['legal']
    for player in (side, enemy):
        for col in legal:
            if _four(_drop(v['board'],col,player),player):
                return {'type':'drop','column':col}
    def score(col):
        after = _drop(v['board'],col,side)
        threats = sum(_four(_drop(after,c,enemy),enemy) for c in range(7) if after[c] == 0)
        return -threats*100 + 3-abs(3-col)+rng.random()*.5
    return {'type':'drop', 'column':max(legal,key=score)} if legal else None


def _ludo(v, pid, memory, rng):
    if v['rolled'] is None:
        return {'type':'roll'}
    def score(index):
        old = v['tokens'][pid][index]
        target = 0 if old == -1 else old+v['rolled']
        absolute = (v['starts'][pid]+target)%52
        captures = sum(1 for other,tokens in v['tokens'].items() if other != pid for n in tokens
                       if 0 <= n < 52 and (v['starts'][other]+n)%52 == absolute) if target<52 and absolute not in v['safe'] else 0
        return (100 if target == 57 else 0) + captures*40 + (18 if old == -1 else 0) + (12 if target<52 and absolute in v['safe'] else 0) + target*.3+rng.random()
    return {'type':'move', 'token':max(v['legal'],key=score)} if v['legal'] else None


# A shared language association dictionary, not a side-channel between teams.
# Captains may see colors. Operatives match clues to these concepts without keys.
_UNIQUE_CLUES = ('yo‘ldosh','miltirash','kosmonavt','daryodan','mutolaa','qulf',
    'podshoh','ildiz','meva','siyoh','cho‘qqi','okean','sahro','muzlatgich',
    'shabada','alanga','vaqt','sayrash','osmon','yelkan','istehkom','chavandoz',
    'asal','guldasta','yoritish','nigoh','sayohat','shisha','jarang','bog‘bon',
    'xazina','pul','himoya','tikuv','nonvoy','sho‘r','ichimlik','uvillash',
    'yirtqich','suzgich','daraxtzor','katakli','maktub','parvoz','futbol',
    'g‘orchi','rangbarang','qish','oqim','chig‘anoq','kumushrang','zargarlik',
    'soniyalar','balandlik','geografiya','shimol','sohil','issiqlik','o‘quvchi')
ASSOCIATIONS = {expanded.normalize(clue): {expanded.normalize(word): 8}
                for word,clue in zip(CODE_WORDS,_UNIQUE_CLUES)}
CLUE_LABELS = {expanded.normalize(clue):clue for clue in _UNIQUE_CLUES}
_GROUPS = {
    'kosmos': ('OY','YULDUZ','RAKETA','QUYOSH'),
    'tabiat': ('DARAXT','GUL','TERAK','BOG‘','TOG‘','QUSH'),
    'dars': ('KITOB','QALAM','DAFTAR','MAKTAB','XARITA'),
    'suvda': ('DENGIZ','KEMA','BALIQ','DARYO','OROL','MARVARID'),
    'ob-havo': ('SHAMOL','BULUT','KAMALAK','QOR','MUZ','QUYOSH'),
    'hayvon': ('OT','ARI','BO‘RI','SHER','BALIQ','QUSH'),
    'qirollik': ('TOJ','QAL’A','OLTIN','QALQON','MINORA'),
    'yozish': ('QALAM','DAFTAR','XAT','KITOB'),
    'qimmatbaho': ('OLTIN','KUMUSH','MARVARID','TANGA'),
    'vaqtlar': ('SOAT','QUMSOAT'),
    'sayohatchi': ('XARITA','KOMPAS','YO‘L','OROL','KO‘PRIK'),
    'taom': ('NON','TUZ','OLMA','SUV'),
    'uchish': ('QUSH','QANOT','RAKETA','ARI'),
}
for _clue,_words in _GROUPS.items():
    ASSOCIATIONS[expanded.normalize(_clue)] = {expanded.normalize(w):5 for w in _words}
    CLUE_LABELS[expanded.normalize(_clue)] = _clue
CAPTAIN_CLUES = tuple(CLUE_LABELS)

_CLUE_ALIASES = {
    'kosmos': ('koinot','fazo','fazoviy','kosmik','astronomiya','space'),
    'tabiat': ('o‘rmon','yashil','o‘simlik','o‘simliklar','nature'),
    'dars': ('ta’lim','bilim','o‘qish','maktabda','education','school'),
    'suvda': ('suvli','dengizchi','baliqchi','okeanlar','water'),
    'ob-havo': ('osmonlar','yomg‘ir','weather'),
    'hayvon': ('hayvonlar','jonivor','jonivorlar','zoologiya','animal'),
    'qirollik': ('shoh','shohlik','saroy','sulton','king'),
    'yozish': ('yozuvlar','yozmoq','yozadi','writing'),
    'qimmatbaho': ('boylik','javohir','metal','metall','zargarliklar'),
    'vaqtlar': ('vaqt','daqiqa','soatlar','time'),
    'sayohatchi': ('yo‘lovchi','safar','yo‘nalish','travel'),
    'taom': ('ovqat','oziq','oshxona','food'),
    'uchish': ('uchadi','uchuvchi','uchadigan','flying'),
}
for _source,_aliases in _CLUE_ALIASES.items():
    for _alias in _aliases:
        _normalized = expanded.normalize(_alias)
        if _normalized not in ASSOCIATIONS:
            ASSOCIATIONS[_normalized] = ASSOCIATIONS[expanded.normalize(_source)]
            CLUE_LABELS[_normalized] = _alias


def _clue_scores(clue, words):
    normalized = expanded.normalize(clue)
    associations = ASSOCIATIONS.get(normalized, {})
    if not associations:
        for suffix in ('larning','lardan','larni','lar','dagi','dan','ning','da'):
            if normalized.endswith(suffix):
                associations = ASSOCIATIONS.get(normalized[:-len(suffix)], {})
                if associations:
                    break
    return [associations.get(expanded.normalize(word), 0) for word in words]


def _codenames(v, pid, memory, rng):
    if v['phase'] == 'clue':
        board_words = {expanded.normalize(w) for w in v['words']}
        choices = []
        for clue in CAPTAIN_CLUES:
            associated = ASSOCIATIONS[clue]
            if clue in board_words:
                continue
            targets = [i for i,w in enumerate(v['words']) if not v['revealed'][i] and expanded.normalize(w) in associated]
            own = [i for i in targets if v['colors'][i] == v['teamTurn']]
            danger = [i for i in targets if v['colors'][i] != v['teamTurn']]
            if own:
                value = len(own)*5-len(danger)*12 + rng.random()
                choices.append((value,clue,len(own)))
        if not choices:
            return None
        _,clue,count = max(choices)
        return {'type':'clue','word':CLUE_LABELS[clue],'count':min(count,9)}
    candidates = [i for i,seen in enumerate(v['revealed']) if not seen]
    scores = _clue_scores((v['clue'] or {}).get('word',''),v['words'])
    matched = [i for i in candidates if scores[i] > 0]
    if not matched or v['guessesLeft'] <= 1:
        return {'type':'end'}
    best = max(matched,key=lambda i: scores[i]+rng.random()*.1)
    return {'type':'guess','cell':best}


def _geography(v, pid, memory, rng):
    question = v['question']
    known = None
    if question['kind'] == 'flag':
        known = next((country for country,iso,_ in COUNTRIES if iso == question.get('flag')),None)
    elif question['kind'] == 'capital':
        known = next((capital for country,_,capital in COUNTRIES if question['prompt'].startswith(country+' ')),None)
    elif question['kind'] == 'landmark':
        known = next((country for _,landmark,country,_ in LANDMARKS if landmark == question.get('landmark')),None)
    elif question['kind'] == 'shape':
        known = next((country for country,shape in SHAPES if shape == question.get('map')),None)
    options = question['options']
    # Approximately four correct answers in five; fallible practice partners.
    correct = options.index(known) if known in options else None
    choice = correct if correct is not None and rng.random() < .8 else rng.choice([i for i in range(len(options)) if i != correct] or [0])
    return {'type':'answer', 'choice':choice}
