"""Shared exceptions for the generation fabric."""


class GenerationFabricError(Exception):
    """Base exception for generation-fabric operations."""


class SchemaError(GenerationFabricError):
    """Raised when a schema, JSON document, or render operation is invalid."""
