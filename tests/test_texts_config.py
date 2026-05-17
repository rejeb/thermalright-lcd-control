# SPDX-License-Identifier: Apache-2.0
"""ConfigLoader parses a standalone ``texts:`` section and migrates a metric's
old ``label``/``label_*`` fields into an independent text (with its OWN font
size), so labels no longer share the metric value's size."""
from thermalright_lcd_control.device_controller.display.config_loader import ConfigLoader


def _base(metrics, texts=None):
    d = {"display": {
        "rotation": 0,
        "background": {"path": "/x/bg.png", "type": "image"},
        "foreground": {"enabled": False, "path": "", "position": {"x": 0, "y": 0}, "alpha": 1.0},
        "metrics": {"enabled": True, "configs": metrics},
        "date": {"enabled": False},
        "time": {"enabled": False},
    }}
    if texts is not None:
        d["display"]["texts"] = texts
    return d


def test_texts_section_parsed():
    cfg = ConfigLoader().load_config_from_dict(_base([], texts=[
        {"text": "Hi", "position": {"x": 10, "y": 20}, "font_size": 24,
         "color": "#FF0000FF"}]), 320, 240)
    assert len(cfg.texts) == 1
    assert cfg.texts[0].text == "Hi"
    assert cfg.texts[0].font_size == 24
    assert cfg.texts[0].position == (10, 20)


def test_metric_label_migrated_to_text_with_own_font():
    metric = {"name": "cpu_temperature", "position": {"x": 100, "y": 100},
              "font_size": 128, "color": "#FFFFFFFF", "unit": "C", "precision": 0,
              "label": "CPU", "label_position": {"x": 90, "y": 60},
              "label_font_size": 48, "label_color": "#00FF00FF"}
    cfg = ConfigLoader().load_config_from_dict(_base([metric]), 320, 240)

    # value keeps its 128 px
    assert cfg.metrics_configs[0].font_size == 128
    # the label became a standalone text with its OWN 48 px (not 128)
    labels = [t for t in cfg.texts if t.text == "CPU"]
    assert len(labels) == 1
    assert labels[0].font_size == 48
    assert labels[0].position == (90, 60)
    # the metric no longer carries the label
    assert cfg.metrics_configs[0].label == ""


def test_metric_without_label_adds_no_text():
    metric = {"name": "cpu_usage", "position": {"x": 10, "y": 10},
              "font_size": 20, "color": "#FFFFFFFF", "unit": "%", "precision": 0}
    cfg = ConfigLoader().load_config_from_dict(_base([metric]), 320, 240)
    assert cfg.texts == []
