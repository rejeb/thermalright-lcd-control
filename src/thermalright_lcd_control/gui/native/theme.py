# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Thèmes light/dark de l'UI native : tokens repris de l'ancienne UI web.

``tokens(mode)`` expose la palette aux widgets custom-peints ;
``build_qss(mode)`` produit la feuille de style applicative (QSS) appliquée via
``QApplication.setStyleSheet``.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QPolygonF

_ASSETS = Path(__file__).parent / "assets"

# Palette héritée de l'ancienne UI web (:root et :root[data-theme="light"]).
_DARK = {
    "shell": "#161616",
    "headerbar": "#2b2b2b",
    "win": "#1c1c1c",
    "card": "#2a2a2a",
    "card2": "#323232",
    "line": "rgba(255,255,255,0.07)",
    "line_strong": "rgba(255,255,255,0.12)",
    "text": "#f2f2f2",
    "dim": "#a8a8a8",
    "faint": "#6f6f6f",
    "accent": "#e95420",
    "accent_soft": "rgba(233,84,32,0.16)",
    "off": "#3c3c3c",
    "text2": "#e6e6e6",
    "hover": "#3a3a3a",
    "hover_strong": "#4a4a4a",
    "toggle_off": "#454545",
    # fond du dialogue device : plus clair que la fenêtre en dark,
    # plus foncé en light (contraste avec la fenêtre principale)
    "dialog_bg": "#2e2e2e",
}

_LIGHT = {
    **_DARK,
    "shell": "#f4f4f4",
    "headerbar": "#ebebeb",
    "win": "#ffffff",
    "card": "#ffffff",
    "card2": "#f1f1f1",
    "line": "rgba(0,0,0,0.10)",
    "line_strong": "rgba(0,0,0,0.17)",
    "text": "#1b1b1b",
    "dim": "#5c5c5c",
    "faint": "#8c8c8c",
    "off": "#cdcdcd",
    "text2": "#2a2a2a",
    "hover": "#e6e6e6",
    "hover_strong": "#dadada",
    "toggle_off": "#c8c8c8",
    "dialog_bg": "#ebebeb",
}


def tokens(mode: str) -> dict[str, str]:
    return _LIGHT if mode == "light" else _DARK


def _chevron_png(color: str) -> str:
    """Génère (et met en cache) un chevron « ⌄ » pour ``QComboBox::down-arrow``.

    QSS exige un fichier pour la propriété ``image`` (contrairement au SVG
    inline utilisé par ``.device-sel`` côté web) : on le dessine une fois par
    couleur et on le réutilise.
    """
    _ASSETS.mkdir(parents=True, exist_ok=True)
    path = _ASSETS / f"chevron_{color.strip('#')}.png"
    if not path.exists():
        pm = QPixmap(14, 14)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        pen = QPen(QColor(color))
        pen.setWidthF(1.6)
        pen.setCapStyle(Qt.RoundCap)
        pen.setJoinStyle(Qt.RoundJoin)
        p.setPen(pen)
        p.drawPolyline(QPolygonF([QPointF(3, 5), QPointF(7, 9), QPointF(11, 5)]))
        p.end()
        pm.save(str(path), "PNG")
    return path.as_posix()


