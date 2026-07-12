from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class RuleDefinition:
    rule_id: str
    rule_code: str
    rule_name: str
    rule_type: str
    target_type: str
    target_codes: list[str]
    condition: dict[str, Any]
    sql_template_id: str
    version: str
    source_file: str
    policy_basis: str | None = None


@dataclass(frozen=True)
class QueryContext:
    date_start: str
    date_end: str
    encounter_type: str | None = None
    institution_codes: list[str] = field(default_factory=list)
    region_codes: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class SqlBuildResult:
    rule_id: str
    sql_template_id: str
    sql: str
    parameters: dict[str, Any]
    output_columns: list[str]
    explanation_template: str


class RuleExecutor(Protocol):
    rule_type: str

    def build_sql(self, rule: RuleDefinition, context: QueryContext) -> SqlBuildResult:
        ...
