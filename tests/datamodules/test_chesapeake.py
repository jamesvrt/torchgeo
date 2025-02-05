# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

import os
from typing import Any, Dict, cast

import pytest
import torch
from omegaconf import OmegaConf

from torchgeo.datamodules import ChesapeakeCVPRDataModule


class TestChesapeakeCVPRDataModule:
    @pytest.fixture(scope="class")
    def datamodule(self) -> ChesapeakeCVPRDataModule:
        conf = OmegaConf.load(
            os.path.join("conf", "task_defaults", "chesapeake_cvpr_5.yaml")
        )
        kwargs = OmegaConf.to_object(conf.experiment.datamodule)
        kwargs = cast(Dict[str, Any], kwargs)

        datamodule = ChesapeakeCVPRDataModule(**kwargs)
        datamodule.prepare_data()
        datamodule.setup()
        return datamodule

    def test_nodata_check(self, datamodule: ChesapeakeCVPRDataModule) -> None:
        nodata_check = datamodule.nodata_check(4)
        sample = {
            "image": torch.ones(1, 2, 2),  # type: ignore[attr-defined]
            "mask": torch.ones(2, 2),  # type: ignore[attr-defined]
        }
        out = nodata_check(sample)
        assert torch.equal(  # type: ignore[attr-defined]
            out["image"], torch.zeros(1, 4, 4)  # type: ignore[attr-defined]
        )
        assert torch.equal(  # type: ignore[attr-defined]
            out["mask"], torch.zeros(4, 4)  # type: ignore[attr-defined]
        )

    def test_invalid_param_config(self) -> None:
        with pytest.raises(ValueError, match="The pre-generated prior labels"):
            ChesapeakeCVPRDataModule(
                os.path.join("tests", "data", "chesapeake", "cvpr"),
                ["de-test"],
                ["de-test"],
                ["de-test"],
                patch_size=32,
                patches_per_tile=2,
                batch_size=2,
                num_workers=0,
                class_set=7,
                use_prior_labels=True,
            )
