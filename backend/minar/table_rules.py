"""Authoritative rules for student rooms. Private state never leaves view()."""
from collections import Counter
import copy
import random
import secrets
import chess
from .errors import MinarError
from . import new_table_rules as expanded

GAMES = {'chess': (2, 2), 'checkers': (2, 2), 'uno': (2, 6), 'mafia': (6, 10), 'sudoku': (1, 1), **expanded.GAMES}
MAFIA_PHASE_SECONDS = {'night': 30, 'discussion': 45, 'vote': 25}
CHECKERS_RULES = 'russian-64-v2'
RNG = random.SystemRandom()


def require(ok, message='Bu yurish mumkin emas.'):
    if not ok:
        raise MinarError(400, message)


def finish(s, winners, reason='completed'):
    s.update(finished=True, winners=winners, reason=reason)


def board_chess(s):
    b = chess.Board()
    for move in s['moves']:
        b.push_uci(move)
    return b


def _legacy_checker_moves(s):
    # An in-progress room must finish with the rules it started with.
    board, side, forced = s['board'], s['turn'], s.get('chain')
    jumps, steps = [], []
    for i, piece in enumerate(board):
        if not piece or (piece > 0) != (side == 0) or (forced is not None and i != forced):
            continue
        row, col = divmod(i, 8)
        for dy in ([1, -1] if abs(piece) == 2 else [1 if piece > 0 else -1]):
            for dx in [-1, 1]:
                y, x = row + dy, col + dx
                if not (0 <= y < 8 and 0 <= x < 8):
                    continue
                j = y*8+x
                if board[j] == 0 and forced is None:
                    steps.append({'from': i, 'to': j})
                elif board[j] and (board[j] > 0) != (piece > 0):
                    y, x = row+dy*2, col+dx*2
                    if 0 <= y < 8 and 0 <= x < 8 and board[y*8+x] == 0:
                        jumps.append({'from': i, 'to': y*8+x, 'capture': j})
    return jumps or ([] if forced is not None else steps)


def checker_moves(s):
    """Draughts-64: flying kings, backward captures, and compulsory chains.

    IDF rules 3.8 and 4.1–4.15: https://fmjd64.org/rules-of-the-game/
    Captured pieces stay on the board as blockers until the complete turn ends;
    an already-captured piece may never be jumped a second time (4.8/4.11).
    Russian rules allow a choice of capture, not a maximum-piece requirement.
    """
    if s.get('rulesVersion') != CHECKERS_RULES:
        return _legacy_checker_moves(s)
    board, side, forced = s['board'], s['turn'], s.get('chain')
    captured = set(s.get('pendingCaptures', []))
    jumps, steps = [], []
    for i, piece in enumerate(board):
        if not piece or i in captured or (piece > 0) != (side == 0) or (forced is not None and i != forced):
            continue
        row, col = divmod(i, 8)
        for dy in (-1, 1):
            for dx in (-1, 1):
                y, x = row + dy, col + dx
                if abs(piece) == 1:
                    if not (0 <= y < 8 and 0 <= x < 8):
                        continue
                    target = y * 8 + x
                    if board[target] == 0:
                        if forced is None and dy == (1 if piece > 0 else -1):
                            steps.append({'from': i, 'to': target})
                    elif target not in captured and (board[target] > 0) != (piece > 0):
                        ly, lx = y + dy, x + dx
                        if 0 <= ly < 8 and 0 <= lx < 8 and board[ly * 8 + lx] == 0:
                            jumps.append({'from': i, 'to': ly * 8 + lx, 'capture': target})
                    continue
                victim = None
                while 0 <= y < 8 and 0 <= x < 8:
                    target = y * 8 + x
                    occupant = board[target]
                    if occupant:
                        if target in captured or victim is not None or (occupant > 0) == (piece > 0):
                            break
                        victim = target
                    elif victim is not None:
                        jumps.append({'from': i, 'to': target, 'capture': victim})
                    elif forced is None:
                        steps.append({'from': i, 'to': target})
                    y, x = y + dy, x + dx
    return jumps or ([] if forced is not None else steps)


def _checker_turn_key(s):
    return ','.join(map(str, s['board'])) + ':' + str(s['turn'])


