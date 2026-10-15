"""Change specification models: parsed security changes and their effects."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

from .vocab import NodeId


class Selector(BaseModel):
    """A selector that identifies one or more components."""

    components: list[NodeId]  # resolved against inventory
    raw: dict[str, Any] = Field(
        default_factory=dict
    )  # original selector for explanation


class PathEffect(BaseModel):
    """Effect of a change on a network path between components."""

    kind: Literal["path"] = "path"
    src: NodeId
    dst: NodeId
    port: int | None = None
    protocol: Literal["TCP", "UDP", "SCTP"] = "TCP"
    before: Literal["allowed", "denied"]
    after: Literal["allowed", "denied"]


class PermissionEffect(BaseModel):
    """Effect of a change on a permission grant."""

    kind: Literal["permission"] = "permission"
    principal: NodeId
    verb: str
    api_group: str
    resource: str
    resource_name: str | None = None
    namespace: str | None = None
    before: Literal["granted", "denied"]
    after: Literal["granted", "denied"]


class SecurityObjective(BaseModel):
    """The security goal this change is trying to achieve."""

    description: str
    kind: Literal[
        "restrict_ingress",
        "restrict_egress",
        "least_privilege",
        "remove_wildcard",
        "custom",
    ]
    target: NodeId | None = None


class ChangeSpec(BaseModel):
    """Complete specification of a proposed security change.

    This is the output of Part 2's change parser and the input to Part 3's analyzer.
    """

    schema_version: str = "1.0"
    change_id: str
    category: Literal["iam", "network", "kubernetes"]
    kind: Literal["k8s_networkpolicy", "k8s_rbac", "tofu_plan"]
    operation: Literal["add", "modify", "delete"]
    summary: str
    before_ref: str | None = None  # path/dir of baseline manifests (or None for add)
    after_ref: str  # path/dir/plan.json of proposed state
    effects: list[PathEffect | PermissionEffect] = Field(default_factory=list)
    direction: Literal["tightens", "loosens", "mixed", "neutral"] = "neutral"
    objective: SecurityObjective | None = None
    supported: bool = True
    parse_warnings: list[str] = Field(default_factory=list)
