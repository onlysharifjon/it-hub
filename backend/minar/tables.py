"""Authenticated online rooms. Lock order: caller account, then room.

Every move commits a version and request receipt. GET is read-only; phase clocks
advance through the authenticated tick action. No hidden roles/cards are serialized.
"""
import json
import secrets
import uuid
from datetime import datetime, timedelta
from sqlalchemy import select, func, case, or_
from .. import models, security
from . import table_rules as rules
from . import new_table_rules as expanded
from . import practice_rooms
from .models import MinarAccount, MinarTableRoom as Room, MinarTablePlayer as Player, MinarResult
from .errors import MinarError

BOARD_REACTIONS = ('bravo', 'wow', 'think', 'good-game', 'oops', 'respect')
REACTION_SECONDS = 8
REACTION_COOLDOWN_SECONDS = 3


def _live_reactions(state, now):
    return [event for event in state.get('reactions', [])
            if datetime.fromisoformat(event['expiresAt'].rstrip('Z')) > now]


def _account_lock(db, acc):
    db.execute(select(MinarAccount.id).where(MinarAccount.id == acc.id).with_for_update()).scalar_one()


def _members(db, room):
    return db.query(Player).filter_by(room_id=room.id).order_by(Player.id).all()


def _active(db, acc):
    return db.query(Room).join(Player, Player.room_id == Room.id).filter(
        Player.account_id == acc.id, Room.status.in_(('waiting', 'playing')),
        Room.expires_at > datetime.utcnow()).first()


def _limited(acc, key, limit):
    if not security.rate_limit_ok(f'minar-table-{key}:{acc.id}', limit=limit, window=60):
        raise MinarError(429, 'Biroz kutib, qayta urinib ko‘ring.')


def _room(db, acc, code, lock=False):
    rules.require(isinstance(code, str) and 6 <= len(code) <= 8)
    query = db.query(Room).filter_by(code=code.upper())
    room = query.populate_existing().with_for_update().first() if lock else query.first()
    if not room:
        raise MinarError(404, 'Xona topilmadi.')
    if not db.query(Player.id).filter_by(room_id=room.id, account_id=acc.id).first():
        raise MinarError(403, 'Avval xona kodi bilan qo‘shiling.')
    if practice_rooms.is_practice(json.loads(room.state)) and room.host_id != acc.id:
        raise MinarError(403, 'Bu shaxsiy mashq xonasi.')
    return room


def _public(db, acc, room):
    from .service import public_name
    members = _members(db, room)
    accounts = db.query(MinarAccount, models.Student.full_name).join(models.Student, models.Student.id == MinarAccount.student_id).filter(MinarAccount.id.in_([m.account_id for m in members])).all()
    data = {a.id: {'id': str(a.id), 'profileId': a.login_id, 'name': public_name(name), 'character': a.character} for a, name in accounts}
    state = json.loads(room.state)
    expired = room.expires_at <= datetime.utcnow()
    result = {'id': room.id, 'code': room.code, 'game': room.game,
            'status': 'expired' if expired and room.status != 'finished' else room.status,
            'host': str(room.host_id), 'me': str(acc.id), 'version': room.version,
            'members': [{**data[m.account_id], 'ready': m.ready, 'isBot': False} for m in members],
            'practice': practice_rooms.is_practice(state),
            'deadline': state.get('deadline'), 'phaseStartedAt': state.get('phaseStartedAt'), 'serverTime': datetime.utcnow().isoformat()+'Z',
            'state': rules.view(room.game, state['game'], str(acc.id)) if 'game' in state else None}
    if result['practice']:
        result['members'] += [{key: bot[key] for key in ('id', 'name', 'character', 'ready', 'isBot')}
                              for bot in state.get('practiceBots', [])]
        thinking = room.status == 'playing' and not expired and bool(state.get('nextBotAt'))
        result.update(botThinking=thinking, nextBotAt=state.get('nextBotAt') if thinking else None)
    if room.game in ('chess', 'checkers'):
        result['reactionOptions'] = list(BOARD_REACTIONS)
        # This projection contains only the deliberately shared reaction events;
        # neither private cooldown state nor request receipts leave the server.
        result['reactions'] = _live_reactions(state, datetime.utcnow())
    return result


def listing(db, acc, game):
    rules.require(isinstance(game, str) and game in rules.GAMES)
    active = _active(db, acc)
    if not active:
        # A disconnect during the final move must not lose the result or its reward.
        claimed = db.query(MinarResult.id).filter(
            MinarResult.account_id == acc.id,
            MinarResult.result_id == 'table:' + Room.id).exists()
        active = db.query(Room).join(Player, Player.room_id == Room.id).filter(
            Player.account_id == acc.id, Room.game == game,
            Room.status == 'finished', ~claimed).order_by(Room.updated_at.desc()).first()
    return {'active': _public(db, acc, active) if active else None}


