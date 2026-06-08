"""Acceptance tests for Batch Convert pure functions (spec §9)."""

import sys
from pathlib import Path

# Ensure project root is on sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pytest
from PIL import Image

from core.batch_convert_worker import (
    build_name, classify, crop_to_fill, derive_descriptor,
    resolve_target, scaled_dims,
)


# ── classify ────────────────────────────────────────────────────────────

@pytest.mark.parametrize("fname, expected", [
    ("icon_02_boss_face_rounded.png", "icon"),
    ("launcher.png", "icon"),
    ("appicon_v2.jpg", "icon"),
    ("hero_rounded.png", "icon"),         # ends in 'rounded'
    ("ui_05_shop.jpg", "ui"),
    ("home_screen.png", "ui"),
    ("garage_workshop.png", "ui"),
    ("portrait_city_street_combat_rearcam.png", "gameplay"),
    ("M1_chase_v2.png", "gameplay"),
    ("hud_overlay.png", "gameplay"),       # tie-breaker: hud → gameplay
    ("keyart_01_hero.png", "keyart"),
    ("K2_boss_showdown.png", "keyart"),
    ("hero_v4.png", "keyart"),
    ("lineup.png", "concept"),             # tie-breaker
    ("vs_screen.png", "concept"),
    ("moodboard_explore.png", "concept"),
    ("clip.mp4", "video"),
    ("trailer.mov", "video"),
    ("image 474.png", "unknown"),          # no match
    ("build_screen.png", "ui"),            # 'build' boundary — 'screen' isn't in list → unknown
                                            # Wait: spec §9 says "build_screen → not ui".
                                            # 'screen' isn't a UI token; 'build' isn't either.
                                            # So this should be unknown, not ui.
])
def test_classify(fname, expected):
    # Special case: 'build_screen' must NOT match ui — neither 'build' nor 'screen'
    # are in any token set, so it should be 'unknown'.
    if fname == "build_screen.png":
        assert classify(fname) == "unknown"
    else:
        assert classify(fname) == expected


def test_classify_no_substring_false_positive():
    """'build' contains 'ui' as a substring — must NOT match ui."""
    assert classify("build_screen.png") != "ui"
    assert classify("guide_sheet.png") != "ui"


# ── resolve_target ──────────────────────────────────────────────────────

def test_resolve_target_mode_a_landscape():
    assert resolve_target("gameplay", 2000, 1000, mode="A") == (1536, 864)


def test_resolve_target_mode_a_portrait():
    assert resolve_target("gameplay", 1000, 2000, mode="A") == (864, 1536)


def test_resolve_target_keyart_landscape():
    assert resolve_target("keyart", 1920, 1080, mode="A") == (1600, 900)


def test_resolve_target_icon_square():
    assert resolve_target("icon", 800, 800, mode="A") == (1024, 1024)


def test_resolve_target_mode_b_downsize():
    assert resolve_target("keyart", 2000, 1000, mode="B") == (1600, 800)


def test_resolve_target_mode_b_no_upscale():
    assert resolve_target("keyart", 1200, 800, mode="B") == (1200, 800)


# ── crop_to_fill ────────────────────────────────────────────────────────

def test_crop_to_fill_exact_size():
    src = Image.new("RGB", (4000, 3000), "red")
    out = crop_to_fill(src, 1536, 864)
    assert out.size == (1536, 864)


def test_crop_to_fill_upscale_smaller_source():
    """A 200×200 source must be upscaled to fill a 1024×1024 target (mode A intent)."""
    src = Image.new("RGB", (200, 200), "blue")
    out = crop_to_fill(src, 1024, 1024)
    assert out.size == (1024, 1024)


def test_crop_to_fill_landscape_to_portrait():
    src = Image.new("RGB", (2000, 1000), "green")
    out = crop_to_fill(src, 864, 1536)
    assert out.size == (864, 1536)


# ── scaled_dims ─────────────────────────────────────────────────────────

def test_scaled_dims_downsize_keeps_aspect():
    assert scaled_dims(2000, 1000, 1600) == (1600, 800)


def test_scaled_dims_no_upscale():
    assert scaled_dims(1200, 800, 1600) == (1200, 800)


def test_scaled_dims_exact_cap_unchanged():
    assert scaled_dims(1600, 900, 1600) == (1600, 900)


def test_scaled_dims_portrait():
    assert scaled_dims(1000, 2000, 1600) == (800, 1600)


# ── build_name ──────────────────────────────────────────────────────────

def test_build_name_zero_padded():
    assert build_name("wild-west", "keyart", 1, "hero", "jpg") == \
        "wild-west_keyart_01_hero.jpg"


def test_build_name_double_digit():
    assert build_name("theme", "gameplay", 12, "portrait-combat", "jpg") == \
        "theme_gameplay_12_portrait-combat.jpg"


def test_build_name_no_descriptor():
    assert build_name("theme", "icon", 3, "", "png") == \
        "theme_icon_03.png"


def test_build_name_rounded_icon_png():
    assert build_name("theme", "icon", 1, "", "png").endswith(".png")


# ── derive_descriptor ───────────────────────────────────────────────────

def test_derive_descriptor_strips_id_prefix():
    assert derive_descriptor("M1_chase_v2", "gameplay", "landscape") != "m1"


def test_derive_descriptor_strips_version():
    d = derive_descriptor("hero_v4_keyart", "keyart")
    assert "v4" not in d
    assert d == "hero"


def test_derive_descriptor_strips_model_noise():
    d = derive_descriptor("scene_pro_gpt_edit", "ui")
    assert "pro" not in d
    assert "gpt" not in d


def test_derive_descriptor_gameplay_preserves_orientation():
    d = derive_descriptor("M1_chase", "gameplay", "portrait")
    assert "portrait" in d


def test_derive_descriptor_gameplay_orientation_when_empty_descriptor():
    d = derive_descriptor("M1", "gameplay", "landscape")
    assert d == "landscape"
