import os
from dataclasses import dataclass, field
from typing import Optional

from village.config._helpers import _env_or_config, _parse_bool, _parse_int, _parse_str


@dataclass
class DebugConfig:
    """Debug configuration."""

    enabled: bool = False

    @classmethod
    def from_env(cls) -> "DebugConfig":
        enabled = _parse_bool(os.environ.get("VILLAGE_DEBUG"), default=False)
        return cls(enabled=enabled)


@dataclass
class LLMConfig:
    """LLM provider configuration."""

    provider: str = "openrouter"
    model: str = "anthropic/claude-3.5-sonnet"
    api_key_env: str = "OPENROUTER_API_KEY"
    timeout: int = 300
    max_tokens: int = 4096

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "LLMConfig":
        provider = _parse_str(_env_or_config("VILLAGE_LLM_PROVIDER", config, "LLM_PROVIDER"), "openrouter")
        model = _parse_str(_env_or_config("VILLAGE_LLM_MODEL", config, "LLM_MODEL"), "anthropic/claude-3.5-sonnet")
        timeout = _parse_int(_env_or_config("VILLAGE_LLM_TIMEOUT", config, "LLM_TIMEOUT"), 300)
        max_tokens = _parse_int(_env_or_config("VILLAGE_LLM_MAX_TOKENS", config, "LLM_MAX_TOKENS"), 4096)

        llm_config = cls(provider=provider, model=model, timeout=timeout, max_tokens=max_tokens)
        api_key = _env_or_config("VILLAGE_LLM_API_KEY", config, "LLM_API_KEY")
        if api_key:
            llm_config.api_key_env = api_key
        return llm_config


@dataclass
class MCPConfig:
    """MCP client configuration."""

    enabled: bool = True
    client_type: str = "mcp-use"
    mcp_use_path: str = "mcp-use"
    tool_name_pattern: str = "mcproxy_{server}__{tool}"

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "MCPConfig":
        enabled_raw = _env_or_config("VILLAGE_MCP_ENABLED", config, "MCP_ENABLED")
        enabled = _parse_bool(enabled_raw, default=True)
        client_type = _parse_str(_env_or_config("VILLAGE_MCP_CLIENT", config, "MCP_CLIENT"), "mcp-use")
        mcp_use_path = _parse_str(config.get("MCP_USE_PATH"), "mcp-use")
        tool_name_pattern = _parse_str(
            _env_or_config("VILLAGE_MCP_TOOL_PATTERN", config, "MCP_TOOL_PATTERN"),
            "mcproxy_{server}__{tool}",
        )
        return cls(
            enabled=enabled, client_type=client_type, mcp_use_path=mcp_use_path, tool_name_pattern=tool_name_pattern
        )


@dataclass
class SafetyConfig:
    """Safety configuration for rollback behavior."""

    rollback_on_failure: bool = True

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "SafetyConfig":
        rollback_raw = _env_or_config("VILLAGE_ROLLBACK_ON_FAILURE", config, "ROLLBACK_ON_FAILURE")
        return cls(rollback_on_failure=_parse_bool(rollback_raw, default=True))


@dataclass
class ConflictConfig:
    """Conflict detection configuration."""

    enabled: bool = True
    block_on_conflict: bool = False

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "ConflictConfig":
        enabled_raw = _env_or_config("VILLAGE_CONFLICT_DETECTION_ENABLED", config, "CONFLICT_DETECTION_ENABLED")
        block_raw = _env_or_config("VILLAGE_BLOCK_ON_CONFLICT", config, "BLOCK_ON_CONFLICT")
        return cls(
            enabled=_parse_bool(enabled_raw, default=True),
            block_on_conflict=_parse_bool(block_raw, default=False),
        )


