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
from .executor import (
    WorkerBeeDocumentPaths,
    build_ascii_billboard,
    build_worker_bee_document,
    build_worker_bee_document_data,
    build_worker_bee_document_schema,
    extract_sketch_phrases,
    normalize_sketch_phrase,
    resolve_sketch_phrases,
    write_worker_bee_document,
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
    "WorkerBeeDocumentPaths",
    "build_generation_packet",
    "build_ascii_billboard",
    "build_worker_bee_document",
    "build_worker_bee_document_data",
    "build_worker_bee_document_schema",
    "build_default_worker_bee_strategy",
    "extract_sketch_phrases",
    "infer_focus",
    "normalize_sketch_phrase",
    "resolve_sketch_phrases",
    "write_worker_bee_document",
]
