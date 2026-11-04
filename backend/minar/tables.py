"""Authenticated online rooms. Lock order: caller account, then room.

Every move commits a version and request receipt. GET is read-only; phase clocks
advance through the authenticated tick action. No hidden roles/cards are serialized.
"""
import json
import secrets
import uuid
from datetime import datetime, timedelta
from sqlalchemy import select
from .. import models, security
from . import table_rules as rules
from .models import MinarAccount, MinarTableRoom as Room, MinarTablePlayer as Player, MinarResult
from .errors import MinarError


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
    return room


def _public(db, acc, room):
    from .service import public_name
    members = _members(db, room)
    accounts = db.query(MinarAccount, models.Student.full_name).join(models.Student, models.Student.id == MinarAccount.student_id).filter(MinarAccount.id.in_([m.account_id for m in members])).all()
    data = {a.id: {'id': str(a.id), 'profileId': a.login_id, 'name': public_name(name), 'character': a.character} for a, name in accounts}
    state = json.loads(room.state)
    expired = room.expires_at <= datetime.utcnow()
    return {'id': room.id, 'code': room.code, 'game': room.game,
            'status': 'expired' if expired and room.status != 'finished' else room.status,
            'host': str(room.host_id), 'me': str(acc.id), 'version': room.version,
            'members': [{**data[m.account_id], 'ready': m.ready} for m in members],
            'deadline': state.get('deadline'), 'phaseStartedAt': state.get('phaseStartedAt'), 'serverTime': datetime.utcnow().isoformat()+'Z',
            'state': rules.view(room.game, state['game'], str(acc.id)) if 'game' in state else None}


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
    # Codes are intentionally private; students share a code with classmates.
    return {'active': _public(db, acc, active) if active else None}


def create(db, acc, payload):
    _limited(acc, 'create', 10)
    game = payload.get('game')
    rules.require(isinstance(game, str) and game in rules.GAMES, 'O‘yin topilmadi.')
    _account_lock(db, acc)
    active = _active(db, acc)
    if active:
        if active.game != game:
            raise MinarError(409, 'Avval ochiq o‘yiningizni yakunlang yoki xonadan chiqing.')
        return _public(db, acc, active)
    code = ''.join(secrets.choice('ABCDEFGHJKLMNPQRSTUVWXYZ23456789') for _ in range(8))
    room = Room(id=str(uuid.uuid4()), code=code, game=game, host_id=acc.id, status='waiting', state='{}', version=1, expires_at=datetime.utcnow()+timedelta(minutes=30))
    db.add(room); db.flush()
    db.add(Player(room_id=room.id, account_id=acc.id, ready=True)); db.flush()
    if game == 'sudoku':
        state = {'game': rules.new_game(game, [str(acc.id)]), 'receipts': []}
        room.status = 'playing'
        room.expires_at = datetime.utcnow()+timedelta(hours=2)
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
        seconds = rules.MAFIA_PHASE_SECONDS[g['phase']] if room.game == 'mafia' else 300
        now = datetime.utcnow()
        state['phaseStartedAt'] = now.isoformat()+'Z'
        state['deadline'] = (now+timedelta(seconds=seconds)).isoformat()+'Z'


def act(db, acc, code, payload):
    _limited(acc, 'action', 100)
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
    if kind not in ('tick', 'leave') and not mafia_phase_action and payload.get('version') != room.version:
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
        if expired:
            if room.game == 'mafia':
                rules.mafia_advance(g)
            else:
                rules.finish(g, [], 'timeout')
            _deadline(room, state)
        elif kind == 'tick':
            return _public(db, acc, room)
        else:
            if kind == 'chat':
                _limited(acc, 'chat', 15)
            rules.move(room.game, g, str(acc.id), payload)
            after = (g['turn'], g.get('phase'), g.get('round'), g.get('plies'))
            # Chat and partial night votes must never prolong a phase.
            changed = before[1:3] != after[1:3] if room.game == 'mafia' else before != after
            if changed:
                _deadline(room, state)
        if g['finished']:
            room.status = 'finished'
            state['deadline'] = None
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
    state = json.loads(room.state).get('game', {})
    won = str(acc.id) in state.get('winners', []) and state.get('reason') == 'completed'
    return {'game': room.game, 'roomId': room_id, 'won': won, 'draw': state.get('reason') == 'draw', 'reason': state.get('reason'), 'score': int(won)}, won
