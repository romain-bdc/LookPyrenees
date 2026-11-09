import pytest


def pytest_addoption(parser):
    parser.addoption("--run-network", action="store_true", help="lance les tests marques 'network'")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-network"):
        config.option.markexpr = ""
        return
    skip = pytest.mark.skip(reason="reseau desactive (utiliser --run-network)")
    for item in items:
        if "network" in item.keywords:
            item.add_marker(skip)
