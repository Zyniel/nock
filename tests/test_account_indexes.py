"""Tests of account/account, AC-23: the indexes of the account store (rule 25).

The account store makes its indexes when it opens, changing no row. A database
"from before" is one that the account store made, from which the test drops the
indexes: the tables are the ones of the store, and nothing depends on how the
indexes are named.

The data: Ana (an account with a session, a pending link and an identity in room
R, where she played with Bob), her record of R with Bob as team-mate, and a pending
link of Zoé's address. Every table of the account store holds a row.

The query plans are those of the SQL the store really runs: the test traces the
statements of one operation (`trace_new_connections` of `lifetime_harness`) and asks
SQLite for the plan of each one. A plan that reads an index shows `SEARCH <table>
USING ... INDEX`; a scan of the table shows `SCAN <table>`, even when it walks the
index of the primary key. The lookups of rule 25 and the operation that runs each:

- identities by room code: `accounts_of_room`;
- history team-mates by room code and player id: `erase_players_from_history`;
- sign-in links by address and sessions by account: `delete_account`.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import NamedTuple

import pytest

from lifetime_harness import (
    drop_created_indexes,
    indexed_tables,
    plan_scans,
    plan_searches,
    query_plan,
    table_rows,
    trace_new_connections,
)
from nock.accounts import AccountStore, RoomIdentity
from nock.grid import Grid
from nock.room import RoomKey
from spec029_harness import Player, play_fx01
from spec032_harness import ANA, BOB, T0, TA, TB, grid_from_text
from spec033_harness import ANA_EMAIL, ZELIE_EMAIL

CODE = "RRRRRR"
ACCOUNT_TABLES = [
    "account_history",
    "account_history_teammates",
    "account_identities",
    "account_links",
    "account_sessions",
    "accounts",
]
INDEXED_TABLES = [
    "account_history_teammates",
    "account_identities",
    "account_links",
    "account_sessions",
]
BOB_IDENTITY = RoomIdentity(code=CODE, player_id=BOB, resume_token=TB, nickname="BOB")


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


def fill_accounts(accounts: AccountStore, grid: Grid) -> str:
    """Put a row in every table of the account store; return Ana's account id."""
    play = play_fx01(
        grid, CODE, [Player("Ana", ANA, TA), Player("Bob", BOB, TB)], start=T0
    )
    started = accounts.sign_in(ANA_EMAIL, T0)
    ana = RoomIdentity(code=CODE, player_id=ANA, resume_token=TA, nickname="ANA")
    assert accounts.link_identity(started.account_id, ana, T0)
    accounts.save_history(started.account_id, play.state)
    accounts.add_link(ANA_EMAIL, None, T0)
    accounts.add_link(ZELIE_EMAIL, RoomKey(code=CODE, resume_token=TA), T0)
    return started.account_id


def write_database_from_before(path: Path, grid: Grid) -> str:
    """Fill a database with the account store, then drop the indexes it made."""
    accounts = AccountStore(path)
    account_id = fill_accounts(accounts, grid)
    accounts.close()
    drop_created_indexes(path)
    assert indexed_tables(path) == []
    return account_id


def test_ac23_a_database_from_before_opens_with_every_row_as_it_was_and_its_indexes(
    tmp_path: Path, fx01_grid: Grid
) -> None:
    path = tmp_path / "nock.sqlite3"
    write_database_from_before(path, fx01_grid)
    before = table_rows(path)

    AccountStore(path).close()

    assert table_rows(path) == before
    for table in ACCOUNT_TABLES:
        assert len(before[table]) > 0, f"the test data has no row in {table}"
    assert indexed_tables(path) == INDEXED_TABLES


class Lookup(NamedTuple):
    """An operation of the account store, and the tables whose lookup it runs."""

    run: Callable[[AccountStore, str], object]
    tables: list[str]


def ask_accounts_of_room(accounts: AccountStore, account_id: str) -> object:
    return accounts.accounts_of_room(CODE)


def erase_bob(accounts: AccountStore, account_id: str) -> object:
    return accounts.erase_players_from_history([BOB_IDENTITY])


def delete_ana(accounts: AccountStore, account_id: str) -> object:
    return accounts.delete_account(account_id)


LOOKUPS = {
    "identities by room code": Lookup(ask_accounts_of_room, ["account_identities"]),
    "history team-mates by room code and player": Lookup(
        erase_bob, ["account_history_teammates"]
    ),
    "links by address and sessions by account": Lookup(
        delete_ana, ["account_links", "account_sessions"]
    ),
}


@pytest.mark.parametrize("database", ["new", "from before"])
@pytest.mark.parametrize("lookup_name", list(LOOKUPS))
def test_ac23_each_lookup_of_the_account_store_reads_an_index(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    fx01_grid: Grid,
    database: str,
    lookup_name: str,
) -> None:
    path = tmp_path / "nock.sqlite3"
    statements = trace_new_connections(monkeypatch)
    account_id = ""
    if database == "from before":
        account_id = write_database_from_before(path, fx01_grid)
    accounts = AccountStore(path)
    try:
        if database == "new":
            account_id = fill_accounts(accounts, fx01_grid)
        lookup = LOOKUPS[lookup_name]
        first_statement = len(statements)

        lookup.run(accounts, account_id)
        plan = query_plan(path, statements[first_statement:])
    finally:
        accounts.close()

    for table in lookup.tables:
        assert plan_scans(plan, table) == [], table
        assert len(plan_searches(plan, table)) > 0, table
