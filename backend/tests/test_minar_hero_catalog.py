"""Hero unlock boundaries are enforced by the server without spending rewards."""
import pytest

from backend.minar import catalog as C
from backend.minar.models import MinarAccount
from backend.tests.test_minar import _minar_env, acct, post


def test_one_marvel_hero_per_level_and_stable_legacy_ids():
    legacy = ("robo", "foxy", "drako") + tuple(f"hero{i:02d}" for i in range(4, 51))
    assert C.MARVEL_CHARACTERS == legacy
    assert len(C.CHARACTERS) == len(set(C.CHARACTERS)) == 60
    assert tuple(C.CHARACTER_LEVEL[key] for key in legacy) == tuple(range(1, 51))
    assert all(len(key) <= 10 for key in C.CHARACTERS)


@pytest.mark.parametrize("character,level", [("foxy", 2), ("drako", 3), ("hero08", 8), ("superman", 5), ("supergirl", 10)])
def test_character_level_boundary_is_server_enforced(client, db, acct, character, level):
    _, credentials = acct
    account = db.query(MinarAccount).filter_by(login_id=credentials["login_id"]).one()
    threshold = 2000 * 2 ** (level - 2)
    account.xp = threshold - 1
    db.commit()
    denied = post(client, "/avatar/character", {"character": character})
    assert denied.status_code == 403
    db.refresh(account)
    assert account.character == "robo" and account.xp == threshold - 1
    account.xp = threshold
    db.commit()
    before = client.get("/space/students/me/bootstrap").json()
    response = post(client, "/avatar/character", {"character": character})
    assert response.status_code == 200, response.text
    state = response.json()["state"]
    assert state["profile"]["character"] == character
    assert state["xp"] == threshold
    assert state["balance"] == before["balance"]
    assert state["equipment"] == before["equipment"]
