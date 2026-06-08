"""Hermes EvalOps plugin spike."""

from .gateway_provider import EvalOpsGatewayProvider
from .hooks import register

__all__ = ["EvalOpsGatewayProvider", "register"]

