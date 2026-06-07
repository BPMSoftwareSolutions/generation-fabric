"""Generation Fabric package.

The package is organized so the file names reflect the architecture:

- `core` for shared infrastructure
- `json_documents` for generic JSON CRUD and schema-driven sample generation
- `schema` for JSON Schema-specific behavior
- `markdown` for rendered document generation, import, and scaffolding
- `worker_bee` for the migration scaffold and packet planner that will sit in front of the fabric
- `cli` for command wiring only
"""

from .exceptions import SchemaError

__all__ = ["SchemaError"]
