"""Sequential Thinking integration for task breakdown."""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from village.chat.baseline import BaselineReport
from village.config import Config
from village.llm import get_llm_client
from village.llm.tools import (
    ATOM_OF_THOUGHTS,
    ATOM_OF_THOUGHTS_TOOL,
    SEQUENTIAL_THINKING,
    SEQUENTIAL_THINKING_TOOL,
    format_mcp_tool_name,
)

if TYPE_CHECKING:
    from village.llm.client import LLMClient

logger = logging.getLogger(__name__)


@dataclass
class TaskBreakdownItem:
    """
    Single task from Sequential Thinking breakdown.

    Attributes:
        title: Task title
        description: Detailed description
        estimated_effort: Effort estimate (hours|days|weeks)
        success_criteria: List of success criteria
        blockers: List of blockers
        dependencies: List of dependency indices (in breakdown list)
        tags: List of tags
    """

    title: str
    description: str
    estimated_effort: str
    success_criteria: list[str]
    blockers: list[str]
    dependencies: list[int]
    tags: list[str]
    search_hints: dict[str, list[str]] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.tags is None:
            self.tags = []


@dataclass
class TaskBreakdown:
    """
    Complete task breakdown from Sequential Thinking.

    Attributes:
        items: List of task breakdown items
        summary: Summary of breakdown
        created_at: Timestamp of breakdown
        title_original: User-provided title
        title_suggested: LLM-suggested better title
    """

    items: list[TaskBreakdownItem]
    summary: str
    created_at: str
    title_original: Optional[str] = None
    title_suggested: Optional[str] = None

    def __post_init__(self) -> None:
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()


def generate_task_breakdown(
    baseline: BaselineReport,
    config: Config,
    tasks_state: Optional[str] = None,
    llm_client: Optional["LLMClient"] = None,
) -> TaskBreakdown:
    """
    Generate task breakdown using configured strategy.

    Routes to appropriate strategy method based on config.task_breakdown.strategy.
    Available strategies: "st_aot_light" (default), "sequential", "atomic"

    Args:
        baseline: Collected baseline information
        config: Village configuration
        tasks_state: Optional current tasks (for context)
        llm_client: Optional LLM client to use (uses get_llm_client(config) if not provided)

    Returns:
        TaskBreakdown with parsed task list

    Raises:
        ValueError: If response is invalid or missing required fields
        json.JSONDecodeError: If response is not valid JSON
    """
    if llm_client is None:
        llm_client = get_llm_client(config)

    strategy = config.task_breakdown.strategy

    if strategy == "st_aot_light":
        return _st_aot_light_strategy(baseline, config, tasks_state, llm_client)

    # Default sequential strategy (for "sequential" and "atomic")
    prompt = _build_sequential_thinking_prompt(
        baseline, tasks_state,
        min_tasks=config.task_breakdown.min_tasks,
        max_tasks=config.task_breakdown.max_tasks,
    )

    logger.info(f"Invoking {strategy} task breakdown via LLM")

    response = llm_client.call(
        prompt,
        timeout=config.llm.timeout,
        max_tokens=config.llm.max_tokens,
        tools=[SEQUENTIAL_THINKING_TOOL] if llm_client.supports_tools else None,
    )

    logger.debug(f"LLM output length: {len(response)}")

    return _parse_task_breakdown(response)


