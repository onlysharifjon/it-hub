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


class FineFlow(StatesGroup):
    choosing_employee = State()
    choosing_template = State()
    waiting_photo = State()
    waiting_amount = State()


class ReportFlow(StatesGroup):
    choosing_employee = State()
