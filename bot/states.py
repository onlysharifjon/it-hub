from aiogram.fsm.state import State, StatesGroup


class NewRole(StatesGroup):
    name = State()


class Broadcast(StatesGroup):
    text = State()
    confirm = State()


class LinkParent(StatesGroup):
    choosing_source = State()
    choosing_employee = State()
    choosing_method = State()
    choosing_group = State()
    choosing_student = State()
    searching = State()
    choosing_search_student = State()




class AttendanceFlow(StatesGroup):
    choosing_group = State()
    choosing_mode = State()
    marking_arrived = State()
    marking_left = State()
    choosing_view_student = State()


class BotSettings(StatesGroup):
    default_parent_id = State()


class PaymentFlow(StatesGroup):
    choosing_group = State()
    choosing_student = State()
