import os
from dotenv import load_dotenv

load_dotenv(".env")

PROFILE_VAR_NAME = "ENV"
VERSION_VAR_NAME = "VERSION"
TG_TOKEN_VAR_NAME = "TELEGRAM_TOKEN"
DEBUG_VAR_NAME = "DEBUG"
ENCRYPTION_KEY_VAR_NAME = "ENCRYPTION"
IP_CHECK_VAR_NAME = "IP_CHECK"
ENABLE_PROMETHEUS_METRICS_SERVER_VAR_NAME = "ENABLE_PROMETHEUS_METRICS_SERVER"
PROMETHEUS_METRICS_SERVER_PORT_VAR_NAME = "PROMETHEUS_METRICS_SERVER_PORT"

DEV_PROFILE_NAME = "DEV"
PROD_PROFILE_NAME = "PROD"


def get_profile() -> str:
    return os.environ.get(PROFILE_VAR_NAME, default="unknown")


def get_version() -> str:
    return os.environ.get(VERSION_VAR_NAME, default="none")


def get_telegram_token() -> str:
    if TG_TOKEN_VAR_NAME not in os.environ:
        raise EnvironmentError(f"{TG_TOKEN_VAR_NAME} env var does not exist")
    return os.environ.get(TG_TOKEN_VAR_NAME)


def get_encryption_key() -> str | None:
    return os.environ.get(ENCRYPTION_KEY_VAR_NAME, default=None)


def get_prometheus_metrics_server_port() -> int:
    return os.environ.get(PROMETHEUS_METRICS_SERVER_PORT_VAR_NAME, default=53000)


def is_ip_check_enabled() -> bool:
    return os.environ.get(IP_CHECK_VAR_NAME) is not None


def is_dev_profile() -> bool:
    return get_profile() == DEV_PROFILE_NAME


def is_prod_profile() -> bool:
    return get_profile() == PROD_PROFILE_NAME


def is_debug() -> bool:
    return os.environ.get(DEBUG_VAR_NAME) is not None


def is_prometheus_metrics_server_enabled() -> bool:
    return os.environ.get(ENABLE_PROMETHEUS_METRICS_SERVER_VAR_NAME) is not None
