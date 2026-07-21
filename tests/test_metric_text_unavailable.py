# SPDX-License-Identifier: Apache-2.0
"""Affichage preview d'une métrique : valeur d'exemple sans donnée live,
« -- » quand la sonde est indisponible (None dans le live)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from thermalright_lcd_control.gui.native.overlay import model


def _widget(key="swap_usage", prec=0, unit="%"):
    return {"type": "metric", "key": key, "prec": prec, "unit": unit}


def test_sample_value_before_first_live_refresh():
    # clé absente du live → valeur d'exemple du catalogue
    text = model.metric_text(_widget(), live_metrics={})
    assert text == "3%"


def test_unavailable_probe_shows_dashes():
    # sonde indisponible (None) → « -- », pas un nombre plausible
    text = model.metric_text(_widget(), live_metrics={"swap_usage": None})
    assert text == "--"


def test_live_value_formatted_with_unit():
    text = model.metric_text(_widget(prec=1), live_metrics={"swap_usage": 12.34})
    assert text == "12.3%"