def _russian_checker_move(s, chosen, pid):
    source, target = chosen['from'], chosen['to']
    piece = s['board'][source]
    s['board'][source], s['board'][target] = 0, piece
    promoted = abs(piece) == 1 and target // 8 == (7 if piece > 0 else 0)
    if promoted:
        s['board'][target] *= 2
    s['lastMove'] = {'from': source, 'to': target, 'capture': chosen.get('capture'), 'promoted': promoted}
    s['chain'] = None
    if 'capture' in chosen:
        s.setdefault('pendingCaptures', []).append(chosen['capture'])
        s['quiet'] = 0
        # Reaching the last row during a capture promotes immediately, so the
        # same turn can continue with a king's distant jump (IDF 4.14).
        s['chain'] = target
        if checker_moves(s):
            return
        s['chain'] = None
        for victim in s['pendingCaptures']:
            s['board'][victim] = 0
        s['pendingCaptures'] = []
    else:
        # Fifteen full turns of king-only movement with no capture is a draw.
        s['quiet'] = s.get('quiet', 0) + 1 if abs(piece) == 2 else 0
    s['turn'] = 1 - s['turn']
    key = _checker_turn_key(s)
    repetitions = s.setdefault('repetitions', {})
    repetitions[key] = repetitions.get(key, 0) + 1
    if not checker_moves(s):
        finish(s, [pid])
    elif s['quiet'] >= 30 or repetitions[key] >= 3:
        finish(s, [], 'draw')


