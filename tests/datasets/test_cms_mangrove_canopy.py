# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
import shutil
from pathlib import Path
from typing import Generator

import pytest
import torch
import torch.nn as nn
from _pytest.monkeypatch import MonkeyPatch
from rasterio.crs import CRS

from torchgeo.datasets import CMSGlobalMangroveCanopy, IntersectionDataset, UnionDataset


def download_url(url: str, root: str, *args: str, **kwargs: str) -> None:
    shutil.copy(url, root)


class TestCMSGlobalMangroveCanopy:
    @pytest.fixture
    def dataset(
        self, monkeypatch: Generator[MonkeyPatch, None, None], tmp_path: Path
    ) -> CMSGlobalMangroveCanopy:
        zipfile = "CMS_Global_Map_Mangrove_Canopy_1665.zip"
        monkeypatch.setattr(  # type: ignore[attr-defined]
            CMSGlobalMangroveCanopy, "zipfile", zipfile
        )

        md5 = "45d894d4516d91212b70fd9a803e28cd"
        monkeypatch.setattr(  # type: ignore[attr-defined]
            CMSGlobalMangroveCanopy, "md5", md5
        )

        root = os.path.join("tests", "data", "cms_mangrove_canopy")
        transforms = nn.Identity()  # type: ignore[attr-defined]
        country = "Angola"

        return CMSGlobalMangroveCanopy(
            root, country=country, transforms=transforms, checksum=True
        )

    def test_getitem(self, dataset: CMSGlobalMangroveCanopy) -> None:
        x = dataset[dataset.bounds]
        assert isinstance(x, dict)
        assert isinstance(x["crs"], CRS)
        assert isinstance(x["mask"], torch.Tensor)

    def test_no_dataset(self) -> None:
        with pytest.raises(RuntimeError, match="Dataset not found in."):
            CMSGlobalMangroveCanopy(root="/test")

    def test_already_downloaded(self, tmp_path: Path) -> None:
        pathname = os.path.join(
            "tests",
            "data",
            "cms_mangrove_canopy",
            "CMS_Global_Map_Mangrove_Canopy_1665.zip",
        )
        root = str(tmp_path)
        shutil.copy(pathname, root)
        CMSGlobalMangroveCanopy(root, country="Angola")

    def test_invalid_country(self) -> None:
        with pytest.raises(AssertionError):
            CMSGlobalMangroveCanopy(country="fakeCountry")

    def test_invalid_measurement(self) -> None:
        with pytest.raises(AssertionError):
            CMSGlobalMangroveCanopy(measurement="wrongMeasurement")

    def test_and(self, dataset: CMSGlobalMangroveCanopy) -> None:
        ds = dataset & dataset
        assert isinstance(ds, IntersectionDataset)

    def test_or(self, dataset: CMSGlobalMangroveCanopy) -> None:
        ds = dataset | dataset
        assert isinstance(ds, UnionDataset)

    def test_plot(self, dataset: CMSGlobalMangroveCanopy) -> None:
        query = dataset.bounds
        x = dataset[query]
        dataset.plot(x["mask"])
