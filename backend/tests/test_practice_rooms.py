"""Authenticated practice, pacing, privacy, reward exclusion and room discovery."""
import json
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.minar import games, service, table_rules as rules
from backend.minar.models import MinarAccount, MinarTableRoom as Room, MinarTablePlayer as Player, MinarResult, MinarGameSession
from backend.tests.test_minar import acct, _minar_env, new_account, login, post


def action(client, room, kind, **kwargs):
    current = client.get('/space/tables/' + room['code']).json()
    body = {'type': kind, 'version': current['version'], 'requestId': str(uuid.uuid4()), **kwargs}
    if (current.get('state') or {}).get('phaseKey'):
        body.setdefault('phaseKey', current['state']['phaseKey'])
    response = post(client, '/tables/' + room['code'] + '/actions', body)
    assert response.status_code == 200, response.text
    return response.json()


def peer_account(client, db, token, name='Sherik Maxfiy'):
    peer = TestClient(app)
    student, creds = new_account(client, db, token, name)
    login(peer, creds)
    return peer, student


def due(db, room):
    db.expire_all()
    stored = db.get(Room, room['id'])
    state = json.loads(stored.state)
    state['nextBotAt'] = (datetime.utcnow() - timedelta(seconds=1)).isoformat() + 'Z'
    stored.state = json.dumps(state)
    db.commit()


@pytest.mark.parametrize('game', list(rules.GAMES))
def test_every_table_game_starts_practice_without_real_bot_accounts(client, db, acct, game):
    accounts_before = db.query(MinarAccount).count()
    response = post(client, '/tables', {'game': game, 'practice': True})
    assert response.status_code == 200, response.text
    room = response.json()
    assert room['status'] == 'playing' and room['practice'] is True
    assert room['me'] == room['host'] and room['state']['players'][0] == room['me']
    assert rules.GAMES[game][0] <= len(room['members']) <= rules.GAMES[game][1]
    assert len(room['members']) == (12 if game == 'mafia' else len(room['state']['players']))
    bots = [member for member in room['members'] if member['isBot']]
    assert len(bots) == len(room['members']) - 1
    assert all(bot['id'].startswith('bot:') and bot['name'].startswith('Kompyuter') and 'profileId' not in bot for bot in bots)
    assert db.query(MinarAccount).count() == accounts_before
    assert db.query(Player).filter_by(room_id=room['id']).count() == 1
    assert not {'roles', 'hands', 'deck', 'solution', 'botMemory', 'questions', 'fleets'} & room['state'].keys()
    assert not {'botMemory', 'practiceBots', 'receipts'} & room.keys()
    assert client.get('/space/tables/servers').json()['rooms'] == []
    assert client.get('/space/tables?game=' + game).json()['active']['id'] == room['id']
    before = db.get(Room, room['id']).state
    client.get('/space/tables/' + room['code'])
    db.expire_all()
    assert db.get(Room, room['id']).state == before
    due(db, room)
    ticked = action(client, room, 'tick')
    assert ticked['practice'] and ticked['status'] == 'playing'


def test_practice_is_owner_only_and_mode_mismatch_is_not_silent(client, db, acct, metodist_token):
    peer, _ = peer_account(client, db, metodist_token)
    room = post(client, '/tables', {'game': 'uno', 'practice': True}).json()
    assert peer.get('/space/tables/' + room['code']).status_code == 403
    assert post(peer, '/tables/' + room['code'] + '/join').status_code == 403
    assert post(peer, '/tables/' + room['code'] + '/actions', {'type': 'tick', 'requestId': str(uuid.uuid4())}).status_code == 403
    assert post(client, '/tables', {'game': 'uno'}).status_code == 409
    assert post(client, '/tables', {'game': 'uno', 'practice': True}).json()['id'] == room['id']
    assert TestClient(app).get('/space/tables/servers').status_code == 401


