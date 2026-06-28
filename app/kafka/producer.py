import json
from typing import Any

from pydantic import BaseModel

from app.config import Settings, get_settings


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
