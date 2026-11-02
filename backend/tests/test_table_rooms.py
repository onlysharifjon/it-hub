"""Real room flows, private projections, durable results and game rule edge cases."""
import json
import uuid
from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient
from backend.main import app
from backend.minar import table_rules as r, tables, service
from backend.minar.errors import MinarError
from backend.minar.models import MinarAccount, MinarTableRoom, MinarResult
from backend.tests.test_minar import acct, _minar_env, new_account, login, post


def action(client, room, kind, **kw):
    room = client.get('/space/tables/'+room['code']).json()
    response = post(client, '/tables/'+room['code']+'/actions', {'type':kind, 'version':room['version'], 'requestId':str(uuid.uuid4()), **kw})
    assert response.status_code == 200, response.text
    return response.json()


def start_pair(client, db, metodist_token, game):
    peer = TestClient(app)
    _, creds = new_account(client, db, metodist_token, 'Sherik Maxfiy')
    login(peer, creds)
    room = post(client, '/tables', {'game':game}).json()
    assert post(peer, '/tables/'+room['code']+'/join').status_code == 200
    action(peer, room, 'ready', ready=True)
    room = action(client, room, 'start')
    return peer, room


def test_chess_turn_legal_move_reconnect_and_idempotence(client, db, acct, metodist_token):
    peer, room = start_pair(client, db, metodist_token, 'chess')
    assert room['status'] == 'playing'
    first = client if room['me'] == room['state']['players'][0] else peer
    second = peer if first is client else client
    payload = {'type':'move','move':'e2e4','requestId':str(uuid.uuid4()),'version':room['version']}
    url = '/tables/'+room['code']+'/actions'
    assert post(second, url, payload).status_code == 400
    assert post(first, url, {**payload,'move':'e2e5'}).status_code == 400
    good = post(first, url, payload)
    assert good.status_code == 200
    assert post(first, url, payload).json()['version'] == good.json()['version']
    assert post(second, url, {**payload,'requestId':str(uuid.uuid4()),'move':'e7e5'}).status_code == 409
    resumed = first.get('/space/tables?game=chess').json()['active']
    assert resumed['state']['log'] == ['e4'] and resumed['state']['turn'] == 1
    assert TestClient(app).get('/space/tables/'+room['code']).status_code == 401


def test_chess_mate_rewards_once_and_no_coin(client, db, acct, metodist_token):
    peer, room = start_pair(client, db, metodist_token, 'chess')
    white, black = (client, peer) if room['me'] == room['state']['players'][0] else (peer, client)
    for tc, move in [(white,'f2f3'),(black,'e7e5'),(white,'g2g4'),(black,'d8h4')]:
        room = action(tc, room, 'move', move=move)
    assert room['status'] == 'finished' and room['state']['winners'] == [room['state']['players'][1]]
    body = {'result':{'game':'chess','roomId':room['id'],'won':True,'lightning':999,'xp':999,'award':999}}
    for tc in [white, black]:
        a = post(tc, '/games/results', body)
        assert a.status_code == 200, a.text
        state = a.json()['state']
        assert state['balance'] == 0
        assert state['xp'] == (5 if tc is black else 0)
        assert state['lightning'] == (2 if tc is black else 0)
        b = post(tc, '/games/results', body).json()['state']
        assert b['xp'] == state['xp'] and b['lightning'] == state['lightning']
    assert db.query(MinarResult).count() == 2
    assert any(a['id']=='chess_win' and a['unlockedAt'] for a in post(black,'/games/results',body).json()['state']['achievements'])


def test_only_members_see_hands_and_unfinished_results_rejected(client, db, acct, metodist_token):
    peer, room = start_pair(client, db, metodist_token, 'uno')
    a = client.get('/space/tables/'+room['code']).json()['state']
    b = peer.get('/space/tables/'+room['code']).json()['state']
    assert len(a['hand']) == len(b['hand']) == 7
    assert not set(c['id'] for c in a['hand']) & set(c['id'] for c in b['hand'])
    assert not {'hands','deck','discard'} & a.keys()
    outsider = TestClient(app)
    _, creds = new_account(client, db, metodist_token, 'Uchinchi Sir')
    login(outsider, creds)
    assert outsider.get('/space/tables/'+room['code']).status_code == 403
    assert post(outsider,'/tables/'+room['code']+'/join').status_code == 400
    assert post(client,'/games/results',{'result':{'roomId':room['id']}}).status_code == 400


def test_mafia_all_six_students_have_independent_secret_roles(client, db, acct, metodist_token):
    clients = [client]
    for i in range(5):
        peer = TestClient(app)
        _, creds = new_account(client, db, metodist_token, f'O‘quvchi Maxfiy{i}')
        login(peer, creds); clients.append(peer)
    room = post(client, '/tables', {'game':'mafia'}).json()
    for peer in clients[1:]:
        assert post(peer, '/tables/'+room['code']+'/join').status_code == 200
        action(peer, room, 'ready', ready=True)
    room = action(client, room, 'start')
    roles = []
    for peer in clients:
        view = peer.get('/space/tables/'+room['code']).json()
        roles.append(view['state']['role'])
        assert not {'roles','choices'} & view['state'].keys()
        assert view['state']['investigations'] == {}
        assert 'phone' not in json.dumps(view)
    assert sorted(roles) == sorted(['mafia','doctor','detective','citizen','citizen','citizen'])
    assert post(client,'/tables/'+room['code']+'/actions',{'type':'start','version':room['version'],'requestId':str(uuid.uuid4())}).status_code == 400


