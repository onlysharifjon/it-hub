"""One-time, explicitly authorized wallet reset. Run with application writers stopped."""
import argparse
import json
from backend.main import app  # Load the complete model registry, without running startup hooks.
from backend.database import SessionLocal
from backend import models, coin_launch
from backend.wallet import balance


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true', required=True)
    parser.add_argument('--test-coins', choices=['discard'], required=True,
                        help='Reset test coins automatically at Monday midnight in Tashkent.')
    parser.parse_args()
    with SessionLocal() as db:
        already = db.get(models.CoinLaunch, 1) is not None
        result = coin_launch.reset_all(db, keep_test_coins=False)
        if not already:
            assert all(balance(db, sid) == 0 for sid, in db.query(models.Student.id)), 'Reset did not zero every wallet'
        db.commit()
        print(json.dumps({**result, 'alreadyApplied': already}, ensure_ascii=False))


if __name__ == '__main__':
    main()
