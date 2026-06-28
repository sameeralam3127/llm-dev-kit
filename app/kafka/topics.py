from app.config import Settings, get_settings


def topic_names(settings: Settings | None = None) -> list[str]:
    settings = settings or get_settings()
    return [
        settings.kafka_topic_docs_changed,
        settings.kafka_topic_docs_indexed,
        settings.kafka_topic_docs_failed,
        settings.kafka_topic_cache_invalidate,
    ]


async def ensure_topics(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    try:
        from aiokafka.admin import AIOKafkaAdminClient, NewTopic
    except ImportError as exc:
        raise RuntimeError("Install aiokafka to manage Kafka topics") from exc

    admin = AIOKafkaAdminClient(bootstrap_servers=settings.kafka_bootstrap_servers)
    await admin.start()
    try:
        existing = await admin.list_topics()
        missing = [
            NewTopic(name=name, num_partitions=3, replication_factor=1)
            for name in topic_names(settings)
            if name not in existing
        ]
        if missing:
            await admin.create_topics(missing)
    finally:
        await admin.close()
