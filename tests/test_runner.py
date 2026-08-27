from whydied.models import ExitTermination, SignalTermination
from whydied.runner import decode_termination


def test_decode_zero_exit_code() -> None:
    assert decode_termination(0) == ExitTermination(code=0)


def test_decode_positive_non_zero_exit_code() -> None:
    assert decode_termination(2) == ExitTermination(code=2)


def test_decode_sigterm() -> None:
    assert decode_termination(-15) == SignalTermination(number=15, name="SIGTERM")


def test_decode_sigkill() -> None:
    assert decode_termination(-9) == SignalTermination(number=9, name="SIGKILL")


def test_decode_sigsegv() -> None:
    assert decode_termination(-11) == SignalTermination(number=11, name="SIGSEGV")


def test_decode_unknown_signal() -> None:
    assert decode_termination(-999) == SignalTermination(
        number=999,
        name="UNKNOWN_SIGNAL",
    )