def test_mafia_chat_does_not_extend_deadline_and_tick_advances(client, db, acct, metodist_token):
    # Build a legitimate six-member room via the preceding helpers, then advance its clock.
    clients=[client]
    room=post(client,'/tables',{'game':'mafia'}).json()
    for i in range(5):
        tc=TestClient(app);_,creds=new_account(client,db,metodist_token,f'Player Secret{i}');login(tc,creds)
        post(tc,'/tables/'+room['code']+'/join');action(tc,room,'ready',ready=True);clients.append(tc)
    room=action(client,room,'start')
    stored=db.get(MinarTableRoom,room['id']);state=json.loads(stored.state)
    state['deadline']=(datetime.utcnow()-timedelta(seconds=1)).isoformat()+'Z';stored.state=json.dumps(state);db.commit()
    room=action(client,room,'tick');assert room['state']['phase']=='discussion'
    deadline=room['deadline'];room=action(client,room,'chat',text='<script>alert(1)</script>')
    assert room['deadline']==deadline and room['state']['chat'][0]['text'].startswith('<script>')
    assert 'choices' not in room['state']


def test_sudoku_unique_hidden_solution_and_server_checked(client, db, acct):
    room=post(client,'/tables',{'game':'sudoku'}).json()
    assert room['status']=='playing' and 'solution' not in room['state']
    assert r.solution_count(room['state']['puzzle'][:])==1
    forged=room['state']['grid'][:];fixed=next(i for i,n in enumerate(forged) if n);forged[fixed]=0
    assert post(client,'/tables/'+room['code']+'/actions',{'type':'solve','grid':forged,'version':room['version'],'requestId':str(uuid.uuid4())}).status_code==400
    stored=json.loads(db.get(MinarTableRoom,room['id']).state)['game']
    room=action(client,room,'save',grid=stored['solution'])
    assert room['status']=='playing'
    room=action(client,room,'solve',grid=stored['solution'])
    assert room['status']=='finished'
    state=post(client,'/games/results',{'result':{'roomId':room['id']}}).json()['state']
    assert state['xp']==5 and state['lightning']==2 and state['balance']==0


def test_host_transfer_capacity_and_abort_no_reward(client, db, acct, metodist_token):
    peer=TestClient(app);_,creds=new_account(client,db,metodist_token);login(peer,creds)
    room=post(client,'/tables',{'game':'chess'}).json()
    assert post(peer,'/tables/'+room['code']+'/join').status_code==200
    assert action(client,room,'leave')=={'left':True}
    current=peer.get('/space/tables/'+room['code']).json()
    assert current['host']==current['me'] and current['members'][0]['ready']
    assert post(client,'/tables/'+room['code']+'/join').status_code==200
    action(client,room,'ready',ready=True);room=action(peer,room,'start')
    action(client,room,'leave')
    data=post(peer,'/games/results',{'result':{'roomId':room['id']}}).json()['state']
    assert data['xp']==data['lightning']==data['balance']==0


def test_room_timeout_is_unrewarded_and_requires_server_clock(client, db, acct, metodist_token):
    peer,room=start_pair(client,db,metodist_token,'chess')
    assert action(client,room,'tick')['status']=='playing'
    stored=db.get(MinarTableRoom,room['id']);state=json.loads(stored.state);state['deadline']='2020-01-01T00:00:00Z';stored.state=json.dumps(state);db.commit()
    room=action(peer,room,'tick');assert room['state']['reason']=='timeout'
    assert post(peer,'/games/results',{'result':{'roomId':room['id']}}).json()['state']['xp']==0


def test_chess_engine_check_castling_and_en_passant():
    s=r.new_game('chess',['a','b'])
    for uci in ['e2e4','a7a6','e4e5','d7d5']:
        r.move('chess',s,s['players'][s['turn']],{'type':'move','move':uci})
    assert 'e5d6' in r.view('chess',s,'a')['legal']
    r.move('chess',s,'a',{'type':'move','move':'e5d6'})
    assert r.board_chess(s).piece_at(__import__('chess').D5) is None
    s=r.new_game('chess',['a','b'])
    for uci in ['e2e4','e7e5','g1f3','b8c6','f1e2','g8f6','e1g1']:
        r.move('chess',s,s['players'][s['turn']],{'type':'move','move':uci})
    assert r.board_chess(s).piece_at(__import__('chess').F1).symbol()=='R'


