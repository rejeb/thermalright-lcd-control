# SPDX-License-Identifier: Apache-2.0
# Copyright © 2025 Rejeb Ben Rejeb

"""Dialogue add/edit device (port du modal de l'ancienne UI web).

Formulaire identique dans les deux modes ; en édition la section de sélection
d'un device connecté est masquée. Le mode driver Native masque les champs
« generic » mais leurs valeurs sont conservées et soumises. Le header est soit
statique (hex), soit structuré (prefix/format/cmd/values avec placeholders
dynamiques width/height/payload_size/cmd). Soumission via
``backend.add_device`` / ``backend.update_device``.
"""

from __future__ import annotations

import json
import re

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QStyle,
    QToolButton,
    QToolTip,
    QVBoxLayout,
    QWidget,
)

from thermalright_lcd_control.gui.native.controls import NoScrollComboBox
from thermalright_lcd_control.gui.native.icons import window_icon
from thermalright_lcd_control.gui.native.theme import tokens
from thermalright_lcd_control.gui.shared.chrome import EdgeResizeMixin

DV_PLACEHOLDERS = ("width", "height", "payload_size", "cmd")
_VALUES_ERR = ("Unknown value. Allowed dynamic values: "
               + ", ".join(DV_PLACEHOLDERS)
               + " — or a number (e.g. 2, 0x1F) or hex bytes (e.g. DADB).")

_TRANSPORTS = ("hid", "usb_bulk", "scsi", "usb_bulk_ly")
_ENCODINGS = ("rgb565_le_columns", "rgb565_be", "jpeg")

# Bulles d'aide des champs (mêmes textes que les .dv-help de la version web).
_HELP_TIPS = {
    "other": "Pick from every connected USB device (lsusb view) to auto-fill "
             "VID/PID and a suggested id below.",
    "driver": "Generic = a driver fully configured by this form (transport, "
              "encoding, header…). Native = a hard-coded driver class; the "
              "generic fields are hidden but kept and still saved.",
    "id": "Unique identifier for this device. Used as the key of its saved "
          "configuration file (config_<id>.yaml). Spaces are converted to underscores.",
    "vid": "USB Vendor ID in hex (e.g. 0x0416). Identifies the manufacturer of the display.",
    "pid": "USB Product ID in hex (e.g. 0x5302). Identifies the specific display model.",
    "resolution": "Screen resolution (width × height) of the display. Only "
                  "resolutions with a matching background folder are listed.",
    "transport": "How frames are sent to the display: hid (HID reports), usb_bulk "
                 "(raw bulk transfer), scsi (SCSI commands), usb_bulk_ly "
                 "(LY handshake + chunked transfer).",
    "encoding": "Pixel format sent to the display: rgb565_le_columns / rgb565_be "
                "(16-bit raw, column- or big-endian) or jpeg (compressed). "
                "Must match what the panel expects.",
    "chunk_size": "Size in bytes of each write block sent over USB. Larger chunks "
                  "reduce transfer overhead; leave empty to use the transport default.",
    "report_id": "HID report id (hex) prepended to each report. Use 00 for "
                 "unnumbered reports. Only relevant for the hid transport.",
    "static_header": "A fixed byte sequence (hex) sent unchanged before every frame. "
                     "Use this when the device expects a constant header.",
    "prefix": "Optional fixed bytes (hex) placed at the very start of the "
              "structured header, before the packed values.",
    "format": "Python struct format string describing how the values below are "
              "packed (e.g. <6HIH). Required for a structured header.",
    "cmd": "Command value injected into the header. Referenced from the values "
           "list with the cmd placeholder.",
    "values": "Values packed according to format. Each entry is either a dynamic "
              "placeholder (width, height, payload_size, cmd) resolved at runtime, "
              "a number (e.g. 2, 0x1F), or hex bytes (e.g. DADB).",
    "command": "Custom SCSI opcode (hex) for the scsi transport. If set, it replaces "
               "the transport's default opcode. A wrong value will make the display "
               "stop responding. Leave empty to use the default.",
    "jpeg_quality": "Compression quality 1–100 for the jpeg encoding. Higher = sharper "
                    "image but heavier frames (more USB bandwidth and CPU). Has no "
                    "effect on rgb565 encodings. Leave empty for the default.",
    "ep_in": "USB IN endpoint address (hex) used to read ACK/handshake replies. "
             "If set, response reading is enabled; a wrong address causes read "
             "timeouts. Leave empty for write-only devices.",
    "start_wait": "Delay in seconds after opening the device before the first frame "
                  "is sent. Increase if the panel initialises slowly; too large "
                  "delays the start of rendering. Leave empty for no wait.",
}


