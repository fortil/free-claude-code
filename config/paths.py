"""Shared filesystem paths for Free Claude Code configuration."""

from pathlib import Path

FCC_CONFIG_DIRNAME = ".fcc"
FCC_ENV_FILENAME = ".env"
LEGACY_REPO_DIRNAME = "free-claude-code"
LEGACY_XDG_CONFIG_DIRNAME = ".config"
CLAUDE_WORKSPACE_DIRNAME = "agent_workspace"
FCC_LOGS_DIRNAME = "logs"
SERVER_LOG_FILENAME = "server.log"
CODEX_MODEL_CATALOG_FILENAME = "codex-model-catalog.json"
MODELS_CATALOG_FILENAME = "models.json"
MODEL_ALIASES_FILENAME = "model-aliases.json"
USAGE_STORE_FILENAME = "usage.json"
MODEL_PRICING_FILENAME = "model-pricing.json"


def config_dir_path() -> Path:
    """Return the default user config directory."""

    return Path.home() / FCC_CONFIG_DIRNAME


def managed_env_path() -> Path:
    """Return the default user-managed env file path."""

    return config_dir_path() / FCC_ENV_FILENAME


def legacy_env_paths() -> tuple[Path, ...]:
    """Return legacy user env paths that can be migrated to ~/.fcc/.env."""

    home = Path.home()
    return (
        home / LEGACY_REPO_DIRNAME / FCC_ENV_FILENAME,
        home / LEGACY_XDG_CONFIG_DIRNAME / LEGACY_REPO_DIRNAME / FCC_ENV_FILENAME,
    )


def default_claude_workspace_path() -> Path:
    """Return the default Claude workspace path."""

    return config_dir_path() / CLAUDE_WORKSPACE_DIRNAME


def server_log_path() -> Path:
    """Return the canonical server log path."""

    return config_dir_path() / FCC_LOGS_DIRNAME / SERVER_LOG_FILENAME


def codex_model_catalog_path() -> Path:
    """Return the generated Codex model catalog path."""

    return config_dir_path() / CODEX_MODEL_CATALOG_FILENAME


def models_catalog_path() -> Path:
    """Return the path of the accumulated discovered-models catalog."""

    return config_dir_path() / MODELS_CATALOG_FILENAME


def model_aliases_path() -> Path:
    """Return the path of the editable keyword -> model alias map."""

    return config_dir_path() / MODEL_ALIASES_FILENAME


def usage_store_path() -> Path:
    """Return the path of the accumulated token-usage store."""

    return config_dir_path() / USAGE_STORE_FILENAME


def model_pricing_path() -> Path:
    """Return the path of the editable per-model price override file."""

    return config_dir_path() / MODEL_PRICING_FILENAME
