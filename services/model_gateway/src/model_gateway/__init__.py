"""model-gateway: the only v3 service that reaches a model (architecture decision 3).

Every chat and embedding call from core-api and the ingest-worker comes
through here, so this is the one place that decides whether data may leave
the network (sovereign mode) and the one place that writes the audit event
for each model call.
"""
