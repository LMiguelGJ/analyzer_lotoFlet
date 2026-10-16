import pytest

from laboratorio.domain.laboratory_wallet import derive_wallet

CASES = [
    ([], 0, 0, 0),
    ([2800], 2000, 2800, 800),
    ([2800, 2000], 2000, 2800, 800),
    ([2800, 0], 2000, 800, -1200),
    ([0, 2800], 4000, 2800, -1200),
    ([2800, 0, 2000], 3200, 2000, -1200),
    ([2800, 1500], 2000, 2300, 300),
    ([0], 2000, 0, -2000),
]


def _session(final_balance):
    return {"final_balance": final_balance}


@pytest.mark.parametrize(("balances", "out_of_pocket", "final_wealth", "total_net"), CASES)
def test_retained_wallet_examples(balances, out_of_pocket, final_wealth, total_net):
    wallet = derive_wallet([_session(value) for value in balances], 2000, total_net)

    assert wallet == {
        "policy": "retain-gains-top-up-v1",
        "out_of_pocket": out_of_pocket,
        "final_wealth": final_wealth,
    }
    assert wallet["final_wealth"] - wallet["out_of_pocket"] == total_net


def test_wallet_accepts_safe_integer_boundaries():
    maximum = 2**53 - 1

    assert derive_wallet([_session(maximum)], maximum, 0) == {
        "policy": "retain-gains-top-up-v1",
        "out_of_pocket": maximum,
        "final_wealth": maximum,
    }


@pytest.mark.parametrize(
    ("sessions", "capital", "total_net"),
    [
        ([_session(True)], 2000, 0),
        ([_session(1.5)], 2000, 0),
        ([_session(-1)], 2000, 0),
        ([_session(2**53)], 2000, 0),
        ([], True, 0),
        ([], 0, False),
        ([{}], 2000, 0),
        ([_session(0)], 2000, -1999),
    ],
)
def test_wallet_rejects_invalid_or_inconsistent_inputs(sessions, capital, total_net):
    with pytest.raises(ValueError):
        derive_wallet(sessions, capital, total_net)
