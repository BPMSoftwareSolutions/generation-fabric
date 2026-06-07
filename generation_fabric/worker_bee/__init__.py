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
from .prompts import build_worker_bee_planning_prompt
from .provider import (
    DeterministicWorkerBeePlanningProvider,
    WorkerBeePlanProposal,
    WorkerBeePlanningProvider,
    build_provider_backed_generation_packet,
    propose_worker_bee_plan,
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
from .observation import (
    CodeObservationDocumentPaths,
    PythonFunctionObservation,
    build_code_observation_document_from_taxonomy,
    build_code_observation_document,
    build_code_observation_document_schema,
    collect_python_function_observations,
    write_code_observation_document_from_taxonomy,
    write_code_observation_document,
)
from .taxonomy import (
    CodeTaxonomyCondition,
    CodeTaxonomyDocument,
    CodeTaxonomyDocumentPaths,
    CodeTaxonomyExecutionPath,
    CodeTaxonomySymbol,
    build_code_taxonomy_document,
    build_code_taxonomy_document_schema,
    scan_python_source_taxonomy,
    write_code_taxonomy_document,
)
from .learning import (
    DEFAULT_WORKER_BEE_LEARNING_CAPABILITIES,
    WorkerBeeLearningCase,
    WorkerBeeLearningCaseResult,
    WorkerBeeLearningReport,
    WorkerBeeLearningRoundResult,
    build_default_worker_bee_learning_cases,
    run_worker_bee_learning_loop,
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
    "WorkerBeePlanProposal",
    "WorkerBeePlanningProvider",
    "DeterministicWorkerBeePlanningProvider",
    "CodeObservationDocumentPaths",
    "PythonFunctionObservation",
    "CodeTaxonomyCondition",
    "CodeTaxonomyDocument",
    "CodeTaxonomyDocumentPaths",
    "CodeTaxonomyExecutionPath",
    "CodeTaxonomySymbol",
    "DEFAULT_WORKER_BEE_LEARNING_CAPABILITIES",
    "WorkerBeeLearningCase",
    "WorkerBeeLearningCaseResult",
    "WorkerBeeLearningReport",
    "WorkerBeeLearningRoundResult",
    "WorkerBeeDocumentPaths",
    "build_generation_packet",
    "build_ascii_billboard",
    "build_worker_bee_document",
    "build_worker_bee_document_data",
    "build_code_observation_document_from_taxonomy",
    "build_code_taxonomy_document",
    "build_code_taxonomy_document_schema",
    "build_provider_backed_generation_packet",
    "build_code_observation_document",
    "build_code_observation_document_schema",
    "build_worker_bee_planning_prompt",
    "build_default_worker_bee_learning_cases",
    "build_worker_bee_document_schema",
    "build_default_worker_bee_strategy",
    "collect_python_function_observations",
    "extract_sketch_phrases",
    "infer_focus",
    "normalize_sketch_phrase",
    "propose_worker_bee_plan",
    "scan_python_source_taxonomy",
    "resolve_sketch_phrases",
    "run_worker_bee_learning_loop",
    "write_code_observation_document_from_taxonomy",
    "write_code_taxonomy_document",
    "write_code_observation_document",
    "write_worker_bee_document",
]
