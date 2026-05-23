def test_core_packages_import() -> None:
    import agent
    import tools
    import workers

    assert agent.__version__ == "0.1.0"
    assert tools is not None
    assert workers is not None
