"""Russian draughts movement and board-room reactions are server authoritative."""
import copy
import json
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.minar import table_rules as rules, tables
from backend.minar.errors import MinarError
from backend.minar.models import MinarLedger, MinarResult, MinarTableRoom
from backend.tests.test_minar import acct, _minar_env, new_account, login, post
from backend.tests.test_table_rooms import action, start_pair


def position(pieces, **values):
    state = rules.new_game('checkers', ['a', 'b'])
    state['board'] = [0] * 64
    for square, piece in pieces.items():
        state['board'][square] = piece
    state.update(values)
    state['repetitions'] = {rules._checker_turn_key(state): 1}
    return state


def move(state, source, target):
    rules.move('checkers', state, state['players'][state['turn']], {'type': 'move', 'from': source, 'to': target})


def test_flying_king_moves_all_free_diagonal_squares_both_directions():
    state = position({17: 2, 7: -1})
    targets = {item['to'] for item in rules.checker_moves(state)}
    assert targets == {8, 10, 3, 24, 26, 35, 44, 53, 62}
    move(state, 17, 62)
    assert state['board'][62] == 2 and state['board'][17] == 0
    assert state['turn'] == 1


def test_flying_king_captures_at_distance_with_choice_of_landing():
    state = position({1: 2, 28: -1, 56: -1})
    assert rules.checker_moves(state) == [
        {'from': 1, 'to': square, 'capture': 28} for square in (37, 46, 55)
    ]
    move(state, 1, 46)
    assert state['board'][28] == 0 and state['board'][46] == 2
    assert state['lastMove'] == {'from': 1, 'to': 46, 'capture': 28, 'promoted': False}


def test_king_cannot_jump_own_piece_two_enemies_or_blocked_landing():
    for blocker in (1, -1):
        state = position({1: 2, 19: -1, 28: blocker, 56: -1})
        assert not [m for m in rules.checker_moves(state) if m['from'] == 1 and 'capture' in m]
    state = position({1: 2, 19: 1, 37: -1})
    assert not [m for m in rules.checker_moves(state) if m['from'] == 1 and m['to'] >= 19]


def test_man_captures_backwards_but_steps_only_forward_and_capture_is_forced():
    state = position({35: 1, 26: -1, 7: -1, 55: 2})
    assert rules.checker_moves(state) == [{'from': 35, 'to': 17, 'capture': 26}]
    with pytest.raises(MinarError):
        move(state, 55, 46)
    move(state, 35, 17)
    assert state['board'][26] == 0
    state = position({35: 1, 7: -1})
    assert {m['to'] for m in rules.checker_moves(state)} == {42, 44}


def test_capture_choice_does_not_require_largest_count():
    state = position({17: 1, 21: 1, 26: -1, 30: -1, 44: -1})
    assert rules.checker_moves(state) == [
        {'from': 17, 'to': 35, 'capture': 26}, {'from': 21, 'to': 39, 'capture': 30}
    ]
    # The other route has two captures, but this valid one-capture route is allowed.
    move(state, 21, 39)
    assert state['turn'] == 1 and state['chain'] is None


def test_promotion_during_capture_continues_as_flying_king():
    state = position({42: 1, 51: -1, 46: -1, 7: -1})
    move(state, 42, 60)
    assert state['board'][60] == 2 and state['chain'] == 60 and state['turn'] == 0
    assert state['pendingCaptures'] == [51]
    assert rules.checker_moves(state) == [{'from': 60, 'to': 39, 'capture': 46}]
    with pytest.raises(MinarError):
        rules.move('checkers', state, 'b', {'type': 'move', 'from': 7, 'to': 14})
    move(state, 60, 39)
    assert state['board'][39] == 2 and state['board'][51] == state['board'][46] == 0
    assert state['pendingCaptures'] == [] and state['chain'] is None and state['turn'] == 1


def test_captured_pieces_block_reverse_recapture_until_whole_turn_finishes():
    state = position({17: 2, 35: -1, 30: -1, 8: -1})
    move(state, 17, 44)
    assert state['chain'] == 44 and state['pendingCaptures'] == [35]
    assert state['board'][35] == -1  # Not physically removed in the middle of a chain.
    assert rules.checker_moves(state) == [{'from': 44, 'to': 23, 'capture': 30}]
    view = rules.view('checkers', state, 'a')
    assert view['pendingCaptures'] == [35] and view['rulesVersion'] == rules.CHECKERS_RULES
    move(state, 44, 23)
    assert state['board'][35] == state['board'][30] == 0 and state['board'][8] == -1


def test_king_only_quiet_draw_and_man_move_resets_counter():
    state = position({17: 2, 7: -2}, quiet=29)
    move(state, 17, 24)
    assert state['finished'] and state['reason'] == 'draw'
    state = position({17: 1, 7: -2}, quiet=29)
    move(state, 17, 24)
    assert state['quiet'] == 0 and not state['finished']


def test_existing_rooms_keep_legacy_short_kings_and_no_backwards_man_capture():
    state = position({17: 2, 7: -1})
    del state['rulesVersion']
    assert {m['to'] for m in rules.checker_moves(state)} == {8, 10, 24, 26}
    assert rules.view('checkers', state, 'a')['rulesVersion'] == 'legacy-v1'
    state = position({35: 1, 26: -1, 7: -1})
    del state['rulesVersion']
    assert rules.checker_moves(state) == [{'from': 35, 'to': 42}, {'from': 35, 'to': 44}]


