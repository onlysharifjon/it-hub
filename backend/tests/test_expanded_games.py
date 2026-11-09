"""Rules, privacy and authenticated durable room flows for all eight additions."""
import copy
import itertools
import json
import random
import uuid
from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.minar import new_table_rules as r, table_rules, tables
from backend.minar.errors import MinarError
from backend.minar.models import MinarTableRoom, MinarResult
from backend.tests.test_minar import acct, _minar_env, new_account, login, post


def play(game, state, player, kind, **payload):
    table_rules.move(game, state, player, {'type': kind, **payload})


def ids(game):
    return [str(n+1) for n in range(r.GAMES[game][0])]


def rejected(call):
    with pytest.raises(MinarError):
        call()


def room_action(client, room, kind, **kw):
    current = client.get('/space/tables/'+room['code']).json()
    payload = {'type': kind, 'version': current['version'], 'requestId': str(uuid.uuid4()), **kw}
    if current.get('state', {}).get('phaseKey') if current.get('state') else False:
        payload.setdefault('phaseKey', current['state']['phaseKey'])
    response = post(client, '/tables/'+room['code']+'/actions', payload)
    assert response.status_code == 200, response.text
    return response.json()


def start_room(client, db, metodist_token, game):
    room = post(client, '/tables', {'game': game}).json()
    clients = [client]
    for index in range(r.GAMES[game][0]-1):
        tc = TestClient(app)
        _, credentials = new_account(client, db, metodist_token, f'Space Sherik {game} {index}')
        login(tc, credentials)
        response = post(tc, '/tables/'+room['code']+'/join')
        assert response.status_code == 200, response.text
        room_action(tc, room, 'ready', ready=True)
        clients.append(tc)
    room = room_action(client, room, 'start')
    by_id = {tc.get('/space/tables/'+room['code']).json()['me']: tc for tc in clients}
    return room, by_id


@pytest.mark.parametrize('game', list(r.GAMES))
def test_initial_views_have_contract_and_outsider_is_rejected(game):
    state = table_rules.new_game(game, ids(game))
    for player in state['players']:
        view = table_rules.view(game, state, player)
        assert view['players'] == state['players'] and view['phaseKey']
        assert view['phaseSeconds'] > 0 and view['winners'] == []
        assert not {'fleets', 'fired', 'hands', 'deck', 'keys', 'answers', 'questions'} & set(view)
        # Views are snapshots, not mutable handles into live server state.
        view['players'].clear()
        assert state['players']
    rejected(lambda: table_rules.move(game, state, 'outsider', {'type': 'move'}))
    rejected(lambda: table_rules.view(game, state, 'outsider'))


def test_draw_private_words_bounded_strokes_exact_scoring_and_complete_match():
    state = r.new_game('draw', ['a', 'b', 'c'])
    for round_number in range(1, 4):
        drawer = state['drawer']
        others = [p for p in state['players'] if p != drawer]
        assert r.view('draw', state, drawer)['word'] == state['word']
        assert all(r.view('draw', state, p)['word'] is None for p in others)
        rejected(lambda: play('draw', state, others[0], 'stroke', color=r.PALETTE[0], width=6, points=[[.2, .3]]))
        for points in [[[float('nan'), 0]], [[1.1, 0]], [[True, 0]], [[0, 0]]*121]:
            rejected(lambda: play('draw', state, drawer, 'stroke', color=r.PALETTE[0], width=6, points=points))
        rejected(lambda: play('draw', state, drawer, 'stroke', color='url(evil)', width=6, points=[[.2, .3]]))
        play('draw', state, drawer, 'stroke', color=r.PALETTE[2], width=6, points=[[.2, .3], [.3, .4]])
        assert len(r.view('draw', state, others[0])['strokes']) == 1
        phase = r.phase_key(state)
        word = state['word']
        play('draw', state, others[0], 'guess', text=word.upper())
        assert r.phase_key(state) == phase and state['scores'][others[0]] >= 100
        assert state['messages'][-1]['text'] == 'So‘zni topdi!'
        rejected(lambda: play('draw', state, others[0], 'guess', text=word))
        play('draw', state, others[1], 'guess', text=word)
        assert state['phase'] == 'reveal' and r.phase_key(state) != phase
        assert r.view('draw', state, others[0])['word'] == word
        r.advance('draw', state)
    assert state['finished'] and set(state['winners']) == {'a', 'b', 'c'}
    assert set(state['scores'].values()) == {260}


