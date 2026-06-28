import json
from collections.abc import AsyncIterator
from typing import Any


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
