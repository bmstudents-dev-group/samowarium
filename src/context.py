from datetime import datetime, timezone
from samoware_api import SamowarePollingContext


class Context:
    def __init__(
        self,
        telegram_id: int,
        samoware_login: str,
        polling_context: SamowarePollingContext | None = None,
        last_revalidation: datetime | None = None,
    ) -> None:
        self.telegram_id = telegram_id
        self.samoware_login = samoware_login
        self.polling_context = polling_context
        if self.polling_context is None:
            self.polling_context = SamowarePollingContext()
        self.last_revalidate = last_revalidation
        if self.last_revalidate is None:
            self.last_revalidate = datetime.now(timezone.utc)
