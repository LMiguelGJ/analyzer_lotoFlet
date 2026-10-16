"""Pure retained-wallet projection for validated owned-laboratory sessions."""

POLICY = "retain-gains-top-up-v1"
MAX_SAFE_INTEGER = 2**53 - 1


def derive_wallet(sessions, capital_per_session, total_net):
    """Return external funding and ending wealth for ordered saved sessions."""
    if type(capital_per_session) is not int or not 0 <= capital_per_session <= MAX_SAFE_INTEGER:
        raise ValueError("capital_per_session must be a non-negative safe integer")
    if type(total_net) is not int or not -MAX_SAFE_INTEGER <= total_net <= MAX_SAFE_INTEGER:
        raise ValueError("total_net must be a safe integer")
    if type(sessions) is not list:
        raise ValueError("sessions must be an ordered list")

    out_of_pocket = 0
    balance = 0
    for session in sessions:
        if type(session) is not dict:
            raise ValueError("session must be a validated mapping")
        final_balance = session.get("final_balance")
        if type(final_balance) is not int or not 0 <= final_balance <= MAX_SAFE_INTEGER:
            raise ValueError("final_balance must be a non-negative safe integer")
        additional = max(0, capital_per_session - balance)
        out_of_pocket += additional
        balance += additional
        balance = balance - capital_per_session + final_balance
        if out_of_pocket > MAX_SAFE_INTEGER or balance > MAX_SAFE_INTEGER:
            raise ValueError("wallet amounts exceed the safe integer range")

    if balance - out_of_pocket != total_net:
        raise ValueError("wallet does not reconcile with the stored total_net")
    return {
        "policy": POLICY,
        "out_of_pocket": out_of_pocket,
        "final_wealth": balance,
    }
