from aiogram.fsm.state import State, StatesGroup


class AuditAuth(StatesGroup):
    login = State()
    password = State()


class NewRole(StatesGroup):
    name = State()


class NewAudit(StatesGroup):
    choosing_employee = State()
    login = State()
    password = State()


class ResetAuditPassword(StatesGroup):
    password = State()


class NewFineTemplate(StatesGroup):
    text = State()
    short_name = State()


class EditFineTemplate(StatesGroup):
    text = State()


class FineFlow(StatesGroup):
    choosing_employee = State()
    choosing_bob = State()
    choosing_template = State()
    waiting_photo = State()
    waiting_amount = State()


class ReportFlow(StatesGroup):
    choosing_employee = State()


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
