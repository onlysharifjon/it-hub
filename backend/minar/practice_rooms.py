"""Bounded, paced bot orchestration; only called inside the room write lock.

Virtual opponents and their private memory live in the room JSON, never in the
student tables. A GET may project this state but must never run a bot.
"""
from datetime import datetime, timedelta

from . import practice_bots
from . import table_rules as rules
from . import new_table_rules as expanded

BOT_DELAY_SECONDS = 1.0
BOT_IDLE_DELAY_SECONDS = 3.0


def is_practice(state):
    return state.get('practice') is True


def create(game, human_id):
    bots = practice_bots.make_bots(game, human_id) if game != 'sudoku' else []
    state = {'practice': True, 'practiceBots': bots, 'botMemory': {}, 'receipts': [],
             'game': rules.new_game(game, [human_id] + [bot['id'] for bot in bots])}
    schedule(game, state)
    return state


def eligible(game, state):
    if not is_practice(state) or state['game']['finished']:
        return []
    return practice_bots.eligible_bot_ids(game, state['game'], state.get('practiceBots', []))


def schedule(game, state, *, reset=False, delay=BOT_DELAY_SECONDS):
    candidates = eligible(game, state)
    if not candidates:
        state['nextBotAt'] = None
    elif reset or not state.get('nextBotAt'):
        state['nextBotAt'] = (datetime.utcnow() + timedelta(seconds=delay)).isoformat() + 'Z'


def phase(game, state):
    if game in expanded.GAMES:
        return expanded.phase_key(state)
    if game == 'mafia':
        return rules.mafia_phase_key(state)
    return (state['turn'], state.get('plies'))


def pump(game, state, now):
    """At most three bounded decisions and ONE move per authenticated tick.

    Round-robin selection prevents one simultaneously eligible bot from starving
    the other students/opponents. Bot actions still use the authoritative rules.
    """
    if not is_practice(state):
        return False
    due = state.get('nextBotAt')
    if due and now < datetime.fromisoformat(due.rstrip('Z')):
        return False
    candidates = eligible(game, state)
    if not candidates:
        if state.get('nextBotAt') is None:
            return False
        state['nextBotAt'] = None
        return True
    cursor = int(state.get('botCursor', 0))
    memory = state.setdefault('botMemory', {})
    moved = False
    for index in range(min(3, len(candidates))):
        bot = candidates[(cursor + index) % len(candidates)]
        state['botCursor'] = cursor + index + 1
        action = practice_bots.choose_bot_action(game, state['game'], bot, memory)
        if action is not None:
            rules.move(game, state['game'], bot, action)
            moved = True
            break
    # Social/cooperative opponents can deliberately wait for the human. Keep
    # their newly learned memory but back off instead of writing every poll.
    schedule(game, state, reset=True, delay=BOT_DELAY_SECONDS if moved else BOT_IDLE_DELAY_SECONDS)
    return True