def build_qss(mode: str) -> str:
    t = tokens(mode)
    return f"""
QMainWindow, QDialog {{ background: {t['win']}; }}
/* dialogue device : fond contrasté + bordure (fenêtre frameless) */
QDialog#deviceDialog {{
    background: {t['dialog_bg']};
    border: 1px solid {t['line_strong']};
}}
QWidget {{ color: {t['text']}; font-family: "Ubuntu", sans-serif; font-size: 13px; }}
QLabel {{ background: transparent; }}

/* ── titlebar ─────────────────────────────────────────────────────────── */
#titlebar {{ background: {t['headerbar']}; border-bottom: 1px solid {t['line_strong']}; }}
#titlebar QLabel#appName {{ font-size: 14px; font-weight: 500; }}

/* ── séparateurs entre zones (cf. #left{{border-right}} web) ─────────────── */
QFrame#vDivider {{ background: {t['line_strong']}; border: none; }}

/* ── cadre LCD autour du preview (cf. .lcd/.lcd-screen web) ──────────────── */
QFrame#lcdFrame {{
    background: qlineargradient(x1:0, y1:0, x2:0.35, y2:1,
        stop:0 {"#3a3a3a" if mode == "light" else "#2e2e2e"}, stop:1 {"#2c2c2c" if mode == "light" else "#222222"});
    border-radius: 16px;
}}

/* pastilles carrées de la titlebar (add/edit/delete device, toggle thème) */
QToolButton#iconBtn {{
    min-width: 32px; max-width: 32px; min-height: 32px; max-height: 32px;
    border-radius: 9px; border: 1px solid {t['line']};
    background: {t['card2']}; color: {t['text2']}; font-size: 15px;
}}
QToolButton#iconBtn:hover {{ background: {t['accent']}; color: #fff; border-color: {t['accent']}; }}

/* croix de suppression des vignettes (cf. .thumb-del web) */
QToolButton#thumbDel {{
    border: none; border-radius: 6px;
    background: rgba(0, 0, 0, 0.55);
}}
QToolButton#thumbDel:hover {{ background: {t['accent']}; }}

/* boutons min/max/close, circulaires (cf. .wbtn web) — winBtnClose porte
   aussi le nom winBtn en Python, mais un seul objectName tient à la fois :
   on répète donc le sélecteur */
QToolButton#winBtn, QToolButton#winBtnClose {{
    min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px;
    border: none; border-radius: 12px; background: {t['hover']}; color: {t['dim']};
}}
QToolButton#winBtn:hover {{ background: {t['hover_strong']}; color: {t['text']}; }}
QToolButton#winBtnClose:hover {{ background: {t['accent']}; color: #fff; }}

/* onglets devices de la titlebar (remplace l'ancienne combobox deviceSel) */
QTabBar#deviceTabs::tab {{
    background: {t['card2']}; border: 1px solid {t['line']}; border-radius: 9px;
    padding: 5px 12px; margin-right: 6px; color: {t['text2']};
    font-family: "Ubuntu Mono", monospace; font-size: 12px; min-height: 20px;
}}
QTabBar#deviceTabs::tab:selected {{
    background: {t['accent']}; color: #fff; border-color: {t['accent']};
}}
QTabBar#deviceTabs::tab:hover:!selected {{ background: {t['hover']}; }}
QTabBar#deviceTabs::tab:disabled {{ color: {t['faint']}; }}
QToolButton#tabEditBtn, QToolButton#tabDelBtn {{
    min-width: 24px; max-width: 24px; min-height: 24px; max-height: 24px;
    border: none; border-radius: 7px; background: transparent;
    color: #fff; font-size: 15px;
}}
QToolButton#tabEditBtn:hover, QToolButton#tabDelBtn:hover {{
    background: rgba(0, 0, 0, 0.25);
}}
QComboBox QAbstractItemView {{
    background: {t['headerbar']}; color: {t['text2']};
    border: 1px solid {t['line_strong']}; selection-background-color: {t['accent']};
}}

/* ── boutons génériques (Save / Apply / modals) ───────────────────────── */
QPushButton {{
    background: {t['card2']}; color: {t['text2']};
    border: 1px solid {t['line']}; border-radius: 9px;
    padding: 7px 14px; font-size: 12.5px;
}}
QPushButton:hover {{ background: {t['hover']}; }}
QPushButton#primary {{ background: {t['accent']}; color: #fff; border-color: {t['accent']}; font-weight: 600; }}
QPushButton#primary:hover {{ background: #f06236; }}
QPushButton#danger {{ background: #c0392b; color: #fff; border-color: #c0392b; }}
QPushButton#danger:hover {{ background: #d64535; }}
QPushButton:disabled {{ color: {t['faint']}; background: {t['off']}; }}

/* ── panneaux / cartes ────────────────────────────────────────────────── */
QFrame#card {{ background: {t['card']}; border: 1px solid {t['line']}; border-radius: 12px; }}
QLabel#sectionTitle {{ font-size: 11px; font-weight: 700; letter-spacing: 0.5px;
    color: {t['dim']}; text-transform: uppercase; }}
QLabel#dimText {{ color: {t['dim']}; font-size: 12px; }}
QLabel#faintText {{ color: {t['faint']}; font-size: 11.5px; }}
QLabel#errText {{ color: #ff7a5c; font-size: 12.5px; }}
QLabel#accentText {{ color: {t['accent']}; font-size: 10.5px; font-weight: 700; letter-spacing: 0.5px; }}

/* ── bandeau « mise à jour disponible » ──────────────────────────────────── */
/* Fond sombre neutre : le lien Download (blanc/souligné) ressort nettement, et
   ça ne se confond ni avec l'accent orange de l'UI ni avec un lien bleu. */
QWidget#updateBanner {{ background: #2b3440; border-bottom: 2px solid #e95420; }}
QWidget#updateBanner QLabel {{ color: #fff; font-size: 15px; font-weight: 600; }}
QWidget#updateBanner QLabel#updateLink {{ color: #fff; font-weight: 700; text-decoration: underline; }}
QToolButton#updateClose {{ color: #fff; background: transparent; border: none; font-size: 17px; }}
QToolButton#updateClose:hover {{ color: rgba(255,255,255,0.7); }}

/* ── bandeau message / erreur (même emplacement que la mise à jour) ───────── */
/* Fond rouge plein (opaque) : ne se confond pas avec le fond de l'application. */
QWidget#messageBanner {{ background: #d32f2f; border-bottom: 2px solid #9a1f1f; }}
QWidget#messageBanner QLabel {{ color: #fff; font-size: 15px; font-weight: 700; }}
QToolButton#messageClose {{ color: #fff; background: transparent; border: none; font-size: 17px; }}
QToolButton#messageClose:hover {{ color: rgba(255,255,255,0.75); }}

/* ── boutons de mode (Native/Generic, Static/Advanced) ───────────────────── */
QPushButton#modeBtn:checked {{
    background: {t['accent']}; color: #fff; border-color: {t['accent']};
    font-weight: 600;
}}

/* ── titre de section pliable (dialogue device) ──────────────────────────── */
QToolButton#secToggle {{
    color: {t['accent']}; background: transparent; border: none; padding: 0;
    font-size: 10.5px; font-weight: 700; letter-spacing: 0.5px;
}}
QToolButton#secToggle:hover {{ color: #f06236; }}

/* ── pastille d'aide « ? » (cf. .dv-help web) ────────────────────────────── */
QLabel#helpDot {{
    color: {t['faint']}; background: transparent;
    border: 1px solid {t['line_strong']}; border-radius: 8px;
    font-size: 10px; font-weight: 700;
}}
QLabel#helpDot:hover {{ color: {t['accent']}; border-color: {t['accent']}; }}
/* même bulle que .dv-help::after web : card-2, bordure fine, radius 8 */
QToolTip {{
    background: {t['card2']}; color: {t['text']};
    border: 1px solid {t['line']}; border-radius: 8px;
    padding: 8px 10px; font-size: 12px;
}}

/* ── ligne méta preview (cf. .preview-meta web) ──────────────────────────── */
QLabel#liveDot {{ color: {t['accent']}; font-size: 9px; }}
QLabel#liveText {{ color: {t['text2']}; font-size: 12px; }}
QLabel#metaSep {{ color: {t['dim']}; font-size: 12px; }}
QLabel#resPill {{
    background: {t['card2']}; border: 1px solid {t['line']};
    color: {t['text2']}; border-radius: 7px;
    padding: 4px 12px 4px 9px; font-size: 12px;
    font-family: "Ubuntu Mono", monospace;
}}

/* ── radios rotation (sous "Live Preview") ───────────────────────────────── */
QRadioButton#rotateRadio {{
    color: {t['text2']}; font-size: 12px; font-weight: 600; spacing: 5px;
}}
QRadioButton#rotateRadio:hover {{ color: {t['text']}; }}
QRadioButton#rotateRadio::indicator {{
    width: 12px; height: 12px; border-radius: 7px;
    border: 1px solid {t['line_strong']}; background: {t['card2']};
}}
QRadioButton#rotateRadio::indicator:checked {{
    border: 3px solid {t['accent']}; background: #fff;
}}

/* ── onglets (panneau droit) ──────────────────────────────────────────── */
QTabWidget::pane {{ border: none; background: transparent; }}
QTabBar::tab {{
    background: transparent; color: {t['dim']}; padding: 9px 14px;
    border: none; border-bottom: 2px solid transparent; font-size: 12.5px;
}}
QTabBar::tab:selected {{ color: {t['text']}; border-bottom: 2px solid {t['accent']}; }}
QTabBar::tab:hover {{ color: {t['text2']}; }}

/* ── grilles de médias ────────────────────────────────────────────────── */
QListWidget {{ background: transparent; border: none; }}
QListWidget::item {{
    background: {t['card']}; border: 1px solid {t['line']};
    border-radius: 10px; color: {t['text2']}; padding: 4px;
}}
QListWidget::item:hover {{ background: {t['hover']}; }}
QListWidget::item:selected {{ border: 2px solid {t['accent']}; background: {t['accent_soft']}; }}

/* ── inputs ───────────────────────────────────────────────────────────── */
QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
    background: {t['card2']}; color: {t['text']};
    border: 1px solid {t['line']}; border-radius: 8px;
    padding: 6px 8px; font-size: 12.5px;
    selection-background-color: {t['accent']};
}}
QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{ border-color: {t['accent']}; }}
QLineEdit#invalid {{ border-color: #ff7a5c; }}
QLineEdit:disabled {{ color: {t['faint']}; }}

/* ── comboboxes : chevron seul, pas de bouton (cf. select web) ───────────── */
QComboBox::drop-down {{ border: none; background: transparent; width: 22px; }}
QComboBox::down-arrow {{ image: url({_chevron_png(t['dim'])}); width: 10px; height: 10px; }}

/* ── bold / italic (cf. .bi-seg .bi web) ─────────────────────────────────── */
QToolButton#biBtn {{
    min-width: 38px; max-width: 38px; min-height: 34px; max-height: 34px;
    border-radius: 8px; border: 1px solid {t['line']};
    background: {t['card2']}; color: {t['dim']}; font-size: 14px;
}}
QToolButton#biBtn:checked {{ background: {t['accent']}; color: #fff; border-color: {t['accent']}; }}
/* sélection partielle (multi-sélection : certains widgets seulement) */
QToolButton#biBtn[mixed="true"] {{
    background: {t['card2']}; color: {t['accent']};
    border: 1px dashed {t['accent']};
}}

/* ── seg toggle (cf. .seg-sm web, ex. Date | Time) ───────────────────────── */
QWidget#segToggle {{ background: {t['card2']}; border-radius: 8px; }}
QToolButton#segBtn {{
    background: transparent; border: none; border-radius: 6px;
    padding: 5px 11px; font-size: 12.5px; color: {t['dim']};
}}
QToolButton#segBtn:checked {{ background: {t['accent']}; color: #fff; }}

/* ── stepper -|valeur|+ (cf. .wconf-step web) ────────────────────────────── */
QWidget#stepper {{ background: {t['card2']}; border: 1px solid {t['line']}; border-radius: 8px; }}
QToolButton#stepBtn {{
    background: transparent; border: none;
    min-width: 34px; max-width: 34px; min-height: 32px; max-height: 32px;
    font-size: 16px; color: {t['dim']};
}}
QToolButton#stepBtn:hover {{ background: {t['hover']}; }}
QLineEdit#stepVal {{
    min-width: 34px; max-width: 34px; font-size: 13px; color: {t['text']};
    background: transparent; border: none; border-radius: 0; padding: 0;
    border-left: 1px solid {t['line']}; border-right: 1px solid {t['line']};
}}
QLineEdit#stepVal:focus {{ border-left: 1px solid {t['accent']}; border-right: 1px solid {t['accent']}; }}

/* ── sliders ──────────────────────────────────────────────────────────── */
QSlider::groove:horizontal {{ height: 5px; border-radius: 2px; background: {t['toggle_off']}; }}
QSlider::sub-page:horizontal {{ background: {t['accent']}; border-radius: 2px; }}
QSlider::handle:horizontal {{
    width: 14px; height: 14px; margin: -5px 0; border-radius: 7px;
    background: #ffffff; border: 1px solid {t['line_strong']};
}}

/* ── scrollbars discrètes ─────────────────────────────────────────────── */
QScrollArea {{ background: transparent; border: none; }}
QScrollBar:vertical {{ background: transparent; width: 10px; margin: 0; }}
QScrollBar::handle:vertical {{ background: {t['hover_strong']}; border-radius: 5px; min-height: 30px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ background: transparent; height: 10px; margin: 0; }}
QScrollBar::handle:horizontal {{ background: {t['hover_strong']}; border-radius: 5px; min-width: 30px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}

/* ── menus (tray) ─────────────────────────────────────────────────────── */
QMenu {{ background: {t['card']}; color: {t['text2']}; border: 1px solid {t['line_strong']}; border-radius: 8px; }}
QMenu::item {{ padding: 6px 18px; border-radius: 6px; }}
QMenu::item:selected {{ background: {t['accent']}; color: #fff; }}
"""