def _build_sequential_thinking_prompt(
    baseline: BaselineReport,
    tasks_state: Optional[str] = None,
    min_tasks: int = 3,
    max_tasks: int = 7,
) -> str:
    """
    Build prompt for Sequential Thinking invocation.

    Explicitly instructs OpenCode to use Sequential Thinking MCP tool
    and return task breakdown in structured format.

    Args:
        baseline: Collected baseline information
        tasks_state: Optional current tasks (for context)

    Returns:
        Prompt string
    """
    prompt = f"""Use Sequential Thinking MCP tool to break down the following task into manageable subtasks:

USER PROVIDED:
  Title: {baseline.title}
  Reasoning: {baseline.reasoning}
"""

    if baseline.parent_task_id:
        prompt += f"  Parent task: {baseline.parent_task_id}\n"

    if baseline.tags:
        prompt += f"  Tags: {', '.join(baseline.tags)}\n"

    prompt += """

TASK:
"""

    if tasks_state:
        prompt += f"""
CONTEXT: Consider these existing tasks:
{tasks_state}

Use this context to:
- Determine if any existing tasks should be parent/related to new tasks
- Avoid creating duplicate tasks with similar titles
- Reference related tasks where appropriate
"""

    prompt += f"""
 1. Break down into {min_tasks}-{max_tasks} concrete, actionable tasks
2. Evaluate if the user's title is precise and descriptive enough
3. If the title is vague, suggest a more specific/recognizable alternative
4. Each task should be independently completable
5. Identify dependencies between tasks (by index)
6. Provide success criteria for each task
7. Estimate effort (hours|days|weeks)
8. Identify potential blockers

OUTPUT FORMAT:
Return a JSON object with the following structure:
{
  "title_original": "User-provided title (as-is)",
  "title_suggested": "More precise/recognizable title (or same if no better option)",
  "items": [
    {
      "title": "Task title (inferred by LLM based on breakdown logic)",
      "description": "Detailed description (what to do)",
      // Description should be keyword-rich for searchability:
      // - Include specific module names and file paths
      // - Name specific error types, function names, or class names
      // - Describe the behavioral change precisely
      // Example: "Add retry logic with exponential backoff to
      //   queue.py task processing. Handle ConnectionError and
      //   TimeoutError from subprocess.run() calls in resume.py."
      "estimated_effort": "X hours|days|weeks",
      "success_criteria": ["criterion 1", "criterion 2"],
      "blockers": ["blocker 1"],
      "dependencies": [0, 1],
      "tags": ["tag1", "tag2"],
      "search_hints": {"modules": ["file.py"], "concepts": ["retry", "backoff"], "patterns": ["subprocess failure"]}
    }
  ],
  "summary": "Brief summary of breakdown"
}

IMPORTANT: Use metamcp_Sequential-Thinking-Tools__sequentialthinking_tools MCP tool to generate this breakdown.
"""

    return prompt