class _HelpDot(QLabel):
    """Pastille « ? » : bulle affichée immédiatement au survol (sans le délai
    standard de QToolTip), comme le ::after CSS de la version web."""

    def __init__(self, tip: str, parent=None):
        super().__init__("?", parent)
        self.setObjectName("helpDot")
        self.setAlignment(Qt.AlignCenter)
        self.setFixedSize(16, 16)
        self.setCursor(Qt.WhatsThisCursor)
        # rich text → la bulle passe en multi-lignes (max ~260px comme le web)
        self._tip = f"<qt><div style='max-width:260px'>{tip}</div></qt>"

    def enterEvent(self, e):
        QToolTip.showText(self.mapToGlobal(self.rect().bottomLeft()), self._tip, self)
        super().enterEvent(e)

    def leaveEvent(self, e):
        QToolTip.hideText()
        super().leaveEvent(e)


def _value_valid(s: str) -> bool:
    s = str(s).strip()
    if s == "" or s in DV_PLACEHOLDERS:
        return True
    if re.fullmatch(r"-?\d+", s) or re.fullmatch(r"0x[0-9a-fA-F]+", s):
        return True
    return bool(re.fullmatch(r"(?:[0-9a-fA-F]{2})+", s))


def _parse_value(s: str):
    s = str(s).strip()
    if s in DV_PLACEHOLDERS:
        return s                        # placeholder résolu à l'exécution
    if re.fullmatch(r"-?\d+", s):
        return int(s)
    if re.fullmatch(r"0x[0-9a-fA-F]+", s):
        return int(s, 16)
    return s                            # littéral hex


