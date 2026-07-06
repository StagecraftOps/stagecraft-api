import asyncio
import json
from concurrent.futures import ThreadPoolExecutor
from typing import Any

import boto3

from app.core.config import settings

_executor = ThreadPoolExecutor(max_workers=2)

class SQSPublisher:

    def __init__(self) -> None:
        self._client = boto3.client("sqs", region_name=settings.AWS_REGION)

    async def publish(self, message: dict[str, Any]) -> str:
        loop = asyncio.get_event_loop()
        message_body = json.dumps(message)
        response = await loop.run_in_executor(
            _executor,
            lambda: self._client.send_message(
                QueueUrl=settings.SQS_QUEUE_URL,
                MessageBody=message_body,
            ),
        )
        return response["MessageId"]
