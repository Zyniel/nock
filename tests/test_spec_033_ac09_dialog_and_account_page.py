"""Tests of spec 033, AC-9 (second part): the dialog, the scans and `/account`.

The room page runs on spec 040's mocked socket and `/account` on mocked answers:
`GET /api/account` and the other account routes are answered by `page.route`
(`AccountRoutes` of `spec033_harness`). The server is the live server of the
harness, with accounts on, so that it serves `/account`.

Scans: spec 035's contrast and language scans find no offending element at 1280 by
720 and 360 by 740, on the room page with the dialog open, then showing
`account-sent`, then `account-error`, and on `/account` in the states
`signed_out`, `signed_in`, `link_invalid` and `deleted`. `/account` has no
horizontal scroll at the sizes of spec 006 AC-5.

Edge cases checked as well, from the spec's "Client": the dialog's structure (a
modal `<dialog>` after the toolbar, labelled by its heading, its form and texts);
the texts and roles of each answer to the link request; the submit button disabled
while its request runs; `account-close`; the signed-in dialog; no account control
while `GET /api/account` answers 404; the new `fr.json` keys.

The toolbar's layout and the keyboard walk are in
`test_spec_033_ac09_toolbar_layout_and_keyboard.py`. The shared setup is in
`spec033_harness` and `spec024_harness` (the mocked room and spec 035's scans).
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Browser, Page, expect

from nock.catalogue import Catalogue
from nock.grid import Grid
from spec024_harness import (
    SETTLE_MS,
    contrast_problems,
    language_data,
    language_problems,
    make_catalogue,
    open_context_page,
    open_room,
)
from spec032_harness import grid_from_text
from spec033_harness import (
    A_TOKEN,
    ACCOUNT_PAGE_PATH,
    ANA_EMAIL,
    SIGNED_IN,
    WAIT_TIMEOUT_MS,
    WINDOW_SIZES,
    AccountRoutes,
    AccountServer,
    account_live_server,
    answer_link,
    expect_account_state,
    load_fr,
    size_ids,
)

SCAN_SIZES = [(1280, 720), (360, 740)]


# The new keys of `fr.json`, as the spec's table writes them.
NEW_KEYS = {
    "account.open": "Compte",
    "account.dialog_heading": "Retrouver vos parties sur tous vos appareils",
    "account.dialog_intro": (
        "Recevez par e-mail un lien de connexion. Vous gardez votre place, votre"
        " couleur et vos lettres dans ce salon."
    ),
    "account.email_label": "Adresse e-mail",
    "account.send": "Recevoir le lien",
    "account.sent": "Lien envoyé à {email}. Il est valable 30 minutes.",
    "account.error.email": "Adresse e-mail non valide.",
    "account.error.too_many": "Trop de demandes. Réessayez dans une heure.",
    "account.error.send": "Impossible d'envoyer le lien. Réessayez plus tard.",
    "account.error.generic": "Une erreur est survenue. Réessayez.",
    "account.close": "Fermer",
    "account.signed_in_heading": "Votre compte",
    "account.signed_in_as": "Connecté avec {email}",
    "account.manage": "Gérer mon compte",
    "account.page_heading": "Mon compte",
    "account.signing_in": "Connexion…",
    "account.link_invalid": "Ce lien n'est plus valable. Demandez-en un nouveau.",
    "account.signed_out_intro": "Recevez par e-mail un lien pour vous connecter.",
    "account.back_to_room": "Retourner au salon {code}",
    "account.sign_out": "Se déconnecter",
    "account.delete": "Supprimer mon compte",
    "account.delete_warning": (
        "Votre adresse et la liste de vos salons seront effacées. Dans vos salons,"
        " votre pseudo deviendra « Ancien joueur »."
    ),
    "account.delete_confirm": "Supprimer définitivement",
    "account.delete_cancel": "Garder mon compte",
    "account.deleted": "Votre compte a été supprimé.",
    "player.former": "Ancien joueur",
    "email.sign_in.subject": "Votre lien de connexion à Nock",
    "email.sign_in.body": (
        "Bonjour,\n\nOuvrez ce lien pour vous connecter à Nock :\n{link}\n\n"
        "Il est valable 30 minutes et ne sert qu'une fois. Si vous n'avez rien"
        " demandé, ignorez ce message."
    ),
}


@pytest.fixture
def fx01_grid(fx01_text: str) -> Grid:
    return grid_from_text(fx01_text)


@pytest.fixture
def account_server(tmp_path: Path, fx01_grid: Grid) -> Iterator[AccountServer]:
    catalogue: Catalogue = make_catalogue(fx01_grid)
    with account_live_server(tmp_path, catalogue) as server:
        yield server


# ---- The room page --------------------------------------------------------------


def open_plain_room(
    browser: Browser,
    browser_name: str,
    base_url: str,
    grid: Grid,
    size: tuple[int, int],
    routes: AccountRoutes,
) -> tuple[Page, Callable[[], None]]:
    """The room of `open_room` (`p1` and `p2`) in a desktop context, with `routes`."""
    width, height = size
    page, close = open_context_page(browser, browser_name, width, height, False)
    try:
        routes.install(page)
        open_room(page, base_url, grid)
        expect(page.get_by_test_id("account-open")).to_have_count(
            1, timeout=WAIT_TIMEOUT_MS
        )
    except BaseException:
        close()
        raise
    return page, close


def open_dialog(page: Page) -> None:
    page.get_by_test_id("account-open").click()
    expect(page.get_by_test_id("account-dialog")).to_have_attribute("open", "")


def submit_address(page: Page, address: str = ANA_EMAIL) -> None:
    page.get_by_test_id("account-email-input").fill(address)
    page.get_by_test_id("account-email-submit").click()


# ---- Scans: the room page -------------------------------------------------------


def room_data(base_url: str) -> set[str]:
    return language_data(base_url, ["Ana", "Bob"]) | {ANA_EMAIL}


@pytest.mark.parametrize("state", ["open", "sent", "error"])
@pytest.mark.parametrize("size", SCAN_SIZES, ids=size_ids(SCAN_SIZES))
def test_ac9_the_scans_find_nothing_on_the_room_page_with_the_dialog(
    browser: Browser,
    browser_name: str,
    account_server: AccountServer,
    fx01_grid: Grid,
    size: tuple[int, int],
    state: str,
) -> None:
    link_status = 422 if state == "error" else 202
    routes = AccountRoutes(link_status=link_status)
    page, close = open_plain_room(
        browser, browser_name, account_server.base_url, fx01_grid, size, routes
    )
    try:
        open_dialog(page)
        if state != "open":
            submit_address(page)
            shown = "account-sent" if state == "sent" else "account-error"
            expect(page.get_by_test_id(shown)).to_be_visible(timeout=WAIT_TIMEOUT_MS)
        page.wait_for_timeout(SETTLE_MS)
        contrast = contrast_problems(page)
        language = language_problems(page, room_data(account_server.base_url))
    finally:
        close()

    assert contrast == []
    assert language == []


# ---- Scans and scrolling: the account page --------------------------------------


def open_account_page(
    browser: Browser,
    browser_name: str,
    base_url: str,
    size: tuple[int, int],
    state: str,
) -> tuple[Page, Callable[[], None]]:
    """Open `/account` in `state`, on mocked answers; return the page, its closer."""
    width, height = size
    page, close = open_context_page(browser, browser_name, width, height, False)
    try:
        if state in ("signed_in", "deleted"):
            routes = AccountRoutes(status_body=SIGNED_IN)
        elif state == "link_invalid":
            routes = AccountRoutes(sign_in_status=404)
        else:
            routes = AccountRoutes()
        routes.install(page)
        if state == "link_invalid":
            page.goto(f"{base_url}{ACCOUNT_PAGE_PATH}#{A_TOKEN}")
        else:
            page.goto(f"{base_url}{ACCOUNT_PAGE_PATH}")
        if state == "deleted":
            expect_account_state(page, "signed_in")
            page.get_by_test_id("account-delete").click()
            page.get_by_test_id("account-delete-confirm").click()
        expect_account_state(page, state)
    except BaseException:
        close()
        raise
    return page, close


ACCOUNT_STATES = ["signed_out", "signed_in", "link_invalid", "deleted"]


@pytest.mark.parametrize("state", ACCOUNT_STATES)
@pytest.mark.parametrize("size", SCAN_SIZES, ids=size_ids(SCAN_SIZES))
def test_ac9_the_scans_find_nothing_on_the_account_page(
    browser: Browser,
    browser_name: str,
    account_server: AccountServer,
    size: tuple[int, int],
    state: str,
) -> None:
    page, close = open_account_page(
        browser, browser_name, account_server.base_url, size, state
    )
    try:
        page.wait_for_timeout(SETTLE_MS)
        contrast = contrast_problems(page)
        language = language_problems(page, {ANA_EMAIL})
    finally:
        close()

    assert contrast == []
    assert language == []


NO_HORIZONTAL_SCROLL_SCRIPT = (
    "() => [document.documentElement.scrollWidth, window.innerWidth]"
)


@pytest.mark.parametrize("state", ["signed_out", "signed_in"])
@pytest.mark.parametrize("size", WINDOW_SIZES, ids=size_ids(WINDOW_SIZES))
def test_ac9_the_account_page_has_no_horizontal_scroll(
    browser: Browser,
    browser_name: str,
    account_server: AccountServer,
    size: tuple[int, int],
    state: str,
) -> None:
    page, close = open_account_page(
        browser, browser_name, account_server.base_url, size, state
    )
    try:
        page.wait_for_timeout(SETTLE_MS)
        scroll_width, window_width = page.evaluate(NO_HORIZONTAL_SCROLL_SCRIPT)
    finally:
        close()

    assert scroll_width <= window_width


# ---- Edge cases of the room page's dialog ---------------------------------------

DIALOG_STRUCTURE_SCRIPT = """
() => {
  const dialog = document.querySelector('[data-testid="account-dialog"]');
  const toolbar = document.querySelector('[data-testid="room-toolbar"]');
  const input = document.querySelector('[data-testid="account-email-input"]');
  const labelledBy = dialog.getAttribute('aria-labelledby');
  const heading = labelledBy === null ? null : document.getElementById(labelledBy);
  const labels = input.labels === null ? [] : Array.from(input.labels);
  return {
    tag: dialog.tagName,
    modal: dialog.matches(':modal'),
    afterToolbar: Boolean(
      toolbar.compareDocumentPosition(dialog) & Node.DOCUMENT_POSITION_FOLLOWING
    ),
    insideToolbar: toolbar.contains(dialog),
    heading: heading === null ? null : heading.textContent.trim(),
    inputType: input.getAttribute('type'),
    autocomplete: input.getAttribute('autocomplete'),
    labels: labels.map(label => label.textContent.trim()),
    inForm: input.closest('[data-testid="account-email-form"]') !== null,
  };
}
"""


def test_ac9_the_dialog_is_a_modal_dialog_after_the_toolbar_labelled_by_its_heading(
    browser: Browser,
    browser_name: str,
    account_server: AccountServer,
    fx01_grid: Grid,
) -> None:
    fr = load_fr()
    page, close = open_plain_room(
        browser,
        browser_name,
        account_server.base_url,
        fx01_grid,
        (1280, 720),
        AccountRoutes(),
    )
    try:
        open_dialog(page)
        structure = page.evaluate(DIALOG_STRUCTURE_SCRIPT)
        dialog = page.get_by_test_id("account-dialog")
        intro_count = dialog.get_by_text(fr["account.dialog_intro"]).count()
        submit = page.get_by_test_id("account-email-submit")
        submit_text = submit.text_content()
    finally:
        close()

    assert structure == {
        "tag": "DIALOG",
        "modal": True,
        "afterToolbar": True,
        "insideToolbar": False,
        "heading": fr["account.dialog_heading"],
        "inputType": "email",
        "autocomplete": "email",
        "labels": [fr["account.email_label"]],
        "inForm": True,
    }
    assert intro_count == 1
    assert (submit_text or "").strip() == fr["account.send"]


@pytest.mark.parametrize(
    ("status", "test_id", "role", "key"),
    [
        pytest.param(202, "account-sent", "status", "account.sent", id="202"),
        pytest.param(422, "account-error", "alert", "account.error.email", id="422"),
        pytest.param(429, "account-error", "alert", "account.error.too_many", id="429"),
        pytest.param(503, "account-error", "alert", "account.error.send", id="503"),
        pytest.param(500, "account-error", "alert", "account.error.send", id="500"),
    ],
)
def test_ac9_each_answer_to_the_link_request_shows_its_message(
    browser: Browser,
    browser_name: str,
    account_server: AccountServer,
    fx01_grid: Grid,
    status: int,
    test_id: str,
    role: str,
    key: str,
) -> None:
    expected = load_fr()[key].replace("{email}", ANA_EMAIL)
    page, close = open_plain_room(
        browser,
        browser_name,
        account_server.base_url,
        fx01_grid,
        (1280, 720),
        AccountRoutes(link_status=status),
    )
    try:
        open_dialog(page)
        submit_address(page)

        message = page.get_by_test_id(test_id)
        expect(message).to_have_text(expected, timeout=WAIT_TIMEOUT_MS)
        expect(message).to_have_attribute("role", role)
    finally:
        close()


def test_ac9_the_submit_button_is_disabled_while_its_request_runs(
    browser: Browser,
    browser_name: str,
    account_server: AccountServer,
    fx01_grid: Grid,
) -> None:
    routes = AccountRoutes()
    routes.hold_links = True
    page, close = open_plain_room(
        browser, browser_name, account_server.base_url, fx01_grid, (1280, 720), routes
    )
    try:
        open_dialog(page)
        submit_address(page)
        waited_ms = 0
        while len(routes.held) == 0 and waited_ms < WAIT_TIMEOUT_MS:
            page.wait_for_timeout(50)
            waited_ms += 50
        assert len(routes.held) == 1

        submit = page.get_by_test_id("account-email-submit")
        expect(submit).to_be_disabled()
        answer_link(routes.held[0], 202)
        expect(page.get_by_test_id("account-sent")).to_be_visible(
            timeout=WAIT_TIMEOUT_MS
        )
    finally:
        close()


def test_ac9_account_close_closes_the_dialog_and_gives_the_focus_back(
    browser: Browser,
    browser_name: str,
    account_server: AccountServer,
    fx01_grid: Grid,
) -> None:
    page, close = open_plain_room(
        browser,
        browser_name,
        account_server.base_url,
        fx01_grid,
        (1280, 720),
        AccountRoutes(),
    )
    try:
        open_dialog(page)
        close_button = page.get_by_test_id("account-close")
        expect(close_button).to_have_text(load_fr()["account.close"])

        close_button.click()

        expect(page.get_by_test_id("account-dialog")).not_to_have_attribute("open", "")
        expect(page.get_by_test_id("account-open")).to_be_focused()
    finally:
        close()


def test_ac9_signed_in_the_dialog_shows_the_account_and_links_to_its_page(
    browser: Browser,
    browser_name: str,
    account_server: AccountServer,
    fx01_grid: Grid,
) -> None:
    fr = load_fr()
    routes = AccountRoutes(status_body=SIGNED_IN)
    page, close = open_plain_room(
        browser, browser_name, account_server.base_url, fx01_grid, (1280, 720), routes
    )
    try:
        open_dialog(page)

        dialog = page.get_by_test_id("account-dialog")
        expect(dialog.get_by_text(fr["account.signed_in_heading"])).to_have_count(1)
        signed_in_as = fr["account.signed_in_as"].replace("{email}", ANA_EMAIL)
        expect(dialog.get_by_text(signed_in_as)).to_have_count(1)
        link = page.get_by_test_id("account-page-link")
        expect(link).to_have_attribute("href", ACCOUNT_PAGE_PATH)
        expect(link).to_have_attribute("tabindex", "0")
        expect(link).to_have_text(fr["account.manage"])
        expect(page.get_by_test_id("account-email-form")).to_have_count(0)
    finally:
        close()


def test_ac9_no_account_control_while_the_account_route_answers_404(
    browser: Browser,
    browser_name: str,
    account_server: AccountServer,
    fx01_grid: Grid,
) -> None:
    routes = AccountRoutes()
    routes.account_off = True
    page, close = open_context_page(browser, browser_name, 1280, 720, False)
    try:
        routes.install(page)
        open_room(page, account_server.base_url, fx01_grid)
        page.wait_for_timeout(SETTLE_MS)
        account_requests = [r for r in routes.requests if r[0] == "GET"]

        expect(page.get_by_test_id("account-open")).to_have_count(0)
        expect(page.get_by_test_id("account-dialog")).to_have_count(0)
    finally:
        close()

    assert len(account_requests) == 1


def test_ac9_fr_json_holds_the_new_keys_of_the_spec() -> None:
    fr = load_fr()

    found = {key: fr.get(key) for key in NEW_KEYS}

    assert found == NEW_KEYS
