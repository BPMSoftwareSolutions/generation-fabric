"""Migration strategy scaffold for the worker-bee integration."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class WorkerBeeSurface:
    """Describe a surface that the worker bee should reuse or grow into."""

    name: str
    status: str
    responsibility: str
    files: tuple[str, ...]


@dataclass(frozen=True)
class WorkerBeePhase:
    """Describe one phase of the worker-bee migration."""

    name: str
    goal: str
    outputs: tuple[str, ...]
    guardrails: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkerBeeMigrationStrategy:
    """Describe the worker-bee migration strategy for this repository."""

    north_star: str
    planner_reviewer_boundary: str
    surfaces: tuple[WorkerBeeSurface, ...]
    phases: tuple[WorkerBeePhase, ...]


def build_default_worker_bee_strategy() -> WorkerBeeMigrationStrategy:
    """Build the default worker-bee migration strategy for Generation Fabric."""

    return WorkerBeeMigrationStrategy(
        north_star="planner -> packet -> worker -> fabric -> verifier",
        planner_reviewer_boundary=(
            "planner may use a language model to propose a contract, but execution "
            "must stay deterministic and contract-backed"
        ),
        surfaces=(
            WorkerBeeSurface(
                name="contract_pipeline",
                status="existing",
                responsibility="Own schema, JSON, and Markdown generation as the current deterministic fabric",
                files=(
                    "generation_fabric/schema/document.py",
                    "generation_fabric/schema/inference.py",
                    "generation_fabric/schema/validation.py",
                    "generation_fabric/json_documents/crud.py",
                    "generation_fabric/json_documents/sample.py",
                    "generation_fabric/markdown/renderer.py",
                    "generation_fabric/markdown/importer.py",
                ),
            ),
            WorkerBeeSurface(
                name="cli_orchestration",
                status="existing",
                responsibility="Own the current command surface that wires schema, JSON, and Markdown operations together",
                files=(
                    "generation_fabric/cli.py",
                    "json_schema_crud.py",
                ),
            ),
            WorkerBeeSurface(
                name="planner_layer",
                status="existing",
                responsibility="Propose a generation plan from a natural-language brief and select the right contract path",
                files=(
                    "generation_fabric/worker_bee/planner.py",
                    "generation_fabric/worker_bee/prompts.py",
                ),
            ),
            WorkerBeeSurface(
                name="executor_layer",
                status="existing",
                responsibility="Apply approved plans through the existing fabric without hand-stitching generated artifacts",
                files=(
                    "generation_fabric/worker_bee/executor.py",
                    "generation_fabric/worker_bee/provider.py",
                ),
            ),
            WorkerBeeSurface(
                name="learning_loop",
                status="existing",
                responsibility="Benchmark the current fabric capabilities and report coverage for the worker-bee surface",
                files=(
                    "generation_fabric/worker_bee/learning.py",
                ),
            ),
            WorkerBeeSurface(
                name="code_observation",
                status="existing",
                responsibility="Observe Python execution paths and render Mermaid sequence-diagram Markdown",
                files=(
                    "generation_fabric/worker_bee/observation.py",
                ),
            ),
            WorkerBeeSurface(
                name="ledger_and_verification",
                status="planned",
                responsibility="Record worker-bee runs, retries, and verification evidence for deterministic replay",
                files=(
                    "generation_fabric/worker_bee/ledger.py",
                    "generation_fabric/worker_bee/verification.py",
                ),
            ),
        ),
        phases=(
            WorkerBeePhase(
                name="stabilize_surface",
                goal="Keep the current CLI and contract pipeline stable while the worker bee is introduced",
                outputs=(
                    "clear module boundaries",
                    "canonical docs",
                    "a stable packet contract for generation tasks",
                ),
                guardrails=(
                    "do_not_break_existing_cli",
                    "do_not_hand_stitch_generated_output",
                ),
            ),
            WorkerBeePhase(
                name="planner_contract",
                goal="Add a planner that turns a brief into a structured generation plan",
                outputs=(
                    "generation brief contract",
                    "provider-neutral plan shape",
                    "approval boundary for reviewer logic",
                ),
                guardrails=(
                    "planner_proposes_only",
                    "planner_must_not_write_files",
                ),
            ),
            WorkerBeePhase(
                name="executor_contract",
                goal="Add a deterministic executor that consumes the approved plan and uses the fabric",
                outputs=(
                    "plan execution path",
                    "existing schema/json/markdown primitives reused",
                    "idempotent file writes",
                ),
                guardrails=(
                    "executor_must_follow_contract",
                    "executor_must_be_replayable",
                ),
            ),
            WorkerBeePhase(
                name="verification_loop",
                goal="Verify generated output through round-trip and golden-file checks",
                outputs=(
                    "round-trip tests",
                    "golden output files",
                    "provider retry evidence",
                ),
                guardrails=(
                    "verification_is_authoritative",
                    "no_completion_without_validation",
                ),
            ),
            WorkerBeePhase(
                name="operationalize",
                goal="Add run ledger, observability, and future provider swap support",
                outputs=(
                    "worker-bee ledger",
                    "portable provider adapter",
                    "operational run history",
                ),
                guardrails=(
                    "ledger_must_be_append_only",
                    "provider_swap_must_not_change_contracts",
                ),
            ),
        ),
    )
