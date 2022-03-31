# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

"""Neon Species Benchmark dataset. https://github.com/weecology/NeonSpeciesBenchmark."""

import glob
import os
import sys
from typing import Any, Callable, Dict, Optional, cast

import matplotlib.pyplot as plt
import rasterio
from rasterio.crs import CRS
from rasterio.vrt import WarpedVRT

from .geo import GeoDataset
from .utils import BoundingBox, check_integrity, download_url, extract_archive


class NEONTreeSpecies(GeoDataset):
    """Neon Tree Species Dataset.

    The Weecology Lab at the University of Florida has developed a
    species prediction benchmark using data from the
    National Ecological Observatory Network `<https://idtrees.org/>`_
    dataset is a dataset for tree species classification.

    Dataset features:

    * RGB, Hyperspectral (HSI), LiDAR-derived CHM model
    * Remote sensing and field data generated by the
      `National Ecological Observatory Network (NEON) <https://data.neonscience.org/>`_
    * 0.1 - 1m resolution imagery
    * Train set contains X images
    * Test set contains X images

    Dataset format:

    * optical - three-channel RGB 200x200 geotiff at 10cm resolution
    * canopy height model - one-channel 20x20 geotiff at 1m resolution
    * hyperspectral - 369-channel 20x20 geotiff at 1m resolution at 1m resolution
    * shapefiles (.shp) containing field collected data on tree stems from
      `NEON's Woody Vegetation Structure Dataset
      <https://data.neonscience.org/data-products/DP1.10098.001>`_

    Dataset classes:

    0. ACPE
    1. ACRU
    2. ACSA3
    3. AMLA
    4. BETUL
    5. CAGL8
    6. CATO6
    7. FAGR
    8. GOLA
    9. LITU
    10. LYLU3
    11. MAGNO
    12. NYBI
    13. NYSY
    14. OXYDE
    15. PEPA37
    16. PIEL
    17. PIPA2
    18. PINUS
    19. PITA
    20. PRSE2
    21. QUAL
    22. QUCO2
    23. QUGE2
    24. QUHE2
    25. QULA2
    26. QULA3
    27. QUMO4
    28. QUNI
    29. QURU
    30. QUERC
    31. ROPS
    32. TSCA

    If you use this dataset in your research, please cite the following paper:

    * https://zenodo.org/record/5914554#.YkLKiTyxVH4

    .. versionadded:: 0.3
    """

    classes = {
        "ACPE": "Acer pensylvanicum L.",
        "ACRU": "Acer rubrum L.",
        "ACSA3": "Acer saccharum Marshall",
        "AMLA": "Amelanchier laevis Wiegand",
        "BETUL": "Betula sp.",
        "CAGL8": "Carya glabra (Mill.) Sweet",
        "CATO6": "Carya tomentosa (Lam.) Nutt.",
        "FAGR": "Fagus grandifolia Ehrh.",
        "GOLA": "Gordonia lasianthus (L.) Ellis",
        "LITU": "Liriodendron tulipifera L.",
        "LYLU3": "Lyonia lucida (Lam.) K. Koch",
        "MAGNO": "Magnolia sp.",
        "NYBI": "Nyssa biflora Walter",
        "NYSY": "Nyssa sylvatica Marshall",
        "OXYDE": "Oxydendrum sp.",
        "PEPA37": "Persea palustris (Raf.) Sarg.",
        "PIEL": "Pinus elliottii Engelm.",
        "PIPA2": "Pinus palustris Mill.",
        "PINUS": "Pinus sp.",
        "PITA": "Pinus taeda L.",
        "PRSE2": "Prunus serotina Ehrh.",
        "QUAL": "Quercus alba L.",
        "QUCO2": "Quercus coccinea",
        "QUGE2": "Quercus geminata Small",
        "QUHE2": "Quercus hemisphaerica W. Bartram ex Willd.",
        "QULA2": "Quercus laevis Walter",
        "QULA3": "Quercus laurifolia Michx.",
        "QUMO4": "Quercus montana Willd.",
        "QUNI": "Quercus nigra L.",
        "QURU": "Quercus rubra L.",
        "QUERC": "Quercus sp.",
        "ROPS": "Robinia pseudoacacia L.",
        "TSCA": "Tsuga canadensis (L.) Carriere",
    }

    metadata = {
        "train": {
            # temp use dropbox url
            "url": "https://zenodo.org/record/5914554/files/training.zip?download=1",  # noqa: E501
            "md5": "8d71412f3dfe9f055e8183f5faed905f",
            "filename": "train.zip",
        },
        "test": {
            "url": "https://zenodo.org/record/5914554/files/evaluation.zip?download=1",  # noqa: E501
            "md5": "f0c444fc59cf0115ce8c981a576fab77",
            "filename": "evaluation.zip",
        },
        "annotations": {
            "url": "https://zenodo.org/record/5914554/files/annotations.zip?download=1",
            "md5": "f577f0948a259d474ee0199fb8d76524",
            "filename": "annotations.zip",
        },
    }

    directories = {
        "train": "training",
        "test": "evaluation",
        "annotations": "annotations",
    }
    splits = ["train", "test"]
    filename_glob = "*.tif"
    filename_regex = ".*"
    date_format = "Y"

    def __init__(
        self,
        root: str = "data",
        split: str = "train",
        crs: Optional[CRS] = None,
        res: Optional[float] = None,
        transforms: Optional[Callable[[Dict[str, Any]], Dict[str, Any]]] = None,
        cache: bool = True,
        download: bool = False,
        checksum: bool = False,
    ) -> None:
        """Initialize a new dataset instance.

        Args:
            root: root directory where dataset can be found
            split: one of "train" or "test"
            crs: :term:`coordinate reference system (CRS)` to warp to
                (defaults to the CRS of the first file found)
            res: resolution of the dataset in units of CRS
                (defaults to the resolution of the first file found)
            transforms: a function/transform that takes an input sample
                and returns a transformed version
            cache: if True, cache file handle to speed up repeated sampling
            download: if True, download dataset and store it in the root directory
            checksum: if True, check the MD5 of the downloaded files (may be slow)

        Raises:
            ImportError: if laspy or pandas are are not installed
        """
        self.root = root
        self.cache = cache
        self.download = download
        self.checksum = checksum

        assert split in self.splits
        self.split = split

        self._verify()

        super().__init__(transforms)

        # Populate the dataset index
        i = 0
        pathname = os.path.join(
            root, self.directories[split], "RGB", self.filename_glob
        )
        for filepath in glob.iglob(pathname, recursive=True):
            base_file = os.path.basename(filepath)
            xml_file = base_file.split(".")[0] + ".xml"
            match = os.path.exists(
                os.path.join("data", "neon", "annotations", xml_file)
            )
            if match:
                try:
                    with rasterio.open(filepath) as src:

                        if crs is None:
                            crs = src.crs
                        if res is None:
                            res = src.res[0]
                        try:
                            with WarpedVRT(src, crs=crs) as vrt:
                                minx, miny, maxx, maxy = vrt.bounds
                        except ValueError:
                            print(0)
                            continue
                except rasterio.errors.RasterioIOError:
                    # Skip files that rasterio is unable to read
                    continue
                else:
                    mint: float = 0
                    maxt: float = sys.maxsize

                    coords = (minx, maxx, miny, maxy, mint, maxt)
                    self.index.insert(i, coords, filepath)
                    i += 1

        if i == 0:
            raise FileNotFoundError(
                f"No {self.__class__.__name__} data was found in '{root}'"
            )

        self._crs = cast(CRS, crs)
        self.res = cast(float, res)

    def __getitem__(self, query: BoundingBox) -> Dict[str, Any]:
        """Retrieve image/mask and metadata indexed by query.

        Args:
            query: (minx, maxx, miny, maxy, mint, maxt) coordinates to index

        Returns:
            sample of image/mask and metadata at that index

        Raises:
            IndexError: if query is not found in the index
        """

    def _verify(self) -> None:
        """Verify the integrity of the dataset.

        Raises:
            RuntimeError: if ``download=False`` but dataset is missing or checksum fails
        """
        split_md5 = self.metadata[self.split]["md5"]
        split_filename = self.metadata[self.split]["filename"]
        split_directories = self.directories[self.split]

        annot_md5 = self.metadata["annotations"]["md5"]
        annot_filename = self.metadata["annotations"]["filename"]
        annot_directories = self.directories["annotations"]
        # Check if the files already exist
        exists = [
            os.path.exists(os.path.join(self.root, directory))
            for directory in [split_directories, annot_directories]
        ]

        if all(exists):
            return
        # Check if downloaded zip files exist
        exists = []
        for filename, md5 in zip(
            [split_filename, annot_filename], [split_md5, annot_md5]
        ):
            filepath = os.path.join(self.root, filename)
            if os.path.isfile(filepath):
                if self.checksum and not check_integrity(filepath, md5):
                    raise RuntimeError("Dataset found, but corrupted.")
                exists.append(True)
                extract_archive(filepath)
            else:
                exists.append(False)

        if all(exists):
            return

        # Check if the user requested to download the dataset
        if not self.download:
            raise RuntimeError(
                f"Dataset not found in `root={self.root}` and `download=False`, "
                "either specify a different `root` directory or use `download=True` "
                "to automaticaly download the dataset."
            )

        # Download the dataset
        self._download()
        self._extract()

    def _download(self) -> None:
        """Download the dataset."""
        # download split data
        download_url(
            self.metadata[self.split]["url"],
            self.root,
            self.metadata[self.split]["filename"],
        )
        # download annotation
        download_url(
            self.metadata["annotations"]["url"],
            self.root,
            self.metadata["annotations"]["filename"],
        )

    def _extract(self) -> None:
        """Extract the dataset."""
        # extract split data
        extract_archive(os.path.join(self.root, self.metadata[self.split]["filename"]))
        # extract annotations
        extract_archive(
            os.path.join(self.root, self.metadata["annotations"]["filename"])
        )

    def plot(
        self,
        sample: Dict[str, Any],
        show_titles: bool = True,
        suptitle: Optional[str] = None,
    ) -> plt.Figure:
        """Plot a sample from the dataset.

        Args:
            sample: a sample returned by :meth:`__getitem__`
            show_titles: flag indicating whether to show titles above each panel
            suptitle: optional string to use as a suptitle

        Returns:
            a matplotlib Figure with the rendered sample
        """