@dataclass
class MetricsConfig:
    """Metrics configuration."""

    backend: str = "prometheus"
    port: int = 9090
    export_interval_seconds: int = 60
    statsd_host: str = "localhost"
    statsd_port: int = 8125

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "MetricsConfig":
        backend = _parse_str(_env_or_config("VILLAGE_METRICS_BACKEND", config, "METRICS_BACKEND"), "prometheus")
        port = _parse_int(_env_or_config("VILLAGE_METRICS_PORT", config, "METRICS_PORT"), 9090)
        export_interval_seconds = _parse_int(
            _env_or_config("VILLAGE_METRICS_EXPORT_INTERVAL", config, "METRICS_EXPORT_INTERVAL"), 60
        )
        statsd_host = _parse_str(_env_or_config("VILLAGE_STATSD_HOST", config, "STATSD_HOST"), "localhost")
        statsd_port = _parse_int(_env_or_config("VILLAGE_STATSD_PORT", config, "STATSD_PORT"), 8125)
        return cls(
            backend=backend,
            port=port,
            export_interval_seconds=export_interval_seconds,
            statsd_host=statsd_host,
            statsd_port=statsd_port,
        )


@dataclass
class DashboardConfig:
    """Dashboard configuration."""

    refresh_interval_seconds: int = 2
    enabled: bool = True

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "DashboardConfig":
        refresh_interval_seconds = _parse_int(
            _env_or_config("VILLAGE_DASHBOARD_REFRESH_INTERVAL", config, "DASHBOARD_REFRESH_INTERVAL"), 2
        )
        enabled_raw = _env_or_config("VILLAGE_DASHBOARD_ENABLED", config, "DASHBOARD_ENABLED")
        return cls(refresh_interval_seconds=refresh_interval_seconds, enabled=_parse_bool(enabled_raw, default=True))


@dataclass
class CIConfig:
    """CI/CD configuration."""

    github_token: str | None = None
    gitlab_token: str | None = None
    jenkins_token: str | None = None

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "CIConfig":
        return cls(
            github_token=os.environ.get("GITHUB_TOKEN"),
            gitlab_token=os.environ.get("GITLAB_TOKEN"),
            jenkins_token=os.environ.get("JENKINS_TOKEN"),
        )


@dataclass
class NotificationConfig:
    """Notification configuration."""

    slack_webhook_url: str | None = None
    discord_webhook_url: str | None = None
    email_smtp_server: str | None = None
    task_failed_enabled: bool = False
    orphan_detected_enabled: bool = False
    high_priority_task_enabled: bool = False

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "NotificationConfig":
        return cls(
            slack_webhook_url=os.environ.get("VILLAGE_SLACK_WEBHOOK_URL"),
            discord_webhook_url=os.environ.get("VILLAGE_DISCORD_WEBHOOK_URL"),
            email_smtp_server=os.environ.get("VILLAGE_EMAIL_SMTP_SERVER"),
            task_failed_enabled=_parse_bool(os.environ.get("VILLAGE_NOTIFY_TASK_FAILED"), default=False),
            orphan_detected_enabled=_parse_bool(os.environ.get("VILLAGE_NOTIFY_ORPHAN_DETECTED"), default=False),
            high_priority_task_enabled=_parse_bool(os.environ.get("VILLAGE_NOTIFY_HIGH_PRIORITY_TASK"), default=False),
        )


@dataclass
class ExtensionConfig:
    """Extension system configuration."""

    enabled: bool = True
    processor_module: Optional[str] = None
    tool_invoker_module: Optional[str] = None
    thinking_refiner_module: Optional[str] = None
    chat_context_module: Optional[str] = None
    task_hooks_module: Optional[str] = None
    server_discovery_module: Optional[str] = None
    llm_adapter_module: Optional[str] = None

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "ExtensionConfig":
        enabled_raw = os.environ.get("VILLAGE_EXTENSIONS_ENABLED") or config.get("EXTENSIONS.ENABLED")
        enabled = enabled_raw is None or enabled_raw.lower() in ("1", "true", "yes", "")
        return cls(
            enabled=enabled,
            processor_module=_env_or_config(
                "VILLAGE_EXTENSIONS_PROCESSOR_MODULE", config, "EXTENSIONS.PROCESSOR_MODULE"
            ),
            tool_invoker_module=_env_or_config(
                "VILLAGE_EXTENSIONS_TOOL_INVOKER_MODULE", config, "EXTENSIONS.TOOL_INVOKER_MODULE"
            ),
            thinking_refiner_module=_env_or_config(
                "VILLAGE_EXTENSIONS_THINKING_REFINER_MODULE", config, "EXTENSIONS.THINKING_REFINER_MODULE"
            ),
            chat_context_module=_env_or_config(
                "VILLAGE_EXTENSIONS_CHAT_CONTEXT_MODULE", config, "EXTENSIONS.CHAT_CONTEXT_MODULE"
            ),
            task_hooks_module=_env_or_config(
                "VILLAGE_EXTENSIONS_TASK_HOOKS_MODULE", config, "EXTENSIONS.TASK_HOOKS_MODULE"
            ),
            server_discovery_module=_env_or_config(
                "VILLAGE_EXTENSIONS_SERVER_DISCOVERY_MODULE", config, "EXTENSIONS.SERVER_DISCOVERY_MODULE"
            ),
            llm_adapter_module=_env_or_config(
                "VILLAGE_EXTENSIONS_LLM_ADAPTER_MODULE", config, "EXTENSIONS.LLM_ADAPTER_MODULE"
            ),
        )


