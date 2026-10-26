import logging
from dataclasses import dataclass

import aioboto3
from boto3.s3.transfer import TransferConfig
from botocore.config import Config
from botocore.exceptions import ClientError

from app.application.ports.services import StoredObject
from app.domain.errors import InvalidInput, NotFound

log = logging.getLogger(__name__)

READ_CHUNK = 256 * 1024
TRANSFER = TransferConfig(
    multipart_threshold=16 * 2**20,
    multipart_chunksize=16 * 2**20,
    max_concurrency=4,
)


@dataclass(frozen=True)
class S3Config:
    bucket: str
    endpoint_url: str | None = None
    region: str = "us-east-1"
    access_key: str | None = None
    secret_key: str | None = None
    prefix: str = ""


class S3FileStorage:
    def __init__(self, config: S3Config):
        self._c = config
        self._session = aioboto3.Session(
            aws_access_key_id=config.access_key or None,
            aws_secret_access_key=config.secret_key or None,
            region_name=config.region,
        )
        self._boto = Config(signature_version="s3v4", s3={"addressing_style": "path"})

    def _client(self):
        return self._session.client(
            "s3", endpoint_url=self._c.endpoint_url or None, config=self._boto
        )

    def _key(self, key: str) -> str:
        return (
            f"{self._c.prefix.strip('/')}/{key}" if self._c.prefix.strip("/") else key
        )

    async def prepare(self) -> None:
        async with self._client() as s3:
            try:
                await s3.head_bucket(Bucket=self._c.bucket)
            except ClientError:
                kwargs = {}
                if self._c.region and self._c.region != "us-east-1":
                    kwargs["CreateBucketConfiguration"] = {
                        "LocationConstraint": self._c.region
                    }
                await s3.create_bucket(Bucket=self._c.bucket, **kwargs)
                log.info("Created S3 bucket %s", self._c.bucket)

    async def put_file(self, key: str, path: str, content_type: str | None) -> None:
        extra = {"ContentType": content_type} if content_type else None
        async with self._client() as s3:
            await s3.upload_file(
                path, self._c.bucket, self._key(key), ExtraArgs=extra, Config=TRANSFER
            )

    async def open(self, key: str, byte_range: str | None = None) -> StoredObject:
        client = self._client()
        s3 = await client.__aenter__()
        try:
            extra = {"Range": byte_range} if byte_range else {}
            resp = await s3.get_object(
                Bucket=self._c.bucket, Key=self._key(key), **extra
            )
        except ClientError as e:
            await client.__aexit__(None, None, None)
            code = e.response.get("Error", {}).get("Code")
            if code in ("NoSuchKey", "404", "NotFound"):
                raise NotFound("Файл не найден в хранилище") from e
            if code == "InvalidRange":
                raise InvalidInput("Неверный диапазон") from e
            raise
        except BaseException:
            await client.__aexit__(None, None, None)
            raise
        body = resp["Body"]

        async def chunks():
            try:
                while chunk := await body.read(READ_CHUNK):
                    yield chunk
            finally:
                body.close()
                await client.__aexit__(None, None, None)

        return StoredObject(
            chunks(),
            resp["ContentLength"],
            resp.get("ContentType"),
            resp.get("ContentRange"),
        )

    async def delete(self, key: str) -> None:
        async with self._client() as s3:
            await s3.delete_object(Bucket=self._c.bucket, Key=self._key(key))