def test_draw_clear_and_no_score_timeout_cannot_mint_reward():
    state = r.new_game('draw', ['a', 'b', 'c'])
    play('draw', state, 'a', 'stroke', color=r.PALETTE[0], width=2, points=[[0, 0]])
    play('draw', state, 'a', 'clear')
    assert state['strokes'] == []
    for _ in range(6):
        r.advance('draw', state)
    assert state['finished'] and not state['winners'] and state['reason'] == 'draw'


FLEET_A = [[0, 1, 2, 3], [16, 24, 32], [54, 55]]
FLEET_B = [[8, 9, 10, 11], [20, 28, 36], [60, 61]]


def test_fleet_placement_privacy_hits_sinking_and_complete_win():
    state = r.new_game('fleet', ['a', 'b'])
    for invalid in [[[0,1,2,8],[16,24,32],[54,55]], [[0,1,2,3],[0,8,16],[54,55]], [[0,1,2,3],[16,24,32],[False,55]]]:
        rejected(lambda: play('fleet', state, 'a', 'deploy', ships=invalid))
    play('fleet', state, 'a', 'deploy', ships=FLEET_A)
    assert r.view('fleet', state, 'b')['ships'] == []
    rejected(lambda: play('fleet', state, 'a', 'deploy', ships=FLEET_A))
    play('fleet', state, 'b', 'deploy', ships=FLEET_B)
    assert state['phase'] == 'battle'
    rejected(lambda: play('fleet', state, 'b', 'fire', cell=0))
    misses = iter([4,5,6,7,12,13,14,15,18])
    targets = [cell for ship in FLEET_B for cell in ship]
    for cell in targets:
        play('fleet', state, 'a', 'fire', cell=cell)
        public = r.view('fleet', state, 'a')
        assert cell in public['hits'] and public['ships'] == FLEET_A
        assert all(set(ship).issubset(public['shots']) for ship in public['sunk'])
        if not state['finished']:
            play('fleet', state, 'b', 'fire', cell=next(misses))
            rejected(lambda: play('fleet', state, 'a', 'fire', cell=cell))
    assert state['finished'] and state['winners'] == ['a']


def solve_lights(cells):
    for bits in itertools.product((False, True), repeat=9):
        attempt = cells[:]
        for cell, press in enumerate(bits):
            if press:
                r.lights_toggle(attempt, cell)
        if not any(attempt):
            return [cell for cell, press in enumerate(bits) if press]
    raise AssertionError('Unsolvable Lights Out puzzle')


def solve_quest_stage(state):
    stage, puzzle = state['stage'], state['puzzle']
    if puzzle['kind'] == 'lights':
        for i, cell in enumerate(solve_lights(puzzle['cells'])):
            play('quest', state, state['players'][i % len(state['players'])], 'toggle', cell=cell)
    elif puzzle['kind'] == 'rotors':
        for i in range(3):
            while state['stage'] == stage and state['puzzle']['values'][i] != state['puzzle']['target'][i]:
                play('quest', state, state['players'][i % len(state['players'])], 'rotate', index=i)
    else:
        for player in state['players']:
            public = r.view('quest', state, player)['puzzle']
            assert 'code' not in public and 'clues' not in public and public['clue']
        play('quest', state, state['players'][0], 'code', code=puzzle['code'])
    assert state['stage'] == stage+1


def test_quest_solvable_cooperative_puzzles_private_clues_chat_and_finish():
    for count in (2, 3, 4):
        state = r.new_game('quest', [str(i) for i in range(count)])
        before = r.phase_key(state)
        play('quest', state, '0', 'chat', text='Quvvatni birga tiklaymiz!')
        assert not state['contributors'] and r.phase_key(state) == before
        for _ in range(6):
            solve_quest_stage(state)
        assert state['finished'] and state['winners'] == state['players'] and state['energy'] == 12
        assert len(state['contributors']) >= 2


def test_quest_wrong_code_costs_energy_and_timeout_never_awards():
    state = r.new_game('quest', ['a','b'])
    state['stage'] = 2
    r.quest_stage(state)
    wrong = '999' if state['puzzle']['code'] != '999' else '888'
    for _ in range(12):
        play('quest', state, 'a', 'code', code=wrong)
    assert state['finished'] and state['reason'] == 'energy' and not state['winners']
    second = r.new_game('quest', ['a','b'])
    r.advance('quest', second)
    assert second['reason'] == 'timeout' and not second['winners']