def test_chess_bot_ticks_are_paced_read_only_get_and_idempotent(client, db, acct):
    room = post(client, '/tables', {'game': 'chess', 'practice': True}).json()
    room = action(client, room, 'move', move='e2e4')
    assert room['botThinking'] and room['nextBotAt']
    assert room['state']['turn'] == 1
    version = room['version']
    assert action(client, room, 'tick')['version'] == version
    due(db, room)
    before = client.get('/space/tables/' + room['code']).json()
    assert before['state']['turn'] == 1
    payload = {'type': 'tick', 'requestId': str(uuid.uuid4())}
    moved = post(client, '/tables/' + room['code'] + '/actions', payload).json()
    assert moved['version'] == version + 1 and moved['state']['turn'] == 0
    assert len(moved['state']['log']) == 2 and not moved['botThinking']
    repeated = post(client, '/tables/' + room['code'] + '/actions', payload).json()
    assert repeated['version'] == moved['version'] and repeated['state']['log'] == moved['state']['log']
    stale = post(client, '/tables/' + room['code'] + '/actions', {
        'type': 'move', 'move': 'g1f3', 'version': version, 'requestId': str(uuid.uuid4())})
    assert stale.status_code == 409


def test_practice_sudoku_win_cannot_farm_rewards_or_daily_quests(client, db, acct):
    room = post(client, '/tables', {'game': 'sudoku', 'practice': True}).json()
    stored = json.loads(db.get(Room, room['id']).state)
    room = action(client, room, 'solve', grid=stored['game']['solution'])
    assert room['status'] == 'finished' and room['state']['winners'] == [room['me']]
    body = {'result': {'roomId': room['id'], 'practice': False, 'xp': 999, 'lightning': 999, 'award': 999}}
    response = post(client, '/games/results', body)
    assert response.status_code == 200, response.text
    state = response.json()['state']
    assert state['xp'] == state['lightning'] == state['balance'] == 0
    assert state['dailyProgress']['games'] == 0
    assert state['results'][0]['practice'] and not state['results'][0]['eligible']
    assert not any(a['unlockedAt'] for a in state['achievements'] if a['id'] in ('sudoku_win', 'first_win'))
    assert post(client, '/games/results', body).json()['state']['xp'] == 0
    assert db.query(MinarResult).count() == 1
    assert client.get('/space/tables?game=sudoku').json()['active'] is None
    account = db.get(MinarAccount, int(room['me']))
    assert service._daily_competitive_games(db, account, service.today_key()) == []


@pytest.mark.parametrize('game', games.GAMES)
def test_legacy_practice_flags_survive_actions_and_cannot_be_spoofed(client, db, acct, monkeypatch, game):
    if game == 'quiz':
        from backend.minar import study
        monkeypatch.setattr(study, 'quiz_questions', lambda *args: [
            {'q': 'Mavzu savoli', 'code': '', 'options': ['A', 'B'], 'answer': 0, 'explain': 'To‘g‘ri', 'topic': 'CRM mavzusi'} for _ in range(5)])
    response = post(client, '/games/start', {'game': game, 'practice': True, 'duration': 10})
    assert response.status_code == 200, response.text
    session = response.json()
    assert session['practice'] is True
    sid = session['id']
    stored = db.get(MinarGameSession, sid)
    stored.started_at = datetime.utcnow() - timedelta(seconds=20)
    db.commit()
    finish = {'session': sid, 'practice': False, 'duration': 10}
    if game == 'quiz':
        for i in range(5):
            assert post(client, '/games/answer', {'session': sid, 'index': i, 'choice': 0}).status_code == 200
    elif game == 'memory':
        cards = games.memory_cards(stored.course, stored.seed)
        for word in sorted(set(cards)):
            for index, value in enumerate(cards):
                if value == word:
                    assert post(client, '/games/flip', {'session': sid, 'card': index}).status_code == 200
    elif game == 'typing':
        finish['typed'] = ' '.join(session['words'][:6])
    else:
        # Simulate distinct legal spawn timestamps without real sleeps; every hit
        # is still submitted through the authenticated, validating HTTP endpoint.
        for i in range(5):
            db.expire_all()
            stored = db.get(MinarGameSession, sid)
            st = json.loads(stored.state)
            st['hits'] = [{**h, 'at': h['at'] - 2} for h in st.get('hits', [])]
            stored.state = json.dumps(st)
            db.commit()
            assert post(client, '/games/hit', {'session': sid, 'index': i, 'word': session['words'][i]}).status_code == 200
        finish['hits'] = list(range(5))
    db.expire_all()
    assert json.loads(db.get(MinarGameSession, sid).state)['practice'] is True
    result = post(client, '/games/results', {'result': finish})
    assert result.status_code == 200, result.text
    data = result.json()['state']
    assert data['xp'] == data['lightning'] == data['balance'] == 0
    assert data['dailyProgress']['games'] == 0 and data['dailyProgress']['typing'] is False
    assert data['results'][0]['practice'] and data['results'][0]['eligible'] is False
    if game == 'typing':
        assert post(client, '/quests/claim', {'quest': 'typing'}).status_code == 400


