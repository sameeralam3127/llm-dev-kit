"""Test support for plugin authors. Requires the ``testing`` extra (pytest).

The contract suites in :mod:`ldk_core.testing.contracts` are what make
"swappable" true: every implementation of a port, first-party or not, passes
the same suite. A plugin's tests subclass the suite for its port and provide
its fixtures::

    from ldk_core.testing.contracts import ChunkerContract

    class TestRecursiveChunker(ChunkerContract):
        @pytest.fixture
        def chunker(self):
            return RecursiveChunker(size=200, overlap=20)
"""
