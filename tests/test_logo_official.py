"""Garante que menu, dashboard e login usam a mesma logo JPEG oficial."""

import hashlib
from pathlib import Path

from PIL import Image

from src.ui_components import LOGO_PATH, LOGIN_LOGO_PATH

# MD5 do arquivo original fornecido (assets/images/logo_acnnorte.jpeg).
OFFICIAL_LOGO_MD5 = "c08f849aa93e09496c5f452f151ff365"
OFFICIAL_LOGO_SIZE = (1600, 405)


def test_logo_paths_point_to_the_same_official_jpeg():
    logo = Path(LOGO_PATH).resolve()
    login_logo = Path(LOGIN_LOGO_PATH).resolve()

    assert logo == login_logo
    assert logo.name == "logo_acnnorte.jpeg"
    assert logo.suffix.lower() == ".jpeg"
    assert logo.is_file()


def test_official_logo_is_original_1600x405_rgb_jpeg():
    with Image.open(LOGO_PATH) as image:
        assert image.format == "JPEG"
        assert image.size == OFFICIAL_LOGO_SIZE
        assert image.mode == "RGB"
        assert abs(image.width / image.height - 1600 / 405) < 0.001


def test_official_logo_bytes_were_not_modified():
    digest = hashlib.md5(Path(LOGO_PATH).read_bytes()).hexdigest().lower()
    assert digest == OFFICIAL_LOGO_MD5