def test_waiting_computers_back_off_without_losing_private_memory(client, db, acct, monkeypatch):
    from backend.minar import practice_bots
    room = post(client, '/tables', {'game': 'quest', 'practice': True}).json()
    calls = []
    def wait(game, state, bot, memory):
        calls.append(bot)
        memory.setdefault(bot, {})['observed'] = 'human turn'
        return None
    monkeypatch.setattr(practice_bots, 'choose_bot_action', wait)
    due(db, room)
    room = action(client, room, 'tick')
    assert len(calls) == 1
    assert datetime.fromisoformat(room['nextBotAt'].rstrip('Z')) > datetime.utcnow() + timedelta(seconds=2)
    version = room['version']
    for _ in range(3):
        assert action(client, room, 'tick')['version'] == version
    assert len(calls) == 1
    db.expire_all()
    assert json.loads(db.get(Room, room['id']).state)['botMemory']['bot:1']['observed'] == 'human turn'
    assert 'observed' not in json.dumps(room)


def test_servers_summary_join_capacity_host_transfer_and_archived_host(client, db, acct, metodist_token):
    peer, peer_student = peer_account(client, db, metodist_token, 'Sherik Maxfiy')
    outsider, _ = peer_account(client, db, metodist_token, 'Uchinchi Maxfiy')
    room = post(client, '/tables', {'game': 'chess'}).json()
    page = peer.get('/space/tables/servers?game=chess').json()
    assert len(page['rooms']) == 1 and page['hasMore'] is False
    summary = page['rooms'][0]
    assert summary['code'] == room['code'] and summary['title'] == 'Azizbek K.'
    assert summary['host'] == {'id': room['host'], 'name': 'Azizbek K.', 'character': room['members'][0]['character']}
    assert (summary['count'], summary['minPlayers'], summary['capacity']) == (1, 2, 2)
    assert set(summary) == {'code', 'game', 'title', 'host', 'count', 'capacity', 'minPlayers', 'createdAt', 'expiresAt'}
    assert 'profileId' not in json.dumps(summary) and 'state' not in summary
    assert peer.get('/space/tables/servers?game=uno').json()['rooms'] == []
    assert post(peer, '/tables/' + summary['code'] + '/join').status_code == 200
    assert outsider.get('/space/tables/servers').json()['rooms'] == []  # full
    assert post(outsider, '/tables/' + summary['code'] + '/join').status_code == 400
    action(client, room, 'leave')
    transferred = outsider.get('/space/tables/servers').json()['rooms'][0]
    assert transferred['title'] == 'Sherik M.' and transferred['host']['id'] != room['host']
    # Production auth explicitly permits archived students even if inactive.
    peer_student.is_active = False
    peer_student.is_archived = True
    db.commit()
    assert peer.get('/space/tables/' + room['code']).status_code == 200
    assert outsider.get('/space/tables/servers').json()['rooms'][0]['title'] == 'Sherik M.'
    assert post(client, '/tables/' + room['code'] + '/join').status_code == 200
    action(client, room, 'ready', ready=True)
    started = action(peer, room, 'start')
    assert started['status'] == 'playing'
    assert outsider.get('/space/tables/servers').json()['rooms'] == []


def test_servers_filter_expiry_and_paginate_with_bounded_input(client, db, acct, metodist_token):
    peer, _ = peer_account(client, db, metodist_token)
    a = post(client, '/tables', {'game': 'uno'}).json()
    b = post(peer, '/tables', {'game': 'mafia'}).json()
    first = client.get('/space/tables/servers?limit=1').json()
    assert len(first['rooms']) == 1 and first['hasMore'] and first['nextOffset'] == 1
    second = client.get('/space/tables/servers?limit=1&offset=1').json()
    assert len(second['rooms']) == 1 and not second['hasMore']
    assert first['rooms'][0]['code'] != second['rooms'][0]['code']
    stored = db.get(Room, b['id'])
    stored.expires_at = datetime.utcnow() - timedelta(seconds=1)
    db.commit()
    assert [r['code'] for r in client.get('/space/tables/servers').json()['rooms']] == [a['code']]
    assert post(client, '/tables/' + b['code'] + '/join').status_code in (404, 409)
    for query in ('limit=51', 'limit=0', 'offset=-1', 'offset=10001', 'game=unknown'):
        assert client.get('/space/tables/servers?' + query).status_code == 400