class DeviceDialog(EdgeResizeMixin, QDialog):
    """Retourne ``QDialog.Accepted`` quand le device a été ajouté/modifié."""

    def __init__(self, backend, parent=None, edit_config: dict | None = None):
        # Volontairement SANS parent QWidget : avec un transient parent + modal,
        # GNOME « attache » le dialogue à la fenêtre principale (drag commun,
        # impossible de le déplacer seul). Modalité application à la place.
        super().__init__(None)
        self._owner = parent
        self.setWindowModality(Qt.ApplicationModal)
        # Sans transient parent, le compositeur ignore la modalité : un clic
        # sur la fenêtre principale la remonte devant le dialogue. On la
        # surveille pour repasser le dialogue au premier plan dans ce cas.
        if parent is not None:
            parent.window().installEventFilter(self)
        self.backend = backend
        self._editing = edit_config is not None
        self._original_id = (edit_config or {}).get("id")

        title = "Edit device" if self._editing else "Add a device"
        self.setWindowTitle(title)
        self.setObjectName("deviceDialog")
        self.setAttribute(Qt.WA_StyledBackground, True)
        self.resize(620, 700)
        self.setMouseTracking(True)     # curseurs de resize sur les bords
        # Fenêtre native (fournie par le WM) toujours sombre, indifférente au
        # thème clair/sombre de l'appli → un header custom, cohérent avec le
        # reste de l'UI, comme la fenêtre principale (cf. gui/shared/chrome.py).
        self.setWindowFlags(Qt.Dialog | Qt.FramelessWindowHint)

        root = QVBoxLayout(self)
        root.setContentsMargins(1, 1, 1, 1)     # laisse la bordure QSS visible
        root.setSpacing(0)

        header = QWidget()
        header.setObjectName("titlebar")
        header.setAttribute(Qt.WA_StyledBackground, True)
        header.setFixedHeight(48)
        head_lay = QHBoxLayout(header)
        head_lay.setContentsMargins(16, 0, 12, 0)
        head_title = QLabel(title)
        head_title.setObjectName("appName")
        head_lay.addWidget(head_title)
        head_lay.addStretch(1)
        close_btn = QToolButton()
        close_btn.setObjectName("winBtnClose")
        close_btn.setIconSize(QSize(10, 10))
        icon_color = QColor(tokens(self.backend.get_ui_theme())["dim"])
        close_btn.setIcon(window_icon("close", icon_color))
        close_btn.setToolTip("Close")
        close_btn.clicked.connect(self.reject)
        head_lay.addWidget(close_btn)
        self._header = header
        self._drag_pos = None
        header.mousePressEvent = self._drag_header
        header.mouseMoveEvent = self._drag_header_move
        header.mouseReleaseEvent = self._drag_header_release
        root.addWidget(header)

        body_wrap = QWidget()
        root.addWidget(body_wrap, 1)
        body_root = QVBoxLayout(body_wrap)
        body_root.setContentsMargins(16, 12, 16, 12)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        body = QWidget()
        self._lay = QVBoxLayout(body)
        self._lay.setSpacing(10)
        scroll.setWidget(body)
        scroll.viewport().setAutoFillBackground(False)
        body.setAutoFillBackground(False)
        body_root.addWidget(scroll, 1)
        self._body_widget = body

        # ── sélection d'un device connecté (mode ajout uniquement) ────────
        if not self._editing:
            self._other_sel = NoScrollComboBox()
            self._lay.addWidget(self._field("Connected USB devices", self._other_sel, _HELP_TIPS["other"]))
            self._load_pick_lists()
            self._other_sel.currentIndexChanged.connect(self._on_other_pick)

        self._outer_lay = self._lay      # layout racine du corps scrollable
        self._sections: list[tuple[QToolButton, QWidget]] = []

        # ── configuration (section pliable) ────────────────────────────────
        cfg_box, self._lay = self._section("Configuration")

        driver_row = QHBoxLayout()
        driver_row.addWidget(QLabel("Driver mode"))
        driver_row.addWidget(self._help(_HELP_TIPS["driver"]))
        driver_row.addStretch(1)
        self._native_btn = QPushButton("Native")
        self._native_btn.setCheckable(True)
        self._native_btn.setObjectName("modeBtn")
        self._generic_btn = QPushButton("Generic")
        self._generic_btn.setCheckable(True)
        self._generic_btn.setObjectName("modeBtn")
        self._native_btn.clicked.connect(lambda: self._set_driver("native"))
        self._generic_btn.clicked.connect(lambda: self._set_driver("generic"))
        driver_row.addWidget(self._native_btn)
        driver_row.addWidget(self._generic_btn)
        self._driver_row = QWidget()
        self._driver_row.setLayout(driver_row)
        self._lay.addWidget(self._driver_row)

        self._inputs: dict[str, QLineEdit | QComboBox] = {}
        self._genonly: list[QWidget] = []

        self._add_row([("id", "Id *", "e.g. ly_5408")])
        self._add_row([("vid", "VID *", "0x0416"), ("pid", "PID *", "0x5302")])
        # résolution : liste fermée des dossiers backgrounds existants — plus de
        # saisie libre width/height (une résolution listée est valide par
        # construction, cf. get_supported_resolutions)
        self._res_combo = NoScrollComboBox()
        try:
            for w, h in json.loads(self.backend.get_supported_resolutions()):
                self._res_combo.addItem(f"{w} × {h}", (int(w), int(h)))
        except Exception:
            pass
        res_box = self._field("Resolution *", self._res_combo,
                              _HELP_TIPS["resolution"])
        self._lay.addWidget(res_box)
        self._genonly.append(res_box)
        # erreur de résolution : juste sous le champ resolution
        self._res_err = QLabel("")
        self._res_err.setObjectName("errText")
        self._res_err.setWordWrap(True)
        self._res_err.hide()        # visible seulement quand il y a une erreur
        self._lay.addWidget(self._res_err)
        row = QWidget()
        grid = QGridLayout(row)
        grid.setContentsMargins(0, 0, 0, 0)
        transport = NoScrollComboBox()
        transport.addItems(_TRANSPORTS)
        encoding = NoScrollComboBox()
        encoding.addItems(_ENCODINGS)
        self._inputs["transport"] = transport
        self._inputs["encoding"] = encoding
        grid.addWidget(self._field("Transport *", transport, _HELP_TIPS["transport"]), 0, 0)
        grid.addWidget(self._field("Encoding *", encoding, _HELP_TIPS["encoding"]), 0, 1)
        self._lay.addWidget(row)
        self._genonly.append(row)
        self._add_row([("chunk_size", "Chunk size", "4096"),
                       ("report_id", "Report id (hid, hex)", "00")], genonly=True)

        # id : espaces → underscores à la saisie
        self._inputs["id"].textEdited.connect(self._clean_id)
        # mode driver : visible seulement si un driver natif existe pour
        # (vid, pid, résolution) — réévalué à chaque changement de ces champs
        self._inputs["vid"].textEdited.connect(self._update_driver_visibility)
        self._inputs["pid"].textEdited.connect(self._update_driver_visibility)
        self._res_combo.currentIndexChanged.connect(self._update_driver_visibility)

        # ── header (section pliable) ───────────────────────────────────────
        hdr_box, self._lay = self._section("Header")
        self._genonly.append(hdr_box)
        mode_row = QHBoxLayout()
        self._static_btn = QPushButton("Static")
        self._static_btn.setCheckable(True)
        self._static_btn.setObjectName("modeBtn")
        self._adv_btn = QPushButton("Advanced")
        self._adv_btn.setCheckable(True)
        self._adv_btn.setObjectName("modeBtn")
        self._static_btn.clicked.connect(lambda: self._set_header_mode("static"))
        self._adv_btn.clicked.connect(lambda: self._set_header_mode("advanced"))
        mode_row.addWidget(self._static_btn)
        mode_row.addWidget(self._adv_btn)
        mode_row.addStretch(1)
        mode_wrap = QWidget()
        mode_wrap.setLayout(mode_row)
        self._lay.addWidget(mode_wrap)
        self._genonly.append(mode_wrap)

        self._header_static = QLineEdit()
        self._header_static.setPlaceholderText("e.g. DADBDCDD00000000")
        self._static_box = self._field("Static header (hex)", self._header_static, _HELP_TIPS["static_header"])
        self._lay.addWidget(self._static_box)
        self._genonly.append(self._static_box)

        self._adv_box = QWidget()
        adv = QVBoxLayout(self._adv_box)
        adv.setContentsMargins(0, 0, 0, 0)
        self._header_prefix = QLineEdit()
        self._header_prefix.setPlaceholderText("DADBDCDD")
        self._header_format = QLineEdit()
        self._header_format.setPlaceholderText("<6HIH")
        pf = QWidget()
        pf_grid = QGridLayout(pf)
        pf_grid.setContentsMargins(0, 0, 0, 0)
        pf_grid.addWidget(self._field("prefix (hex)", self._header_prefix, _HELP_TIPS["prefix"]), 0, 0)
        pf_grid.addWidget(self._field("format (struct)", self._header_format, _HELP_TIPS["format"]), 0, 1)
        adv.addWidget(pf)
        self._cmd_input = QLineEdit()
        self._cmd_input.setPlaceholderText("0")
        adv.addWidget(self._field("cmd", self._cmd_input, _HELP_TIPS["cmd"]))
        values_cap = QHBoxLayout()
        values_cap.addWidget(QLabel("values"))
        values_cap.addWidget(self._help(_HELP_TIPS["values"]))
        values_cap.addStretch(1)
        adv.addLayout(values_cap)
        self._values_box = QVBoxLayout()
        values_host = QWidget()
        values_host.setLayout(self._values_box)
        adv.addWidget(values_host)
        add_value = QPushButton("+ Add value")
        add_value.clicked.connect(lambda: self._add_value_row(""))
        adv.addWidget(add_value)
        self._lay.addWidget(self._adv_box)
        self._genonly.append(self._adv_box)

        # ── avancé (optionnel, section pliable) ────────────────────────────
        advopt_box, self._lay = self._section("Advanced (optional)")
        self._genonly.append(advopt_box)
        self._add_row([("command", "command (scsi, hex)", "0xF5"),
                       ("jpeg_quality", "JPEG quality", "85")], genonly=True)
        self._add_row([("ep_in", "ep_in (usb, hex)", "0x81"),
                       ("start_wait", "start_wait (s)", "0")], genonly=True)

        self._lay = self._outer_lay      # fin des sections
        self._err = QLabel("")
        self._err.setObjectName("errText")
        self._err.setWordWrap(True)
        self._lay.addWidget(self._err)
        self._lay.addStretch(1)

        self._foot_box = QWidget()
        foot = QHBoxLayout(self._foot_box)
        foot.setContentsMargins(0, 0, 0, 0)
        foot.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        submit = QPushButton("Save changes" if self._editing else "Add device")
        submit.setObjectName("primary")
        submit.clicked.connect(self._submit)
        foot.addWidget(cancel)
        foot.addWidget(submit)
        body_root.addWidget(self._foot_box)

        # état initial
        self._driver = "generic"
        self._header_mode = "static"
        self._set_header_mode("static")
        self._reset_values(None)
        if edit_config:
            self._fill_from_config(edit_config)
        else:
            self._set_driver("generic")
        self._update_driver_visibility()
        self._fit_to_content()
        if self._owner is not None:     # centre sur la fenêtre principale
            g = self._owner.frameGeometry()
            self.move(g.center() - self.rect().center())

    # ── construction ──────────────────────────────────────────────────────
    @staticmethod
    def _help(tip: str) -> QLabel:
        """Pastille « ? » avec bulle d'aide au survol (cf. .dv-help web)."""
        return _HelpDot(tip)

    @staticmethod
    def _sechead(text: str) -> QLabel:
        cap = QLabel(text.upper())
        cap.setObjectName("accentText")
        return cap

    def _section(self, title: str) -> tuple[QWidget, QVBoxLayout]:
        """Section pliable : titre cliquable ▾/▸ + corps masquable.
        Retourne (conteneur, layout du corps) ; le conteneur est ajouté au
        layout courant ``self._lay``."""
        box = QWidget()
        col = QVBoxLayout(box)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(10)
        btn = QToolButton()
        btn.setObjectName("secToggle")
        btn.setCheckable(True)
        btn.setChecked(True)
        btn.setText("▾  " + title.upper())
        body = QWidget()
        body_lay = QVBoxLayout(body)
        body_lay.setContentsMargins(0, 0, 0, 0)
        body_lay.setSpacing(10)

        def toggle(on: bool) -> None:
            btn.setText(("▾  " if on else "▸  ") + title.upper())
            body.setVisible(on)
            box.updateGeometry()    # purge le cache QWidgetItemV2 du parent
            QTimer.singleShot(0, self._fit_to_content)   # après relayout

        btn.toggled.connect(toggle)
        col.addWidget(btn)
        col.addWidget(body)
        self._outer_lay.addWidget(box)      # toujours au niveau racine
        self._sections.append((btn, body))
        return box, body_lay

    def _fit_to_content(self) -> None:
        """Hauteur = contenu visible, plafonnée à la fenêtre principale
        (ou à l'écran) ; au-delà le scroll prend le relais."""
        parent = self._owner
        if parent is not None:
            cap_w, cap_h = parent.width(), parent.height()
        else:
            g = self.screen().availableGeometry()
            cap_w, cap_h = int(g.width() * 0.9), int(g.height() * 0.9)
        # les hints de layout sont cachés (QWidgetItemV2) : purger toute la
        # chaîne de conteneurs avant de mesurer, sinon les tailles n'évoluent
        # pas après un show/hide ou un ajout de ligne
        for w in (self._static_box, self._adv_box):
            w.updateGeometry()
        for _btn, body in self._sections:
            box = body.parentWidget()
            body.updateGeometry()
            box.updateGeometry()
            box_lay = box.layout()
            if box_lay is not None:
                box_lay.invalidate()
            body_lay = body.layout()
            if body_lay is not None:
                body_lay.invalidate()
        lay = self._body_widget.layout()
        if lay is not None:
            lay.invalidate()
            lay.activate()
        hint = self._body_widget.sizeHint()
        wanted_h = (48                                # barre de titre
                    + 24                              # marges de body_root
                    + self._foot_box.sizeHint().height()
                    + hint.height()
                    + 16)                             # respiration scroll/foot
        # largeur du contenu + marges (32) + barre de scroll verticale
        # éventuelle, pour ne jamais déclencher de scroll horizontal
        sb = self.style().pixelMetric(QStyle.PM_ScrollBarExtent)
        wanted_w = max(self.width(), hint.width() + 32 + sb + 8)
        self.resize(min(wanted_w, cap_w), min(wanted_h, cap_h))

    @classmethod
    def _field(cls, label: str, control: QWidget, tip: str | None = None) -> QWidget:
        box = QWidget()
        lay = QVBoxLayout(box)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(3)
        cap = QLabel(label)
        cap.setObjectName("faintText")
        if tip:
            head = QHBoxLayout()
            head.setContentsMargins(0, 0, 0, 0)
            head.addWidget(cap)
            head.addStretch(1)
            head.addWidget(cls._help(tip))
            lay.addLayout(head)
        else:
            lay.addWidget(cap)
        lay.addWidget(control)
        return box

    def _add_row(self, fields: list[tuple[str, str, str]], genonly: bool = False) -> None:
        row = QWidget()
        grid = QGridLayout(row)
        grid.setContentsMargins(0, 0, 0, 0)
        for col, (name, label, placeholder) in enumerate(fields):
            edit = QLineEdit()
            edit.setPlaceholderText(placeholder)
            self._inputs[name] = edit
            grid.addWidget(self._field(label, edit, _HELP_TIPS.get(name)), 0, col)
        self._lay.addWidget(row)
        if genonly:
            self._genonly.append(row)

    # ── pick lists (mode ajout) ───────────────────────────────────────────
    def _load_pick_lists(self) -> None:
        try:
            self._usb = json.loads(self.backend.get_usb_devices())
        except Exception:
            self._usb = []
        self._other_sel.addItem("— pick from connected USB —", None)
        for i, u in enumerate(self._usb):
            self._other_sel.addItem(u.get("label", "?"), i)

    def _on_other_pick(self, _index: int) -> None:
        i = self._other_sel.currentData()
        if i is None:
            return
        u = self._usb[i]
        self._set("vid", f"0x{int(u.get('vid', 0)):04X}")
        self._set("pid", f"0x{int(u.get('pid', 0)):04X}")
        self._suggest_id(u.get("bus"), u.get("device"))
        self._update_driver_visibility()

    def _suggest_id(self, bus, device) -> None:
        vid = self._text("vid")
        pid = self._text("pid")
        if not vid or not pid:
            return
        try:
            suggested = self.backend.suggest_device_id(
                vid, pid, "" if bus is None else str(bus),
                "" if device is None else str(device))
            if suggested:
                self._set("id", re.sub(r"\s+", "_", suggested))
        except Exception:
            pass

    # ── driver / header modes ─────────────────────────────────────────────
    def _set_driver(self, mode: str) -> None:
        self._driver = "native" if mode == "native" else "generic"
        native = self._driver == "native"
        self._native_btn.setChecked(native)
        self._generic_btn.setChecked(not native)
        # Native masque les champs generic ; leurs valeurs restent soumises.
        for w in self._genonly:
            w.setVisible(not native)
        if not native:
            self._set_header_mode(self._header_mode)
        if hasattr(self, "_foot_box"):
            self._fit_to_content()

    def _update_driver_visibility(self) -> None:
        """Masque le choix de mode driver quand aucune classe native n'existe
        pour (vid, pid, résolution) : Generic est alors le seul mode possible
        et est forcé."""
        res = self._resolution() or (0, 0)
        try:
            check = json.loads(self.backend.check_native_driver(
                self._text("vid"), self._text("pid"), str(res[0]), str(res[1])))
            available = bool(check.get("available"))
        except Exception:
            available = True                # en cas de doute, laisser le choix
        self._driver_row.setVisible(available)
        if not available and self._driver == "native":
            self._set_driver("generic")
        self._request_fit()

    def _set_header_mode(self, mode: str) -> None:
        self._header_mode = mode
        self._static_btn.setChecked(mode == "static")
        self._adv_btn.setChecked(mode == "advanced")
        if self._driver == "generic":
            self._static_box.setVisible(mode == "static")
            self._adv_box.setVisible(mode == "advanced")
            self._static_box.updateGeometry()   # purge caches QWidgetItemV2
            self._adv_box.updateGeometry()
        self._request_fit()

    def _request_fit(self) -> None:
        """Refit différé (après relayout), une fois le dialogue construit."""
        if hasattr(self, "_foot_box"):
            QTimer.singleShot(0, self._fit_to_content)

    # ── header values ─────────────────────────────────────────────────────
    def _add_value_row(self, value: str) -> QLineEdit:
        row = QWidget()
        col = QVBoxLayout(row)
        col.setContentsMargins(0, 0, 0, 0)
        col.setSpacing(2)
        line = QWidget()
        lay = QHBoxLayout(line)
        lay.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit(value)
        edit.setPlaceholderText("e.g. 2, width, payload_size")
        edit.textEdited.connect(self._validate_values)
        remove = QToolButton()
        remove.setObjectName("iconBtn")
        remove.setText("−")
        remove.setToolTip("Remove value")
        remove.clicked.connect(lambda: (row.setParent(None), row.deleteLater(),
                                        self._validate_values(),
                                        self._request_fit()))
        lay.addWidget(edit, 1)
        lay.addWidget(remove)
        col.addWidget(line)
        # erreur sous le champ en cours d'édition (pas en fin de section)
        err = QLabel(_VALUES_ERR)
        err.setObjectName("errText")
        err.setWordWrap(True)
        err.hide()
        col.addWidget(err)
        self._values_box.addWidget(row)
        self._request_fit()
        return edit

    def _value_inputs(self) -> list[QLineEdit]:
        out = []
        for i in range(self._values_box.count()):
            row = self._values_box.itemAt(i).widget()
            if row is not None:
                edit = row.findChild(QLineEdit)
                if edit is not None:
                    out.append(edit)
        return out

    def _reset_values(self, values) -> None:
        for i in reversed(range(self._values_box.count())):
            w = self._values_box.itemAt(i).widget()
            if w is not None:
                w.setParent(None)
                w.deleteLater()
        if values:
            for v in values:
                self._add_value_row(str(v))
        else:
            self._add_value_row("")
        self._validate_values()

    def _validate_values(self) -> bool:
        ok = True
        for i in range(self._values_box.count()):
            row = self._values_box.itemAt(i).widget()
            if row is None:
                continue
            edit = row.findChild(QLineEdit)
            err = row.findChild(QLabel)
            if edit is None:
                continue
            bad = not _value_valid(edit.text())
            edit.setObjectName("invalid" if bad else "")
            edit.style().unpolish(edit)
            edit.style().polish(edit)
            if err is not None:
                err.setVisible(bad)
            if bad:
                ok = False
        return ok

    def _build_header(self) -> str:
        if self._header_mode == "static":
            v = self._header_static.text().strip()
            return json.dumps({"static": v}) if v else ""
        fmt = self._header_format.text().strip()
        if not fmt:
            return ""                       # format requis pour un header structuré
        values = [_parse_value(e.text()) for e in self._value_inputs()
                  if e.text().strip() != ""]
        spec: dict = {"format": fmt, "values": values}
        prefix = self._header_prefix.text().strip()
        if prefix:
            spec["prefix"] = prefix
        return json.dumps(spec)

    # ── remplissage / lecture ─────────────────────────────────────────────
    def _set(self, name: str, value) -> None:
        ctl = self._inputs.get(name)
        if ctl is None:
            return
        text = "" if value is None else str(value)
        if isinstance(ctl, QComboBox):
            idx = ctl.findText(text)
            ctl.setCurrentIndex(idx if idx >= 0 else 0)
        else:
            ctl.setText(text)

    def _text(self, name: str) -> str:
        ctl = self._inputs.get(name)
        if ctl is None:
            return ""
        return ctl.currentText() if isinstance(ctl, QComboBox) else ctl.text()

    def _set_resolution(self, width, height) -> None:
        """Sélectionne ``width × height`` dans la liste ; une résolution absente
        (config existante avec un dossier disparu) est ajoutée pour rester
        affichable — _check_resolution signalera le dossier manquant."""
        try:
            res = (int(width), int(height))
        except (TypeError, ValueError):
            return
        idx = self._res_combo.findData(res)
        if idx < 0:
            self._res_combo.addItem(f"{res[0]} × {res[1]}", res)
            idx = self._res_combo.count() - 1
        self._res_combo.setCurrentIndex(idx)

    def _resolution(self) -> tuple[int, int] | None:
        data = self._res_combo.currentData()
        return tuple(data) if data else None

    def _fill_from_config(self, cfg: dict) -> None:
        for name in self._inputs:
            if cfg.get(name) is not None:
                self._set(name, cfg[name])
        if cfg.get("width") is not None and cfg.get("height") is not None:
            self._set_resolution(cfg["width"], cfg["height"])
        # generic vaut true par défaut ; seul un false explicite → driver natif
        self._set_driver("native" if cfg.get("generic") is False else "generic")
        self._cmd_input.setText("" if cfg.get("cmd") is None else str(cfg["cmd"]))
        header = cfg.get("header")
        if isinstance(header, dict):
            if header.get("static") is not None:
                self._set_header_mode("static")
                self._header_static.setText(str(header["static"]))
                self._reset_values(None)
            else:
                self._set_header_mode("advanced")
                self._header_static.setText("")
                self._header_prefix.setText(str(header.get("prefix") or ""))
                self._header_format.setText(str(header.get("format") or ""))
                values = header.get("values")
                self._reset_values(values if isinstance(values, list) else None)
        else:
            self._set_header_mode("static")
            self._header_static.setText("")
            self._reset_values(None)
        self._update_driver_visibility()

    # ── validations / soumission ──────────────────────────────────────────
    def _clean_id(self, text: str) -> None:
        cleaned = re.sub(r"\s+", "_", text)
        if cleaned != text:
            edit = self._inputs["id"]
            pos = edit.cursorPosition()
            edit.setText(cleaned)
            edit.setCursorPosition(pos)

    def eventFilter(self, obj, e):
        # la fenêtre principale reprend le focus au clic (pas de transient
        # parent, cf. __init__) → on repasse le dialogue devant.
        if e.type() == QEvent.WindowActivate and self.isVisible():
            QTimer.singleShot(0, self._bring_to_front)
        return super().eventFilter(obj, e)

    def _bring_to_front(self) -> None:
        if self.isVisible():
            self.raise_()
            self.activateWindow()

    # ── drag de la fenêtre (header custom, fenêtre frameless) ──────────────
    # Déplacement manuel (move()) plutôt que startSystemMove : sur certains
    # compositeurs le move système d'un dialogue modal entraîne la fenêtre
    # parente avec lui.
    def _drag_header(self, e) -> None:
        if e.button() != Qt.LeftButton:
            return
        p = e.position().toPoint()
        # bord haut / coins hauts du header → resize, pas déplacement
        edges = Qt.Edges()
        if p.y() <= 8:
            edges |= Qt.TopEdge
            if p.x() <= 8:
                edges |= Qt.LeftEdge
            elif p.x() >= self._header.width() - 8:
                edges |= Qt.RightEdge
        if edges:
            handle = self.windowHandle()
            if handle is not None and hasattr(handle, "startSystemResize"):
                handle.startSystemResize(edges)
                e.accept()
                return
        # Wayland ignore move() client : startSystemMove est le seul déplacement
        # fiable — sans transient parent, il ne bouge plus la fenêtre principale.
        handle = self.windowHandle()
        if handle is not None and hasattr(handle, "startSystemMove"):
            handle.startSystemMove()
            e.accept()
            return
        self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()
        e.accept()

    def _drag_header_move(self, e) -> None:
        if self._drag_pos is not None and e.buttons() & Qt.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)
            e.accept()

    def _drag_header_release(self, e) -> None:
        self._drag_pos = None
        e.accept()

    def _check_resolution(self) -> bool:
        res = self._resolution()
        if res is None:
            self._res_err.setText("No resolution selected: no background "
                                  "folder exists for any resolution.")
            self._res_err.show()
            return False
        w, h = res
        try:
            check = json.loads(self.backend.check_resolution(str(w), str(h)))
        except Exception:
            return True
        if not check.get("supported"):
            self._res_err.setText(f"Unsupported resolution {w}×{h}: "
                                  f"no matching background folder exists.")
            self._res_err.show()
            return False
        self._res_err.setText("")
        self._res_err.hide()
        return True

    def _submit(self) -> None:
        form = {name: self._text(name) for name in self._inputs}
        res = self._resolution()
        if res is not None:
            form["width"], form["height"] = str(res[0]), str(res[1])
        # Toujours soumettre la config generic complète (champs masqués compris),
        # taguée avec le mode driver choisi.
        form["generic"] = self._driver == "generic"
        form["cmd"] = self._cmd_input.text()
        form["header"] = self._build_header()
        self._err.setText("")
        if not self._check_resolution():
            return
        if self._header_mode == "advanced" and not self._validate_values():
            return
        try:
            if self._editing:
                raw = self.backend.update_device(self._original_id, json.dumps(form))
            else:
                raw = self.backend.add_device(json.dumps(form))
            res = json.loads(raw)
        except Exception as e:
            self._err.setText(str(e))
            return
        if res.get("success"):
            self.accept()
        else:
            self._err.setText(res.get("error") or "Failed to save device")
