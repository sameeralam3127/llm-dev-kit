"""llm-dev-kit core: ports, error envelope, settings and logging.

The ports are the interfaces every swappable capability plugs into; the rest
is what every service shares.

Nothing here talks to a model, a database or the network. Implementations
live in plugins and are found through the registry (``ldk_core.plugins``).
"""

__version__ = "0.1.0"
