"""
Quota-Aware Agent - Budget and quota management

Handles:
- Provider quota checking
- Budget enforcement
- Provider switching
- Rate limit handling
"""

from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
import re


class QuotaStatus(Enum):
    """Quota status for a provider."""

    OK = "ok"
    RATE_LIMITED = "rate_limited"
    QUOTA_EXHAUSTED = "quota_exhausted"
    CIRCUIT_OPEN = "circuit_open"


@dataclass
class ProviderQuota:
    """Quota information for a provider."""

    provider: str
    status: QuotaStatus
    requests_remaining: Optional[int] = None
    requests_total: Optional[int] = None
    reset_at: Optional[datetime] = None
    circuit_resets_at: Optional[datetime] = None


@dataclass
class BudgetConfig:
    """Budget configuration."""

    max_requests_per_session: Optional[int] = None
    max_cost_per_session: Optional[float] = None
    warning_threshold_percent: float = 80.0


class QuotaManager:
    """Manages provider quotas and budget."""

    def __init__(self):
        self.provider_quotas: Dict[str, ProviderQuota] = {}
        self.session_requests = 0
        self.session_cost = 0.0
        self.circuit_breakers: Dict[str, datetime] = {}

    def check_quota(
        self, provider_name: str, parallel_count: int = 1
    ) -> Tuple[bool, Optional[str]]:
        """
        Check if provider has sufficient quota.

        Returns:
            (is_ok, warning_message or None)
        """
        quota = self.provider_quotas.get(provider_name)

        if not quota:
            return True, None

        # Check circuit breaker
        if quota.status == QuotaStatus.CIRCUIT_OPEN:
            reset_str = ""
            if quota.circuit_resets_at:
                reset_str = (
                    f" (resets {self._format_relative_time(quota.circuit_resets_at)})"
                )
            return (
                False,
                f"⚠️ Provider '{provider_name}' is unavailable{reset_str}. Consider switching providers.",
            )

        # Check rate limit
        if quota.status in (QuotaStatus.RATE_LIMITED, QuotaStatus.QUOTA_EXHAUSTED):
            return (
                False,
                f"⚠️ '{provider_name}' is rate-limited. Your operation ({parallel_count} calls) may fail.",
            )

        # Check remaining quota
        if quota.requests_remaining is not None and quota.requests_total:
            remaining_pct = (quota.requests_remaining / quota.requests_total) * 100

            if quota.requests_remaining < parallel_count and remaining_pct < 10:
                reset_str = ""
                if quota.reset_at:
                    reset_str = (
                        f" (resets {self._format_relative_time(quota.reset_at)})"
                    )

                return False, (
                    f"⚠️ Low quota: '{provider_name}' has only {quota.requests_remaining}/{quota.requests_total} "
                    f"requests remaining ({remaining_pct:.0f}%){reset_str}. "
                    f"Your operation requires {parallel_count} calls."
                )
            elif remaining_pct < 20:
                return (
                    True,
                    f"⚠️ Warning: '{provider_name}' running low on quota ({remaining_pct:.0f}% remaining)",
                )

        return True, None

    def update_quota(
        self,
        provider_name: str,
        status: QuotaStatus,
        remaining: Optional[int] = None,
        total: Optional[int] = None,
        reset_at: Optional[datetime] = None,
    ):
        """Update quota information for a provider."""
        self.provider_quotas[provider_name] = ProviderQuota(
            provider=provider_name,
            status=status,
            requests_remaining=remaining,
            requests_total=total,
            reset_at=reset_at,
        )

    def open_circuit(self, provider_name: str, duration_seconds: int = 60):
        """Open circuit breaker for a provider."""
        resets_at = datetime.now() + timedelta(seconds=duration_seconds)
        self.circuit_breakers[provider_name] = resets_at

        if provider_name in self.provider_quotas:
            self.provider_quotas[provider_name].status = QuotaStatus.CIRCUIT_OPEN
            self.provider_quotas[provider_name].circuit_resets_at = resets_at

    def find_alternative_provider(self, current_provider: str) -> Optional[str]:
        """Find an available alternative provider."""
        for provider_name, quota in self.provider_quotas.items():
            if provider_name != current_provider and quota.status == QuotaStatus.OK:
                return provider_name
        return None

    def parse_switch_metadata(
        self, tool_output: str
    ) -> Optional[Tuple[str, Optional[str]]]:
        """
        Parse provider switch metadata from tool output.

        Format: <!-- metadata: {"action":"switch_provider","provider":"kimi"} -->

        Returns:
            (provider_name, model) or None
        """
        pattern = r"<!-- metadata:\s*(\{[^}]+\})\s*-->"
        match = re.search(pattern, tool_output)

        if match:
            try:
                metadata = json.loads(match.group(1))
                if metadata.get("action") == "switch_provider":
                    provider = metadata.get("provider")
                    model = metadata.get("model")
                    if provider:
                        return (provider, model)
            except json.JSONDecodeError:
                pass

        return None

    def _format_relative_time(self, dt: datetime) -> str:
        """Format datetime as relative time."""
        now = datetime.now()
        diff = dt - now

        if diff.total_seconds() < 0:
            # In the past
            abs_diff = timedelta(seconds=-diff.total_seconds())
            if abs_diff.seconds >= 3600:
                return f"{abs_diff.seconds // 3600}h ago"
            elif abs_diff.seconds >= 60:
                return f"{abs_diff.seconds // 60}m ago"
            else:
                return f"{abs_diff.seconds}s ago"
        else:
            # In the future
            if diff.seconds >= 3600:
                return f"in {diff.seconds // 3600}h {diff.seconds % 3600 // 60}m"
            elif diff.seconds >= 60:
                return f"in {diff.seconds // 60}m"
            else:
                return f"in {diff.seconds}s"


