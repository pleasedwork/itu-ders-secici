# === IMPORTS ===
from driver_manager import DriverManager
from selenium.webdriver.common.by import By
from time import sleep
from logger import Logger
import re
import requests
import threading

# === CONSTANTS ===
PAGE_LOAD_DELAY = 3
TOKEN_URL = "https://obs.itu.edu.tr/api/ogrenci/Takvim/KayitZamaniKontrolu"
TOKEN_REFRESH_INTERVAL = 60  # Token refresh interval (seconds)

# === CLASS DEFINITON ===
class ContinuousTokenFetcher(threading.Thread):
    """
    Thread class that continuously fetches tokens in the background.
    Provides thread-safe token access.
    """
    def __init__(self, url: str, login: str, password: str, use_headless_browser: bool=False) -> None:
        super().__init__(daemon=True)
        self.url = url
        self.creds = [login, password]
        self.driver = None
        self._token = ""
        self._token_lock = threading.Lock()
        self._running = False
        self._started_event = threading.Event()
        self.use_headless_browser = use_headless_browser
    
    def login_to_kepler(self) -> None:
        """Starts the driver and performs login."""
        is_repeat = self._started_event.is_set()

        Logger.log("Kepler açılıyor...", silent=is_repeat)
        if self.driver is None:
            self.driver = DriverManager.create_driver(headless=self.use_headless_browser)
        
        self.driver.get(self.url)

        # Wait to see if the URL changes to the login page
        sleep(PAGE_LOAD_DELAY)
        if "girisv3.itu.edu.tr" not in self.driver.current_url: 
            Logger.log("Kepler'e giriş yapılmış, giriş yapma aşaması atlanıyor...", silent=is_repeat)
            return
        
        # Login to the system
        Logger.log("Kepler'e giriş yapılıyor...", silent=is_repeat)
        input_elements = self.driver.find_elements(By.TAG_NAME, "input")
        index = 0

        for element in input_elements:
            # Skip the hidden elements
            if element.get_attribute("type") == "hidden": 
                continue

            # Fill in the credentials.
            element.click()
            if index <= 1:
                element.send_keys(self.creds[index])
            index += 1
            sleep(.1)
        
        if "SelectIdentity" in self.driver.current_url:
            sleep(.1)
            Logger.log("Yatay geçiş hesabı algılandı, aktif İTÜ hesabı seçilecek.", silent=is_repeat)
            identity_cards = self.driver.find_elements(By.CLASS_NAME, "card-body")
            for identity_card in identity_cards:
                rows = identity_card.find_elements(By.TAG_NAME, "tr")
                last_row = rows[-1]
                content = last_row.get_attribute("innerHTML").lower()
                if "durum" in content and "aktif" in content:
                    try:
                        selected_field = rows[1].find_element(By.TAG_NAME, "td").get_attribute("innerHTML").strip()
                        selected_studentid = rows[2].find_element(By.TAG_NAME, "td").get_attribute("innerHTML").strip()
                        Logger.log(f"Seçilen hesap: \"{selected_field} ({selected_studentid})\".")
                    except Exception:
                        pass
                    

                    select_button = identity_card.find_element(By.TAG_NAME, "a")
                    select_button.click()
                    sleep(.1)
                    break
        
        Logger.log("Kepler'e giriş yapıldı, ders seçim sitesine yönlendiriliyor...")
        self.driver.get(self.url)
        sleep(PAGE_LOAD_DELAY)
    
    def _find_token_in_browser_state(self) -> str:
        """Look for the bearer token in browser state without Selenium Wire."""
        script = """
        (() => {
            const values = [];
            const push = (value) => {
                if (typeof value !== 'string') return;
                const trimmed = value.trim();
                if (trimmed && trimmed.length > 10 && !values.includes(trimmed)) {
                    values.push(trimmed);
                }
            };

            for (const storage of [window.localStorage, window.sessionStorage]) {
                if (!storage) continue;
                for (const key of Object.keys(storage)) {
                    push(storage.getItem(key));
                }
            }

            push(document.cookie || '');
            push(document.body ? document.body.innerText : '');
            push(document.head ? document.head.innerText : '');

            try {
                const keys = Object.keys(window).filter((key) => /token|auth|jwt|bearer/i.test(key));
                for (const key of keys) {
                    push(String(window[key]));
                    if (window[key] && typeof window[key] === 'object') {
                        push(JSON.stringify(window[key]));
                    }
                }
            } catch (error) {
                // Ignore window inspection failures.
            }

            return values;
        })();
        """

        try:
            storage_values = self.driver.execute_script(script) or []
        except Exception:
            storage_values = []

        for value in storage_values:
            if not isinstance(value, str):
                continue
            token = self._normalize_token(value)
            if token:
                return token

        return ""

    @staticmethod
    def _extract_jwt_from_response(response) -> str:
        """Read the JWT from the OBS auth endpoint or any response containing a bearer token."""
        if response is None:
            return ""

        header_value = (
            response.headers.get("authorization")
            or response.headers.get("Authorization")
            or ""
        )
        if header_value:
            token = ContinuousTokenFetcher._normalize_token(header_value)
            if token:
                return token

        payload = getattr(response, "text", "") or ""
        if payload:
            token = ContinuousTokenFetcher._normalize_token(payload)
            if token:
                return token

        try:
            data = response.json()
        except Exception:
            data = None

        if isinstance(data, dict):
            for key in ("jwt", "token", "access_token", "accessToken", "authorization", "Authorization"):
                if key in data:
                    token = ContinuousTokenFetcher._normalize_token(str(data[key]))
                    if token:
                        return token

        return ""

    @staticmethod
    def _normalize_token(value: str) -> str:
        """Extract a bearer token from a candidate string if one is present."""
        if not isinstance(value, str):
            return ""

        value = value.strip()
        if not value:
            return ""

        patterns = [
            r'(?i)\bBearer\s+([A-Za-z0-9\-._~+/]+=*)',
            r'(?i)(?:authorization|access[_-]?token|jwt|token)\s*[:=]\s*["\']?\s*(?:Bearer\s+)?([A-Za-z0-9\-._~+/]+=*)',
            r'(?i)(?:authorization|access[_-]?token|jwt|token)\s*[:=]\s*["\']?\s*(?:Bearer\s+)?([A-Za-z0-9\-._~+/]+=*(?:\.[A-Za-z0-9\-._~+/]+=*)+)',
        ]

        for pattern in patterns:
            matches = re.findall(pattern, value)
            for match in matches:
                token = match[0] if isinstance(match, tuple) else match
                token = token.strip().strip('"\'')
                if token and len(token) > 20:
                    if token.lower().startswith("bearer "):
                        return token
                    return f"Bearer {token}" if "Bearer " not in token else token

        for candidate in [
            value,
            *value.split(";"),
            *value.split(","),
            *value.split("\\n"),
            *value.split("\\r"),
        ]:
            candidate = candidate.strip().strip('"\'')
            if not candidate:
                continue
            if candidate.lower().startswith("bearer ") and len(candidate) > 20:
                return candidate

            if candidate.lower().startswith("eyj") and len(candidate) > 20:
                return f"Bearer {candidate}"

            if re.search(r'(?i)\beyj[A-Za-z0-9\-._~+/]+=*\.[A-Za-z0-9\-._~+/]+=*\.[A-Za-z0-9\-._~+/]+=*', candidate):
                token = re.search(r'(?i)(eyj[A-Za-z0-9\-._~+/]+=*\.[A-Za-z0-9\-._~+/]+=*\.[A-Za-z0-9\-._~+/]+=*)', candidate)
                if token:
                    return f"Bearer {token.group(1)}"

        return ""

    def _fetch_obs_jwt(self) -> str:
        """Fetch the JWT directly from the OBS auth endpoint used by the frontend."""
        try:
            session = requests.Session()
            for cookie in self.driver.get_cookies():
                session.cookies.set(
                    cookie["name"],
                    cookie["value"],
                    domain=cookie.get("domain") or ".itu.edu.tr",
                    path=cookie.get("path") or "/",
                )

            response = session.get("https://obs.itu.edu.tr/ogrenci/auth/jwt", timeout=20)
            return self._extract_jwt_from_response(response)
        except Exception as exc:
            Logger.log(f"OBS JWT endpointinden token alınamadı: {exc}", silent=True)
            return ""

    def _fetch_token_once(self) -> str:
        """Single token fetch operation without a proxy layer."""
        if self.url not in self.driver.current_url:
            Logger.log("Ders seçim sitesi açılıyor...", silent=self._started_event.is_set())
            self.driver.get(self.url)
            sleep(PAGE_LOAD_DELAY)

        self.driver.refresh()
        sleep(1)

        if "girisv3.itu.edu.tr" in self.driver.current_url:
            Logger.log("Kepler hesabından çıkıldığı algılandı, tekrar giriş yapılıyor...")
            self.login_to_kepler()
            self.driver.refresh()
            sleep(1)

        token = self._fetch_obs_jwt()
        if token:
            return token

        token = self._find_token_in_browser_state()
        if token:
            return token

        try:
            session = requests.Session()
            for cookie in self.driver.get_cookies():
                session.cookies.set(
                    cookie["name"],
                    cookie["value"],
                    domain=cookie.get("domain") or ".itu.edu.tr",
                    path=cookie.get("path") or "/",
                )

            response = session.get(TOKEN_URL, timeout=20)
            token = self._extract_jwt_from_response(response)
            if token:
                return token
        except Exception as exc:
            Logger.log(f"Token çıkarma sırasında tarayıcı oturumu çözümlenemedi: {exc}", silent=True)

        return ""
    
    def run(self) -> None:
        """Thread main loop - continuously fetches tokens."""
        self._running = True
        Logger.log("Token fetcher thread başlatıldı, sürekli token alınacak...", silent=True)
        
        while self._running:
            try:
                Logger.log("Yeni API Token aranıyor.", silent=True)
                new_token = self._fetch_token_once()
                if new_token and "ERROR" not in new_token and new_token != self._token:
                    with self._token_lock:
                        self._token = new_token
                    Logger.log("API Token güncellendi.")
                    
                    # Set event when first successful token is received
                    if not self._started_event.is_set():
                        self._started_event.set()
                        Logger.log("İlk token başarıyla alındı.")
            except Exception as e:
                Logger.log(f"Token fetch hatası: {e}", silent=True)
            
            sleep(TOKEN_REFRESH_INTERVAL)
    
    def get_token(self) -> str:
        """Thread-safe token access."""
        with self._token_lock:
            return self._token
    
    def wait_for_first_token(self, timeout: float = 60) -> bool:
        """Waits until the first token is received."""
        return self._started_event.wait(timeout)
    
    def stop(self) -> None:
        """Stops the token fetcher."""
        self._running = False
        Logger.log("Token fetcher thread durduruluyor...")
        if self.driver:
            try:
                self.driver.minimize_window()
            except:
                pass
    
    def has_token(self) -> bool:
        """Checks if a token exists."""
        with self._token_lock:
            return len(self._token) > 0