@dataclass
class TaskBreakdownConfig:
    """Task breakdown strategy and granularity configuration."""

    strategy: str = "st_aot_light"
    min_tasks: int = 3
    max_tasks: int = 7
    max_effort_hours: int = 4

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "TaskBreakdownConfig":
        strategy = _parse_str(
            _env_or_config("VILLAGE_TASK_BREAKDOWN_STRATEGY", config, "TASK_BREAKDOWN.STRATEGY"), "st_aot_light"
        )
        min_tasks = _parse_int(
            os.environ.get("VILLAGE_TASK_MIN")
            or config.get("task_breakdown.min_tasks", ""),
            3,
        )
        max_tasks = _parse_int(
            os.environ.get("VILLAGE_TASK_MAX")
            or config.get("task_breakdown.max_tasks", ""),
            7,
        )
        max_effort_hours = _parse_int(
            os.environ.get("VILLAGE_TASK_MAX_EFFORT_HOURS")
            or config.get("task_breakdown.max_effort_hours", ""),
            4,
        )
        if min_tasks > max_tasks:
            min_tasks, max_tasks = max_tasks, min_tasks
        return cls(strategy=strategy, min_tasks=min_tasks, max_tasks=max_tasks, max_effort_hours=max_effort_hours)


@dataclass
class MemoryConfig:
    """File-based memory configuration."""

    enabled: bool = False
    store_path: str = ".village/memory/"
    ollama_url: str = ""
    embed_model: str = ""

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "MemoryConfig":
        enabled_raw = (
            os.environ.get("VILLAGE_MEMORY_ENABLED", "").lower()
            or config.get("memory.enabled", "").lower()
            or config.get("MEMORY.ENABLED", "").lower()
        )
        store_path = _parse_str(
            os.environ.get("VILLAGE_MEMORY_PATH") or config.get("memory.store_path") or config.get("MEMORY.STORE_PATH"),
            ".village/memory/",
        )
        ollama_url = (
            os.environ.get("VILLAGE_EMBED_URL", "")
            or os.environ.get("OLLAMA_BASE_URL", "")
            or config.get("memory.ollama_url", "")
            or config.get("MEMORY.OLLAMA_URL", "")
        )
        embed_model = (
            os.environ.get("VILLAGE_EMBED_MODEL", "")
            or config.get("memory.embed_model", "")
            or config.get("MEMORY.EMBED_MODEL", "")
        )
        return cls(
            enabled=_parse_bool(enabled_raw, default=False),
            store_path=store_path,
            ollama_url=ollama_url,
            embed_model=embed_model,
        )


