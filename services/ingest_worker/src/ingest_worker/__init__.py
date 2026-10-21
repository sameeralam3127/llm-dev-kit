"""ingest-worker: the one pipeline every document goes through.

claim a job → read the original → parse → chunk → embed → replace the
document's chunks in one transaction. See :mod:`ingest_worker.pipeline`.
"""