def test_checkers_forced_multiple_capture_and_crowning():
    s=r.new_game('checkers',['a','b']);s['board']=[0]*64
    s['board'][17]=1;s['board'][26]=-1;s['board'][44]=-1;s['board'][3]=1;s['board'][62]=-1
    assert r.checker_moves(s)==[{'from':17,'to':35,'capture':26}]
    with pytest.raises(MinarError):r.move('checkers',s,'a',{'type':'move','from':3,'to':10})
    r.move('checkers',s,'a',{'type':'move','from':17,'to':35});assert s['chain']==35 and s['turn']==0
    r.move('checkers',s,'a',{'type':'move','from':35,'to':53});assert s['chain'] is None and s['turn']==1
    s['turn']=0;s['board'][62]=0
    r.move('checkers',s,'a',{'type':'move','from':53,'to':60});assert s['board'][60]==2


def test_uno_wild_four_restriction_and_uno_penalty():
    s=r.new_game('uno',['a','b']);s['color']='R';s['hands']['a']=[{'id':'x','color':'W','value':'+4'},{'id':'y','color':'R','value':'7'}]
    with pytest.raises(MinarError):r.move('uno',s,'a',{'type':'play','card':'x','color':'B'})
    r.move('uno',s,'a',{'type':'play','card':'y'});assert len(s['hands']['a'])==3


@pytest.mark.parametrize('count',[2,3,6])
def test_uno_full_round_conserves_108_unique_cards(count):
    s=r.new_game('uno',[str(i) for i in range(count)])
    for _ in range(2000):
        all_cards=s['deck']+s['discard']+[c for h in s['hands'].values() for c in h]
        assert len(all_cards)==108 and len({c['id'] for c in all_cards})==108
        if s['finished']:break
        pid=s['players'][s['turn']];legal=[c for c in s['hands'][pid] if r.uno_legal(s,c,pid)]
        if legal:
            r.move('uno',s,pid,{'type':'play','card':legal[0]['id'],'color':'R','uno':True})
        else:r.move('uno',s,pid,{'type':'pass' if s['drawn'] else 'draw'})
    assert s['finished'] and len(s['winners'])==1


def test_mafia_doctor_detective_secrets_and_team_victory():
    s=r.new_game('mafia',list('abcdef'));s['roles']=dict(zip('abcdef',['mafia','doctor','detective','citizen','citizen','citizen']))
    r.move('mafia',s,'a',{'type':'choose','target':'d'});r.move('mafia',s,'b',{'type':'choose','target':'d'});r.move('mafia',s,'c',{'type':'choose','target':'a'})
    assert s['phase']=='discussion' and len(s['alive'])==6
    assert r.view('mafia',s,'c')['investigations']=={'a':True}
    assert r.view('mafia',s,'d')['investigations']=={} and 'roles' not in r.view('mafia',s,'d')
    r.mafia_advance(s)
    for pid in 'abcdef':r.move('mafia',s,pid,{'type':'choose','target':'b' if pid=='a' else 'a'})
    assert s['finished'] and s['winners']==list('bcdef') and s['winningTeam']=='citizen'


def test_invalid_game_is_400_and_private_sudoku_cannot_join(client,db,acct,metodist_token):
    assert post(client,'/tables',{'game':[]}).status_code==400
    room=post(client,'/tables',{'game':'sudoku'}).json()
    tc=TestClient(app);_,creds=new_account(client,db,metodist_token);login(tc,creds)
    assert post(tc,'/tables/'+room['code']+'/join').status_code==400


def test_sudoku_daily_cap_and_claim_cannot_cross_accounts(client, db, acct, metodist_token):
    peer=TestClient(app);_,creds=new_account(client,db,metodist_token);login(peer,creds)
    for n in range(4):
        room=post(client,'/tables',{'game':'sudoku'}).json()
        solution=json.loads(db.get(MinarTableRoom,room['id']).state)['game']['solution']
        action(client,room,'solve',grid=solution)
        body={'result':{'roomId':room['id']}}
        assert post(peer,'/games/results',body).status_code==400
        state=post(client,'/games/results',body).json()['state']
        assert state['xp']==min(n+1,3)*5 and state['lightning']==min(n+1,3)*2 and state['balance']==0


def test_postgres_simultaneous_move_retries_are_one_move(client, db, acct, metodist_token):
    if db.bind.dialect.name!='postgresql':pytest.skip('PostgreSQL row locks')
    from concurrent.futures import ThreadPoolExecutor
    from backend.tests.conftest import TestSessionLocal
    _,room=start_pair(client,db,metodist_token,'chess')
    account_id=int(room['state']['players'][0])
    payload={'type':'move','move':'e2e4','version':room['version'],'requestId':'simultaneous-same-move'}
    def worker():
        with TestSessionLocal() as session:
            acc=session.get(MinarAccount,account_id)
            return tables.act(session,acc,room['code'],payload)
    with ThreadPoolExecutor(max_workers=2) as pool:results=list(pool.map(lambda _:worker(),range(2)))
    assert [x['version'] for x in results]==[room['version']+1]*2
    assert all(x['state']['log']==['e4'] for x in results)