@pytest.mark.parametrize('count', [2,3,4])
def test_domino_full_match_orientation_private_hands_and_blocked_finish(count):
    state = r.new_game('domino', [str(i) for i in range(count)])
    all_tiles = [tile['id'] for hand in state['hands'].values() for tile in hand] + [tile['id'] for tile in state['deck']]
    assert len(all_tiles) == len(set(all_tiles)) == 28
    for _ in range(350):
        pid = state['players'][state['turn']]
        public = r.view('domino', state, pid)
        assert public['hand'] == state['hands'][pid] and 'hands' not in public and 'deck' not in public
        if public['legal']:
            chosen = public['legal'][0]
            play('domino', state, pid, 'play', tile=chosen['id'], side=chosen['side'])
        elif public['canDraw']:
            play('domino', state, pid, 'draw')
        else:
            play('domino', state, pid, 'pass')
        assert all(a['b'] == b['a'] for a,b in zip(state['chain'],state['chain'][1:]))
        if state['finished']:
            break
    assert state['finished']


def test_domino_forced_draw_pass_and_blocked_tie():
    state = r.new_game('domino', ['a','b'])
    rejected(lambda: play('domino', state, 'a', 'draw'))
    rejected(lambda: play('domino', state, 'a', 'pass'))
    state.update(chain=[{'id':'6-6','a':6,'b':6}], hands={'a':[{'id':'1-2','a':1,'b':2}], 'b':[{'id':'0-3','a':0,'b':3}]}, deck=[])
    play('domino', state, 'a', 'pass')
    play('domino', state, 'b', 'pass')
    assert state['finished'] and state['reason'] == 'draw' and state['winners'] == []


@pytest.mark.parametrize('columns', [[0,1,0,1,0,1,0], [0,0,1,1,2,2,3]])
def test_connect4_gravity_vertical_horizontal_wins_and_wrong_turn(columns):
    state = r.new_game('connect4', ['a','b'])
    rejected(lambda: play('connect4', state, 'b', 'drop', column=0))
    rejected(lambda: play('connect4', state, 'a', 'drop', column=True))
    for column in columns:
        pid = state['players'][state['turn']]
        play('connect4', state, pid, 'drop', column=column)
    assert state['finished'] and state['winners'] == ['a'] and len(state['winningCells']) == 4
    rejected(lambda: play('connect4', state, 'a', 'drop', column=4))


def test_connect4_full_column_and_diagonal():
    state = r.new_game('connect4', ['a','b'])
    for _ in range(6):
        play('connect4', state, state['players'][state['turn']], 'drop', column=6)
    rejected(lambda: play('connect4', state, state['players'][state['turn']], 'drop', column=6))
    state = r.new_game('connect4', ['a','b'])
    # Gravity-respecting board directly before a diagonal winning drop.
    for row,col in [(5,0),(4,1),(3,2)]: state['board'][row*7+col] = 1
    for row,col in [(5,1),(5,2),(4,2),(5,3),(4,3),(3,3)]: state['board'][row*7+col] = 2
    play('connect4', state, 'a', 'drop', column=3)
    assert state['winners'] == ['a'] and state['winningCells'] == [17,23,29,35]


def test_ludo_server_roll_entry_capture_safe_square_exact_home_and_three_sixes(monkeypatch):
    class Die:
        def randint(self,a,b): return 6
    monkeypatch.setattr(r,'RNG',Die())
    state = r.new_game('ludo',['a','b'])
    rejected(lambda: play('ludo',state,'a','move',token=0))
    play('ludo',state,'a','roll',value=1)
    assert state['rolled'] == 6
    play('ludo',state,'a','move',token=0)
    assert state['tokens']['a'][0] == 0 and state['turn'] == 0
    play('ludo',state,'a','roll');play('ludo',state,'a','move',token=0)
    play('ludo',state,'a','roll')
    assert state['turn'] == 1 and state['rolled'] is None and state['lastRoll']['forfeited']
    state.update(turn=0,rolled=1)
    state['tokens']['a'][0] = 4
    state['tokens']['b'][0] = 44 # start13 +44 wraps to absolute5
    play('ludo',state,'a','move',token=0)
    assert state['tokens']['b'][0] == -1 and state['lastMove']['captured'] == [{'player':'b','token':0}]
    state.update(turn=0,rolled=1)
    state['tokens']['a'][0] = 7
    state['tokens']['b'][0] = 47 # absolute8 safe
    play('ludo',state,'a','move',token=0)
    assert state['tokens']['b'][0] == 47
    state.update(turn=0,rolled=2)
    state['tokens']['a'] = [56,57,57,57]
    assert r.ludo_legal(state,'a') == []
    state['rolled'] = 1
    play('ludo',state,'a','move',token=0)
    assert state['finished'] and state['winners'] == ['a']


