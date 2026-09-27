import pytest
from importlib.metadata import PackageNotFoundError

from driver_manager import DriverManager


def test_validate_runtime_stack_accepts_supported_versions(monkeypatch):
    def fake_version(package_name: str) -> str:
        versions = {
            "selenium": "4.35.0",
        }
        if package_name in versions:
            return versions[package_name]
        raise PackageNotFoundError(package_name)

    monkeypatch.setattr("driver_manager.version", fake_version)

    DriverManager.validate_runtime_stack()


def test_validate_runtime_stack_accepts_same_minor_family(monkeypatch):
    def fake_version(package_name: str) -> str:
        versions = {
            "selenium": "4.35.1",
        }
        if package_name in versions:
            return versions[package_name]
        raise PackageNotFoundError(package_name)

    monkeypatch.setattr("driver_manager.version", fake_version)

    DriverManager.validate_runtime_stack()


def test_validate_runtime_stack_accepts_modern_versions(monkeypatch):
    def fake_version(package_name: str) -> str:
        versions = {
            "selenium": "4.35.0",
        }
        if package_name in versions:
            return versions[package_name]
        raise PackageNotFoundError(package_name)

    monkeypatch.setattr("driver_manager.version", fake_version)

    DriverManager.validate_runtime_stack()


def test_validate_runtime_stack_rejects_incompatible_selenium(monkeypatch):
    def fake_version(package_name: str) -> str:
        versions = {
            "selenium": "3.141.0",
        }
        if package_name in versions:
            return versions[package_name]
        raise PackageNotFoundError(package_name)

    monkeypatch.setattr("driver_manager.version", fake_version)

    with pytest.raises(RuntimeError, match=r"selenium.*3\.141\.0|Selenium"):
        DriverManager.validate_runtime_stack()
