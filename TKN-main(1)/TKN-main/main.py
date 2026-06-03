"""
USB Logic Analyzer
Left  : waveform plot (drag to pan X / Y)
Right : settings panel
  1. Device Setting  – channel visibility, looping, timer, trigger
  2. Measurement     – +/- keys to zoom
  3. Timing Marker   – + key adds marker; list with Δt
  4. Extensions      – placeholders / future plug-ins
"""

import sys
import numpy as np
import collections
from PyQt5 import QtWidgets, QtCore, QtGui
import pyqtgraph as pg
try:
    import serial
    import serial.tools.list_ports
    _HAS_SERIAL = True
except ImportError:
    _HAS_SERIAL = False


# ═══════════════════════════════════════════════════════════════════
#  Helpers
# ═══════════════════════════════════════════════════════════════════
class MsAxisItem(pg.AxisItem):
    def tickStrings(self, values, scale, spacing):
        return [f"{int(v)} ms" for v in values]


# ═══════════════════════════════════════════════════════════════════
#  Serial Worker  –  đọc raw bytes từ STM32 USB CDC trên thread riêng
# ═══════════════════════════════════════════════════════════════════
class SerialWorker(QtCore.QThread):
    """Background thread: đọc raw bytes từ cổng COM (USB CDC).
    Mỗi byte = 1 sample, bit[n] = kênh n+1."""
    data_received  = QtCore.pyqtSignal(bytes)
    error_occurred = QtCore.pyqtSignal(str)
    CHUNK = 4096

    def __init__(self, port, baudrate=2_000_000, parent=None):
        super().__init__(parent)
        self._port     = port
        self._baudrate = baudrate
        self._running  = False

    def run(self):
        if not _HAS_SERIAL:
            self.error_occurred.emit("pyserial chưa được cài. Chạy: pip install pyserial")
            return
        try:
            ser = serial.Serial(
                self._port, self._baudrate,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE,
                timeout=0.05,
            )
            try:
                ser.set_buffer_size(rx_size=1_048_576)  # 1 MB RX buffer
            except Exception:
                pass
            self._running = True
            while self._running:
                chunk = ser.read(self.CHUNK)
                if chunk:
                    self.data_received.emit(bytes(chunk))
            ser.close()
        except Exception as exc:
            self.error_occurred.emit(str(exc))

    def stop(self):
        self._running = False
        self.wait(2000)


def _section_title(text):
    lbl = QtWidgets.QLabel(text)
    lbl.setStyleSheet(
        "font-size:12px; font-weight:700; color:#3a6eff; "
        "padding:6px 0 2px 0; letter-spacing:1px;")
    return lbl


def _h_line():
    f = QtWidgets.QFrame()
    f.setFrameShape(QtWidgets.QFrame.HLine)
    f.setStyleSheet("color:#111111;")
    return f


# ═══════════════════════════════════════════════════════════════════
#  Colour Themes
# ═══════════════════════════════════════════════════════════════════
THEMES = {
    "🌑 Dark": {
        "win_bg"       : "#0f1120",
        "toolbar_bg"   : "#161926",
        "toolbar_border": "#2a3050",
        "plot_bg"      : "#0d1018",
        "panel_bg"     : "#12151f",
        "panel_border" : "#2a3050",
        "text"         : "#c8d8f0",
        "subtext"      : "#607090",
        "accent"       : "#3a6eff",
        "grid_alpha"   : 0.20,
        "axis_pen"     : "#2a3050",
        "axis_text"    : "#8899bb",
        "swatch"       : "#0f1120",
    },
    "☀️ Light": {
        "win_bg"       : "#ffffff",
        "toolbar_bg"   : "#f2f2f2",
        "toolbar_border": "#111111",
        "plot_bg"      : "#ffffff",
        "panel_bg"     : "#f8f8f8",
        "panel_border" : "#111111",
        "text"         : "#111111",
        "subtext"      : "#444444",
        "accent"       : "#1a5cff",
        "grid_alpha"   : 0.40,
        "axis_pen"     : "#111111",
        "axis_text"    : "#222222",
        "swatch"       : "#ffffff",
    },
    "🌊 Ocean": {
        "win_bg"       : "#07192b",
        "toolbar_bg"   : "#0a2035",
        "toolbar_border": "#0e3050",
        "plot_bg"      : "#061525",
        "panel_bg"     : "#081e30",
        "panel_border" : "#0e3050",
        "text"         : "#a0d8ef",
        "subtext"      : "#3a7090",
        "accent"       : "#00b4d8",
        "grid_alpha"   : 0.18,
        "axis_pen"     : "#0e3050",
        "axis_text"    : "#3a8090",
        "swatch"       : "#07192b",
    },
    "🌲 Forest": {
        "win_bg"       : "#0c1a0e",
        "toolbar_bg"   : "#111f13",
        "toolbar_border": "#1e4020",
        "plot_bg"      : "#091409",
        "panel_bg"     : "#0e1c10",
        "panel_border" : "#1e4020",
        "text"         : "#a8d8a8",
        "subtext"      : "#3a6040",
        "accent"       : "#39d353",
        "grid_alpha"   : 0.18,
        "axis_pen"     : "#1e4020",
        "axis_text"    : "#3a7040",
        "swatch"       : "#0c1a0e",
    },
    "🌅 Sunset": {
        "win_bg"       : "#1a0c18",
        "toolbar_bg"   : "#220f1e",
        "toolbar_border": "#50203a",
        "plot_bg"      : "#140810",
        "panel_bg"     : "#1c0d18",
        "panel_border" : "#50203a",
        "text"         : "#f0c0d8",
        "subtext"      : "#805060",
        "accent"       : "#ff6fa8",
        "grid_alpha"   : 0.18,
        "axis_pen"     : "#50203a",
        "axis_text"    : "#906070",
        "swatch"       : "#1a0c18",
    },
    "💻 Hacker": {
        "win_bg"       : "#000000",
        "toolbar_bg"   : "#050505",
        "toolbar_border": "#003300",
        "plot_bg"      : "#000000",
        "panel_bg"     : "#020502",
        "panel_border" : "#003300",
        "text"         : "#00ff41",
        "subtext"      : "#006600",
        "accent"       : "#00ff41",
        "grid_alpha"   : 0.15,
        "axis_pen"     : "#003300",
        "axis_text"    : "#008800",
        "swatch"       : "#000000",
    },
}