def test_chess_last_move_and_check_square_use_visible_board_indexes():
    state = rules.new_game('chess', ['a', 'b'])
    for uci in ('f2f3', 'e7e5', 'g2g4', 'd8h4'):
        rules.move('chess', state, state['players'][state['turn']], {'type': 'move', 'move': uci})
    view = rules.view('chess', state, 'a')
    assert view['lastMove'] == {'from': 3, 'to': 39, 'uci': 'd8h4', 'capture': False, 'promotion': None}
    assert view['checkedSquare'] == 60 and view['check'] is True


def test_reactions_are_shared_idempotent_and_do_not_change_turn_clock_or_version(client, db, acct, metodist_token):
    peer, room = start_pair(client, db, metodist_token, 'chess')
    initial_state = copy.deepcopy(room['state'])
    body = {'type': 'reaction', 'reaction': 'bravo', 'requestId': str(uuid.uuid4()), 'version': -1, 'player': 'forged'}
    url = '/tables/' + room['code'] + '/actions'
    response = post(client, url, body)
    assert response.status_code == 200, response.text
    shared = response.json()
    assert shared['version'] == room['version'] and shared['state'] == initial_state
    assert shared['deadline'] == room['deadline'] and shared['phaseStartedAt'] == room['phaseStartedAt']
    event = shared['reactions'][0]
    assert event['player'] == room['me'] and event['reaction'] == 'bravo'
    assert set(event) == {'id', 'player', 'reaction', 'createdAt', 'expiresAt'}
    assert peer.get('/space/tables/' + room['code']).json()['reactions'] == [event]
    assert post(client, url, body).json()['reactions'] == [event]
    assert post(client, url, {**body, 'requestId': str(uuid.uuid4())}).status_code == 429
    assert 'reactionTimes' not in json.dumps(shared) and 'receipts' not in shared
    assert db.query(MinarLedger).count() == db.query(MinarResult).count() == 0
    white = client if room['state']['players'][0] == room['me'] else peer
    # A reaction must not invalidate the opponent's already-selected move.
    played = post(white, url, {'type': 'move', 'move': 'e2e4', 'version': room['version'], 'requestId': str(uuid.uuid4())})
    assert played.status_code == 200


def test_reactions_allowlist_membership_and_game_scope(client, db, acct, metodist_token):
    _, room = start_pair(client, db, metodist_token, 'checkers')
    url = '/tables/' + room['code'] + '/actions'
    for reaction in ('<script>', '', ['bravo'], 'laugh-at-opponent', None):
        body = {'type': 'reaction', 'reaction': reaction, 'version': room['version'], 'requestId': str(uuid.uuid4())}
        assert post(client, url, body).status_code == 400
    outsider = TestClient(app)
    _, credentials = new_account(client, db, metodist_token, 'Outside Viewer')
    login(outsider, credentials)
    body = {'type': 'reaction', 'reaction': 'wow', 'requestId': str(uuid.uuid4())}
    assert post(outsider, url, body).status_code == 403
    assert post(TestClient(app), url, body).status_code == 401
    assert outsider.get('/space/tables/' + room['code']).status_code == 403
    action(client, room, 'leave')
    solo = post(client, '/tables', {'game': 'sudoku'}).json()
    assert post(client, '/tables/' + solo['code'] + '/actions', body).status_code == 400


def test_reactions_expire_without_get_mutation_and_work_after_game_finishes(client, db, acct, metodist_token):
    _, room = start_pair(client, db, metodist_token, 'chess')
    room = action(client, room, 'leave')
    # Finished members remain eligible for a brief sportsmanship reaction.
    stored = db.query(MinarTableRoom).filter_by(game='chess').one()
    snapshot = json.loads(stored.state)
    version, deadline = stored.version, snapshot.get('deadline')
    body = {'type': 'reaction', 'reaction': 'good-game', 'requestId': str(uuid.uuid4())}
    response = post(client, '/tables/' + stored.code + '/actions', body)
    assert response.status_code == 200
    assert response.json()['version'] == version and response.json()['deadline'] == deadline
    db.expire_all(); stored = db.get(MinarTableRoom, stored.id)
    snapshot = json.loads(stored.state)
    snapshot['reactions'][0]['expiresAt'] = (datetime.utcnow() - timedelta(seconds=1)).isoformat() + 'Z'
    stored.state = json.dumps(snapshot); db.commit()
    before = stored.state
    view = client.get('/space/tables/' + stored.code).json()
    assert view['reactions'] == []
    db.expire_all()
    assert db.get(MinarTableRoom, stored.id).state == before
    assert view['state']['reason'] == 'abandoned' and view['state']['winners'] == []


def test_reaction_minute_limit_still_applies_when_cooldown_has_elapsed(client, db, acct, metodist_token, monkeypatch):
    _, room = start_pair(client, db, metodist_token, 'checkers')
    clock = [datetime.utcnow()]

    class Clock(datetime):
        @classmethod
        def utcnow(cls):
            return clock[0]

    monkeypatch.setattr(tables, 'datetime', Clock)
    url = '/tables/' + room['code'] + '/actions'
    for _ in range(8):
        response = post(client, url, {'type': 'reaction', 'reaction': 'respect', 'requestId': str(uuid.uuid4())})
        assert response.status_code == 200
        assert len(response.json()['reactions']) <= 2
        clock[0] += timedelta(seconds=4)
    denied = post(client, url, {'type': 'reaction', 'reaction': 'respect', 'requestId': str(uuid.uuid4())})
    assert denied.status_code == 429
    assert client.get('/space/tables/' + room['code']).json()['version'] == room['version']