class BudgetTracker:
    """Tracks session budget usage."""

    def __init__(self, config: BudgetConfig):
        self.config = config
        self.request_count = 0
        self.estimated_cost = 0.0

    def record_request(self, cost: Optional[float] = None):
        """Record a request."""
        self.request_count += 1
        if cost:
            self.estimated_cost += cost

    def check_budget(self) -> Tuple[bool, Optional[str]]:
        """
        Check if within budget.

        Returns:
            (within_budget, warning_or_none)
        """
        # Check request limit
        if self.config.max_requests_per_session:
            if self.request_count >= self.config.max_requests_per_session:
                return (
                    False,
                    f"❌ Request limit reached ({self.request_count}/{self.config.max_requests_per_session})",
                )

            usage_pct = (
                self.request_count / self.config.max_requests_per_session
            ) * 100
            if usage_pct >= self.config.warning_threshold_percent:
                return (
                    True,
                    f"⚠️ Approaching request limit ({self.request_count}/{self.config.max_requests_per_session})",
                )

        # Check cost limit
        if self.config.max_cost_per_session:
            if self.estimated_cost >= self.config.max_cost_per_session:
                return (
                    False,
                    f"❌ Budget exceeded (${self.estimated_cost:.2f}/${self.config.max_cost_per_session:.2f})",
                )

            usage_pct = (self.estimated_cost / self.config.max_cost_per_session) * 100
            if usage_pct >= self.config.warning_threshold_percent:
                return (
                    True,
                    f"⚠️ Approaching budget limit (${self.estimated_cost:.2f}/${self.config.max_cost_per_session:.2f})",
                )

        return True, None

    def get_stats(self) -> Dict[str, Any]:
        """Get budget statistics."""
        return {
            "requests": self.request_count,
            "max_requests": self.config.max_requests_per_session,
            "estimated_cost": self.estimated_cost,
            "max_cost": self.config.max_cost_per_session,
        }


def check_quota_before_operation(
    quota_manager: QuotaManager,
    provider_name: str,
    parallel_count: int = 1,
) -> Optional[str]:
    """
    Check quota before an expensive operation.

    Returns:
        Warning message if quota is low, None if OK
    """
    if parallel_count < 5:
        # Only warn for operations with 5+ parallel calls
        return None

    is_ok, warning = quota_manager.check_quota(provider_name, parallel_count)
    return warning if not is_ok else None


import json
