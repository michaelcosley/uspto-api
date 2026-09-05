"""ODP bulk catalog and file downloads. No implicit archive downloads."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING, Any
from urllib.parse import quote

from pydantic import Field

from uspto_client.models import UsptoModel, UsptoResponse
from uspto_client.streaming import StreamDownload, stream_download

if TYPE_CHECKING:
    from uspto_client.client import UsptoClient

SUPPORTED_PRODUCTS = ("PTFWPRE", "PTFWPRD", "PASYR", "PASDL")


class BulkFile(UsptoModel):
    file_name: str = Field(alias="fileName")
    file_size: int | None = Field(default=None, alias="fileSize")
    data_from: str | None = Field(default=None, alias="fileDataFromDate")
    data_to: str | None = Field(default=None, alias="fileDataToDate")
    file_type: str | None = Field(default=None, alias="fileTypeText")
    download_uri: str | None = Field(default=None, alias="fileDownloadURI")
    release_date: str | None = Field(default=None, alias="fileReleaseDate")
    modified: str | None = Field(default=None, alias="fileLastModifiedDateTime")


class BulkFileBag(UsptoModel):
    count: int | None = None
    files: list[BulkFile] = Field(default_factory=list, alias="fileDataBag")


class BulkProduct(UsptoModel):
    product_identifier: str = Field(alias="productIdentifier")
    title: str | None = Field(default=None, alias="productTitleText")
    description: str | None = Field(default=None, alias="productDescriptionText")
    frequency: str | None = Field(default=None, alias="productFrequencyText")
    total_bytes: int | None = Field(default=None, alias="productTotalFileSize")
    file_count: int | None = Field(default=None, alias="productFileTotalQuantity")
    file_bag: BulkFileBag = Field(default_factory=BulkFileBag, alias="productFileBag")


class BulkResponse(UsptoResponse):
    products: list[BulkProduct] = Field(
        default_factory=list, alias="bulkDataProductBag"
    )


class BulkClient:
    def __init__(self, client: UsptoClient) -> None:
        self._client = client

    def search(
        self, *, q: str | None = None, offset: int = 0, limit: int = 25
    ) -> BulkResponse:
        return self._client.request(
            "GET",
            "/api/v1/datasets/products/search",
            params={"q": q, "offset": offset, "limit": limit},
            response_model=BulkResponse,
        )

    def get_product(
        self,
        product: str,
        *,
        include_files: bool = True,
        offset: int = 0,
        limit: int = 100,
        latest: bool = False,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> BulkResponse:
        return self._client.request(
            "GET",
            f"/api/v1/datasets/products/{quote(product, safe='')}",
            params={
                "includeFiles": str(include_files).lower(),
                "offset": offset,
                "limit": limit,
                "latest": str(latest).lower(),
                "fileDataFromDate": date_from,
                "fileDataToDate": date_to,
            },
            response_model=BulkResponse,
        )

    def iter_files(
        self,
        product: str,
        *,
        date_from: str | None = None,
        date_to: str | None = None,
        page_size: int = 100,
    ) -> Iterator[BulkFile]:
        if page_size < 1:
            raise ValueError("page_size must be positive")
        seen: set[str] = set()
        offset = 0
        while True:
            response = self.get_product(
                product,
                offset=offset,
                limit=page_size,
                date_from=date_from,
                date_to=date_to,
            )
            files = [file for item in response.products for file in item.file_bag.files]
            if not files:
                return
            new = [file for file in files if file.file_name not in seen]
            if not new:
                raise ValueError(
                    "Bulk pagination made no progress; coverage is incomplete"
                )
            for file in new:
                seen.add(file.file_name)
                yield file
            offset += page_size
            # ODP can append documentation files outside the requested data limit.
            data_count = sum(file.file_type != "Document" for file in files)
            if data_count < page_size:
                return

    def download_file(
        self, product: str, filename: str, *, output_path: str | Path, **options: Any
    ) -> StreamDownload:
        path = (
            f"/api/v1/datasets/products/files/{quote(product, safe='')}/"
            f"{quote(filename, safe='')}"
        )
        return stream_download(self._client, path, Path(output_path), **options)
