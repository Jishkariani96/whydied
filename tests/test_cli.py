from whydied.cli import build_parser


def test_parser_program_name() -> None:
    parser = build_parser()

    assert parser.prog == "whydied"
