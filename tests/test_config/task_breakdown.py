"""Tests for task breakdown config."""

from pathlib import Path

import pytest

from village.config import Config, TaskBreakdownConfig


@pytest.fixture
def test_config(tmp_path: Path) -> Config:
    """Create a test Config instance with required fields."""
    return Config(
        git_root=tmp_path,
        village_dir=tmp_path / ".village",
        worktrees_dir=tmp_path / ".worktrees",
    )


class TestTaskBreakdownConfig:
    """Test TaskBreakdownConfig dataclass."""

    def test_default_strategy_is_st_aot_light(self):
        """Test that default strategy is st_aot_light."""
        config = TaskBreakdownConfig()
        assert config.strategy == "st_aot_light"

    def test_can_set_sequential_strategy(self):
        """Test setting strategy to sequential."""
        config = TaskBreakdownConfig(strategy="sequential")
        assert config.strategy == "sequential"

    def test_can_set_atomic_strategy(self):
        """Test setting strategy to atomic."""
        config = TaskBreakdownConfig(strategy="atomic")
        assert config.strategy == "atomic"

    def test_strategy_is_str(self):
        """Test that strategy field is string type."""
        config = TaskBreakdownConfig(strategy="st_aot_light")
        assert isinstance(config.strategy, str)

    def test_all_strategy_options(self):
        """Test all valid strategy options."""
        valid_strategies = ["sequential", "atomic", "st_aot_light"]
        for strategy in valid_strategies:
            config = TaskBreakdownConfig(strategy=strategy)
            assert config.strategy == strategy

    def test_strategy_default_case(self):
        """Test that lowercase values work for default."""
        config = TaskBreakdownConfig(strategy="sequential".lower())
        assert config.strategy == "sequential"

    def test_default_granularity(self):
        """Test default granularity bounds."""
        config = TaskBreakdownConfig()
        assert config.min_tasks == 3
        assert config.max_tasks == 7
        assert config.max_effort_hours == 4

    def test_can_override_granularity(self):
        """Test overriding granularity bounds."""
        config = TaskBreakdownConfig(min_tasks=1, max_tasks=3, max_effort_hours=2)
        assert config.min_tasks == 1
        assert config.max_tasks == 3
        assert config.max_effort_hours == 2

    def test_min_max_swap_when_inverted(self, monkeypatch: pytest.MonkeyPatch):
        """Test that min/max are swapped if min > max."""
        monkeypatch.delenv("VILLAGE_TASK_MIN", raising=False)
        monkeypatch.delenv("VILLAGE_TASK_MAX", raising=False)
        monkeypatch.delenv("VILLAGE_TASK_MAX_EFFORT_HOURS", raising=False)
        config = TaskBreakdownConfig.from_env_and_config(
            {"task_breakdown.min_tasks": "10", "task_breakdown.max_tasks": "2"}
        )
        assert config.min_tasks == 2
        assert config.max_tasks == 10

    def test_from_env_granularity(self, monkeypatch: pytest.MonkeyPatch):
        """Test granularity from env vars."""
        monkeypatch.setenv("VILLAGE_TASK_MIN", "2")
        monkeypatch.setenv("VILLAGE_TASK_MAX", "5")
        monkeypatch.setenv("VILLAGE_TASK_MAX_EFFORT_HOURS", "8")
        config = TaskBreakdownConfig.from_env_and_config({})
        assert config.min_tasks == 2
        assert config.max_tasks == 5
        assert config.max_effort_hours == 8

    def test_from_config_dict_granularity(self, monkeypatch: pytest.MonkeyPatch):
        """Test granularity from config dict."""
        monkeypatch.delenv("VILLAGE_TASK_MIN", raising=False)
        monkeypatch.delenv("VILLAGE_TASK_MAX", raising=False)
        monkeypatch.delenv("VILLAGE_TASK_MAX_EFFORT_HOURS", raising=False)
        config = TaskBreakdownConfig.from_env_and_config(
            {"task_breakdown.min_tasks": "1", "task_breakdown.max_tasks": "4", "task_breakdown.max_effort_hours": "2"}
        )
        assert config.min_tasks == 1
        assert config.max_tasks == 4
        assert config.max_effort_hours == 2

    def test_env_overrides_config_dict(self, monkeypatch: pytest.MonkeyPatch):
        """Test env vars take priority over config dict."""
        monkeypatch.setenv("VILLAGE_TASK_MIN", "1")
        monkeypatch.setenv("VILLAGE_TASK_MAX", "2")
        config = TaskBreakdownConfig.from_env_and_config(
            {"task_breakdown.min_tasks": "5", "task_breakdown.max_tasks": "10"}
        )
        assert config.min_tasks == 1
        assert config.max_tasks == 2


class TestConfigWithTaskBreakdown:
    """Test TaskBreakdownConfig integrated into Config."""

    def test_default_task_breakdown_config(self, test_config: Config):
        """Test Config has default TaskBreakdownConfig."""
        assert hasattr(test_config, "task_breakdown")
        assert isinstance(test_config.task_breakdown, TaskBreakdownConfig)
        assert test_config.task_breakdown.strategy == "st_aot_light"

    def test_can_override_task_breakdown_strategy(self, test_config: Config):
        """Test overriding task breakdown strategy."""
        test_config.task_breakdown.strategy = "sequential"
        assert test_config.task_breakdown.strategy == "sequential"

    def test_task_breakdown_persists_across_instantiation(self):
        """Test task breakdown config persists."""
        from pathlib import Path

        config1 = Config(
            git_root=Path("/tmp/test1"),
            village_dir=Path("/tmp/test1/.village"),
            worktrees_dir=Path("/tmp/test1/.worktrees"),
        )
        config1.task_breakdown.strategy = "atomic"

        config2 = Config(
            git_root=Path("/tmp/test2"),
            village_dir=Path("/tmp/test2/.village"),
            worktrees_dir=Path("/tmp/test2/.worktrees"),
        )
        assert config2.task_breakdown.strategy == "st_aot_light"

    def test_task_breakdown_inheritance(self, test_config: Config):
        """Test task breakdown is separate from other config."""
        assert test_config.task_breakdown.strategy == "st_aot_light"
        assert hasattr(test_config, "llm")
        assert hasattr(test_config, "mcp")
