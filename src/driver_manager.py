# === IMPORTS ===
from importlib.metadata import PackageNotFoundError, version
from packaging.version import Version
from webdriver_manager.chrome import ChromeDriverManager
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from logger import Logger

import atexit

# === CLASS DEFINITON ===
class DriverManager:
    active_drivers = []

    @staticmethod
    def validate_runtime_stack() -> None:
        """Ensure the project is using a modern, Selenium Wire-free browser stack."""
        supported_versions = {
            "selenium": ("4.0.0", "99.0.0"),
        }

        for package_name, (min_version, max_version) in supported_versions.items():
            try:
                installed_version = version(package_name)
            except PackageNotFoundError:
                continue

            if not (Version(min_version) <= Version(installed_version) < Version(max_version)):
                raise RuntimeError(
                    "Modern Selenium stack için uyumsuz runtime tespit edildi. "
                    f"{package_name} {installed_version} yüklü, ancak desteklenen aralık "
                    f"{min_version} <= {package_name} < {max_version} olmalıdır. "
                    "Lütfen pip install 'selenium>=4.0.0' komutunu çalıştırın."
                )

    @staticmethod
    def create_driver(headless: bool = False):
        Logger.log("Web sürücüsü başlatılıyor...")
        DriverManager.validate_runtime_stack()

        chrome_options = Options()
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("log-level=3")
        chrome_options.add_argument("--disable-background-networking")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-logging"])
        chrome_options.add_experimental_option("useAutomationExtension", False)
        if headless:
            chrome_options.add_argument("--headless=new")

        driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        DriverManager.active_drivers.append(driver)
        return driver

    @staticmethod
    def clear_drivers():
        Logger.log("Aktif web sürücüleri temizleniyor...")
        for driver in DriverManager.active_drivers:
            try:
                driver.quit()
            except Exception:
                pass

# === DRIVER CLEANUP ===
atexit.register(DriverManager.clear_drivers)