def sudoku_solution():
    rows = [g*3+r for g in RNG.sample(range(3), 3) for r in RNG.sample(range(3), 3)]
    cols = [g*3+c for g in RNG.sample(range(3), 3) for c in RNG.sample(range(3), 3)]
    digits = RNG.sample(range(1, 10), 9)
    return [digits[(r*3+r//3+c) % 9] for r in rows for c in cols]


def solution_count(grid, limit=2):
    best, options = None, None
    for i, n in enumerate(grid):
        if n:
            continue
        r, c = divmod(i, 9)
        used = set(grid[r*9:r*9+9]) | set(grid[c::9]) | {grid[y*9+x] for y in range(r//3*3, r//3*3+3) for x in range(c//3*3, c//3*3+3)}
        choices = set(range(1, 10))-used
        if not choices:
            return 0
        if options is None or len(choices) < len(options):
            best, options = i, choices
    if best is None:
        return 1
    total = 0
    for n in options:
        grid[best] = n
        total += solution_count(grid, limit-total)
        if total >= limit:
            break
    grid[best] = 0
    return total


def new_game(game, ids):
    if game in expanded.GAMES:
        return expanded.new_game(game, ids)
    s = {'players': ids[:], 'turn': 0, 'plies': 0, 'finished': False, 'winners': [], 'log': []}
    if game == 'chess':
        s['moves'] = []
    elif game == 'checkers':
        s.update(board=[(1 if i//8 < 3 else -1 if i//8 > 4 else 0) if (i//8+i%8)%2 else 0 for i in range(64)], chain=None, quiet=0, repetitions={}, rulesVersion=CHECKERS_RULES, pendingCaptures=[])
        s['repetitions'][_checker_turn_key(s)] = 1
    elif game == 'uno':
        deck = []
        for color in 'RGBY':
            for value in ['0'] + [str(n) for n in range(1, 10)]*2 + ['skip', 'reverse', '+2']*2:
                deck.append({'id': str(len(deck)), 'color': color, 'value': value})
        for value in ['wild']*4+['+4']*4:
            deck.append({'id': str(len(deck)), 'color': 'W', 'value': value})
        RNG.shuffle(deck)
        hands = {pid: [deck.pop() for _ in range(7)] for pid in ids}
        numeric = next(i for i, card in enumerate(deck) if card['value'].isdigit())
        top = deck.pop(numeric)
        s.update(deck=deck, hands=hands, discard=[top], color=top['color'], direction=1, drawn=None)
    elif game == 'mafia':
        roles = ['mafia']*(2 if len(ids) >= 7 else 1)+['doctor', 'detective']
        roles += ['citizen']*(len(ids)-len(roles))
        RNG.shuffle(roles)
        s.update(roles=dict(zip(ids, roles)), alive=ids[:], phase='night', round=1, choices={}, investigations={}, eliminated=[], chat=[], lastNight=None, discussionReady=[], events=[], lastVote=None)
    elif game == 'sudoku':
        solution = sudoku_solution()
        puzzle = solution[:]
        for i in RNG.sample(range(81), 81):
            old = puzzle[i]
            puzzle[i] = 0
            if solution_count(puzzle[:]) != 1:
                puzzle[i] = old
            if puzzle.count(0) >= 43:
                break
        s.update(puzzle=puzzle, solution=solution, grid=puzzle[:])
    return s


def uno_legal(s, card, pid):
    top = s['discard'][-1]
    if s.get('drawn') and card['id'] != s['drawn']:
        return False
    if card['value'] == '+4':
        return not any(c['color'] == s['color'] for c in s['hands'][pid])
    return card['color'] in ('W', s['color']) or card['value'] == top['value']


def draw_cards(s, pid, n):
    for _ in range(n):
        if not s['deck']:
            s['deck'] = s['discard'][:-1]
            s['discard'] = s['discard'][-1:]
            RNG.shuffle(s['deck'])
        if s['deck']:
            s['hands'][pid].append(s['deck'].pop())


def mafia_winner(s):
    mafia = sum(s['roles'][p] == 'mafia' for p in s['alive'])
    if not mafia or mafia >= len(s['alive'])-mafia:
        team = 'mafia' if mafia else 'citizen'
        finish(s, [p for p in s['players'] if (s['roles'][p] == 'mafia') == (team == 'mafia')])
        s['winningTeam'] = team
        return True
    return False


def eliminate(s, pid):
    if pid in s['alive']:
        s['alive'].remove(pid)
        s['eliminated'].append({'id': pid, 'role': s['roles'][pid]})


def mafia_phase_key(s):
    return f"{s['round']}:{s['phase']}"


def _mafia_event(s, kind, target=None, **extra):
    # Only resolved, public outcomes enter this log. Never include night votes,
    # saved targets, detective choices, or the number of night actions submitted.
    event = {'id': mafia_phase_key(s), 'round': s['round'], 'type': kind, 'target': target, **extra}
    s['events'] = (s.get('events', []) + [event])[-40:]


def _unique_vote_target(votes):
    ranked = votes.most_common()
    return ranked[0][0] if ranked and (len(ranked) == 1 or ranked[0][1] > ranked[1][1]) else None


def mafia_advance(s):
    if s['finished']:
        return
    choices = s['choices']
    if s['phase'] == 'night':
        votes = Counter(v for p, v in choices.items() if s['roles'][p] == 'mafia')
        # A split mafia vote must not be decided by request arrival order.
        target = _unique_vote_target(votes)
        saved = {v for p, v in choices.items() if s['roles'][p] == 'doctor'}
        if target and target not in saved:
            eliminate(s, target)
        else:
            target = None
        s['lastNight'] = target
        _mafia_event(s, 'night_eliminated' if target else 'night_safe', target)
        s['phase'] = 'discussion'
    elif s['phase'] == 'discussion':
        s['phase'] = 'vote'
    else:
        votes = Counter(v for v in choices.values() if v is not None)
        target = _unique_vote_target(votes)
        tally = dict(votes)
        abstentions = sum(v is None for v in choices.values())
        s['lastVote'] = {'round': s['round'], 'target': target, 'tied': bool(votes and not target), 'tally': tally, 'abstentions': abstentions}
        if target:
            eliminate(s, target)
        _mafia_event(s, 'vote_eliminated' if target else 'vote_tied' if votes else 'no_vote', target, tally=tally, abstentions=abstentions)
        s['phase'] = 'night'
        s['round'] += 1
    s['choices'] = {}
    s['discussionReady'] = []
    mafia_winner(s)


def move(game, s, pid, action):
    if game in expanded.GAMES:
        return expanded.move(game, s, pid, action)
    require(not s['finished'], 'O‘yin tugagan.')
    require(pid in s['players'], 'Siz bu xonada emassiz.')
    kind = action.get('type')
    if kind == 'resign':
        # Quitting cannot manufacture reward wins for friends.
        finish(s, [], 'abandoned')
        return
    if game == 'mafia':
        require(pid in s['alive'], 'Siz kuzatuvchisiz.')
        if action.get('phaseKey') is not None and action['phaseKey'] != mafia_phase_key(s):
            raise MinarError(409, 'Bosqich yangilandi. Yangi vaziyatni tekshiring.')
        if kind == 'chat':
            require(s['phase'] in ('discussion', 'vote'), 'Muhokama kunduz kuni ochiladi.')
            body = action.get('text')
            require(isinstance(body, str) and 0 < len(body.strip()) <= 300, 'Xabar 1–300 belgi bo‘lsin.')
            s['chat'] = (s['chat']+[{'id': secrets.token_hex(6), 'player': pid, 'text': body.strip(), 'round': s['round']}])[-60:]
            return
        if kind in ('discussion-ready', 'discussion_ready'):
            require(s['phase'] == 'discussion', 'Tayyorlik faqat muhokama vaqtida belgilanadi.')
            require(type(action.get('ready')) is bool, 'Tayyorlik holatini tanlang.')
            ready = set(s.get('discussionReady', []))
            if action['ready']:
                ready.add(pid)
            else:
                ready.discard(pid)
            s['discussionReady'] = [p for p in s['alive'] if p in ready]
            if all(p in ready for p in s['alive']):
                mafia_advance(s)
            return
        require(kind in ('choose', 'abstain') and s['phase'] in ('night', 'vote'))
        require(pid not in s['choices'], 'Tanlovingiz yuborilgan. Bosqich yakunlanishini kuting.')
        if kind == 'abstain':
            require(s['phase'] == 'vote', 'Ovoz bermaslik faqat kunduzgi ovoz berishda mumkin.')
        target = action.get('target')
        require(kind == 'abstain' or target in s['alive'])
        role = s['roles'][pid]
        if s['phase'] == 'night':
            require(role != 'citizen')
            if role == 'mafia':
                require(s['roles'][target] != 'mafia')
            if role == 'detective':
                require(pid != target)
                s['investigations'].setdefault(pid, {})[target] = s['roles'][target] == 'mafia'
        elif kind == 'choose':
            require(pid != target)
        s['choices'][pid] = None if kind == 'abstain' else target
        expected = s['alive'] if s['phase'] == 'vote' else [p for p in s['alive'] if s['roles'][p] != 'citizen']
        if all(p in s['choices'] for p in expected):
            mafia_advance(s)
        s['plies'] += 1
        return
    if game == 'sudoku':
        require(kind in ('save', 'solve'))
        grid = action.get('grid')
        require(isinstance(grid, list) and len(grid) == 81 and all(type(n) is int and 0 <= n <= 9 for n in grid))
        require(all(not n or grid[i] == n for i, n in enumerate(s['puzzle'])), 'Berilgan raqamni o‘zgartirib bo‘lmaydi.')
        if kind == 'solve':
            require(grid == s['solution'], 'Jadval hali to‘g‘ri to‘ldirilmagan.')
            finish(s, [pid])
        s['grid'] = grid[:]
        return
    require(s['players'][s['turn']] == pid, 'Hozir raqibning navbati.')
    if game == 'chess':
        require(kind == 'move')
        uci = action.get('move')
        require(isinstance(uci, str) and len(uci) in (4, 5))
        b = board_chess(s)
        try:
            m = chess.Move.from_uci(uci)
        except ValueError:
            raise MinarError(400, 'Yurish noto‘g‘ri.')
        require(m in b.legal_moves)
        s['lastMove'] = {'from': (7 - chess.square_rank(m.from_square)) * 8 + chess.square_file(m.from_square),
                         'to': (7 - chess.square_rank(m.to_square)) * 8 + chess.square_file(m.to_square),
                         'uci': uci, 'capture': b.is_capture(m),
                         'promotion': chess.piece_symbol(m.promotion) if m.promotion else None}
        san = b.san(m)
        b.push(m)
        s['moves'].append(uci)
        s['log'] = (s['log']+[san])[-100:]
        s['turn'] = 0 if b.turn else 1
        outcome = b.outcome(claim_draw=True)
        if outcome:
            finish(s, [] if outcome.winner is None else [s['players'][0 if outcome.winner else 1]], 'draw' if outcome.winner is None else 'completed')
    elif game == 'checkers':
        require(kind == 'move')
        require(type(action.get('from')) is int and type(action.get('to')) is int, 'Katak raqami noto‘g‘ri.')
        legal = checker_moves(s)
        chosen = next((m for m in legal if m['from'] == action.get('from') and m['to'] == action.get('to')), None)
        require(chosen)
        if s.get('rulesVersion') == CHECKERS_RULES:
            _russian_checker_move(s, chosen, pid)
            s['plies'] += 1
            return
        a, b = chosen['from'], chosen['to']
        piece = s['board'][a]
        s['board'][a], s['board'][b] = 0, piece
        promoted = abs(piece) == 1 and b//8 == (7 if piece > 0 else 0)
        if promoted:
            s['board'][b] *= 2
        s['chain'] = None
        if 'capture' in chosen:
            s['board'][chosen['capture']] = 0
            s['quiet'] = 0
            if not promoted:
                s['chain'] = b
                if not checker_moves(s):
                    s['chain'] = None
        else:
            s['quiet'] += 1
        if s['chain'] is None:
            s['turn'] = 1-s['turn']
            key = ','.join(map(str, s['board']))+':'+str(s['turn'])
            s['repetitions'][key] = s['repetitions'].get(key, 0)+1
            if not checker_moves(s):
                finish(s, [pid])
            elif s['quiet'] >= 80 or s['repetitions'][key] >= 3:
                finish(s, [], 'draw')
    elif game == 'uno':
        hand = s['hands'][pid]
        n, direction = len(s['players']), s['direction']
        next_turn = (s['turn']+direction) % n
        if kind == 'draw':
            require(not s['drawn'])
            before = len(hand)
            draw_cards(s, pid, 1)
            if len(hand) > before and uno_legal(s, hand[-1], pid):
                s['drawn'] = hand[-1]['id']
                return
            s['turn'] = next_turn
        elif kind == 'pass':
            require(s['drawn'])
            s['turn'] = next_turn
        else:
            require(kind == 'play')
            card = next((c for c in hand if c['id'] == action.get('card')), None)
            require(card and uno_legal(s, card, pid))
            color = action.get('color') if card['color'] == 'W' else card['color']
            require(color in 'RGBY' and len(color) == 1 if isinstance(color, str) else False)
            hand.remove(card)
            s['discard'].append(card)
            s['color'] = color
            value = card['value']
            if value == 'reverse':
                s['direction'] = -direction
                next_turn = s['turn'] if n == 2 else (s['turn']-direction) % n
            if value in ('+2', '+4'):
                draw_cards(s, s['players'][next_turn], 2 if value == '+2' else 4)
            if value in ('skip', '+2', '+4'):
                next_turn = (next_turn+direction) % n
            if len(hand) == 1 and not action.get('uno'):
                draw_cards(s, pid, 2)
            if not hand:
                finish(s, [pid])
            s['turn'] = next_turn
        s['drawn'] = None
    s['plies'] += 1


def view(game, s, pid):
    if game in expanded.GAMES:
        return expanded.view(game, s, pid)
    out = {k: copy.deepcopy(s.get(k)) for k in ('players', 'turn', 'plies', 'finished', 'winners', 'reason')}
    if game == 'chess':
        b = board_chess(s)
        out.update(fen=b.fen(), board=[b.piece_at(chess.square(i%8, 7-i//8)).symbol() if b.piece_at(chess.square(i%8, 7-i//8)) else '' for i in range(64)], legal=[m.uci() for m in b.legal_moves], check=b.is_check(), log=s['log'])
        king = b.king(b.turn) if b.is_check() else None
        out.update(lastMove=copy.deepcopy(s.get('lastMove')), checkedSquare=(7 - chess.square_rank(king)) * 8 + chess.square_file(king) if king is not None else None)
    elif game == 'checkers':
        out.update(board=s['board'][:], legal=checker_moves(s), chain=s['chain'],
                   rulesVersion=s.get('rulesVersion', 'legacy-v1'), pendingCaptures=s.get('pendingCaptures', [])[:], lastMove=copy.deepcopy(s.get('lastMove')))
    elif game == 'uno':
        out.update(hand=copy.deepcopy(s['hands'].get(pid, [])), counts={p: len(h) for p, h in s['hands'].items()}, top=copy.deepcopy(s['discard'][-1]), color=s['color'], direction=s['direction'], deckCount=len(s['deck']), drawn=s['drawn'] if s['players'][s['turn']] == pid else None, legal=[c['id'] for c in s['hands'].get(pid, []) if uno_legal(s, c, pid)])
    elif game == 'mafia':
        # The shared move counter would reveal how many hidden night choices
        # have arrived. Mafia clients only need the public round/phase.
        out.pop('plies', None)
        out.update(role=s['roles'].get(pid), alive=s['alive'][:], phase=s['phase'], round=s['round'], eliminated=copy.deepcopy(s['eliminated']), chat=copy.deepcopy(s['chat']), investigations=copy.deepcopy(s['investigations'].get(pid, {})), chosen=s['choices'].get(pid), lastNight=s['lastNight'], winningTeam=s.get('winningTeam'))
        out.update(phaseKey=mafia_phase_key(s), phaseSeconds=0 if s['finished'] else MAFIA_PHASE_SECONDS[s['phase']],
                   discussionReady=s.get('discussionReady', [])[:] if s['phase'] == 'discussion' else [],
                   choiceReceived=pid in s['choices'], abstained=pid in s['choices'] and s['choices'][pid] is None,
                   events=copy.deepcopy(s.get('events', [])), lastVote=copy.deepcopy(s.get('lastVote')))
        if s['roles'].get(pid) == 'mafia':
            out['team'] = [p for p, r in s['roles'].items() if r == 'mafia']
        if s['finished']:
            out['roles'] = s['roles'].copy()
    elif game == 'sudoku':
        out.update(puzzle=s['puzzle'][:], grid=s['grid'][:])
    return out