def test_ludo_random_complete_match(monkeypatch):
    monkeypatch.setattr(r,'RNG',random.Random(901))
    state = r.new_game('ludo',['a','b','c','d'])
    for _ in range(2500):
        pid=state['players'][state['turn']]
        if state['rolled'] is None:
            play('ludo',state,pid,'roll')
        else:
            legal=r.ludo_legal(state,pid)
            assert legal
            play('ludo',state,pid,'move',token=max(legal,key=lambda i:state['tokens'][pid][i]))
        if state['finished']:break
    assert state['finished'] and len(state['winners'])==1


def test_codenames_roles_key_privacy_clue_validation_and_team_win():
    state=r.new_game('codenames',['a','b','c','d'])
    for player in ('a','b'):
        assert None not in r.view('codenames',state,player)['colors']
    for player in ('c','d'):
        assert r.view('codenames',state,player)['colors']==[None]*25
    rejected(lambda:play('codenames',state,'c','clue',word='Tabiat',count=2))
    rejected(lambda:play('codenames',state,'a','clue',word=state['words'][0],count=1))
    rejected(lambda:play('codenames',state,'a','clue',word='Ikki so‘z',count=1))
    play('codenames',state,'a','clue',word='Birlik',count=9)
    rejected(lambda:play('codenames',state,'a','guess',cell=0))
    rejected(lambda:play('codenames',state,'d','guess',cell=0))
    for cell,key in enumerate(state['keys']):
        if key == 0:
            play('codenames',state,'c','guess',cell=cell)
    assert state['finished'] and state['winners']==['a','c']


def test_codenames_trap_neutral_enemy_and_timeout():
    for color in ('trap','neutral',1):
        state=r.new_game('codenames',['a','b','c','d'])
        key=r.phase_key(state)
        play('codenames',state,'a','clue',word='Ufq',count=2)
        play('codenames',state,'c','guess',cell=state['keys'].index(color))
        if color == 'trap':assert state['winners']==['b','d']
        else:
            assert state['phase']=='clue' and state['teamTurn']==1 and r.phase_key(state)!=key
            revealed=r.view('codenames',state,'d')['colors']
            assert sum(c is not None for c in revealed)==1
    state=r.new_game('codenames',['a','b','c','d'])
    for _ in range(6):r.advance('codenames',state)
    assert state['finished'] and state['reason']=='timeout' and not state['winners']


def test_geography_hides_answers_until_reveal_unique_questions_and_full_match():
    state=r.new_game('geography',['a','b'])
    assert len({(q['kind'],q['prompt'],q.get('flag')) for q in state['questions']})==8
    assert {'flag','capital','landmark','shape'} <= {q['kind'] for q in state['questions']}
    for _ in range(8):
        a=r.view('geography',state,'a')
        assert 'answer' not in a and 'explanation' not in a and 'answer' not in a['question']
        answer=state['question']['answer']
        play('geography',state,'a','answer',choice=answer)
        rejected(lambda:play('geography',state,'a','answer',choice=answer))
        assert r.view('geography',state,'b')['myAnswer'] is None
        play('geography',state,'b','answer',choice=(answer+1)%4)
        assert r.view('geography',state,'b')['answer']==answer
        r.advance('geography',state)
    assert state['finished'] and state['winners']==['a'] and state['scores']=={'a':800,'b':0}