# ═══════════════════════════════════════════════════════════════════
#  Dialog – Add Analyzer
# ═══════════════════════════════════════════════════════════════════
class AddAnalyzerDialog(QtWidgets.QDialog):
    PANEL_SS = """
        QDialog  { background:#ffffff; color:#111111; font-family:Segoe UI; }
        QLabel   { color:#333333; }
        QComboBox, QSpinBox {
            background:#f5f5f5; color:#111111; border:1px solid #111111;
            border-radius:4px; padding:4px 8px; font-size:13px; }
        QPushButton {
            background:#1a5cff; color:#fff; border:none; border-radius:5px;
            padding:7px 18px; font-size:13px; font-weight:600; }
        QPushButton:hover { background:#3a6eff; }
        QPushButton#cancel { background:#f0f0f0; color:#333333; border:1px solid #111111; }
        QPushButton#cancel:hover { background:#e0e0e0; }
    """
    def __init__(self, n_channels, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Analyzer")
        self.setFixedSize(340, 260)
        self.setStyleSheet(self.PANEL_SS)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setSpacing(14);  lay.setContentsMargins(22, 18, 22, 18)

        t = QtWidgets.QLabel("🔍  Protocol Analyzer")
        t.setStyleSheet("font-size:15px; font-weight:700; color:#e0e6f0;")
        lay.addWidget(t)

        form = QtWidgets.QFormLayout();  form.setSpacing(10)
        self.proto_combo = QtWidgets.QComboBox()
        self.proto_combo.addItems(["UART", "SPI", "I2C", "CAN", "1-Wire"])
        form.addRow("Protocol:", self.proto_combo)

        self.ch_combo = QtWidgets.QComboBox()
        for i in range(n_channels):
            self.ch_combo.addItem(f"CH{i+1}")
        form.addRow("Channel:", self.ch_combo)

        self.baud_spin = QtWidgets.QSpinBox()
        self.baud_spin.setRange(300, 10_000_000)
        self.baud_spin.setValue(9600);  self.baud_spin.setSingleStep(9600)
        form.addRow("Baud rate:", self.baud_spin)
        lay.addLayout(form);  lay.addSpacing(6)

        row = QtWidgets.QHBoxLayout()
        ok = QtWidgets.QPushButton("Add");  ok.clicked.connect(self.accept)
        ca = QtWidgets.QPushButton("Cancel")
        ca.setObjectName("cancel");  ca.clicked.connect(self.reject)
        row.addWidget(ca);  row.addWidget(ok)
        lay.addLayout(row)

    def result_data(self):
        return dict(protocol=self.proto_combo.currentText(),
                    channel=self.ch_combo.currentIndex(),
                    baud=self.baud_spin.value())


# ═══════════════════════════════════════════════════════════════════
#  Right-side Settings Panel
# ═══════════════════════════════════════════════════════════════════
PANEL_SS = """
    QWidget#rightPanel {
        background:#f8f8f8;
        border-left:1px solid #111111;
    }
    QLabel       { color:#111111; font-family:Segoe UI; font-size:12px; }
    QCheckBox    { color:#111111; font-family:Segoe UI; font-size:12px; spacing:6px; }
    QCheckBox::indicator {
        width:14px; height:14px; border-radius:3px;
        border:1px solid #111111; background:#ffffff; }
    QCheckBox::indicator:checked { background:#1a5cff; border-color:#1a5cff; }
    QPushButton  {
        background:#ffffff; color:#333333; border:1px solid #111111;
        border-radius:5px; padding:4px 10px; font-size:12px; font-family:Segoe UI; }
    QPushButton:hover  { background:#e8e8e8; color:#111111; border-color:#1a5cff; }
    QPushButton:checked { background:#1a3a8f; color:#fff; border:2px solid #1a5cff; }
    QComboBox, QSpinBox, QDoubleSpinBox {
        background:#ffffff; color:#111111; border:1px solid #111111;
        border-radius:4px; padding:3px 6px; font-size:12px; }
    QScrollArea  { background:transparent; border:none; }
    QListWidget  {
        background:#ffffff; color:#111111; border:1px solid #111111;
        border-radius:4px; font-size:11px; }
    QListWidget::item:selected { background:#dde6ff; color:#111111; }
    QLineEdit    {
        background:#ffffff; color:#111111; border:1px solid #111111;
        border-radius:4px; padding:3px 6px; font-size:12px; }
    QGroupBox    {
        color:#333333; font-size:11px; font-weight:600;
        border:1px solid #111111; border-radius:5px; margin-top:8px;
        padding-top:6px; }
    QGroupBox::title { subcontrol-origin:margin; left:8px; }
"""


class SettingsPanel(QtWidgets.QWidget):
    # ── signals ──────────────────────────────────────────────────────
    sig_channel_toggled   = QtCore.pyqtSignal(int, bool)   # ch_idx, visible
    sig_looping_changed   = QtCore.pyqtSignal(bool)
    sig_timer_changed     = QtCore.pyqtSignal(float)        # ms
    sig_trigger_changed   = QtCore.pyqtSignal(int, str)     # ch_idx, edge
    sig_add_marker        = QtCore.pyqtSignal()
    sig_clear_markers     = QtCore.pyqtSignal()
    sig_zoom_in           = QtCore.pyqtSignal()
    sig_zoom_out          = QtCore.pyqtSignal()
    sig_add_measurement   = QtCore.pyqtSignal(int, str)   # ch_idx, metric
    sig_del_measurement   = QtCore.pyqtSignal(int)        # row index
    sig_theme_changed     = QtCore.pyqtSignal(str)        # theme name

    def __init__(self, n_channels, colors, parent=None):
        super().__init__(parent)
        self.setObjectName("rightPanel")
        self.setStyleSheet(PANEL_SS)
        self.setFixedWidth(270)
        self.n_channels = n_channels
        self.colors = colors

        # main scroll
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        content = QtWidgets.QWidget()
        content.setStyleSheet("background:#f8f8f8;")
        self._content_widget = content          # keep ref for theme updates
        self._vlay = QtWidgets.QVBoxLayout(content)
        self._vlay.setContentsMargins(12, 10, 12, 14)
        self._vlay.setSpacing(4)
        scroll.setWidget(content)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self._build_device_setting()
        self._build_measurement()
        self._build_timing_marker()
        self._build_extensions()
        self._build_appearance()
        self._vlay.addStretch()

    # ────────────────────────── helpers ──────────────────────────────
    def _add(self, w): self._vlay.addWidget(w)

    # ══════════════════ 1. DEVICE SETTING ════════════════════════════
    def _build_device_setting(self):
        self._add(_section_title("① DEVICE SETTING"))
        self._add(_h_line())

        # — Display sub-group ----------------------------------------
        disp_grp = QtWidgets.QGroupBox("Display")
        disp_lay = QtWidgets.QVBoxLayout(disp_grp)
        disp_lay.setSpacing(4)

        sub_lbl = QtWidgets.QLabel("Digital channels")
        sub_lbl.setStyleSheet("color:#444444; font-size:11px;")
        disp_lay.addWidget(sub_lbl)

        self._ch_checks = []
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(4)
        for i in range(self.n_channels):
            cb = QtWidgets.QCheckBox(f"CH{i+1}")
            cb.setChecked(True)
            color = self.colors[i % len(self.colors)]
            cb.setStyleSheet(
                f"QCheckBox {{ color:{color}; }} "
                f"QCheckBox::indicator:checked {{ background:{color}; border-color:{color}; }}")
            idx = i
            cb.toggled.connect(lambda st, j=idx: self.sig_channel_toggled.emit(j, st))
            self._ch_checks.append(cb)
            grid.addWidget(cb, i // 2, i % 2)
        disp_lay.addLayout(grid)
        self._add(disp_grp)

        # — Functions sub-group --------------------------------------
        fn_grp = QtWidgets.QGroupBox("Functions")
        fn_lay = QtWidgets.QFormLayout(fn_grp)
        fn_lay.setSpacing(6)

        # Looping
        self._loop_cb = QtWidgets.QCheckBox("Enabled")
        self._loop_cb.toggled.connect(self.sig_looping_changed)
        fn_lay.addRow("Looping:", self._loop_cb)

        # Timer (ms)
        self._timer_spin = QtWidgets.QDoubleSpinBox()
        self._timer_spin.setRange(0, 100_000)
        self._timer_spin.setValue(1000)
        self._timer_spin.setSuffix(" ms")
        self._timer_spin.setSingleStep(100)
        self._timer_spin.valueChanged.connect(self.sig_timer_changed)
        fn_lay.addRow("Timer:", self._timer_spin)

        # Trigger channel
        trig_row = QtWidgets.QHBoxLayout()
        self._trig_ch = QtWidgets.QComboBox()
        for i in range(self.n_channels):
            self._trig_ch.addItem(f"CH{i+1}")
        self._trig_edge = QtWidgets.QComboBox()
        self._trig_edge.addItems(["Rising ↑", "Falling ↓", "Both ↕", "High", "Low"])
        trig_row.addWidget(self._trig_ch)
        trig_row.addWidget(self._trig_edge)
        fn_lay.addRow("Trigger:", trig_row)

        trig_btn = QtWidgets.QPushButton("Apply Trigger")
        trig_btn.clicked.connect(self._emit_trigger)
        fn_lay.addRow("", trig_btn)

        self._add(fn_grp)
        self._add(QtWidgets.QLabel(""))   # spacer

    def _emit_trigger(self):
        ch   = self._trig_ch.currentIndex()
        edge = self._trig_edge.currentText()
        self.sig_trigger_changed.emit(ch, edge)

    # ══════════════════ 2. MEASUREMENT ═══════════════════════════════
    def _build_measurement(self):
        self._add(_section_title("② MEASUREMENT"))
        self._add(_h_line())

        meas_grp = QtWidgets.QGroupBox("Measurements  ( + to add )")
        m_lay = QtWidgets.QVBoxLayout(meas_grp)
        m_lay.setSpacing(6)

        # ── Picker row ──────────────────────────────────────────────
        pick_row = QtWidgets.QHBoxLayout()
        self._meas_ch = QtWidgets.QComboBox()
        for i in range(self.n_channels):
            self._meas_ch.addItem(f"CH{i+1}")
        self._meas_ch.setFixedWidth(62)

        self._meas_type = QtWidgets.QComboBox()
        self._meas_type.addItems([
            "Frequency", "Period", "PW-High", "PW-Low", "Duty Cycle"])

        add_btn = QtWidgets.QPushButton("+")
        add_btn.setFixedWidth(30)
        add_btn.setStyleSheet(
            "QPushButton{background:#1a3a8f;color:#fff;border:none;"
            "border-radius:4px;font-size:16px;font-weight:700;}"
            "QPushButton:hover{background:#2a5adf;}")
        add_btn.setToolTip("Add measurement (shortcut: + key)")
        add_btn.clicked.connect(self._emit_add_measurement)

        pick_row.addWidget(self._meas_ch)
        pick_row.addWidget(self._meas_type, stretch=1)
        pick_row.addWidget(add_btn)
        m_lay.addLayout(pick_row)

        # ── Measurement list ─────────────────────────────────────────
        self._meas_list = QtWidgets.QTableWidget(0, 3)
        self._meas_list.setHorizontalHeaderLabels(["CH", "Metric", "Value"])
        self._meas_list.horizontalHeader().setStretchLastSection(True)
        self._meas_list.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectRows)
        self._meas_list.setEditTriggers(
            QtWidgets.QAbstractItemView.NoEditTriggers)
        self._meas_list.verticalHeader().setVisible(False)
        self._meas_list.setFixedHeight(130)
        self._meas_list.setStyleSheet(
            "QTableWidget{background:#ffffff;color:#111111;"
            "gridline-color:#111111;font-size:11px;border:1px solid #111111;}"
            "QHeaderView::section{background:#f0f0f0;color:#333333;"
            "padding:3px;border:1px solid #111111;}")
        m_lay.addWidget(self._meas_list)

        # ── Delete selected row ──────────────────────────────────────
        del_row = QtWidgets.QHBoxLayout()
        del_btn = QtWidgets.QPushButton("🗑  Remove")
        del_btn.clicked.connect(self._emit_del_measurement)
        del_row.addStretch()
        del_row.addWidget(del_btn)
        m_lay.addLayout(del_row)

        # ── View info (updated externally) ───────────────────────────
        self._view_lbl = QtWidgets.QLabel("View: 0 – 200 ms  (200 ms)")
        self._view_lbl.setStyleSheet(
            "color:#1a5cff; font-size:10px; padding-top:2px;")
        m_lay.addWidget(self._view_lbl)

        hint = QtWidgets.QLabel("Zoom: Ctrl + +/−  or  scroll wheel")
        hint.setStyleSheet("color:#555555; font-size:10px;")
        m_lay.addWidget(hint)

        self._add(meas_grp)
        self._add(QtWidgets.QLabel(""))

    def _emit_add_measurement(self):
        self.sig_add_measurement.emit(
            self._meas_ch.currentIndex(),
            self._meas_type.currentText())

    def _emit_del_measurement(self):
        rows = sorted({i.row() for i in self._meas_list.selectedItems()},
                      reverse=True)
        for r in rows:
            self._meas_list.removeRow(r)
            self.sig_del_measurement.emit(r)

    def add_measurement_row(self, ch_name, metric, value):
        row = self._meas_list.rowCount()
        self._meas_list.insertRow(row)
        self._meas_list.setItem(row, 0, QtWidgets.QTableWidgetItem(ch_name))
        self._meas_list.setItem(row, 1, QtWidgets.QTableWidgetItem(metric))
        self._meas_list.setItem(row, 2, QtWidgets.QTableWidgetItem(value))
        self._meas_list.scrollToBottom()

    def set_view_info(self, xmin, xmax):
        self._view_lbl.setText(
            f"View: {xmin:.0f} – {xmax:.0f} ms  ({xmax-xmin:.0f} ms)")

    # ══════════════════ 3. TIMING MARKER ══════════════════════════════
    def _build_timing_marker(self):
        self._add(_section_title("③ TIMING MARKER"))
        self._add(_h_line())

        tm_grp = QtWidgets.QGroupBox("Markers  (press  +  to add)")
        t_lay = QtWidgets.QVBoxLayout(tm_grp)
        t_lay.setSpacing(6)

        hint = QtWidgets.QLabel(
            "Press  +  (or button) to add a marker\nat the current cursor position.\nMax 2 markers → Δt shown.")
        hint.setStyleSheet("color:#444444; font-size:11px;")
        hint.setWordWrap(True)
        t_lay.addWidget(hint)

        add_btn = QtWidgets.QPushButton("⊕  Add Marker  (+)")
        add_btn.clicked.connect(self.sig_add_marker)
        t_lay.addWidget(add_btn)

        clr_btn = QtWidgets.QPushButton("✕  Clear Markers")
        clr_btn.clicked.connect(self.sig_clear_markers)
        t_lay.addWidget(clr_btn)

        # Marker list
        self._marker_list = QtWidgets.QListWidget()
        self._marker_list.setFixedHeight(90)
        t_lay.addWidget(self._marker_list)

        # Δt label
        self._dt_lbl = QtWidgets.QLabel("Δt = —")
        self._dt_lbl.setStyleSheet(
            "color:#1a5cff; font-size:13px; font-weight:700; "
            "padding:4px; background:#e8eeff; border:1px solid #111111; border-radius:4px;")
        self._dt_lbl.setAlignment(QtCore.Qt.AlignCenter)
        t_lay.addWidget(self._dt_lbl)

        self._add(tm_grp)
        self._add(QtWidgets.QLabel(""))

    def update_marker_panel(self, markers):
        """markers = list of (ms, line_obj)"""
        self._marker_list.clear()
        for idx, (ms, _) in enumerate(markers):
            self._marker_list.addItem(f"M{idx+1}:  {ms:.2f} ms")
        if len(markers) == 2:
            dt = abs(markers[1][0] - markers[0][0])
            self._dt_lbl.setText(f"Δt = {dt:.3f} ms")
        else:
            self._dt_lbl.setText("Δt = —")

    # ══════════════════ 4. EXTENSIONS ═════════════════════════════════
    def _build_extensions(self):
        self._add(_section_title("④ EXTENSIONS"))
        self._add(_h_line())

        ext_grp = QtWidgets.QGroupBox("Installed Extensions")
        e_lay = QtWidgets.QVBoxLayout(ext_grp)
        e_lay.setSpacing(6)

        extensions = [
            ("📦 SPI Flash Decoder",  False),
            ("📦 I2C Scanner",         False),
            ("📦 UART Logger",         False),
            ("📦 CAN Bus Analyzer",    False),
        ]
        for name, enabled in extensions:
            row = QtWidgets.QHBoxLayout()
            lbl = QtWidgets.QLabel(name)
            lbl.setStyleSheet("font-size:11px; color:#222222;")
            btn = QtWidgets.QPushButton("Enable" if not enabled else "Disable")
            btn.setFixedWidth(64)
            btn.setStyleSheet("font-size:10px; padding:2px 6px;")
            row.addWidget(lbl)
            row.addStretch()
            row.addWidget(btn)
            e_lay.addLayout(row)

        add_ext_btn = QtWidgets.QPushButton("⊕  Load Extension…")
        add_ext_btn.clicked.connect(lambda: QtWidgets.QMessageBox.information(
            self, "Extensions", "Extension marketplace – coming soon!"))
        e_lay.addWidget(add_ext_btn)

        self._add(ext_grp)

    # ══════════════════ 5. APPEARANCE ════════════════════════════════
    def _build_appearance(self):
        self._add(_section_title("⑤ APPEARANCE"))
        self._add(_h_line())

        app_grp = QtWidgets.QGroupBox("Interface Theme")
        a_lay = QtWidgets.QVBoxLayout(app_grp)
        a_lay.setSpacing(6)

        hint = QtWidgets.QLabel("Select a colour theme for the whole interface.")
        hint.setStyleSheet("color:#444444; font-size:10px;")
        hint.setWordWrap(True)
        a_lay.addWidget(hint)

        # ── One button per theme ──────────────────────────────────────────
        self._theme_btns = {}
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(5)
        for idx, (name, t) in enumerate(THEMES.items()):
            btn = QtWidgets.QPushButton(name)
            btn.setCheckable(True)
            btn.setChecked(name == "☀️ Light")   # default
            # colour swatch as stylesheet border + bg preview
            swatch = t["swatch"]
            accent = t["accent"]
            text_c = t["text"]
            btn.setStyleSheet(
                f"QPushButton{{"
                f"background:{swatch};color:{text_c};"
                f"border:2px solid #2a3050;border-radius:5px;"
                f"padding:4px 6px;font-size:11px;font-weight:600;}}"
                f"QPushButton:checked{{border:2px solid {accent};}}"
                f"QPushButton:hover{{border-color:{accent};}}"
            )
            btn.clicked.connect(lambda _, n=name: self._on_theme_btn(n))
            self._theme_btns[name] = btn
            grid.addWidget(btn, idx // 2, idx % 2)
        a_lay.addLayout(grid)
        self._add(app_grp)
        self._add(QtWidgets.QLabel(""))

    def _on_theme_btn(self, chosen_name):
        # Uncheck all others
        for name, btn in self._theme_btns.items():
            btn.setChecked(name == chosen_name)
        self.sig_theme_changed.emit(chosen_name)

    def mark_theme_active(self, name):
        """Called externally to sync checkbox state."""
        for n, btn in self._theme_btns.items():
            btn.setChecked(n == name)

# ═══════════════════════════════════════════════════════════════════
#  Mode Selection Dialog
# ═══════════════════════════════════════════════════════════════════
class ModeSelectDialog(QtWidgets.QDialog):
    """Màn hình lựa chọn chế độ hoạt động khi khởi động."""

    DIALOG_SS = """
        QDialog {
            background: qlineargradient(
                x1:0, y1:0, x2:1, y2:1,
                stop:0 #0b0e1a, stop:1 #0f1830);
        }
        QLabel#title {
            color: #ffffff;
            font-family: Segoe UI;
            font-size: 26px;
            font-weight: 700;
            letter-spacing: 2px;
        }
        QLabel#subtitle {
            color: #607090;
            font-family: Segoe UI;
            font-size: 13px;
        }
        QPushButton#modeBtn {
            background: transparent;
            border: 2px solid #2a3a60;
            border-radius: 16px;
            color: #c8d8f0;
            font-family: Segoe UI;
            font-size: 13px;
            padding: 0px;
            text-align: left;
        }
        QPushButton#modeBtn:hover {
            border-color: #3a6eff;
            background: rgba(58, 110, 255, 0.08);
        }
        QPushButton#modeBtn:pressed {
            background: rgba(58, 110, 255, 0.18);
        }
    """

    def __init__(self, parent=None):
        super().__init__(parent)
        self.chosen_mode = None
        self.setWindowTitle("USB Logic Analyzer – Select Mode")
        self.setFixedSize(620, 400)
        self.setWindowFlags(QtCore.Qt.Dialog | QtCore.Qt.FramelessWindowHint)
        self.setStyleSheet(self.DIALOG_SS)

        root = QtWidgets.QVBoxLayout(self)
        root.setContentsMargins(48, 40, 48, 40)
        root.setSpacing(0)

        # ── Header ───────────────────────────────────────────────────────
        icon_lbl = QtWidgets.QLabel("⚡")
        icon_lbl.setStyleSheet("font-size:36px; color:#3a6eff;")
        icon_lbl.setAlignment(QtCore.Qt.AlignCenter)
        root.addWidget(icon_lbl)

        title = QtWidgets.QLabel("USB Logic Analyzer")
        title.setObjectName("title")
        title.setAlignment(QtCore.Qt.AlignCenter)
        root.addWidget(title)

        sub = QtWidgets.QLabel("Chọn chế độ hoạt động để bắt đầu")
        sub.setObjectName("subtitle")
        sub.setAlignment(QtCore.Qt.AlignCenter)
        root.addWidget(sub)

        root.addSpacing(32)

        # ── Mode cards ───────────────────────────────────────────────────
        cards_row = QtWidgets.QHBoxLayout()
        cards_row.setSpacing(20)

        demo_btn = self._make_card(
            "1",
            "🎬  Demo Mode",
            "Xem tín hiệu giả lập (không cần thiết bị).\nThử nghiệm tính năng, giao diện, đo lường.",
            "#3a6eff",
        )
        demo_btn.clicked.connect(lambda: self._choose("demo"))

        live_btn = self._make_card(
            "2",
            "🔌  Live Signal Mode",
            "Kết nối thiết bị thật qua USB CDC.\nHiển thị tín hiệu số thời gian thực.",
            "#00c878",
        )
        live_btn.clicked.connect(lambda: self._choose("live"))

        cards_row.addWidget(demo_btn)
        cards_row.addWidget(live_btn)
        root.addLayout(cards_row)

        root.addStretch()

        # ── Footer hint ──────────────────────────────────────────────────
        hint = QtWidgets.QLabel("Nhấn  1  hoặc  2  trên bàn phím để chọn nhanh")
        hint.setStyleSheet("color:#3a4870; font-size:11px; font-family:Segoe UI;")
        hint.setAlignment(QtCore.Qt.AlignCenter)
        root.addWidget(hint)

    # ── Helpers ──────────────────────────────────────────────────────────
    def _make_card(self, shortcut, header, body, accent):
        btn = QtWidgets.QPushButton()
        btn.setObjectName("modeBtn")
        btn.setFixedSize(240, 160)
        btn.setCursor(QtCore.Qt.PointingHandCursor)

        lay = QtWidgets.QVBoxLayout(btn)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)

        # Shortcut badge
        badge = QtWidgets.QLabel(shortcut)
        badge.setStyleSheet(
            f"color:{accent}; font-size:28px; font-weight:700;"
            f"font-family:'Segoe UI';")
        lay.addWidget(badge)

        head = QtWidgets.QLabel(header)
        head.setStyleSheet(
            f"color:{accent}; font-size:14px; font-weight:700;"
            f"font-family:'Segoe UI';")
        lay.addWidget(head)

        desc = QtWidgets.QLabel(body)
        desc.setStyleSheet(
            "color:#8090b0; font-size:11px; font-family:'Segoe UI';")
        desc.setWordWrap(True)
        lay.addWidget(desc)

        lay.addStretch()
        return btn

    def _choose(self, mode):
        self.chosen_mode = mode
        self.accept()

    def keyPressEvent(self, ev):
        if ev.key() == QtCore.Qt.Key_1:
            self._choose("demo")
        elif ev.key() == QtCore.Qt.Key_2:
            self._choose("live")
        elif ev.key() == QtCore.Qt.Key_Escape:
            self.reject()
        else:
            super().keyPressEvent(ev)


# ═══════════════════════════════════════════════════════════════════
#  Main Window
# ═══════════════════════════════════════════════════════════════════
class LogicAnalyzer(QtWidgets.QMainWindow):

    COLORS = [
        '#00BFFF', '#00FF7F', '#FF6347', '#FFD700',
        '#DA70D6', '#FF8C00', '#7FFFD4', '#FF69B4',
    ]

    def __init__(self, mode="demo"):
        super().__init__()
        self._mode = mode   # "demo" | "live"
        title_suffix = "– Demo Mode" if mode == "demo" else "– Live Signal Mode"
        self.setWindowTitle(f"USB Logic Analyzer  {title_suffix}")
        self.setGeometry(80, 80, 1440, 820)
        self._apply_global_style()

        # ── Data ──────────────────────────────────────────────────────────
        self.n_channels    = 8
        self.n_samples     = 2000
        # Mỗi kênh gán tên giao thức để người dùng dễ nhận biết
        self.channel_names = [
            "CH1 UART-TX",
            "CH2 SPI-CLK",
            "CH3 SPI-MOSI",
            "CH4 SPI-CS",
            "CH5 I2C-SCL",
            "CH6 I2C-SDA",
            "CH7 PWM",
            "CH8 CLK",
        ]
        # Live mode: khởi tạo data = 0 (flat line) – không hiện tín hiệu giả
        # Demo mode: data ngẫu nhiên như cũ
        self.data = (
            self._generate_data() if mode == "demo"
            else [np.zeros(self.n_samples, dtype=np.uint8)
                  for _ in range(self.n_channels)]
        )
        self._ch_visible   = [True] * self.n_channels

        # ── Central container ─────────────────────────────────────────────
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        root_v = QtWidgets.QVBoxLayout(central)
        root_v.setContentsMargins(0, 0, 0, 0)
        root_v.setSpacing(0)

        # Toolbar
        root_v.addWidget(self._build_toolbar())

        # Body (plot + right panel)
        body = QtWidgets.QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # ── Plot ──────────────────────────────────────────────────────────
        self.graphWidget = pg.PlotWidget(
            background='#0d1018',
            axisItems={'bottom': MsAxisItem(orientation='bottom')}
        )
        self.graphWidget.setMouseEnabled(x=False, y=False)
        self.graphWidget.showGrid(x=True, y=False, alpha=0.2)
        body.addWidget(self.graphWidget, stretch=1)

        # ── Right panel ───────────────────────────────────────────────────
        self._panel = SettingsPanel(self.n_channels, self.COLORS)
        body.addWidget(self._panel)
        root_v.addLayout(body, stretch=1)

        # ── Status bar ────────────────────────────────────────────────────
        self._status = QtWidgets.QStatusBar()
        self._status.setStyleSheet(
            "QStatusBar{ background:#f2f2f2; color:#444444; font-size:12px; border-top:1px solid #111111; }")
        self.setStatusBar(self._status)
        if self._mode == "live":
            self._status.showMessage(
                "🔌  Live Signal Mode  |  Chọn cổng COM rồi nhấn  Connect  để bắt đầu nhận tín hiệu thật")
        else:
            self._status.showMessage(
                "Ready  |  Drag to pan  |  +/− to zoom  |  Click tool buttons to activate")

        # ── Plot init ─────────────────────────────────────────────────────
        self._setup_y_axis()
        self._plot_waveform()
        self.VIEW_MS = 200
        self.graphWidget.setXRange(0, self.VIEW_MS, padding=0)
        self._update_y_range()

        # ── Measurement store ─────────────────────────────────────────────
        self._measurements = []    # list of (ch_idx, metric)

        # ── Connect panel signals ─────────────────────────────────────────
        self._panel.sig_channel_toggled.connect(self._on_ch_toggle)
        self._panel.sig_looping_changed.connect(self._on_looping)
        self._panel.sig_timer_changed.connect(self._on_timer_change)
        self._panel.sig_trigger_changed.connect(self._on_trigger)
        self._panel.sig_zoom_in.connect(self._zoom_in)
        self._panel.sig_zoom_out.connect(self._zoom_out)
        self._panel.sig_add_measurement.connect(self._on_add_measurement)
        self._panel.sig_del_measurement.connect(self._on_del_measurement)
        self._panel.sig_add_marker.connect(self._add_marker_at_center)
        self._panel.sig_clear_markers.connect(self._clear_markers)
        self._panel.sig_theme_changed.connect(self.apply_theme)
        self._panel.set_view_info(0, self.VIEW_MS)
        # Re-apply theme after all widgets are created
        self.apply_theme("☀️ Light")

        # ── Drag state ────────────────────────────────────────────────────
        self._drag_start_x    = None
        self._drag_start_y    = None
        self._view_start_xrng = None
        self._view_start_yrng = None

        # ── Demo ──────────────────────────────────────────────────────────
        self._demo_running = False
        self._demo_timer   = QtCore.QTimer()
        self._demo_timer.setInterval(80)
        self._demo_timer.timeout.connect(self._demo_tick)

        # ── Looping (repeat demo) ─────────────────────────────────────────
        self._loop_enabled = False
        self._trigger_info  = None       # (ch, edge)

        # ── Analyzers ─────────────────────────────────────────────────────
        self._analyzers      = []
        self._analyzer_items = []

        # ── Range management ─────────────────────────────────────────────
        self._range_mode  = False
        self._range_start = None
        self._range_rect  = None
        self._ranges      = []
        self._range_items = []

        # ── Timing markers ────────────────────────────────────────────────
        self._marker_mode  = False
        self._markers      = []          # [(ms, InfiniteLine)]
        self._marker_label = None

        # ── Mouse hook ────────────────────────────────────────────────────
        scene = self.graphWidget.scene()
        scene.mousePressEvent   = self._scene_mouse_press
        scene.mouseMoveEvent    = self._scene_mouse_move
        scene.mouseReleaseEvent = self._scene_mouse_release
        scene.wheelEvent        = self._scene_wheel_event

        # ── Keyboard shortcut ─────────────────────────────────────────────
        self.graphWidget.installEventFilter(self)
        self.installEventFilter(self)

        # ── Serial / USB-CDC state ────────────────────────────────────────
        self._serial_mode     = False
        self._serial_worker   = None
        self._serial_new_data = False
        # Circular buffer: 1 deque per channel, giữ n_samples mẫu mới nhất
        self._serial_buf = [
            collections.deque([0] * self.n_samples, maxlen=self.n_samples)
            for _ in range(self.n_channels)
        ]
        # Timer cập nhật plot từ buffer (~60 fps)
        self._serial_timer = QtCore.QTimer()
        self._serial_timer.setInterval(16)          # ~60 fps
        self._serial_timer.timeout.connect(self._serial_refresh)

        # ── Scan COM ports on startup ──────────────────────────────────
        if _HAS_SERIAL:
            self._scan_ports()

    # ═══════════════════════════════ STYLE ═══════════════════════════════ #
    def _apply_global_style(self):
        """Apply default (Light) theme on startup."""
        self.apply_theme("☀️ Light")

    def apply_theme(self, name):
        """Apply a named theme to every visual element."""
        t = THEMES.get(name)
        if t is None:
            return
        self._current_theme = name

        # ── Window / global QSS ──────────────────────────────────────────
        win_bg = t["win_bg"]
        text   = t["text"]
        accent = t["accent"]
        subtext = t["subtext"]
        tb_bg  = t["toolbar_bg"]
        tb_brd = t["toolbar_border"]
        pb_bg  = t["panel_bg"]
        pb_brd = t["panel_border"]

        self.setStyleSheet(f"""
            QMainWindow {{ background:{win_bg}; }}
            QWidget      {{ background:{win_bg}; color:{text};
                           font-family:Segoe UI; }}
            QToolTip     {{ background:{pb_bg}; color:{text};
                           border:1px solid {accent}; }}
            QStatusBar   {{ background:{tb_bg}; color:{subtext};
                           font-size:12px; }}
        """)

        # ── Toolbar widget ────────────────────────────────────────────────
        if hasattr(self, '_toolbar_widget'):
            self._toolbar_widget.setStyleSheet(
                f"background:{tb_bg}; border-bottom:1px solid {tb_brd};")

        # ── Right panel ───────────────────────────────────────────────────
        panel_ss = f"""
            QWidget#rightPanel {{
                background:{pb_bg};
                border-left:1px solid {pb_brd};
            }}
            QLabel       {{ color:{text}; font-family:Segoe UI; font-size:12px; }}
            QCheckBox    {{ color:{text}; font-family:Segoe UI;
                           font-size:12px; spacing:6px; }}
            QCheckBox::indicator {{
                width:14px; height:14px; border-radius:3px;
                border:1px solid {pb_brd}; background:{pb_bg}; }}
            QCheckBox::indicator:checked {{
                background:{accent}; border-color:{accent}; }}
            QPushButton  {{
                background:{pb_bg}; color:{subtext}; border:1px solid {pb_brd};
                border-radius:5px; padding:4px 10px;
                font-size:12px; font-family:Segoe UI; }}
            QPushButton:hover  {{
                background:{tb_bg}; color:{text}; border-color:{accent}; }}
            QPushButton:checked {{
                background:{accent}; color:#fff; border:2px solid {accent}; }}
            QComboBox, QSpinBox, QDoubleSpinBox {{
                background:{pb_bg}; color:{text}; border:1px solid {pb_brd};
                border-radius:4px; padding:3px 6px; font-size:12px; }}
            QScrollArea  {{ background:transparent; border:none; }}
            QListWidget  {{
                background:{win_bg}; color:{text}; border:1px solid {pb_brd};
                border-radius:4px; font-size:11px; }}
            QListWidget::item:selected {{ background:{tb_bg}; color:{text}; }}
            QLineEdit    {{
                background:{pb_bg}; color:{text}; border:1px solid {pb_brd};
                border-radius:4px; padding:3px 6px; font-size:12px; }}
            QGroupBox    {{
                color:{subtext}; font-size:11px; font-weight:600;
                border:1px solid {pb_brd}; border-radius:5px;
                margin-top:8px; padding-top:6px; }}
            QGroupBox::title {{ subcontrol-origin:margin; left:8px; }}
        """
        if hasattr(self, '_panel'):
            self._panel.setStyleSheet(panel_ss)
            # sync inner content widget background via stored reference
            if hasattr(self._panel, '_content_widget'):
                self._panel._content_widget.setStyleSheet(f"background:{pb_bg};")
            self._panel.mark_theme_active(name)

        # ── Plot area ─────────────────────────────────────────────────────
        if hasattr(self, 'graphWidget'):
            self.graphWidget.setBackground(t["plot_bg"])
            self.graphWidget.showGrid(x=True, y=False, alpha=t["grid_alpha"])
            ax = self.graphWidget.getAxis('left')
            ax.setPen(pg.mkPen(t["axis_pen"]))
            ax.setTextPen(pg.mkPen(t["axis_text"]))
            bx = self.graphWidget.getAxis('bottom')
            bx.setPen(pg.mkPen(t["axis_pen"]))
            bx.setTextPen(pg.mkPen(t["axis_text"]))
            # Only re-colour the bottom time label; left label removed (ticks carry channel names)
            self.graphWidget.setLabel(
                'bottom', 'Time (ms)',
                **{'color': t["subtext"], 'font-size': '11pt'})
            self.graphWidget.getAxis('left').setLabel('')   # keep blank

        if hasattr(self, '_status'):
            self._status.showMessage(f"Theme applied: {name}")

    # ═══════════════════════════ TOOLBAR ══════════════════════════════════ #
    def _build_toolbar(self):
        bar = QtWidgets.QWidget()
        self._toolbar_widget = bar          # keep ref for theme switching
        bar.setFixedHeight(56)
        bar.setStyleSheet("background:#f2f2f2; border-bottom:1px solid #111111;")
        h = QtWidgets.QHBoxLayout(bar)
        h.setContentsMargins(14, 4, 14, 4);  h.setSpacing(8)

        logo = QtWidgets.QLabel("⚡ Logic Analyzer")
        logo.setStyleSheet("font-size:16px; font-weight:700; color:#1a5cff;")
        h.addWidget(logo);  h.addSpacing(16)

        def vsep():
            s = QtWidgets.QFrame()
            s.setFrameShape(QtWidgets.QFrame.VLine)
            s.setStyleSheet("color:#2a3050;")
            return s

        N = """QPushButton {
            background:#ffffff; color:#222222; border:1px solid #111111;
            border-radius:6px; padding:5px 14px; font-size:13px; font-weight:600; min-width:120px;}
            QPushButton:hover {background:#e8e8e8;color:#111111;border-color:#1a5cff;}"""
        A = """QPushButton {
            background:#1a3a8f; color:#fff; border:2px solid #1a5cff;
            border-radius:6px; padding:5px 14px; font-size:13px; font-weight:700; min-width:120px;}"""
        self._BTN_NORMAL = N;  self._BTN_ACTIVE = A

        # ── Mode badge (Live mode only) ─────────────────────────────────
        if self._mode == "live":
            live_badge = QtWidgets.QLabel("🔴  LIVE")
            live_badge.setStyleSheet(
                "color:#00ff88; font-size:14px; font-weight:700;"
                "background:rgba(0,200,100,0.12); border:1px solid #00c878;"
                "border-radius:6px; padding:4px 12px; font-family:Segoe UI;")
            h.addWidget(live_badge)
            h.addWidget(vsep())

        self._btn_demo = QtWidgets.QPushButton("▶  Start Demo")
        self._btn_demo.setStyleSheet(N)
        self._btn_demo.clicked.connect(self._toggle_demo)
        # Demo mode: ẩn hoàn toàn nút Start Demo nếu đang ở Live mode
        if self._mode == "live":
            self._btn_demo.hide()

        self._btn_analyzer = QtWidgets.QPushButton("🔍  Add Analyzer")
        self._btn_analyzer.setStyleSheet(N)
        self._btn_analyzer.clicked.connect(self._open_add_analyzer)

        self._btn_range = QtWidgets.QPushButton("📐  Range Mgmt")
        self._btn_range.setStyleSheet(N);  self._btn_range.setCheckable(True)
        self._btn_range.clicked.connect(self._toggle_range_mode)

        self._btn_marker = QtWidgets.QPushButton("⏱  Timing Marker")
        self._btn_marker.setStyleSheet(N);  self._btn_marker.setCheckable(True)
        self._btn_marker.clicked.connect(self._toggle_marker_mode)

        visible_btns = [self._btn_analyzer, self._btn_range, self._btn_marker]
        if self._mode == "demo":
            visible_btns.insert(0, self._btn_demo)
        for btn in visible_btns:
            h.addWidget(btn);  h.addWidget(vsep())

        # ── Serial Port (USB CDC) ───────────────────────────────────────
        # Live mode: cổng COM nổi bật hơn
        _live = (self._mode == "live")
        SCS = ("QComboBox{background:#ffffff;color:#111111;"
               f"border:{'2px solid #00c878' if _live else '1px solid #111111'};border-radius:5px;"
               "padding:3px 6px;font-size:12px;}"
               "QComboBox::drop-down{border:none;}"
               "QComboBox QAbstractItemView{background:#ffffff;"
               "color:#111111;selection-background-color:#dde6ff;}")
        BSS = ("QPushButton{background:#ffffff;color:#333333;"
               "border:1px solid #111111;border-radius:5px;"
               "padding:4px 8px;font-size:13px;font-weight:600;}"
               "QPushButton:hover{background:#e8e8e8;color:#111111;"
               "border-color:#1a5cff;}")

        self._port_combo = QtWidgets.QComboBox()
        self._port_combo.setFixedWidth(105)
        self._port_combo.setStyleSheet(SCS)
        self._port_combo.setToolTip("Chọn cổng COM (STM32 USB CDC)")
        if not _HAS_SERIAL:
            self._port_combo.addItem("pyserial n/a")
            self._port_combo.setEnabled(False)

        self._btn_scan = QtWidgets.QPushButton("↺")
        self._btn_scan.setFixedWidth(30)
        self._btn_scan.setStyleSheet(BSS)
        self._btn_scan.setToolTip("Quét / làm mới danh sách cổng COM")
        self._btn_scan.clicked.connect(self._scan_ports)

        self._btn_connect = QtWidgets.QPushButton("🔌 Connect")
        # Live mode: nút Connect nổi bật với màu xanh lá
        _LIVE_CONNECT_SS = (
            "QPushButton{background:#00c878;color:#000;border:none;"
            "border-radius:6px;padding:5px 14px;font-size:13px;font-weight:700;"
            "min-width:120px;}"
            "QPushButton:hover{background:#00e890;}"
        )
        self._btn_connect.setFixedWidth(118)
        self._btn_connect.setStyleSheet(_LIVE_CONNECT_SS if _live else N)
        self._btn_connect.setToolTip("Kết nối / ngắt STM32 qua USB CDC")
        self._btn_connect.setEnabled(_HAS_SERIAL)
        self._btn_connect.clicked.connect(self._toggle_connect)

        h.addWidget(self._port_combo)
        h.addWidget(self._btn_scan)
        h.addWidget(vsep())
        h.addWidget(self._btn_connect)
        h.addWidget(vsep())

        h.addStretch()

        # ranges list, clear markers, zoom buttons (compact, right-aligned)
        ZS = """QPushButton{
            background:#ffffff;color:#222222;border:1px solid #111111;
            border-radius:5px;padding:4px 10px;font-size:14px;font-weight:700;}
            QPushButton:hover{background:#e8e8e8;color:#111111;border-color:#1a5cff;}"""

        for label, slot in [("📋 Ranges", self._open_range_manager),
                             ("✕ Markers", self._clear_markers)]:
            b = QtWidgets.QPushButton(label)
            b.setStyleSheet(N);  b.setFixedWidth(110)
            b.clicked.connect(slot)
            h.addWidget(b)

        h.addSpacing(8)

        # ── Zoom In / Zoom Out ──────────────────────────────────────────
        self._btn_zoom_in  = QtWidgets.QPushButton("🔍 +")
        self._btn_zoom_out = QtWidgets.QPushButton("🔍 −")
        for zb, tt, slot in [
            (self._btn_zoom_in,  "Zoom In  (Ctrl ++)",  self._zoom_in),
            (self._btn_zoom_out, "Zoom Out  (Ctrl +−)", self._zoom_out),
        ]:
            zb.setStyleSheet(ZS)
            zb.setFixedWidth(62)
            zb.setToolTip(tt)
            zb.clicked.connect(slot)
            h.addWidget(zb)

        return bar

    # ═══════════════════════════ KEY EVENTS ══════════════════════════════ #
    def keyPressEvent(self, ev):
        key  = ev.key()
        ctrl = ev.modifiers() & QtCore.Qt.ControlModifier

        is_plus  = key in (QtCore.Qt.Key_Plus, QtCore.Qt.Key_Equal)
        is_minus = key == QtCore.Qt.Key_Minus

        # Ctrl + / Ctrl -  →  zoom
        if ctrl and is_plus:   self._zoom_in();   return
        if ctrl and is_minus:  self._zoom_out();  return

        # + (no Ctrl) inside Timing Marker mode  →  add marker at centre
        if is_plus and self._marker_mode:
            self._add_marker_at_center();  return

        # + (no Ctrl, no special mode)  →  add measurement from panel picker
        if is_plus:
            self._panel._emit_add_measurement();  return

        super().keyPressEvent(ev)

    def eventFilter(self, obj, ev):
        if ev.type() == QtCore.QEvent.KeyPress:
            self.keyPressEvent(ev)
            return True
        return False

    # ═══════════════════════════ ZOOM ════════════════════════════════════ #
    def _zoom_in(self, anchor_ms=None):
        xr  = self.graphWidget.viewRange()[0]
        mid = anchor_ms if anchor_ms is not None else (xr[0] + xr[1]) / 2
        hw  = (xr[1] - xr[0]) / 2 * 0.7       # shrink by 30 %
        hw  = max(hw, 10)                       # min 10 ms window
        # keep the anchor point fixed: shift window so mid stays under cursor
        ratio = (mid - xr[0]) / max(xr[1] - xr[0], 1e-9)
        x0 = mid - ratio * hw * 2
        x1 = x0 + hw * 2
        x0 = max(0, x0);  x1 = min(self.n_samples, x1)
        self.graphWidget.setXRange(x0, x1, padding=0)
        self._panel.set_view_info(x0, x1)
        self._status.showMessage(f"Zoom IN  |  {x0:.0f} – {x1:.0f} ms  (scroll down to zoom out)")

    def _zoom_out(self, anchor_ms=None):
        xr  = self.graphWidget.viewRange()[0]
        mid = anchor_ms if anchor_ms is not None else (xr[0] + xr[1]) / 2
        hw  = (xr[1] - xr[0]) / 2 * 1 / 0.7   # expand by ~43 %
        ratio = (mid - xr[0]) / max(xr[1] - xr[0], 1e-9)
        x0 = mid - ratio * hw * 2
        x1 = x0 + hw * 2
        x0 = max(0, x0);  x1 = min(self.n_samples, x1)
        self.graphWidget.setXRange(x0, x1, padding=0)
        self._panel.set_view_info(x0, x1)
        self._status.showMessage(f"Zoom OUT  |  {x0:.0f} – {x1:.0f} ms  (scroll up to zoom in)")

    def _scene_wheel_event(self, ev):
        """Zoom in/out at the cursor position using the mouse wheel."""
        delta = ev.delta() if hasattr(ev, 'delta') else ev.angleDelta().y()
        vb    = self.graphWidget.getViewBox()
        # Map the cursor scene position to the data (time) coordinate
        scene_pos  = ev.scenePos()
        anchor_ms  = vb.mapSceneToView(scene_pos).x()
        if delta > 0:
            self._zoom_in(anchor_ms=anchor_ms)
        else:
            self._zoom_out(anchor_ms=anchor_ms)
        ev.accept()

    # ══════════════════════════ MEASUREMENT ═══════════════════════════════ #
    def _compute_measurement(self, ch_idx, metric):
        """Tính giá trị đo từ toàn bộ dữ liệu kênh ch_idx."""
        sig    = self.data[ch_idx].astype(float)
        n      = len(sig)
        diff   = np.diff(sig)
        rising = np.where(diff > 0)[0]   # sample index trước cạnh lên

        if metric == "Frequency":
            if len(rising) < 2:
                return "N/A  (< 2 edges)"
            avg_period_ms = np.diff(rising).mean()
            freq_hz = 1000.0 / avg_period_ms
            return f"{freq_hz/1000:.3f} kHz" if freq_hz >= 1000 else f"{freq_hz:.2f} Hz"

        elif metric == "Period":
            if len(rising) < 2:
                return "N/A  (< 2 edges)"
            return f"{np.diff(rising).mean():.2f} ms"

        elif metric == "PW-High":
            hi_ms = int(sig.sum())
            return f"{hi_ms} ms  ({hi_ms/n*100:.1f}%)"

        elif metric == "PW-Low":
            lo_ms = int((1 - sig).sum())
            return f"{lo_ms} ms  ({lo_ms/n*100:.1f}%)"

        elif metric == "Duty Cycle":
            return f"{sig.mean()*100:.2f} %"

        return "?"

    def _on_add_measurement(self, ch_idx, metric):
        value = self._compute_measurement(ch_idx, metric)
        self._measurements.append((ch_idx, metric))
        self._panel.add_measurement_row(f"CH{ch_idx+1}", metric, value)
        self._status.showMessage(
            f"Measurement: CH{ch_idx+1}  {metric} = {value}")

    def _on_del_measurement(self, row):
        if 0 <= row < len(self._measurements):
            self._measurements.pop(row)

    # ──────────────────────── TRIGGER SEARCH ─────────────────────────── #
    def _find_trigger_position(self, ch, edge):
        """Tìm sample index đầu tiên thỏa điều kiện trigger trên kênh ch.
        Trả về giá trị ms (= index vì 1 sample = 1ms), hoặc None nếu không tìm thấy.
        """
        sig  = self.data[ch].astype(int)
        diff = np.diff(sig)            # +1 = cạnh lên, -1 = cạnh xuống

        if edge == "Rising ↑":
            idxs = np.where(diff > 0)[0]
        elif edge == "Falling ↓":
            idxs = np.where(diff < 0)[0]
        elif edge == "Both ↕":
            idxs = np.where(diff != 0)[0]
        elif edge == "High":
            idxs = np.where(sig > 0)[0]
        elif edge == "Low":
            idxs = np.where(sig == 0)[0]
        else:
            idxs = np.array([])

        return float(idxs[0]) if len(idxs) > 0 else None

    # ══════════════════════════ DEMO ══════════════════════════════════════ #
    def _toggle_demo(self):
        if not self._demo_running:
            self._demo_running = True
            self._demo_timer.start()
            self._btn_demo.setText("⏹  Stop Demo")
            self._btn_demo.setStyleSheet(self._BTN_ACTIVE)
            # Nếu đã đặt trigger thì bắt đầu từ vị trí trigger, không thì từ 0
            win   = self.VIEW_MS
            start = getattr(self, '_trigger_pos_ms', 0)
            x0    = max(0, start - 10)   # hiện 10ms trước trigger
            x1    = x0 + win
            self.graphWidget.setXRange(x0, x1, padding=0)
            self._panel.set_view_info(x0, x1)
            if start > 0:
                self._status.showMessage(
                    f"▶ Demo từ trigger @ {start:.0f} ms – trục thời gian đang tiến…")
            else:
                self._status.showMessage("▶ Demo đang chạy – trục thời gian đang tiến…")
        else:
            self._demo_running = False
            self._demo_timer.stop()
            self._btn_demo.setText("▶  Start Demo")
            self._btn_demo.setStyleSheet(self._BTN_NORMAL)
            self._status.showMessage("Demo stopped")

    def _demo_tick(self):
        """Trượt view window sang phải mỗi tick → trục thời gian chạy tiến.
        Data protocol giữ tĩnh (đã tạo sẵn đủ dài), view cuộn qua data.
        Khi đến cuối: nếu Looping bật thì quay về đầu, không thì dừng demo.
        """
        shift = 6   # số ms tiến mỗi tick (~80ms interval → ~75ms/s thực)
        xr    = self.graphWidget.viewRange()[0]
        yr    = self.graphWidget.viewRange()[1]
        win   = xr[1] - xr[0]          # độ rộng cửa sổ hiện tại

        new_x0 = xr[0] + shift
        new_x1 = xr[1] + shift

        if new_x1 >= self.n_samples:
            if self._loop_enabled:
                # Quay về đầu
                new_x0 = 0
                new_x1 = win
            else:
                # Dừng ở cuối, không cuộn thêm
                new_x0 = max(0, self.n_samples - win)
                new_x1 = self.n_samples
                self._demo_running = False
                self._demo_timer.stop()
                self._btn_demo.setText("▶  Start Demo")
                self._btn_demo.setStyleSheet(self._BTN_NORMAL)
                self._status.showMessage(
                    "Demo ended – nhấn ▶ Start Demo để phát lại, "
                    "hoặc bật Looping để lặp tự động")

        self._plot_waveform()
        self.graphWidget.setXRange(new_x0, new_x1, padding=0)
        self.graphWidget.setYRange(yr[0], yr[1], padding=0)
        self._panel.set_view_info(new_x0, new_x1)
        self._redraw_overlays()
        self._status.showMessage(
            f"⏱  Demo  |  {new_x0:.0f} – {new_x1:.0f} ms  "
            f"| Drag to pan  |  Scroll to zoom")

    # ═══════════════════════ DEVICE SETTING SLOTS ═════════════════════════ #
    def _on_ch_toggle(self, ch_idx, visible):
        self._ch_visible[ch_idx] = visible
        self._plot_waveform()
        xr = self.graphWidget.viewRange()[0]
        yr = self.graphWidget.viewRange()[1]
        self.graphWidget.setXRange(xr[0], xr[1], padding=0)
        self.graphWidget.setYRange(yr[0], yr[1], padding=0)
        self._redraw_overlays()
        state = "ON" if visible else "OFF"
        self._status.showMessage(
            f"CH{ch_idx+1} display {state}")

    def _on_looping(self, enabled):
        self._loop_enabled = enabled
        self._status.showMessage(
            f"Looping {'ENABLED' if enabled else 'DISABLED'}")

    def _on_timer_change(self, ms):
        self._status.showMessage(f"Timer set to {ms:.0f} ms")

    def _on_trigger(self, ch, edge):
        """Lưu trigger info và tìm vị trí trigger trong data hiện tại."""
        self._trigger_info = (ch, edge)
        pos = self._find_trigger_position(ch, edge)
        if pos is None:
            self._status.showMessage(
                f"⚠️  Trigger: CH{ch+1} {edge} – Không tìm thấy cạnh phù hợp trong data")
            return

        # Lưu vị trí trigger để dùng khi Start Demo
        self._trigger_pos_ms = pos

        # Vẽ một đường thẳng đứng màu vàng đánh dấu vị trí trigger
        if hasattr(self, '_trigger_line') and self._trigger_line:
            self.graphWidget.removeItem(self._trigger_line)
        self._trigger_line = pg.InfiniteLine(
            pos=pos, angle=90,
            pen=pg.mkPen('#ffaa00', width=2, style=QtCore.Qt.DashLine),
            label=f"T  {pos:.0f}ms",
            labelOpts={'color': '#ffaa00', 'position': 0.85,
                       'anchors': [(0.5, 0), (0.5, 0)]})
        self.graphWidget.addItem(self._trigger_line)

        # Nhảy view đến vị trí trigger
        win = self.VIEW_MS
        x0  = max(0, pos - 10)       # hiện thị 10ms trước trigger
        x1  = x0 + win
        self.graphWidget.setXRange(x0, x1, padding=0)
        self._panel.set_view_info(x0, x1)

        edge_vn = {'Rising ↑': 'cạnh Lên', 'Falling ↓': 'cạnh Xuống',
                   'Both ↕': 'cả 2 cạnh', 'High': 'mức HIGH', 'Low': 'mức LOW'}
        self._status.showMessage(
            f"⚡  Trigger: CH{ch+1} {edge_vn.get(edge, edge)} "
            f"– tìm thấy tại {pos:.0f} ms  "
            f"| Nhấn ► Start Demo để phát từ điểm này")

    # ══════════════════════════ ANALYZER ══════════════════════════════════ #
    def _open_add_analyzer(self):
        dlg = AddAnalyzerDialog(self.n_channels, self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            info = dlg.result_data()
            self._analyzers.append(info)
            self._draw_analyzer_label(info)
            self._status.showMessage(
                f"Analyzer: {info['protocol']} on CH{info['channel']+1} "
                f"@ {info['baud']} baud")

    def _draw_analyzer_label(self, info):
        ch    = info['channel']
        y_pos = ch * 2 + 1.7
        txt   = pg.TextItem(
            text=f"[{info['protocol']} {info['baud']}]",
            color='#ffe080', anchor=(0, 1))
        txt.setPos(2, y_pos)
        self.graphWidget.addItem(txt)
        self._analyzer_items.append(txt)

    # ══════════════════════════ RANGE ══════════════════════════════════════ #
    def _toggle_range_mode(self, checked):
        self._range_mode = checked
        if checked:
            self._btn_range.setStyleSheet(self._BTN_ACTIVE)
            self._marker_mode = False
            self._btn_marker.setChecked(False)
            self._btn_marker.setStyleSheet(self._BTN_NORMAL)
            self._status.showMessage("Range mode ON – drag to mark a time range")
        else:
            self._btn_range.setStyleSheet(self._BTN_NORMAL)
            if self._range_rect:
                self.graphWidget.removeItem(self._range_rect)
                self._range_rect = None
            self._range_start = None
            self._status.showMessage("Range mode OFF")

    def _open_range_manager(self):
        if not self._ranges:
            QtWidgets.QMessageBox.information(
                self, "Ranges", "No ranges yet. Use 📐 Range Mgmt mode.")
            return
        items = [f"{l}: {s:.1f} – {e:.1f} ms  (Δ{e-s:.1f})"
                 for l, s, e in self._ranges]
        QtWidgets.QInputDialog.getItem(
            self, "Range List", "Saved ranges:", items, 0, False)

    def _start_range_drag(self, sx):
        vb = self.graphWidget.getViewBox()
        self._range_start = vb.mapSceneToView(QtCore.QPointF(sx, 0)).x()
        if self._range_rect:
            self.graphWidget.removeItem(self._range_rect)
        self._range_rect = pg.LinearRegionItem(
            values=[self._range_start, self._range_start],
            brush=pg.mkBrush(60, 100, 255, 50),
            pen=pg.mkPen('#3a6eff', width=1.5), movable=False)
        self.graphWidget.addItem(self._range_rect)

    def _update_range_drag(self, sx):
        if not self._range_rect or self._range_start is None: return
        vb = self.graphWidget.getViewBox()
        cur = vb.mapSceneToView(QtCore.QPointF(sx, 0)).x()
        lo, hi = sorted([self._range_start, cur])
        self._range_rect.setRegion([lo, hi])

    def _finish_range_drag(self, sx):
        if not self._range_rect or self._range_start is None: return
        vb = self.graphWidget.getViewBox()
        cur = vb.mapSceneToView(QtCore.QPointF(sx, 0)).x()
        lo, hi = sorted([self._range_start, cur])
        if hi - lo < 1:
            self.graphWidget.removeItem(self._range_rect)
            self._range_rect = None;  self._range_start = None;  return
        label = f"R{len(self._ranges)+1}"
        self._range_rect.setMovable(True)
        self._ranges.append((label, lo, hi))
        self._range_items.append(self._range_rect)
        self._range_rect = None;  self._range_start = None
        self._status.showMessage(
            f"Range {label}: {lo:.1f} – {hi:.1f} ms  (Δ{hi-lo:.1f} ms)")

    # ══════════════════════════ TIMING MARKERS ════════════════════════════ #
    def _toggle_marker_mode(self, checked):
        self._marker_mode = checked
        if checked:
            self._btn_marker.setStyleSheet(self._BTN_ACTIVE)
            self._range_mode = False
            self._btn_range.setChecked(False)
            self._btn_range.setStyleSheet(self._BTN_NORMAL)
            self._status.showMessage(
                "Timing Marker mode ON – click waveform or press + to add marker")
        else:
            self._btn_marker.setStyleSheet(self._BTN_NORMAL)
            self._status.showMessage("Timing Marker mode OFF")

    def _place_marker_at(self, ms):
        if len(self._markers) >= 2:
            self._clear_markers()
        color = '#ffdd44' if len(self._markers) == 0 else '#ff6644'
        line = pg.InfiniteLine(
            pos=ms, angle=90,
            pen=pg.mkPen(color, width=2, style=QtCore.Qt.DashLine),
            label=f"M{len(self._markers)+1}\n{ms:.1f}ms",
            labelOpts={'color': color, 'position': 0.96,
                       'anchors': [(0.5, 0), (0.5, 0)]})
        self.graphWidget.addItem(line)
        self._markers.append((ms, line))
        self._panel.update_marker_panel(self._markers)

        if len(self._markers) == 2:
            dt  = abs(self._markers[1][0] - self._markers[0][0])
            mid = (self._markers[0][0] + self._markers[1][0]) / 2
            yr  = self.graphWidget.viewRange()[1]
            y_top = yr[1] - (yr[1] - yr[0]) * 0.05
            if self._marker_label:
                self.graphWidget.removeItem(self._marker_label)
            self._marker_label = pg.TextItem(
                text=f"Δt = {dt:.2f} ms", color='#fff',
                fill=pg.mkBrush(20, 50, 140, 190), anchor=(0.5, 1))
            self._marker_label.setPos(mid, y_top)
            self.graphWidget.addItem(self._marker_label)
            self._status.showMessage(
                f"M1:{self._markers[0][0]:.1f}ms  M2:{self._markers[1][0]:.1f}ms  "
                f"Δt={dt:.3f}ms")
        else:
            self._status.showMessage(
                f"Marker 1 @ {ms:.1f} ms – click again for Marker 2")

    def _add_marker_at_center(self):
        """Add marker at the center of current view (triggered by + key or button)."""
        xr = self.graphWidget.viewRange()[0]
        ms = (xr[0] + xr[1]) / 2
        self._place_marker_at(ms)

    def _place_marker(self, scene_x):
        """Place marker at click position."""
        vb = self.graphWidget.getViewBox()
        ms = vb.mapSceneToView(QtCore.QPointF(scene_x, 0)).x()
        self._place_marker_at(ms)

    def _clear_markers(self):
        for _, line in self._markers:
            self.graphWidget.removeItem(line)
        self._markers.clear()
        if self._marker_label:
            self.graphWidget.removeItem(self._marker_label)
            self._marker_label = None
        self._panel.update_marker_panel([])
        self._status.showMessage("Markers cleared")

    # ══════════════════════════ MOUSE EVENTS ══════════════════════════════ #
    def _scene_mouse_press(self, ev):
        if ev.button() == QtCore.Qt.LeftButton:
            if self._range_mode:
                self._start_range_drag(ev.scenePos().x())
                pg.GraphicsScene.mousePressEvent(self.graphWidget.scene(), ev)
                return
            if self._marker_mode:
                self._place_marker(ev.scenePos().x())
                pg.GraphicsScene.mousePressEvent(self.graphWidget.scene(), ev)
                return
            self._drag_start_x    = ev.scenePos().x()
            self._drag_start_y    = ev.scenePos().y()
            r = self.graphWidget.viewRange()
            self._view_start_xrng = list(r[0])
            self._view_start_yrng = list(r[1])
        pg.GraphicsScene.mousePressEvent(self.graphWidget.scene(), ev)

    def _scene_mouse_move(self, ev):
        if self._range_mode and self._range_start is not None:
            self._update_range_drag(ev.scenePos().x())
            pg.GraphicsScene.mouseMoveEvent(self.graphWidget.scene(), ev)
            return
        if self._drag_start_x is not None and self._view_start_xrng is not None:
            dx = ev.scenePos().x() - self._drag_start_x
            dy = ev.scenePos().y() - self._drag_start_y
            vb = self.graphWidget.getViewBox()
            sr = vb.sceneBoundingRect()
            w, h = sr.width(), sr.height()
            xw = self._view_start_xrng[1] - self._view_start_xrng[0]
            yw = self._view_start_yrng[1] - self._view_start_yrng[0]

            if w > 0:
                x0 = max(0, self._view_start_xrng[0] - dx * (xw / w))
                x1 = x0 + xw
                if x1 > self.n_samples:
                    x1 = self.n_samples;  x0 = x1 - xw
                self.graphWidget.setXRange(x0, x1, padding=0)
                self._panel.set_view_info(x0, x1)

            if h > 0:
                y0 = self._view_start_yrng[0] + dy * (yw / h)
                y1 = y0 + yw
                yb, yt = -0.5, self._y_total() + 0.5
                if y0 < yb: y0, y1 = yb, yb + yw
                if y1 > yt: y1, y0 = yt, yt - yw
                self.graphWidget.setYRange(y0, y1, padding=0)

        pg.GraphicsScene.mouseMoveEvent(self.graphWidget.scene(), ev)

    def _scene_mouse_release(self, ev):
        if self._range_mode and self._range_start is not None:
            self._finish_range_drag(ev.scenePos().x())
            pg.GraphicsScene.mouseReleaseEvent(self.graphWidget.scene(), ev)
            return
        self._drag_start_x = self._drag_start_y = None
        self._view_start_xrng = self._view_start_yrng = None
        pg.GraphicsScene.mouseReleaseEvent(self.graphWidget.scene(), ev)

    # ══════════════════════════ HELPERS ═══════════════════════════════════ #
    def _y_total(self):
        return self.n_channels * 2

    def _update_y_range(self, ymin=None):
        if ymin is None: ymin = -0.5
        self.graphWidget.setYRange(ymin, ymin + self._y_total() + 0.5, padding=0)

    def _setup_y_axis(self):
        ax = self.graphWidget.getAxis('left')
        ax.setStyle(tickFont=QtGui.QFont("Segoe UI", 8))
        # Hiển thị tên giao thức thay vì chỉ số kênh
        ticks = [(i*2+0.5, self.channel_names[i]) for i in range(self.n_channels)]
        ax.setTicks([ticks])
        ax.setPen(pg.mkPen('#2a3050'));  ax.setTextPen(pg.mkPen('#8899bb'))
        bx = self.graphWidget.getAxis('bottom')
        bx.setPen(pg.mkPen('#2a3050'));  bx.setTextPen(pg.mkPen('#8899bb'))

    # ─────────────────────────────────────────────────────────────────────
    #  Protocol signal generators
    # ─────────────────────────────────────────────────────────────────────
    @staticmethod
    def _gen_uart(n, bits_per_frame=10, bit_w=20):
        """UART: idle HIGH, start-bit LOW, 8 data bits, stop-bit HIGH.
        Truyền ký tự 0xA5 (10100101) lặp lại.
        """
        data_byte = 0b10100101          # 0xA5
        # frame: [start=0, b0..b7, stop=1]
        frame_bits = [0] + [(data_byte >> i) & 1 for i in range(8)] + [1]
        frame = np.repeat(frame_bits, bit_w)  # mỗi bit dài bit_w mẫu
        # idle gaps ngắn giữa các frame
        idle = np.ones(bit_w * 3, dtype=np.uint8)
        packet = np.concatenate([np.array(frame, dtype=np.uint8), idle])
        repeats = n // len(packet) + 2
        sig = np.tile(packet, repeats)[:n]
        return sig

    @staticmethod
    def _gen_spi_clk(n, clk_half=8):
        """SPI clock: xung vuông đều, chu kỳ = 2*clk_half mẫu."""
        half = np.array([0]*clk_half + [1]*clk_half, dtype=np.uint8)
        return np.tile(half, n // (2*clk_half) + 1)[:n]

    @staticmethod
    def _gen_spi_mosi(n, clk_half=8):
        """SPI MOSI: dữ liệu thay đổi ở cạnh xuống của CLK.
        Truyền byte 0b11001010 lặp lại.
        """
        byte_val = 0b11001010
        bits = [(byte_val >> (7-i)) & 1 for i in range(8)]
        # mỗi bit kéo dài 2*clk_half mẫu
        bit_sig = np.repeat(bits, 2*clk_half).astype(np.uint8)
        return np.tile(bit_sig, n // len(bit_sig) + 1)[:n]

    @staticmethod
    def _gen_spi_cs(n, frame_len=200, idle_len=60):
        """SPI CS (Chip Select): active LOW trong frame, HIGH ngoài."""
        frame = np.array([1]*idle_len + [0]*frame_len + [1]*idle_len,
                         dtype=np.uint8)
        return np.tile(frame, n // len(frame) + 1)[:n]

    @staticmethod
    def _gen_i2c_scl(n, bit_w=16, addr_bits=9, data_bits=8):
        """I2C SCL: HIGH khi idle, xung clock trong transaction."""
        sig = np.ones(n, dtype=np.uint8)
        total_bits = addr_bits + data_bits + 3   # addr + data + ACKs
        clk_seq = []
        for _ in range(total_bits):
            clk_seq += [0]*bit_w + [1]*bit_w
        clk_arr = np.array(clk_seq, dtype=np.uint8)
        # lặp lại transaction với khoảng nghỉ
        idle_gap = np.ones(bit_w * 8, dtype=np.uint8)
        packet = np.concatenate([np.ones(bit_w, dtype=np.uint8),   # idle before
                                  clk_arr, idle_gap])
        return np.tile(packet, n // len(packet) + 1)[:n]

    @staticmethod
    def _gen_i2c_sda(n, bit_w=16):
        """I2C SDA: địa chỉ 0x27 (W) + data 0b10110100, START/STOP condition."""
        addr = 0x27  # 7-bit address
        data = 0b10110100
        # Build bits: [START implied by SDA going LOW while SCL HIGH]
        # address bits (7) + R/W=0 + ACK=0 + data bits (8) + ACK=0
        addr_bits  = [(addr >> (6-i)) & 1 for i in range(7)] + [0]  # R/W=Write
        ack_addr   = [0]          # ACK from slave
        data_bits  = [(data >> (7-i)) & 1 for i in range(8)]
        ack_data   = [0]          # ACK
        payload    = addr_bits + ack_addr + data_bits + ack_data
        sda_seq    = np.repeat(payload, bit_w).astype(np.uint8)
        idle_gap   = np.ones(bit_w * 8, dtype=np.uint8)
        # Start condition: SDA dip before clock
        start_cond = np.array([1]*bit_w + [0]*bit_w, dtype=np.uint8)
        packet     = np.concatenate([start_cond, sda_seq, idle_gap])
        return np.tile(packet, n // len(packet) + 1)[:n]

    @staticmethod
    def _gen_pwm(n, period=60, duty=0.33):
        """PWM: duty cycle ~33%."""
        hi = int(period * duty)
        lo = period - hi
        cycle = np.array([1]*hi + [0]*lo, dtype=np.uint8)
        return np.tile(cycle, n // period + 1)[:n]

    @staticmethod
    def _gen_clock(n, half=5):
        """Clock nhanh: tần số cơ sở (chu kỳ = 2*half mẫu)."""
        cycle = np.array([0]*half + [1]*half, dtype=np.uint8)
        return np.tile(cycle, n // (2*half) + 1)[:n]

    def _generate_data(self):
        """Tạo tín hiệu mô phỏng thực tế cho từng kênh theo giao thức."""
        n = self.n_samples
        return [
            self._gen_uart(n),          # CH1  UART-TX
            self._gen_spi_clk(n),       # CH2  SPI CLK
            self._gen_spi_mosi(n),      # CH3  SPI MOSI
            self._gen_spi_cs(n),        # CH4  SPI CS
            self._gen_i2c_scl(n),       # CH5  I2C SCL
            self._gen_i2c_sda(n),       # CH6  I2C SDA
            self._gen_pwm(n),           # CH7  PWM 33%
            self._gen_clock(n),         # CH8  CLK nhanh
        ]

    def _plot_waveform(self):
        self.graphWidget.clear()
        self.graphWidget.setLabel('bottom', 'Time (ms)',
                                  **{'color': '#505878', 'font-size': '11pt'})
        self.graphWidget.setLabel('left', 'Channels',
                                  **{'color': '#505878', 'font-size': '11pt'})
        for i, signal in enumerate(self.data):
            if not self._ch_visible[i]:
                continue
            x = np.arange(len(signal)+1, dtype=float)
            y = signal.astype(float) + i*2
            self.graphWidget.plot(
                x, y, stepMode=True,
                pen=pg.mkPen(color=self.COLORS[i % len(self.COLORS)], width=2))

    def _redraw_overlays(self):
        for it in self._analyzer_items:
            self.graphWidget.addItem(it)
        for _, line in self._markers:
            self.graphWidget.addItem(line)
        if self._marker_label:
            yr = self.graphWidget.viewRange()[1]
            self._marker_label.setY(yr[1] - (yr[1]-yr[0])*0.05)
            self.graphWidget.addItem(self._marker_label)
        for it in self._range_items:
            self.graphWidget.addItem(it)

    # ══════════════════════════ SERIAL / USB CDC ═══════════════════════════ #
    def _scan_ports(self):
        """Quét và điền danh sách cổng COM khả dụng vào combo box."""
        if not _HAS_SERIAL:
            return
        current = self._port_combo.currentText()
        self._port_combo.clear()
        ports = [p.device for p in serial.tools.list_ports.comports()]
        self._port_combo.addItems(ports if ports else ["(no ports)"])
        if current in ports:
            self._port_combo.setCurrentText(current)
        msg = f"Tìm thấy {len(ports)} cổng: {', '.join(ports)}" if ports else "Không tìm thấy cổng COM nào"
        self._status.showMessage(msg)

    def _toggle_connect(self):
        if self._serial_mode:
            self._disconnect_serial()
        else:
            self._connect_serial()

    def _connect_serial(self):
        port = self._port_combo.currentText()
        if not port or port in ("(no ports)", "pyserial n/a"):
            QtWidgets.QMessageBox.warning(
                self, "Không có cổng", "Chọn cổng COM hợp lệ rồi thử lại.")
            return
        self._serial_worker = SerialWorker(port)
        self._serial_worker.data_received.connect(self._on_serial_data)
        self._serial_worker.error_occurred.connect(self._on_serial_error)
        self._serial_worker.start()
        self._serial_mode = True
        self._serial_timer.start()
        # Dừng demo nếu đang chạy
        if self._demo_running:
            self._toggle_demo()
        self._btn_connect.setText("⏹ Disconnect")
        self._btn_connect.setStyleSheet(self._BTN_ACTIVE)
        self._status.showMessage(
            f"Đã kết nối {port}  |  1 byte/sample · bit[0..7] = CH1..CH8")

    def _disconnect_serial(self):
        if self._serial_worker:
            self._serial_worker.stop()
            self._serial_worker = None
        self._serial_mode = False
        self._serial_timer.stop()
        self._btn_connect.setText("🔌 Connect")
        self._btn_connect.setStyleSheet(self._BTN_NORMAL)
        self._status.showMessage("Đã ngắt kết nối serial")

    def _on_serial_data(self, chunk: bytes):
        """Gọi từ SerialWorker thread – thêm bit vào circular buffer."""
        for byte in chunk:
            for ch in range(self.n_channels):
                self._serial_buf[ch].append((byte >> ch) & 1)
        self._serial_new_data = True

    def _on_serial_error(self, msg: str):
        self._disconnect_serial()
        QtWidgets.QMessageBox.critical(self, "Lỗi Serial", msg)

    def _serial_refresh(self):
        """Timer ~60fps: đẩy dữ liệu buffer vào plot."""
        if not self._serial_new_data:
            return
        self._serial_new_data = False
        for i in range(self.n_channels):
            self.data[i] = np.array(self._serial_buf[i], dtype=np.uint8)
        xr = self.graphWidget.viewRange()[0]
        yr = self.graphWidget.viewRange()[1]
        self._plot_waveform()
        self.graphWidget.setXRange(xr[0], xr[1], padding=0)
        self.graphWidget.setYRange(yr[0], yr[1], padding=0)
        self._redraw_overlays()


# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")

    # ── Màn hình lựa chọn mode ────────────────────────────────────────
    dlg = ModeSelectDialog()
    if dlg.exec_() != QtWidgets.QDialog.Accepted:
        sys.exit(0)          # Người dùng đóng dialog → thoát

    mode = dlg.chosen_mode   # "demo" | "live"
    window = LogicAnalyzer(mode=mode)
    window.show()
    # Không tự động kết nối – để người dùng chọn cổng và nhấn Connect

    sys.exit(app.exec_())