def _parse_task_breakdown(output: str) -> TaskBreakdown:
    """
    Parse OpenCode output into TaskBreakdown.

    Extracts JSON from output (handles markdown code fences).

    Args:
        output: Raw stdout from OpenCode

    Returns:
        TaskBreakdown with parsed items

    Raises:
        ValueError: If JSON is invalid or missing required fields
        json.JSONDecodeError: If output is not valid JSON
    """
    import re

    json_str = output.strip()

    if "```json" in json_str:
        json_match = re.search(r"```json\s+(.*?)\s*```", json_str, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
    elif "```" in json_str:
        json_match = re.search(r"```\s+(.*?)\s*```", json_str, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Failed to parse JSON output: {e}")

    if "items" not in data:
        raise ValueError("Missing 'items' field in output")

    items = []
    for i, item_data in enumerate(data["items"]):
        try:
            item = TaskBreakdownItem(
                title=item_data.get("title", f"Task {i + 1}"),
                description=item_data.get("description", ""),
                estimated_effort=item_data.get("estimated_effort", "unknown"),
                success_criteria=item_data.get("success_criteria", []),
                blockers=item_data.get("blockers", []),
                dependencies=item_data.get("dependencies", []),
                tags=item_data.get("tags", []),
                search_hints=item_data.get("search_hints", {}),
            )
            items.append(item)
        except Exception as e:
            raise ValueError(f"Failed to parse task {i}: {e}")

    summary = data.get("summary", "")
    title_original = data.get("title_original")
    title_suggested = data.get("title_suggested")
    created_at = datetime.now().isoformat()

    return TaskBreakdown(
        items=items,
        summary=summary,
        title_original=title_original,
        title_suggested=title_suggested,
        created_at=created_at,
    )


def validate_dependencies(breakdown: TaskBreakdown) -> bool:
    """
    Validate that all dependency indices are valid.

    Args:
        breakdown: Task breakdown to validate

    Returns:
        True if all dependencies are valid, False otherwise
    """
    num_items = len(breakdown.items)

    for i, item in enumerate(breakdown.items):
        for dep in item.dependencies:
            if dep < 0 or dep >= num_items or dep == i:
                logger.error(f"Invalid dependency in task {i}: {dep}")
                return False

    return True


def _build_st_analysis_prompt(
    baseline: BaselineReport,
    tasks_state: Optional[str] = None,
    config: Optional[Config] = None,
) -> str:
    """
    Build Phase 1 prompt for Sequential Thinking analysis.

    Thoroughly analyzes the task to identify requirements, dependencies, edge cases,
    and other important considerations. Does NOT create tasks yet.

    Args:
        baseline: Collected baseline information
        tasks_state: Optional current tasks (for context)
        config: Village configuration (for tool name pattern)

    Returns:
        Prompt string
    """
    tool_name = format_mcp_tool_name(SEQUENTIAL_THINKING, config)

    prompt = f"""Use Sequential Thinking MCP tool to deeply analyze this task and identify all important considerations.

USER PROVIDED:
  Title: {baseline.title}
  Reasoning: {baseline.reasoning}
"""

    if baseline.parent_task_id:
        prompt += f"  Parent task: {baseline.parent_task_id}\n"

    if baseline.tags:
        prompt += f"  Tags: {', '.join(baseline.tags)}\n"

    prompt += """

TASK:
"""

    if tasks_state:
        prompt += f"""
CONTEXT: Consider these existing tasks:
{tasks_state}

Use this context to:
- Identify dependencies on existing work
- Avoid duplicating existing functionality
- Ensure new work integrates properly with existing tasks
"""

    prompt += (
        """
1. Analyze the requirements thoroughly (not tasks yet)
2. Identify all technical requirements and constraints
3. Determine necessary system components or modules
4. Identify dependencies (internal and external)
5. Identify edge cases and error conditions
6. Determine testing and verification requirements
7. Consider performance and scaling considerations
8. Identify potential risks and blockers
9. Consider security and access requirements
10. Think about maintenance and future extensibility

OUTPUT FORMAT:
Return a JSON object with the following structure:
{
  "analysis": {
    "requirements": ["requirement 1", "requirement 2"],
    "technical_constraints": ["constraint 1", "constraint 2"],
    "system_components": ["component 1", "component 2"],
    "dependencies": ["dependency 1", "dependency 2"],
    "edge_cases": ["edge case 1", "edge case 2"],
    "testing_requirements": ["test type 1", "test type 2"],
    "performance_considerations": ["consideration 1", "consideration 2"],
    "risks_and_blockers": ["risk/blocker 1", "risk/blocker 2"],
    "security_requirements": ["requirement 1", "requirement 2"],
    "maintenance_considerations": ["consideration 1", "consideration 2"]
  },
  "summary": "Brief summary of analysis findings"
}

IMPORTANT: Use """
        + tool_name
        + """ MCP tool to generate this analysis.
"""
    )

    return prompt


def _build_aot_light_atomization_prompt(
    analysis: dict[str, object],
    baseline: BaselineReport,
    max_effort_hours: int = 4,
) -> str:
    """
    Build Phase 2 prompt for Atom of Thoughts (AoT-light) atomization.

    Takes Sequential Thinking's analysis as input and creates atomic, queueable tasks.

    Args:
        analysis: Analysis from Sequential Thinking (requirements, constraints, etc.)
        baseline: Original baseline information

    Returns:
        Prompt string
    """
    tool_name = format_mcp_tool_name(ATOM_OF_THOUGHTS)

    prompt = f"""Use Atom of Thoughts (AoT-light) MCP tool to create atomic, queueable tasks based on the analysis.

ANALYSIS:
{json.dumps(analysis, indent=2, ensure_ascii=False)}
"""

    prompt += f"""
USER PROVIDED:
  Title: {baseline.title}
"""

    if baseline.tags:
        prompt += f"  Tags: {', '.join(baseline.tags)}\n"

    prompt += (
        f"""
TASK:
1. Create atomic, queueable tasks (each should be completable in 1-{max_effort_hours} hours)
2. Each task should have clear, independent scope
3. Avoid mixing concerns across tasks
4. Ensure tasks can be executed independently
5. Provide success criteria for each task
6. Identify dependencies between tasks (by index)
7. Each task should be testable and verifiable
8. Tasks should be small enough to queue and process

OUTPUT FORMAT:
Return a JSON object with the following structure:
{
  "items": [
    {
      "title": "Atomic task title",
      "description": "Detailed description of what to do",
      // Description should be keyword-rich for searchability:
      // - Include specific module names and file paths
      // - Name specific error types, function names, or class names
      // - Describe the behavioral change precisely
      // Example: "Add retry logic with exponential backoff to
      //   queue.py task processing. Handle ConnectionError and
      //   TimeoutError from subprocess.run() calls in resume.py."
      "estimated_effort": "X hours",
      "success_criteria": ["success criterion 1", "success criterion 2"],
      "dependencies": [0, 1],
      "tags": ["tag1", "tag2"],
      "search_hints": {"modules": ["file.py"], "concepts": ["retry", "backoff"], "patterns": ["subprocess failure"]}
    }
  ],
  "summary": "Brief summary of task breakdown"
}

IMPORTANT: Use """
        + tool_name
        + """ MCP tool to generate this atomic breakdown.
Focus on creating small, manageable tasks that can be queued and executed independently.
"""
    )

    return prompt


def _st_aot_light_strategy(
    baseline: BaselineReport,
    config: Config,
    tasks_state: Optional[str] = None,
    llm_client: Optional["LLMClient"] = None,
) -> TaskBreakdown:
    """
    ST → AoT Light strategy: Deep analysis first, then atomic atomization.

    Phase 1: Use Sequential Thinking for thorough analysis
    Phase 2: Use Atom of Thoughts (AoT-light) for creating atomic, queueable tasks

    Args:
        baseline: Collected baseline information
        config: Village configuration
        tasks_state: Optional current tasks (for context)
        llm_client: Optional LLM client to use

    Returns:
        TaskBreakdown with atomic task list

    Raises:
        ValueError: If response is invalid or missing required fields
        json.JSONDecodeError: If response is not valid JSON
    """
    if llm_client is None:
        llm_client = get_llm_client(config)

    logger.info("Phase 1: Running Sequential Thinking for deep analysis")
    analysis_prompt = _build_st_analysis_prompt(baseline, tasks_state, config)

    analysis_response = llm_client.call(
        analysis_prompt,
        timeout=config.llm.timeout,
        max_tokens=config.llm.max_tokens,
        tools=[SEQUENTIAL_THINKING_TOOL] if llm_client.supports_tools else None,
    )

    logger.debug(f"Sequential Thinking analysis output length: {len(analysis_response)}")

    try:
        analysis = json.loads(analysis_response)
        logger.info(f"Analysis collected: {len(analysis.get('analysis', {}))} categories")
    except json.JSONDecodeError:
        logger.warning("Failed to parse Sequential Thinking analysis, using fallback")
        analysis = {"analysis": {}, "summary": analysis_response[:200]}

    logger.info("Phase 2: Running AoT-light for atomic task creation")
    atomization_prompt = _build_aot_light_atomization_prompt(
        analysis, baseline,
        max_effort_hours=config.task_breakdown.max_effort_hours,
    )

    response = llm_client.call(
        atomization_prompt,
        timeout=config.llm.timeout,
        max_tokens=config.llm.max_tokens,
        tools=[ATOM_OF_THOUGHTS_TOOL] if llm_client.supports_tools else None,
    )

    logger.debug(f"AoT-light atomization output length: {len(response)}")
    logger.debug(f"AoT-light atomization response: {response[:500]}")

    return _parse_task_breakdown(response)