@dataclass
class CouncilConfig:
    default_type: str = "chat"
    max_turns: int = 10
    extension_turns: int = 5
    default_rounds: int = 3
    resolution_strategy: str = "synthesis"
    personas_dir: str = "personas/"

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "CouncilConfig":
        default_type = _parse_str(
            _env_or_config("VILLAGE_COUNCIL_TYPE", config, "council.default_type", "COUNCIL.DEFAULT_TYPE"), "chat"
        )
        max_turns = _parse_int(
            os.environ.get("VILLAGE_COUNCIL_MAX_TURNS")
            or config.get("council.max_turns")
            or config.get("COUNCIL.MAX_TURNS"),
            10,
        )
        extension_turns = _parse_int(
            os.environ.get("VILLAGE_COUNCIL_EXTENSION_TURNS")
            or config.get("council.extension_turns")
            or config.get("COUNCIL.EXTENSION_TURNS"),
            5,
        )
        default_rounds = _parse_int(
            os.environ.get("VILLAGE_COUNCIL_ROUNDS")
            or config.get("council.default_rounds")
            or config.get("COUNCIL.DEFAULT_ROUNDS"),
            3,
        )
        resolution_strategy = _parse_str(
            _env_or_config(
                "VILLAGE_COUNCIL_RESOLUTION", config, "council.resolution_strategy", "COUNCIL.RESOLUTION_STRATEGY"
            ),
            "synthesis",
        )
        personas_dir = _parse_str(
            _env_or_config("VILLAGE_COUNCIL_PERSONAS_DIR", config, "council.personas_dir", "COUNCIL.PERSONAS_DIR"),
            "personas/",
        )
        return cls(
            default_type=default_type,
            max_turns=max_turns,
            extension_turns=extension_turns,
            default_rounds=default_rounds,
            resolution_strategy=resolution_strategy,
            personas_dir=personas_dir,
        )


@dataclass
class OnboardConfig:
    """Adaptive onboarding configuration."""

    interview_model: str = "openrouter/anthropic/claude-3-haiku"
    max_questions: int = 15
    skip_on_first_up: bool = False
    ppc_mode: str = "onboard"
    ppc_traits: list[str] = field(default_factory=lambda: ["critical", "probing"])
    ppc_format: str = "markdown"
    critic_persona: str = "red-team"
    self_critique: bool = True

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "OnboardConfig":
        interview_model = _parse_str(
            _env_or_config(
                "VILLAGE_ONBOARD_INTERVIEW_MODEL", config, "ONBOARD.INTERVIEW_MODEL", "onboard.interview_model"
            ),
            "openrouter/anthropic/claude-3-haiku",
        )
        max_questions = _parse_int(
            os.environ.get("VILLAGE_ONBOARD_MAX_QUESTIONS")
            or config.get("ONBOARD.MAX_QUESTIONS")
            or config.get("onboard.max_questions"),
            15,
        )
        skip_raw = (
            os.environ.get("VILLAGE_ONBOARD_SKIP_ON_FIRST_UP", "").lower()
            or config.get("ONBOARD.SKIP_ON_FIRST_UP", "").lower()
            or config.get("onboard.skip_on_first_up", "").lower()
        )
        ppc_mode = _parse_str(config.get("ONBOARD.PPC_MODE") or config.get("onboard.ppc_mode"), "onboard")
        traits_config = config.get("ONBOARD.PPC_TRAITS") or config.get("onboard.ppc_traits")
        ppc_traits = (
            [t.strip() for t in traits_config.split(",") if t.strip()] if traits_config else ["critical", "probing"]
        )
        ppc_format = _parse_str(config.get("ONBOARD.PPC_FORMAT") or config.get("onboard.ppc_format"), "markdown")
        critic_persona = _parse_str(
            config.get("ONBOARD.CRITIC_PERSONA") or config.get("onboard.critic_persona"), "red-team"
        )
        critique_raw = (
            os.environ.get("VILLAGE_ONBOARD_SELF_CRITIQUE", "").lower()
            or config.get("ONBOARD.SELF_CRITIQUE", "").lower()
            or config.get("onboard.self_critique", "").lower()
        )
        self_critique = critique_raw not in ("0", "false", "no") if critique_raw else True
        return cls(
            interview_model=interview_model,
            max_questions=max_questions,
            skip_on_first_up=_parse_bool(skip_raw, default=False),
            ppc_mode=ppc_mode,
            ppc_traits=ppc_traits,
            ppc_format=ppc_format,
            critic_persona=critic_persona,
            self_critique=self_critique,
        )


@dataclass
class ACPAgentCapability:
    """ACP agent capability definition."""

    name: str
    description: str = ""
    parameters: dict[str, str] = field(default_factory=dict)