def servers(db, acc, game=None, offset=0, limit=30):
    """Public waiting-room metadata only; joining revalidates under a room lock."""
    from .service import public_name
    _limited(acc, 'servers', 90)
    rules.require(game is None or game in rules.GAMES, 'O‘yin topilmadi.')
    rules.require(type(offset) is int and 0 <= offset <= 10000 and type(limit) is int and 1 <= limit <= 50)
    counts = db.query(Player.room_id, func.count(Player.id).label('count')).group_by(Player.room_id).subquery()
    capacity = case({key: value[1] for key, value in rules.GAMES.items()}, value=Room.game, else_=0)
    query = db.query(Room, MinarAccount, models.Student.full_name, counts.c.count).join(
        counts, counts.c.room_id == Room.id).join(MinarAccount, MinarAccount.id == Room.host_id).join(
        models.Student, models.Student.id == MinarAccount.student_id).filter(
        Room.status == 'waiting', Room.expires_at > datetime.utcnow(), Room.game != 'sudoku',
        counts.c.count < capacity, MinarAccount.is_active.is_(True),
        or_(MinarAccount.is_test.is_(True), models.Student.is_active.is_(True), models.Student.is_archived.is_(True)))
    if game is not None:
        query = query.filter(Room.game == game)
    rows = query.order_by(Room.created_at.desc(), Room.id.desc()).offset(offset).limit(limit + 1).all()
    rooms = []
    for room, host, full_name, count in rows[:limit]:
        # Practice starts immediately; also exclude any legacy/recovered waiting practice state.
        if practice_rooms.is_practice(json.loads(room.state)):
            continue
        name = public_name(full_name)
        rooms.append({'code': room.code, 'game': room.game, 'title': name,
                      'host': {'id': str(host.id), 'name': name, 'character': host.character},
                      'count': count, 'capacity': rules.GAMES[room.game][1], 'minPlayers': rules.GAMES[room.game][0],
                      'createdAt': room.created_at.isoformat() + 'Z', 'expiresAt': room.expires_at.isoformat() + 'Z'})
    more = len(rows) > limit
    return {'rooms': rooms, 'offset': offset, 'limit': limit, 'hasMore': more, 'nextOffset': offset + limit if more else None}


def create(db, acc, payload):
    _limited(acc, 'create', 10)
    game = payload.get('game')
    rules.require(isinstance(game, str) and game in rules.GAMES, 'O‘yin topilmadi.')
    practice = payload.get('practice', False)
    rules.require(type(practice) is bool, 'Mashq sozlamasi noto‘g‘ri.')
    _account_lock(db, acc)
    active = _active(db, acc)
    if active:
        if active.game != game or practice_rooms.is_practice(json.loads(active.state)) != practice:
            raise MinarError(409, 'Avval ochiq o‘yiningizni yakunlang yoki xonadan chiqing.')
        return _public(db, acc, active)
    code = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(8))
    room = Room(id=str(uuid.uuid4()), code=code, game=game, host_id=acc.id, status='waiting', state='{}', version=1, expires_at=datetime.utcnow()+timedelta(minutes=30))
    db.add(room); db.flush()
    db.add(Player(room_id=room.id, account_id=acc.id, ready=True)); db.flush()
    if practice or game == 'sudoku':
        state = (practice_rooms.create(game, str(acc.id)) if practice else
                 {'game': rules.new_game(game, [str(acc.id)]), 'receipts': []})
        room.status = 'playing'
        room.expires_at = datetime.utcnow()+timedelta(hours=2)
        _deadline(room, state)
        room.state = json.dumps(state)
    db.commit()
    return _public(db, acc, room)


def join(db, acc, code):
    _limited(acc, 'join', 20)
    rules.require(isinstance(code, str) and len(code) == 8)
    _account_lock(db, acc)
    active = _active(db, acc)
    if active and active.code != code.upper():
        raise MinarError(409, 'Sizda boshqa ochiq xona bor. Avval undan chiqing.')
    room = db.query(Room).filter_by(code=code.upper()).populate_existing().with_for_update().first()
    if not room or room.expires_at <= datetime.utcnow():
        raise MinarError(404, 'Xona topilmadi yoki vaqti tugagan.')
    if practice_rooms.is_practice(json.loads(room.state)) and room.host_id != acc.id:
        raise MinarError(403, 'Kompyuter bilan mashq shaxsiy o‘yin hisoblanadi.')
    members = _members(db, room)
    if any(m.account_id == acc.id for m in members):
        return _public(db, acc, room)
    rules.require(room.status == 'waiting' and room.game != 'sudoku', 'O‘yin boshlangan.')
    rules.require(len(members) < rules.GAMES[room.game][1], 'Xona to‘lgan.')
    db.add(Player(room_id=room.id, account_id=acc.id, ready=False))
    room.version += 1
    db.commit()
    return _public(db, acc, room)