@pytest.mark.parametrize('game', list(r.GAMES))
def test_real_room_start_first_action_privacy_reconnect_receipt_and_auth(client,db,acct,metodist_token,game):
    room, clients=start_room(client,db,metodist_token,game)
    state=room['state']
    pid=state['players'][state['turn']]
    actor=clients[pid]
    room=actor.get('/space/tables/'+room['code']).json()
    state=room['state']
    actions={
        'draw':{'type':'stroke','color':r.PALETTE[0],'width':6,'points':[[0,0],[1,1]]},
        'fleet':{'type':'deploy','ships':FLEET_A},
        'quest':{'type':'toggle','cell':0},
        'domino':{'type':'play','tile':state.get('legal',[{}])[0].get('id') if game=='domino' else None,'side':'right'},
        'connect4':{'type':'drop','column':3},
        'ludo':{'type':'roll'},
        'codenames':{'type':'clue','word':'Ufq','count':2},
        'geography':{'type':'answer','choice':0},
    }
    payload={**actions[game],'version':room['version'],'phaseKey':state['phaseKey'],'requestId':str(uuid.uuid4())}
    path='/tables/'+room['code']+'/actions'
    if r.phase_actions(game,payload['type']):
        bad=post(actor,path,{**payload,'phaseKey':'stale'})
        assert bad.status_code==409
    changed=post(actor,path,payload)
    assert changed.status_code==200,changed.text
    receipt=post(actor,path,payload)
    assert receipt.status_code==200 and receipt.json()['version']==changed.json()['version']
    resumed=actor.get('/space/tables?game='+game).json()['active']
    assert resumed['id']==room['id'] and resumed['version']==changed.json()['version']
    for tc in clients.values():
        projection=tc.get('/space/tables/'+room['code']).json()['state']
        assert not {'fleets','fired','hands','deck','keys','answers','questions'} & set(projection)
        if game=='geography':
            assert 'answer' not in projection['question'] and 'explanation' not in projection['question']
        if game=='quest':
            assert 'code' not in projection['puzzle'] and 'clues' not in projection['puzzle']
    assert TestClient(app).get('/space/tables/'+room['code']).status_code==401
    assert post(actor,'/games/results',{'result':{'roomId':room['id'],'won':True,'xp':999}}).status_code==400


def test_simultaneous_draw_actions_keep_deadline_and_reject_old_round(client,db,acct,metodist_token):
    room, clients=start_room(client,db,metodist_token,'draw')
    state=room['state'];drawer=state['drawer'];others=[p for p in state['players'] if p!=drawer]
    word=clients[drawer].get('/space/tables/'+room['code']).json()['state']['word']
    original_deadline=room['deadline'];old_key=state['phaseKey']
    first=post(clients[others[0]],'/tables/'+room['code']+'/actions',{'type':'guess','text':word,'phaseKey':old_key,'version':room['version'],'requestId':str(uuid.uuid4())})
    assert first.status_code==200 and first.json()['deadline']==original_deadline
    second=post(clients[others[1]],'/tables/'+room['code']+'/actions',{'type':'guess','text':word,'phaseKey':old_key,'version':room['version'],'requestId':str(uuid.uuid4())})
    assert second.status_code==200 and second.json()['state']['phase']=='reveal'
    stale=post(clients[drawer],'/tables/'+room['code']+'/actions',{'type':'clear','phaseKey':old_key,'version':second.json()['version'],'requestId':str(uuid.uuid4())})
    assert stale.status_code==409


def test_connect4_real_win_rewards_once_daily_limit_and_no_coins(client,db,acct,metodist_token):
    room,clients=start_room(client,db,metodist_token,'connect4')
    winner=room['state']['players'][0]
    for col in [0,1,0,1,0,1,0]:
        room=room_action(clients[room['state']['players'][room['state']['turn']]],room,'drop',column=col)
    assert room['status']=='finished' and room['state']['winners']==[winner]
    body={'result':{'roomId':room['id'],'game':'anything','won':True,'xp':9999,'lightning':9999,'award':9999}}
    for pid,tc in clients.items():
        first=post(tc,'/games/results',body)
        assert first.status_code==200,first.text
        state=first.json()['state']
        assert state['balance']==0 and state['xp']==(5 if pid==winner else 0) and state['lightning']==(2 if pid==winner else 0)
        again=post(tc,'/games/results',body).json()['state']
        assert again['xp']==state['xp'] and again['lightning']==state['lightning']
    assert db.query(MinarResult).count()==2


