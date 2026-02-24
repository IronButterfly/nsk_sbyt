import requests
import logging
import re
from requests.compat import urljoin
from .const import LOGIN_URL, ACCOUNTS_URL

_LOGGER = logging.getLogger(__name__)

class NskSbytApi:
    def __init__(self, login, password):
        self.login = login
        self.password = password
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/26.2 Safari/605.1.15",
            "Accept": "text/html, */*; q=0.01",
            "Accept-Language": "ru",
            "X-Requested-With": "XMLHttpRequest",
            "Origin": "https://narod.nskes.ru",
            "Connection": "keep-alive"
        })

    def _get_csrf_token(self):
        try:
            resp = self.session.get(LOGIN_URL)
            match = re.search(r'<meta name="csrf-token" content="([^"]+)"', resp.text)
            if match:
                return match.group(1)
            return None
        except Exception as e:
            _LOGGER.error(f"Ошибка при получении CSRF токена: {e}")
            return None

    def authenticate(self):
        csrf_token = self._get_csrf_token()
        if not csrf_token:
            return False

        login_type = "email" if "@" in self.login else "phone"
        form_data = {
            "_csrf-lk": (None, csrf_token),
            "Login[login]": (None, self.login),
            "Login[password]": (None, self.password),
            "type_login": (None, login_type)
        }
        
        headers = {
            "X-CSRF-Token": csrf_token,
            "X-PJAX": "true",
            "X-PJAX-Container": "#p0",
            "Referer": LOGIN_URL
        }

        try:
            resp = self.session.post(LOGIN_URL, files=form_data, headers=headers, allow_redirects=False)

            if resp.status_code == 302:
                location = resp.headers.get('Location')
                if not location: location = resp.headers.get('x-pjax-url')
                if not location: location = "/"
                if location.startswith('/'): location = urljoin(LOGIN_URL, location)
                
                self.session.get(location)
                return True
            
            elif resp.status_code == 200:
                _LOGGER.error("Ошибка авторизации: 200. Неверный логин/пароль?")
                return False
            
            return False

        except Exception as e:
            _LOGGER.error(f"Исключение при авторизации: {e}")
            return False

    def get_accounts(self):
        csrf_cookie = self.session.cookies.get('_csrf-lk')
        headers = {}
        if csrf_cookie:
            headers["X-CSRF-Token"] = csrf_cookie

        try:
            resp = self.session.get(ACCOUNTS_URL, headers=headers)
            if resp.status_code == 200:
                try:
                    return resp.json()
                except ValueError:
                    return None
            return None
        except Exception as e:
            _LOGGER.error(f"Ошибка при запросе счетов: {e}")
            return None
    
    def get_account_details(self):
        """Получение детализации (HTML) и парсинг."""
        csrf_cookie = self.session.cookies.get('_csrf-lk')
        headers = {
            "X-CSRF-Token": csrf_cookie,
            "X-PJAX": "true",
            "X-PJAX-Container": "#pjax-account-details",
            "Referer": "https://narod.nskes.ru/"
        }
        
        url = "https://narod.nskes.ru/accounts-details/?full=N&_pjax=%23pjax-account-details"
        
        try:
            resp = self.session.get(url, headers=headers)
            if resp.status_code == 200:
                html_text = resp.text
                
                try:
                    from bs4 import BeautifulSoup
                    soup = BeautifulSoup(html_text, 'html.parser')
                    
                    details = {}

                    # 1. Парсинг платежей
                    payments_items = soup.find_all('div', class_='account-details-page__payments-item')
                    for item in payments_items:
                        title_div = item.find('div', class_='account-details-page__payments-item-title')
                        text_div = item.find('div', class_='account-details-page__payments-item-text')
                        if title_div and text_div:
                            key = title_div.get_text(strip=True)
                            val = text_div.get_text(strip=True)
                            details[key] = val

                    # 2. Парсинг таблицы показаний
                    rows = soup.find_all('div', class_='account-details-page__last-table-row')
                    for row in rows:
                        cols = row.find_all('div', class_='account-details-page__last-table-col')
                        if len(cols) == 2:
                            key = cols[0].get_text(strip=True)
                            
                            # Специальная обработка для Тарифа (он спрятан в span)
                            if "Тариф" in key:
                                # Ищем span с классом --value
                                val_span = cols[1].find('span', class_='account-details-page__last-table-col--value')
                                if val_span:
                                    val = val_span.get_text(strip=True)
                                else:
                                    # Fallback: просто текст
                                    val = cols[1].get_text(strip=True).split('Информация')[0].strip()
                            else:
                                # Обычный текст
                                val = cols[1].get_text(strip=True)
                            
                            details[key] = val

                    return details
                
                except Exception as parse_ex:
                     _LOGGER.error(f"Ошибка парсинга: {parse_ex}")
                     return {}
                    
            else:
                return None
        except Exception as e:
            _LOGGER.error(f"Исключение при получении детализации: {e}")
            return None