def get(db, acc, code):
    return _public(db, acc, _room(db, acc, code))


def _deadline(room, state):
    g = state['game']
    if g['finished'] or room.game == 'sudoku':
        state['deadline'] = None
    else:
        seconds = (expanded.phase_seconds(room.game, g) if room.game in expanded.GAMES else
                   rules.MAFIA_PHASE_SECONDS[g['phase']] if room.game == 'mafia' else 300)
        now = datetime.utcnow()
        state['phaseStartedAt'] = now.isoformat()+'Z'
        state['deadline'] = (now+timedelta(seconds=seconds)).isoformat()+'Z'


def act(db, acc, code, payload):
    _limited(acc, 'action', 240)
    req = payload.get('requestId')
    rules.require(isinstance(req, str) and 8 <= len(req) <= 64, 'So‘rov kaliti kerak.')
    _account_lock(db, acc)
    room = _room(db, acc, code, lock=True)
    state = json.loads(room.state)
    receipt = str(acc.id)+':'+req
    if receipt in state.get('receipts', []):
        return _public(db, acc, room)
    kind = payload.get('type')
    if room.expires_at <= datetime.utcnow() and room.status != 'finished':
        raise MinarError(410, 'Xona vaqti tugagan. Yangi xona oching.')
    if kind == 'reaction':
        rules.require(room.game in ('chess', 'checkers') and room.status in ('playing', 'finished'), 'Reaksiya o‘yin vaqtida yuboriladi.')
        rules.require(str(acc.id) in state.get('game', {}).get('players', []), 'Siz bu o‘yin ishtirokchisi emassiz.')
        reaction = payload.get('reaction')
        rules.require(isinstance(reaction, str) and reaction in BOARD_REACTIONS, 'Ro‘yxatdagi reaksiyani tanlang.')
        now = datetime.utcnow()
        previous = state.get('reactionTimes', {}).get(str(acc.id))
        if previous and now < datetime.fromisoformat(previous.rstrip('Z')) + timedelta(seconds=REACTION_COOLDOWN_SECONDS):
            raise MinarError(429, 'Keyingi reaksiya uchun 3 soniya kuting.')
        _limited(acc, 'reaction', 8)
        now_text = now.isoformat() + 'Z'
        event = {'id': secrets.token_hex(8), 'player': str(acc.id), 'reaction': reaction,
                 'createdAt': now_text, 'expiresAt': (now + timedelta(seconds=REACTION_SECONDS)).isoformat() + 'Z'}
        state['reactions'] = (_live_reactions(state, now) + [event])[-12:]
        state.setdefault('reactionTimes', {})[str(acc.id)] = now_text
        state['receipts'] = (state.get('receipts', []) + [receipt])[-100:]
        room.state = json.dumps(state)
        # Reactions are independent of the turn. They must not invalidate a
        # legal move already selected by the opponent or restart any clock.
        room.updated_at = now
        db.commit()
        return _public(db, acc, room)
    # Mafia choices/chat concern a phase, not incidental chat or another player's
    # private choice. A phase key allows simultaneous actions without weakening
    # the optimistic version check for turn-based games or older clients.
    mafia_phase_action = (
        room.game == 'mafia' and room.status == 'playing'
        and kind in ('chat', 'choose', 'abstain', 'discussion-ready', 'discussion_ready')
        and payload.get('phaseKey') is not None
    )
    if mafia_phase_action and payload['phaseKey'] != rules.mafia_phase_key(state['game']):
        raise MinarError(409, 'Bosqich yangilandi. Yangi vaziyatni tekshiring.')
    expanded_phase_action = (room.game in expanded.GAMES and room.status == 'playing'
                             and expanded.phase_actions(room.game, kind))
    if expanded_phase_action and payload.get('phaseKey') != expanded.phase_key(state['game']):
        raise MinarError(409, 'Bosqich yangilandi. Yangi vaziyatni tekshiring.')
    if kind not in ('tick', 'leave') and not mafia_phase_action and not expanded_phase_action and payload.get('version') != room.version:
        raise MinarError(409, 'Xona yangilandi. Yurishni yana tanlang.')
    members = _members(db, room)
    now = datetime.utcnow()
    if kind == 'leave':
        if room.status == 'waiting':
            db.delete(next(m for m in members if m.account_id == acc.id))
            remaining = [m for m in members if m.account_id != acc.id]
            if remaining:
                room.host_id = remaining[0].account_id
                remaining[0].ready = True
            else:
                room.status = 'finished'
        elif room.status == 'playing':
            rules.finish(state['game'], [], 'abandoned')
            room.status = 'finished'
        state['deadline'] = None
    elif room.status == 'waiting':
        if kind == 'ready':
            member = next(m for m in members if m.account_id == acc.id)
            member.ready = bool(payload.get('ready'))
        elif kind == 'start':
            rules.require(room.host_id == acc.id, 'Faqat xona egasi boshlaydi.')
            rules.require(len(members) >= rules.GAMES[room.game][0] and all(m.ready for m in members), 'Barcha o‘quvchilar tayyor bo‘lishi kerak.')
            ids = [str(m.account_id) for m in members]
            rules.RNG.shuffle(ids)
            state['game'] = rules.new_game(room.game, ids)
            room.status = 'playing'
            room.expires_at = now+timedelta(hours=2)
            _deadline(room, state)
        else:
            rules.require(False, 'O‘yin hali boshlanmadi.')
    elif room.status == 'playing':
        g = state['game']
        expired = state.get('deadline') and now >= datetime.fromisoformat(state['deadline'].rstrip('Z'))
        before = (g['turn'], g.get('phase'), g.get('round'), g.get('plies'))
        previous_phase = expanded.phase_key(g) if room.game in expanded.GAMES else None
        if expired:
            if room.game in expanded.GAMES:
                expanded.advance(room.game, g)
            elif room.game == 'mafia':
                rules.mafia_advance(g)
            else:
                rules.finish(g, [], 'timeout')
            _deadline(room, state)
        elif kind == 'tick':
            previous_bot_phase = practice_rooms.phase(room.game, g)
            if not practice_rooms.pump(room.game, state, now):
                return _public(db, acc, room)
            if previous_bot_phase != practice_rooms.phase(room.game, g):
                _deadline(room, state)
        else:
            if kind == 'chat':
                _limited(acc, 'chat', 15)
            if room.game == 'draw':
                if kind == 'stroke':
                    _limited(acc, 'stroke', 160)
                elif kind == 'guess':
                    _limited(acc, 'guess', 30)
                elif kind == 'clear':
                    _limited(acc, 'clear', 12)
            rules.move(room.game, g, str(acc.id), payload)
            after = (g['turn'], g.get('phase'), g.get('round'), g.get('plies'))
            # Chat and partial night votes must never prolong a phase.
            changed = (previous_phase != expanded.phase_key(g) if room.game in expanded.GAMES else
                       before[1:3] != after[1:3] if room.game == 'mafia' else before != after)
            if changed:
                _deadline(room, state)
        if g['finished']:
            room.status = 'finished'
            state['deadline'] = None
        if practice_rooms.is_practice(state):
            practice_rooms.schedule(room.game, state)
    else:
        if kind == 'tick':
            return _public(db, acc, room)
        raise MinarError(409, 'O‘yin tugagan.')
    state['receipts'] = (state.get('receipts', [])+[receipt])[-100:]
    room.state = json.dumps(state)
    room.version += 1
    room.updated_at = now
    db.commit()
    return {'left': True} if kind == 'leave' else _public(db, acc, room)


def result(db, acc, room_id):
    rules.require(isinstance(room_id, str) and len(room_id) == 36)
    room = db.query(Room).filter_by(id=room_id, status='finished').first()
    rules.require(room and db.query(Player.id).filter_by(room_id=room_id, account_id=acc.id).first(), 'Yakunlangan o‘yin topilmadi.')
    room_state = json.loads(room.state)
    state = room_state.get('game', {})
    practice = practice_rooms.is_practice(room_state)
    rules.require(not practice or room.host_id == acc.id, 'Bu shaxsiy mashq xonasi.')
    won = str(acc.id) in state.get('winners', []) and state.get('reason') == 'completed'
    if room.game == 'quest':
        won = won and str(acc.id) in state.get('contributors', [])
    return {'game': room.game, 'roomId': room_id, 'won': won, 'practice': practice, 'draw': state.get('reason') == 'draw', 'reason': state.get('reason'), 'score': int(won)}, won and not practice
