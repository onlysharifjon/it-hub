"""Real rule validation, complete bot matches and hidden-information boundaries."""
import copy
import json
import random
import re
import time

import pytest

from backend.minar import table_rules as rules
from backend.minar import new_table_rules as expanded
from backend.minar import practice_bots as bots
from backend.minar.new_table_content import DRAW_WORDS, CODE_WORDS
from backend.minar.practice_drawing import drawing_strokes


@pytest.fixture(autouse=True)
def deterministic_rules(monkeypatch):
    monkeypatch.setattr(rules, 'RNG', random.Random(84))
    monkeypatch.setattr(expanded, 'RNG', random.Random(84))


def room(game):
    members = bots.make_bots(game, 'human')
    ids = ['human']+[b['id'] for b in members]
    return rules.new_game(game, ids), members


@pytest.mark.parametrize('game', list(bots.BOT_COUNTS))
def test_virtual_roster_respects_game_capacity_and_names(game):
    state, members = room(game)
    minimum, maximum = rules.GAMES[game]
    assert minimum <= len(state['players']) <= maximum
    assert len(set(state['players'])) == len(state['players'])
    assert all(m['ready'] and m['isBot'] and m['name'].startswith('Kompyuter · ') for m in members)
    if game == 'mafia':
        assert len(state['players']) == 12
    for member in members:
        action = bots.choose_bot_action(game,state,member['id'],{})
        if action:
            rules.move(game,copy.deepcopy(state),member['id'],action)


@pytest.mark.parametrize('game', list(bots.BOT_COUNTS))
def test_bot_policy_does_not_mutate_game_or_act_when_finished(game):
    state, members = room(game)
    before = copy.deepcopy(state)
    memory = {}
    for player in state['players']:
        bots.choose_bot_action(game,state,player,memory)
    assert state == before
    assert bots.choose_bot_action(game,state,'outsider',memory) is None
    state['finished'] = True
    assert bots.eligible_bot_ids(game,state,members) == []
    assert all(bots.choose_bot_action(game,state,p,memory) is None for p in state['players'])
    assert len(json.dumps(memory)) < 20000


@pytest.mark.parametrize('game,limit', [('checkers',450),('uno',700),('fleet',150),
    ('domino',160),('connect4',43),('ludo',2200),('mafia',450),('codenames',100),('geography',60)])
def test_complete_matches_use_only_legal_moves(game,limit):
    state,_ = room(game)
    memory = {}
    actions = 0
    for _ in range(limit):
        if state['finished']:
            break
        candidates = bots.eligible_bot_ids(game,state,state['players'])
        performed = False
        for pid in candidates:
            action = bots.choose_bot_action(game,state,pid,memory)
            if action is not None:
                rules.move(game,state,pid,action)
                actions += 1
                performed = True
                break
        if not performed:
            if game == 'mafia':
                rules.mafia_advance(state)
            elif game in ('geography','codenames'):
                expanded.advance(game,state)
            else:
                pytest.fail(f'{game} stalled: {state}')
    assert state['finished'], f'{game} did not finish in {limit} steps'
    assert actions > 0
    assert len(json.dumps(memory)) < 20000


def test_chess_bounded_search_and_forced_mate():
    state = rules.new_game('chess',['human','bot:1'])
    memory = {}
    started = time.monotonic()
    for _ in range(12):
        pid = state['players'][state['turn']]
        action = bots.choose_bot_action('chess',state,pid,memory)
        assert action['move'] in rules.view('chess',state,pid)['legal']
        rules.move('chess',state,pid,action)
    # Generous CI bound catches accidental unbounded search, not CPU variation.
    assert time.monotonic()-started < 20
    mate = rules.new_game('chess',['human','bot:1'])
    for pid,move in [('human','f2f3'),('bot:1','e7e5'),('human','g2g4')]:
        rules.move('chess',mate,pid,{'type':'move','move':move})
    action = bots.choose_bot_action('chess',mate,'bot:1',{})
    assert action['move'] == 'd8h4'
    rules.move('chess',mate,'bot:1',action)
    assert mate['finished'] and mate['winners'] == ['bot:1']


def test_checkers_mandatory_backward_capture_and_flying_king():
    state = rules.new_game('checkers',['bot:1','human'])
    state['board'] = [0]*64
    state['board'][35] = 1
    state['board'][26] = -1
    state['board'][62] = -1
    action = bots.choose_bot_action('checkers',state,'bot:1',{})
    assert action['from'] == 35 and action['to'] == 17
    rules.move('checkers',state,'bot:1',action)
    state['turn'] = 0
    state['board'] = [0]*64
    state['board'][56] = 2
    state['board'][35] = -1
    state['board'][7] = -1
    action = bots.choose_bot_action('checkers',state,'bot:1',{})
    assert action['to'] in (28,21,14)
    rules.move('checkers',state,'bot:1',action)


