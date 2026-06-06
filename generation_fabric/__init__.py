"""Generation Fabric package.

The package is organized so the file names reflect the architecture:

- `core` for shared infrastructure
- `json_documents` for generic JSON CRUD
- `schema` for JSON Schema-specific behavior
- `markdown` for rendered document generation and scaffolding
- `cli` for command wiring only
"""

from .exceptions import SchemaError

__all__ = ["SchemaError"]
