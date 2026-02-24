import voluptuous as vol
from homeassistant import config_entries
from .const import DOMAIN, CONF_LOGIN, CONF_PASSWORD

class NskSbytConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            # Сохраняем данные и создаем запись
            return self.async_create_entry(
                title=f"НСЭ (ЛС: {user_input[CONF_LOGIN]})", 
                data=user_input
            )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({
                vol.Required(CONF_LOGIN): str,
                vol.Required(CONF_PASSWORD): str,
            }),
            errors=errors,
        )