@dataclass
class ACPConfig:
    """ACP server configuration."""

    enabled: bool = False
    server_host: str = "localhost"
    server_port: int = 9876
    protocol_version: int = 1
    capabilities: list[ACPAgentCapability] = field(default_factory=list)
    permission_mode: str = "auto"
    permission_policy_file: str | None = None

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "ACPConfig":
        enabled_raw = (
            os.environ.get("VILLAGE_ACP_ENABLED", "").lower()
            or config.get("ACP.ENABLED", "").lower()
            or config.get("acp.enabled", "").lower()
        )
        server_host = _parse_str(_env_or_config("VILLAGE_ACP_HOST", config, "ACP.HOST", "acp.host"), "localhost")
        server_port = _parse_int(
            os.environ.get("VILLAGE_ACP_PORT") or config.get("ACP.PORT") or config.get("acp.port"), 9876
        )
        protocol_version = _parse_int(
            os.environ.get("VILLAGE_ACP_VERSION") or config.get("ACP.VERSION") or config.get("acp.version"), 1
        )

        capabilities: list[ACPAgentCapability] = []
        for key, value in config.items():
            if key.startswith("ACP.CAPABILITY_") or key.startswith("acp.capability_"):
                prefix = "ACP.CAPABILITY_" if key.startswith("ACP.CAPABILITY_") else "acp.capability_"
                cap_name = key[len(prefix) :].lower()
                capabilities.append(ACPAgentCapability(name=cap_name, description=value))

        permission_mode = _parse_str(
            os.environ.get("VILLAGE_ACP_PERMISSION_MODE")
            or config.get("ACP.PERMISSION_MODE")
            or config.get("acp.permission_mode"),
            "auto",
        )
        permission_policy_file = (
            os.environ.get("VILLAGE_ACP_PERMISSION_POLICY_FILE")
            or config.get("ACP.PERMISSION_POLICY_FILE")
            or config.get("acp.permission_policy_file")
        )
        return cls(
            enabled=_parse_bool(enabled_raw, default=False),
            server_host=server_host,
            server_port=server_port,
            protocol_version=protocol_version,
            capabilities=capabilities,
            permission_mode=permission_mode,
            permission_policy_file=permission_policy_file,
        )


@dataclass
class ApprovalConfig:
    """Approval gate configuration."""

    enabled: bool = False
    threshold: int = 1

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "ApprovalConfig":
        enabled_raw = (
            os.environ.get("VILLAGE_APPROVAL_ENABLED", "").lower()
            or config.get("queue.approval_enabled", "").lower()
            or config.get("QUEUE.APPROVAL_ENABLED", "").lower()
        )
        threshold = _parse_int(
            os.environ.get("VILLAGE_APPROVAL_THRESHOLD")
            or config.get("queue.approval_threshold")
            or config.get("QUEUE.APPROVAL_THRESHOLD"),
            1,
        )
        return cls(enabled=_parse_bool(enabled_raw, default=False), threshold=threshold)


@dataclass
class TelegramConfig:
    """Telegram bot configuration."""

    bot_token_env: str = "VILLAGE_TELEGRAM_BOT_TOKEN"
    milestone_interval: int = 50
    max_context_messages: int = 10

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "TelegramConfig":
        bot_token_env = _parse_str(
            os.environ.get("VILLAGE_TELEGRAM_BOT_TOKEN_ENV")
            or config.get("TELEGRAM.BOT_TOKEN_ENV")
            or config.get("telegram.bot_token_env"),
            "VILLAGE_TELEGRAM_BOT_TOKEN",
        )
        milestone_interval = _parse_int(
            os.environ.get("VILLAGE_TELEGRAM_MILESTONE_INTERVAL")
            or config.get("TELEGRAM.MILESTONE_INTERVAL")
            or config.get("telegram.milestone_interval"),
            50,
        )
        max_context_messages = _parse_int(
            os.environ.get("VILLAGE_TELEGRAM_MAX_CONTEXT_MESSAGES")
            or config.get("TELEGRAM.MAX_CONTEXT_MESSAGES")
            or config.get("telegram.max_context_messages"),
            10,
        )
        return cls(
            bot_token_env=bot_token_env,
            milestone_interval=milestone_interval,
            max_context_messages=max_context_messages,
        )


@dataclass
class TransportConfig:
    """Transport configuration."""

    default: str = "cli"

    @classmethod
    def from_env_and_config(cls, config: dict[str, str]) -> "TransportConfig":
        default = _parse_str(
            _env_or_config("VILLAGE_TRANSPORT_DEFAULT", config, "TRANSPORT.DEFAULT", "transport.default"), "cli"
        )
        return cls(default=default)
