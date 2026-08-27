import signal

from whydied.models import ExitTermination, SignalTermination


def decode_termination(returncode: int) -> ExitTermination | SignalTermination:
    if returncode >= 0:
        return ExitTermination(code=returncode)

    signal_number = -returncode

    try:
        signal_name = signal.Signals(signal_number).name
    except ValueError:
        signal_name = "UNKNOWN_SIGNAL"

    return SignalTermination(number=signal_number, name=signal_name)
