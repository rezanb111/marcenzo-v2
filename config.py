from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
from pathlib import Path


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    BOT_TOKEN: str
    API_ID: int = 0
    API_HASH: str = ""
    ADMINS: str = "marcenzo,shibainuo"
    ADMIN_IDS: str = ""
    BOT_USERNAME: str = "See30bot"
    SUPPORT_USERNAME: str = "marcenzo"

    POLYGON_RPC_URL: str = "https://polygon-rpc.com"
    POLYGON_PRIVATE_KEY: str
    TREASURY_ADDRESS: str

    XROCKET_API_KEY: str = ""
    XROCKET_BASE_URL: str = "https://pay.api.xrocket.exchange"

    DATABASE_URL: str = "sqlite+aiosqlite:///./data/loan_bot.db"
    DEFAULT_CURRENCY: str = "USDT"
    MIN_LOAN_AMOUNT: float = 0.10
    MAX_LOAN_AMOUNT: float = 100.0
    INITIAL_CREDIT_LIMIT: float = 5.0
    CREDIT_MULTIPLIER: float = 2.0
    SUCCESSFUL_LOANS_FOR_UPGRADE: int = 3
    LOAN_INTEREST_PERCENT: float = 10.0
    INTEREST_PERIOD_DAYS: int = 7
    LATE_INCREASE_PERCENT: float = 1.0
    INSTALLMENT_PERIOD_DAYS: int = 7
    MIN_INVEST_AMOUNT: float = 1.0
    DEFAULT_LANGUAGE: str = "en"

    # Referral
    REFERRAL_BONUS_SIGNUP: float = 0.5
    REFERRAL_BONUS_FIRST_LOAN: float = 1.0
    MAX_LOANS_PER_DAY: int = 3
    EARLY_REPAY_DISCOUNT_PERCENT: float = 5.0

    USDT_CONTRACT: str = "0xc2132D05D31c914a87C6611C10748AEb04B58e8F"
    USDT_DECIMALS: int = 6
    CHAIN_ID: int = 137

    @property
    def admin_usernames(self) -> List[str]:
        return [a.strip().lower().lstrip("@") for a in self.ADMINS.split(",") if a.strip()]

    @property
    def admin_ids(self) -> List[int]:
        if not self.ADMIN_IDS.strip():
            return []
        return [int(x.strip()) for x in self.ADMIN_IDS.split(",") if x.strip()]


settings = Settings()
