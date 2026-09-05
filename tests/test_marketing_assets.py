"""Regression checks for public brand and README assets."""

from pathlib import Path

from PIL import Image

from tools.release import write_windows_version_info

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_brand_pngs_are_transparent_and_correctly_sized():
    expected = {
        'logo.png': (1024, 1024),
        'web/static/logo.png': (512, 512),
        'web/static/logo-192.png': (192, 192),
        'web/static/logo-512.png': (512, 512),
    }
    for relative, dimensions in expected.items():
        with Image.open(REPO_ROOT / relative) as image:
            assert image.size == dimensions
            assert image.mode == 'RGBA'
            assert image.getpixel((0, 0))[3] == 0

    with Image.open(REPO_ROOT / 'web/static/logo-maskable-512.png') as maskable:
        assert maskable.size == (512, 512)
        assert maskable.mode == 'RGBA'
        assert maskable.getpixel((0, 0))[3] == 255


def test_windows_icon_contains_common_shell_sizes():
    with Image.open(REPO_ROOT / 'icon.ico') as image:
        assert image.format == 'ICO'
        assert {16, 24, 32, 48, 64, 128, 256}.issubset({size[0] for size in image.ico.sizes()})


def test_marketing_images_have_expected_dimensions():
    for filename in (
        'readiness-dashboard.png',
        'preparedness-workflows.png',
        'inventory-planning.png',
        'offline-maps.png',
        'offline-library.png',
    ):
        with Image.open(REPO_ROOT / 'docs' / 'media' / filename) as image:
            assert image.size == (1600, 1000)

    with Image.open(REPO_ROOT / '.github' / 'social-preview.png') as social:
        assert social.size == (1280, 640)


def test_windows_release_metadata_matches_public_version(tmp_path):
    version_file = write_windows_version_info(tmp_path, '7.66.41')
    metadata = version_file.read_text(encoding='utf-8')
    build_spec = (REPO_ROOT / 'build.spec').read_text(encoding='utf-8')

    assert 'filevers=(7, 66, 41, 0)' in metadata
    assert "StringStruct('FileDescription', 'NOMAD Field Desk')" in metadata
    assert "StringStruct('FileVersion', '7.66.41')" in metadata
    assert "StringStruct('ProductVersion', '7.66.41')" in metadata
    assert "version='build/version_info.txt' if _is_windows else None" in build_spec


def test_readme_uses_current_assets_and_clean_public_text():
    readme = (REPO_ROOT / 'README.md').read_text(encoding='utf-8')
    assert '# NOMAD Field Desk v7.66.41' in readme
    assert '.github/social-preview.png' in readme
    assert 'docs/media/readiness-dashboard.png' in readme
    assert 'representative data created in a disposable local profile' in readme
    assert 'â' not in readme
    assert 'ðŸ' not in readme
    assert '—' not in readme
    assert '–' not in readme
