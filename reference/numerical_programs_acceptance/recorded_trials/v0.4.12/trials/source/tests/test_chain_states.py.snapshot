

# --- the three edges that decide whether the monitor can ever turn green ---------
def test_stale_is_not_terminal():
    """STALE means the old verdict is void, so fresh evidence may set a new one.

    Keeping STALE terminal is how the page stayed red for a day after the audit it was
    waiting for had already run.
    """
    import tools.chain_states as cs

    assert cs.transition("STALE", "PASS") == "PASS"
    assert cs.transition("STALE", "SKIP") == "SKIP"
    assert cs.transition("STALE", "FAIL") == "FAIL"


def test_fail_cannot_become_pass_without_running():
    """A chain may not be declared fixed without having been executed."""
    import tools.chain_states as cs

    assert cs.transition("FAIL", "PASS") == "STALE"
    assert cs.transition("RUNNING", "PASS") == "PASS"


def test_a_fresh_batch_audit_clears_stale_in_one_sample():
    import tools.chain_states as cs

    previous = {"gates": "STALE", "quarto": "STALE"}
    observed = {"gates": "PASS", "quarto": "SKIP"}
    assert cs.advance(previous, observed, live=False) == {"gates": "PASS", "quarto": "SKIP"}