def test_quest_result_requires_actual_contribution_and_timeouts_do_not_reward(client,db,acct,metodist_token):
    room,clients=start_room(client,db,metodist_token,'quest')
    stored=db.get(MinarTableRoom,room['id']);data=json.loads(stored.state)
    active=room['state']['players'][0];passive=room['state']['players'][1]
    # Solve a full match via authoritative rules; chat alone never earns participation.
    for _ in range(6):
        s=data['game'];p=s['puzzle'];stage=s['stage']
        if p['kind']=='lights':
            for cell in solve_lights(p['cells']):play('quest',s,active,'toggle',cell=cell)
        elif p['kind']=='rotors':
            for i in range(3):
                while s['stage']==stage and s['puzzle']['values'][i]!=s['puzzle']['target'][i]:play('quest',s,active,'rotate',index=i)
        else:play('quest',s,active,'code',code=p['code'])
    stored.state=json.dumps(data);stored.status='finished';db.commit()
    for pid,tc in clients.items():
        state=post(tc,'/games/results',{'result':{'roomId':room['id']}}).json()['state']
        assert state['xp']==(5 if pid==active else 0) and state['balance']==0
    assert passive not in data['game']['contributors']


def test_server_clock_tick_advances_geography_not_early_and_preserves_answers(client,db,acct,metodist_token):
    room,clients=start_room(client,db,metodist_token,'geography')
    deadline=room['deadline'];version=room['version']
    early=room_action(client,room,'tick')
    assert early['version']==version and early['deadline']==deadline
    stored=db.get(MinarTableRoom,room['id']);data=json.loads(stored.state)
    data['deadline']=(datetime.utcnow()-timedelta(seconds=1)).isoformat()+'Z'
    stored.state=json.dumps(data);db.commit()
    revealed=room_action(client,room,'tick')
    assert revealed['state']['phase']=='reveal' and 'answer' in revealed['state']
    assert revealed['state']['scores']=={p:0 for p in room['state']['players']}


def test_four_real_connect4_wins_only_three_rewards(client,db,acct,metodist_token):
    room,clients=start_room(client,db,metodist_token,'connect4')
    winning_id=next(pid for pid,tc in clients.items() if tc is client)
    for match in range(4):
        if match:
            room=post(client,'/tables',{'game':'connect4'}).json()
            peer=next(tc for tc in clients.values() if tc is not client)
            assert post(peer,'/tables/'+room['code']+'/join').status_code==200
            room_action(peer,room,'ready',ready=True)
            room=room_action(client,room,'start')
        # Whichever seat was randomly dealt first, the nominated player obtains
        # an actual vertical four; the other seat spreads legal moves across columns.
        other_columns=iter([2,4,2,4])
        while room['status']=='playing':
            pid=room['state']['players'][room['state']['turn']]
            room=room_action(clients[pid],room,'drop',column=0 if pid==winning_id else next(other_columns))
        assert room['state']['winners']==[winning_id]
        for tc in clients.values():
            response=post(tc,'/games/results',{'result':{'roomId':room['id']}})
            assert response.status_code==200,response.text
            if tc is client:
                state=response.json()['state']
                assert state['xp']==min(match+1,3)*5 and state['lightning']==min(match+1,3)*2
                assert state['balance']==0


def test_room_membership_origin_leave_and_board_stale_versions(client,db,acct,metodist_token):
    room,clients=start_room(client,db,metodist_token,'connect4')
    outsider=TestClient(app)
    _,credentials=new_account(client,db,metodist_token,'Outside Demo')
    login(outsider,credentials)
    assert outsider.get('/space/tables/'+room['code']).status_code==403
    assert post(outsider,'/tables/'+room['code']+'/join').status_code==400
    actor=clients[room['state']['players'][0]]
    payload={'type':'drop','column':0,'version':room['version'],'requestId':str(uuid.uuid4())}
    assert actor.post('/space/tables/'+room['code']+'/actions',json=payload,headers={'Origin':'https://untrusted.invalid'}).status_code==403
    changed=post(actor,'/tables/'+room['code']+'/actions',payload)
    assert changed.status_code==200
    opponent=clients[room['state']['players'][1]]
    stale=post(opponent,'/tables/'+room['code']+'/actions',{**payload,'requestId':str(uuid.uuid4())})
    assert stale.status_code==409
    left=room_action(actor,room,'leave')
    assert left=={'left':True}
    final=opponent.get('/space/tables/'+room['code']).json()
    assert final['status']=='finished' and final['state']['reason']=='abandoned' and not final['state']['winners']
    for tc in clients.values():
        result=post(tc,'/games/results',{'result':{'roomId':room['id'],'won':True}}).json()['state']
        assert result['xp']==0 and result['lightning']==0 and result['balance']==0