def test_uno_declares_last_card_and_respects_drawn_card():
    state = rules.new_game('uno',['bot:1','human'])
    state['hands']['bot:1'] = [{'id':'mine','color':'R','value':'4'}, {'id':'rest','color':'B','value':'8'}]
    state['discard'] = [{'id':'top','color':'R','value':'1'}]
    state['color'] = 'R'
    action = bots.choose_bot_action('uno',state,'bot:1',{})
    assert action['card'] == 'mine' and action['uno'] is True
    rules.move('uno',state,'bot:1',action)
    assert len(state['hands']['bot:1']) == 1


@pytest.mark.parametrize('side', [1,2])
def test_connect_four_takes_win_and_blocks_opponent(side):
    state = rules.new_game('connect4',['bot:1','human'])
    state['board'][35:38] = [side]*3
    action = bots.choose_bot_action('connect4',state,'bot:1',{})
    assert action['column'] == 3


def test_fleet_targets_neighbors_of_public_hit():
    state = rules.new_game('fleet',['bot:1','human'])
    rules.move('fleet',state,'bot:1',{'type':'deploy','ships':[[0,1,2,3],[16,17,18],[40,41]]})
    rules.move('fleet',state,'human',{'type':'deploy','ships':[[8,9,10,11],[24,25,26],[48,49]]})
    state['fired']['bot:1'] = [9]
    action = bots.choose_bot_action('fleet',state,'bot:1',{})
    assert action['cell'] in (1,8,10,17)


def test_hidden_enemy_hands_and_fleet_do_not_change_decisions():
    for game in ('uno','domino'):
        state = rules.new_game(game,['bot:1','human'])
        altered = copy.deepcopy(state)
        altered['hands']['human'] = list(reversed(altered['hands']['human']))
        if game == 'uno':
            for card in altered['hands']['human']:
                card.update(color='W',value='+4')
        else:
            for tile in altered['hands']['human']:
                tile.update(a=6,b=6)
        altered['deck'] = list(reversed(altered['deck']))
        assert bots.choose_bot_action(game,state,'bot:1',{}) == bots.choose_bot_action(game,altered,'bot:1',{})
    state = rules.new_game('fleet',['bot:1','human'])
    for pid,ships in [('bot:1',[[0,1,2,3],[16,17,18],[40,41]]),('human',[[8,9,10,11],[24,25,26],[48,49]])]:
        rules.move('fleet',state,pid,{'type':'deploy','ships':ships})
    changed = copy.deepcopy(state)
    changed['fleets']['human'] = [[4,5,6,7],[32,33,34],[56,57]]
    assert bots.choose_bot_action('fleet',state,'bot:1',{}) == bots.choose_bot_action('fleet',changed,'bot:1',{})


def test_citizen_and_operative_do_not_read_hidden_roles_or_key():
    state,_ = room('mafia')
    pid = next(p for p,r in state['roles'].items() if r == 'citizen')
    state.update(phase='vote', choices={})
    changed = copy.deepcopy(state)
    other = [p for p in state['players'] if p != pid]
    roles = [changed['roles'][p] for p in other]
    for p,role in zip(other,reversed(roles)):
        changed['roles'][p] = role
    assert bots.choose_bot_action('mafia',state,pid,{}) == bots.choose_bot_action('mafia',changed,pid,{})
    code,_ = room('codenames')
    captain = code['captains'][0]
    clue = bots.choose_bot_action('codenames',code,captain,{})
    rules.move('codenames',code,captain,clue)
    operative = code['players'][2]
    changed = copy.deepcopy(code)
    changed['keys'] = list(reversed(changed['keys']))
    assert bots.choose_bot_action('codenames',code,operative,{}) == bots.choose_bot_action('codenames',changed,operative,{})


def test_geography_uses_question_not_hidden_answer_and_is_fallible():
    state,_ = room('geography')
    original = bots.choose_bot_action('geography',state,'bot:1',{})
    changed = copy.deepcopy(state)
    changed['question']['answer'] = (state['question']['answer']+1)%4
    changed['question']['explanation'] = 'secret changed'
    assert original == bots.choose_bot_action('geography',changed,'bot:1',{})
    correct = 0
    for round_number in range(1,101):
        state['round'] = round_number
        state['phaseSerial'] = round_number
        action = bots.choose_bot_action('geography',state,'bot:1',{})
        correct += action['choice'] == state['question']['answer']
    assert 60 <= correct <= 95


def test_every_word_has_safe_recognizable_strokes_accepted_by_rules():
    for word in DRAW_WORDS:
        state = rules.new_game('draw',['bot:1','human','bot:2'])
        state['word'] = word
        strokes = drawing_strokes(word)
        assert 1 <= len(strokes) <= 40
        for stroke in strokes:
            assert len(stroke['points']) <= 120
            rules.move('draw',state,'bot:1',stroke)
        assert len(state['strokes']) == len(strokes)
        assert all('text' not in stroke for stroke in state['strokes'])


def test_draw_guess_uses_visible_geometry_never_secret_word():
    state = rules.new_game('draw',['human','bot:1','bot:2'])
    state['word'] = 'raketa'
    for stroke in drawing_strokes('raketa'):
        rules.move('draw',state,'human',stroke)
    action = bots.choose_bot_action('draw',state,'bot:1',{})
    assert action['type'] == 'guess' and action['text'] == 'raketa'
    changed = copy.deepcopy(state)
    changed['word'] = 'mushuk'  # Same visible length, different hidden answer.
    assert action == bots.choose_bot_action('draw',changed,'bot:1',{})
    rules.move('draw',state,'bot:1',action)
    assert 'bot:1' in state['guessed']


