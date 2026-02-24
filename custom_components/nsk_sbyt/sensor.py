from homeassistant.components.sensor import SensorEntity
from .const import DOMAIN
from .api import NskSbytApi
import logging
import re

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    login = entry.data["login"]
    password = entry.data["password"]
    
    api = NskSbytApi(login, password)
    
    is_auth = await hass.async_add_executor_job(api.authenticate)
    if not is_auth:
        return

    accounts = await hass.async_add_executor_job(api.get_accounts)
    details_data = await hass.async_add_executor_job(api.get_account_details)
    
    sensors = []
    
    if accounts:
        if isinstance(accounts, list):
            for acc in accounts:
                sensors.append(NskSbytSensor(acc, login, details_data))
        elif isinstance(accounts, dict) and 'items' in accounts:
             for acc in accounts['items']:
                sensors.append(NskSbytSensor(acc, login, details_data))
        else:
             sensors.append(NskSbytSensor(accounts, login, details_data))

    if sensors:
        async_add_entities(sensors)

class NskSbytSensor(SensorEntity):
    def __init__(self, account_data, login_prefix, details_data=None):
        self._attr_extra_state_attributes = {}
        
        # --- 1. Извлечение данных из JSON (База) ---
        account_id = account_data.get("id", "unknown")
        address = account_data.get("address", "")
        
        contract_info = {}
        if "contracts" in account_data and isinstance(account_data["contracts"], list) and len(account_data["contracts"]) > 0:
            contract_info = account_data["contracts"][0]
        
        debt = contract_info.get("debtAmount", 0)
        total = contract_info.get("totalAmount", 0)
        
        meter_info = {}
        if "meterDevices" in contract_info and isinstance(contract_info["meterDevices"], list) and len(contract_info["meterDevices"]) > 0:
            meter_info = contract_info["meterDevices"][0]
            
        meter_serial = meter_info.get("serialNumber", "")
        meter_reading = meter_info.get("meterReading", 0)
        meter_date = meter_info.get("dateMeterReading", "")

        # --- 2. Формирование атрибутов ---
        attrs = {
            "Лицевой счет": account_id,
            "Адрес": address,
            "Задолженность": f"{debt} ₽",
            "К оплате": f"{total} ₽",
            "Номер счетчика": meter_serial,
            "Последние показания": meter_reading,
            "Дата показаний": meter_date,
        }

        # --- 3. Обогащение данными из HTML (Детализация) ---
        if details_data and isinstance(details_data, dict):
            
            # Тариф (ищем ключ, содержащий "Тариф")
            for k, v in details_data.items():
                if "Тариф" in k:
                    attrs["Тариф"] = f"{v} ₽/кВт⋅ч"
                    break
            
            # Последний платеж (ищем ключ, содержащий "Последний платеж")
            # В HTML ключ был "Последний платеж от 12.02.2026", мы сделаем просто "Последний платеж"
            pay_key = next((k for k in details_data if "Последний платеж" in k), None)
            if pay_key:
                attrs["Последний платеж"] = details_data.get(pay_key)
                # Попробуем извлечь дату из ключа
                date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', pay_key)
                if date_match:
                    attrs["Дата последнего платежа"] = date_match.group(1)

            # Сумма к оплате по состоянию на дату
            sum_key = next((k for k in details_data if "Сумма к оплате" in k), None)
            if sum_key:
                attrs["Сумма к оплате (текущая)"] = details_data.get(sum_key)
                date_match = re.search(r'(\d{2}\.\d{2}\.\d{4})', sum_key)
                if date_match:
                    attrs["Дата расчета"] = date_match.group(1)

            # Остальные полезные поля
            attrs["Объем потребления"] = details_data.get("Объем кв/ч для расчета")
            attrs["Начислено"] = details_data.get("Начислено, руб.")
            attrs["Метод расчета"] = details_data.get("Метод расчета")

        # --- 4. Настройка сенсора ---
        self._attr_name = f"НСЭ {account_id}"
        self._attr_unique_id = f"nsk_sbyt_{login_prefix}_{account_id}"
        
        # Состояние - просто число долга (для графиков)
        try:
            self._state = float(debt)
        except:
            self._state = 0.0
        
        self._attr_native_unit_of_measurement = "₽"
        self._attr_icon = "mdi:cash"
        self._attr_extra_state_attributes = attrs

    @property
    def native_value(self):
        return self._state