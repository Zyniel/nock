"""Tests of spec 038 (privacy and operations), AC-6: what the throttles keep in memory.

As the spec's "Test harness" says, each test builds the throttle itself,
`_WrongCodeThrottle()` imported from `nock.server` (spec 011), and passes the time
of each failure to `record_unless_blocked`: no app, clock or request is needed.
An app does not expose its two throttles, the wrong room codes of spec 011 and the
refused ops requests of rule 2, and both are instances of that class, so each
check here holds for both.

"What the server keeps": an address is kept until 60 seconds after its last
failure, and at most until the next failure the throttle records after that.
Each time the throttle records a failure, it first forgets every address none of
whose failure times `t` satisfies `t > now - 60`.

Edge cases checked as well, from "Edge cases and errors": the five addresses held
after their failures, a sixth failure at `t + 59.9` (kept) and at `t + 60.0`
(forgotten), an address with one failure still in the window whatever its older
ones, and `is_blocked` and `held_addresses()`, which record nothing.
"""

from __future__ import annotations

from nock.server import _WrongCodeThrottle
from spec038_harness import WRONG_CODE_LIMIT

# ---- Values of the spec --------------------------------------------------------------

FIVE_ADDRESSES = ["10.0.0.1", "10.0.0.2", "10.0.0.3", "10.0.0.4", "10.0.0.5"]
SIXTH_ADDRESS = "10.0.0.6"

# ---- Values of the test harness ------------------------------------------------------

# The time of the first failures: a whole number of seconds, so that `t + 60.0`
# minus 60 is `t` exactly.
T = 1_000.0
OTHER_ADDRESS = "10.0.0.7"


def throttle_with_five_failures_at_t() -> _WrongCodeThrottle:
    """A new throttle that recorded one failure of each of the five addresses at T."""
    throttle = _WrongCodeThrottle()
    for address in FIVE_ADDRESSES:
        assert throttle.record_unless_blocked(address, T) is True
    return throttle


# ---- AC-6: the throttle forgets the addresses out of the window ----------------------


def test_ac6_a_failure_at_t_plus_61_leaves_only_its_own_address_held() -> None:
    throttle = throttle_with_five_failures_at_t()

    assert throttle.record_unless_blocked(SIXTH_ADDRESS, T + 61) is True

    assert throttle.held_addresses() == frozenset({SIXTH_ADDRESS})


def test_ac6_after_five_failures_at_t_the_throttle_holds_those_five_addresses() -> None:
    throttle = throttle_with_five_failures_at_t()

    held = throttle.held_addresses()

    assert isinstance(held, frozenset)
    assert held == frozenset(FIVE_ADDRESSES)


def test_ac6_a_failure_at_t_plus_59_9_keeps_the_addresses_of_t() -> None:
    throttle = throttle_with_five_failures_at_t()

    assert throttle.record_unless_blocked(SIXTH_ADDRESS, T + 59.9) is True

    assert throttle.held_addresses() == frozenset([*FIVE_ADDRESSES, SIXTH_ADDRESS])


def test_ac6_a_failure_at_t_plus_60_forgets_the_addresses_of_t() -> None:
    # At T + 60.0, `T > now - 60` no longer holds for the failures of T.
    throttle = throttle_with_five_failures_at_t()

    assert throttle.record_unless_blocked(SIXTH_ADDRESS, T + 60.0) is True

    assert throttle.held_addresses() == frozenset({SIXTH_ADDRESS})


def test_ac6_an_address_with_one_failure_in_the_window_stays() -> None:
    # 10.0.0.1 failed at T, then at T + 30: at T + 61 its failure of T + 30 is
    # still in the window, whatever its failure of T.
    throttle = throttle_with_five_failures_at_t()
    first_address = FIVE_ADDRESSES[0]
    assert throttle.record_unless_blocked(first_address, T + 30) is True

    assert throttle.record_unless_blocked(SIXTH_ADDRESS, T + 61) is True

    assert throttle.held_addresses() == frozenset({first_address, SIXTH_ADDRESS})


def test_ac6_a_blocked_address_is_forgotten_too_once_its_failures_are_old() -> None:
    throttle = _WrongCodeThrottle()
    for _ in range(WRONG_CODE_LIMIT):
        assert throttle.record_unless_blocked(FIVE_ADDRESSES[0], T) is True
    assert throttle.is_blocked(FIVE_ADDRESSES[0], T) is True

    assert throttle.record_unless_blocked(SIXTH_ADDRESS, T + 61) is True

    assert throttle.held_addresses() == frozenset({SIXTH_ADDRESS})


# ---- AC-6: is_blocked and held_addresses record nothing ------------------------------


def test_ac6_is_blocked_records_no_failure_of_an_address_never_seen() -> None:
    throttle = throttle_with_five_failures_at_t()

    blocked = throttle.is_blocked(OTHER_ADDRESS, T + 1)

    assert blocked is False
    assert throttle.held_addresses() == frozenset(FIVE_ADDRESSES)


def test_ac6_is_blocked_adds_no_failure_to_an_address() -> None:
    throttle = _WrongCodeThrottle()
    address = FIVE_ADDRESSES[0]
    for _ in range(WRONG_CODE_LIMIT - 1):
        assert throttle.record_unless_blocked(address, T) is True
    for _ in range(WRONG_CODE_LIMIT):
        assert throttle.is_blocked(address, T) is False

    # Nine failures recorded, whatever is_blocked was asked: the tenth is recorded.
    assert throttle.record_unless_blocked(address, T) is True
    assert throttle.is_blocked(address, T) is True


def test_ac6_held_addresses_forgets_nothing() -> None:
    throttle = throttle_with_five_failures_at_t()

    first_read = throttle.held_addresses()
    second_read = throttle.held_addresses()

    assert first_read == frozenset(FIVE_ADDRESSES)
    assert second_read == frozenset(FIVE_ADDRESSES)


def test_ac6_held_addresses_adds_no_failure_to_an_address() -> None:
    throttle = _WrongCodeThrottle()
    address = FIVE_ADDRESSES[0]
    for _ in range(WRONG_CODE_LIMIT - 1):
        assert throttle.record_unless_blocked(address, T) is True

    for _ in range(WRONG_CODE_LIMIT):
        throttle.held_addresses()

    # Still nine failures: the address is not blocked.
    assert throttle.is_blocked(address, T) is False


def test_ac6_a_new_throttle_holds_no_address() -> None:
    throttle = _WrongCodeThrottle()

    assert throttle.held_addresses() == frozenset()