def test_full_drawing_match_advances_on_server_deadlines():
    state,_ = room('draw')
    memory = {}
    drawn = set()
    for _ in range(200):
        if state['finished']:
            break
        moved = False
        # Artist first makes progress; no hidden answer enters guesser policy.
        ids = [state['drawer']]+[p for p in state['players'] if p != state['drawer']]
        for pid in bots.eligible_bot_ids('draw',state,ids):
            action = bots.choose_bot_action('draw',state,pid,memory)
            if action:
                rules.move('draw',state,pid,action)
                if action['type'] == 'stroke':
                    drawn.add(state['round'])
                moved = True
                break
        if not moved:
            expanded.advance('draw',state)
    assert state['finished']
    assert drawn == {1,2,3}


def test_quest_leaves_human_turn_and_shares_only_own_vault_clue():
    state,_ = room('quest')
    memory = {}
    initial_stage = state['stage']
    for _ in range(8):
        action = bots.choose_bot_action('quest',state,'bot:1',memory)
        if action:
            rules.move('quest',state,'bot:1',action)
    assert state['stage'] == initial_stage
    assert state['stageActions'] <= 1
    # Human participates and the partner can help again.
    solution = bots._lights_solution(state['puzzle']['cells'])
    rules.move('quest',state,'human',{'type':'toggle','cell':solution[0]})
    assert bots.choose_bot_action('quest',state,'bot:1',memory) is not None
    state['stage'] = 2
    expanded.quest_stage(state)
    action = bots.choose_bot_action('quest',state,'bot:1',memory)
    assert action['type'] == 'chat'
    assert state['puzzle']['clues']['bot:1'] in action['text']
    assert state['puzzle']['code'] not in action['text']
    changed = copy.deepcopy(state)
    changed['puzzle']['code'] = '999'
    changed['puzzle']['clues']['human'] = 'secret changed'
    assert bots.choose_bot_action('quest',state,'bot:1',{}) == bots.choose_bot_action('quest',changed,'bot:1',{})


def test_quest_human_and_partner_can_finish_all_six_stages():
    state,_ = room('quest')
    memory = {}
    human_stages = set()
    for _ in range(100):
        if state['finished']:
            break
        # Initial hint and an assist cannot consume a whole puzzle alone.
        for _ in range(2):
            action = bots.choose_bot_action('quest',state,'bot:1',memory)
            if action:
                rules.move('quest',state,'bot:1',action)
            if state['finished']:
                break
        if state['finished']:
            break
        view = rules.view('quest',state,'human')
        puzzle = view['puzzle']
        if puzzle['kind'] == 'lights':
            action = {'type':'toggle','cell':bots._lights_solution(puzzle['cells'])[0]}
        elif puzzle['kind'] == 'rotors':
            index = next(i for i,(a,b) in enumerate(zip(puzzle['values'],puzzle['target'])) if a != b)
            action = {'type':'rotate','index':index}
        else:
            # Read exactly the human's clue and partner's public message.
            clues = puzzle['clue']+' '+next(message['text'] for message in reversed(view['messages']) if message['player']=='bot:1' and 'Mendagi maslahat:' in message['text'])
            digits = dict(re.findall(r'([123])-raqam: ([0-9])',clues))
            action = {'type':'code','code':''.join(digits[str(i)] for i in (1,2,3))}
        human_stages.add(state['stage'])
        rules.move('quest',state,'human',action)
    assert state['finished'] and set(state['winners']) == {'human','bot:1'}
    assert human_stages == set(range(6))
    assert set(state['contributors']) == {'human','bot:1'}


def test_unchanged_ambiguous_drawing_is_not_recomputed(monkeypatch):
    state = rules.new_game('draw',['human','bot:1','bot:2'])
    state['word'] = 'raketa'
    for i in range(4):
        rules.move('draw',state,'human',{'type':'stroke','width':3,'color':'#17243b',
                                       'points':[[.01,.01],[.02+i*.01,.01]]})
    memory = {}
    assert bots.choose_bot_action('draw',state,'bot:1',memory) is None
    def forbidden(_):
        raise AssertionError('unchanged sketch was recognized again')
    monkeypatch.setattr(bots,'drawing_strokes',forbidden)
    assert bots.choose_bot_action('draw',state,'bot:1',memory) is None


def test_codenames_every_board_word_has_a_meaningful_association():
    assert len(bots._UNIQUE_CLUES) == len(CODE_WORDS)
    for word in CODE_WORDS:
        assert any(expanded.normalize(word) in meanings for meanings in bots.ASSOCIATIONS.values())


def test_codenames_operative_understands_common_human_clues():
    assert bots._clue_scores('koinot',['RAKETA','KITOB','OY']) == [5,0,5]
    assert bots._clue_scores('hayvonlar',['OT','KITOB','SHER']) == [5,0,5]
    assert bots._clue_scores('geografiya',['XARITA','QALAM']) == [8,0]
