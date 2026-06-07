"""Worker bee migration scaffolding for Generation Fabric.

This package holds the strategy dataclasses and future planner/executor
boundaries for the worker-bee integration.
"""

from .planner import (
    PACKET_TYPE,
    PACKET_VERSION,
    WorkerBeeGenerationPacket,
    WorkerBeePlanStep,
    build_generation_packet,
    infer_focus,
)
from .strategy import WorkerBeeMigrationStrategy, WorkerBeePhase, WorkerBeeSurface, build_default_worker_bee_strategy

__all__ = [
    "PACKET_TYPE",
    "PACKET_VERSION",
    "WorkerBeeGenerationPacket",
    "WorkerBeePlanStep",
    "WorkerBeeMigrationStrategy",
    "WorkerBeePhase",
    "WorkerBeeSurface",
    "build_generation_packet",
    "build_default_worker_bee_strategy",
    "infer_focus",
]
