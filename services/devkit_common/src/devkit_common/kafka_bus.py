import json
from collections.abc import AsyncIterator
from typing import Any

from pydantic import BaseModel

from devkit_common.config import Settings, get_settings


class KafkaEventBus:
    def __init__(self, bootstrap_servers: str) -> None:
        self.bootstrap_servers = bootstrap_servers
        self._producer = None

    @classmethod
    def from_settings(cls, settings: Settings | None = None) -> "KafkaEventBus":
        settings = settings or get_settings()
        return cls(settings.kafka_bootstrap_servers)

    async def _get_producer(self):
        if self._producer is None:
            try:
                from aiokafka import AIOKafkaProducer
            except ImportError as exc:
                raise RuntimeError("Install aiokafka to publish Kafka events") from exc
            self._producer = AIOKafkaProducer(
                bootstrap_servers=self.bootstrap_servers,
                value_serializer=lambda value: json.dumps(value).encode(),
                key_serializer=lambda value: value.encode() if value else None,
            )
            await self._producer.start()
        return self._producer

    async def publish(self, topic: str, event: Any, key: str | None = None) -> None:
        payload = event.model_dump(mode="json") if isinstance(event, BaseModel) else event
        producer = await self._get_producer()
        await producer.send_and_wait(topic, payload, key=key)

    async def close(self) -> None:
        if self._producer is not None:
            await self._producer.stop()
            self._producer = None


class JsonKafkaConsumer:
    def __init__(
        self,
        *,
        bootstrap_servers: str,
        topic: str,
        group_id: str,
    ) -> None:
        self.bootstrap_servers = bootstrap_servers
        self.topic = topic
        self.group_id = group_id
        self._consumer = None

    async def start(self) -> None:
        try:
            from aiokafka import AIOKafkaConsumer
        except ImportError as exc:
            raise RuntimeError("Install aiokafka to consume Kafka events") from exc

        self._consumer = AIOKafkaConsumer(
            self.topic,
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.group_id,
            enable_auto_commit=False,
            value_deserializer=lambda value: json.loads(value.decode()),
        )
        await self._consumer.start()

    async def stop(self) -> None:
        if self._consumer is not None:
            await self._consumer.stop()
            self._consumer = None

    async def messages(self) -> AsyncIterator[tuple[dict[str, Any], Any]]:
        if self._consumer is None:
            await self.start()
        async for message in self._consumer:
            context = {
                "consumer_group": self.group_id,
                "partition": message.partition,
                "offset": message.offset,
            }
            yield message.value, context

    async def commit(self) -> None:
        if self._consumer is not None:
            await self._consumer.commit()


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
