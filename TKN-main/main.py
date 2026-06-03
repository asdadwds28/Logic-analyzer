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
    f.setStyleSheet("color:#2a3050;")
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
        "win_bg"       : "#f0f2f8",
        "toolbar_bg"   : "#ffffff",
        "toolbar_border": "#d0d6e8",
        "plot_bg"      : "#ffffff",
        "panel_bg"     : "#f5f7fc",
        "panel_border" : "#d0d6e8",
        "text"         : "#1a2040",
        "subtext"      : "#6070a0",
        "accent"       : "#1a5cff",
        "grid_alpha"   : 0.18,
        "axis_pen"     : "#c0c8e0",
        "axis_text"    : "#4050a0",
        "swatch"       : "#f0f2f8",
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
        QDialog  { background:#1e2130; color:#e0e6f0; font-family:Segoe UI; }
        QLabel   { color:#a0b0c8; }
        QComboBox, QSpinBox {
            background:#2a3050; color:#e0e6f0; border:1px solid #3a4570;
            border-radius:4px; padding:4px 8px; font-size:13px; }
        QPushButton {
            background:#3a6eff; color:#fff; border:none; border-radius:5px;
            padding:7px 18px; font-size:13px; font-weight:600; }
        QPushButton:hover { background:#5580ff; }
        QPushButton#cancel { background:#2a3050; color:#a0b0c8; }
        QPushButton#cancel:hover { background:#3a4570; }
    """
    def __init__(self, n_channels, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Analyzer")
        self.setMinimumWidth(380)
        self.setStyleSheet(self.PANEL_SS)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setSpacing(10);  lay.setContentsMargins(22, 18, 22, 18)

        t = QtWidgets.QLabel("🔍  Protocol Analyzer")
        t.setStyleSheet("font-size:15px; font-weight:700; color:#e0e6f0;")
        lay.addWidget(t)

        form = QtWidgets.QFormLayout();  form.setSpacing(8)
        self.proto_combo = QtWidgets.QComboBox()
        self.proto_combo.addItems(["UART", "I2C", "SPI", "I2S"])
        self.proto_combo.currentTextChanged.connect(self._on_proto_change)
        form.addRow("Protocol:", self.proto_combo)

        self._ch_rows = {}
        self._param_rows = {}

        # Channel config area
        self._ch_group = QtWidgets.QGroupBox("Channel Mapping")
        self._ch_lay = QtWidgets.QFormLayout(self._ch_group)
        self._ch_lay.setSpacing(6)
        form.addRow(self._ch_group)

        # Parameter config area
        self._param_group = QtWidgets.QGroupBox("Parameters")
        self._param_lay = QtWidgets.QFormLayout(self._param_group)
        self._param_lay.setSpacing(6)
        form.addRow(self._param_group)

        lay.addLayout(form);  lay.addSpacing(6)

        row = QtWidgets.QHBoxLayout()
        ok = QtWidgets.QPushButton("Decode");  ok.clicked.connect(self.accept)
        ca = QtWidgets.QPushButton("Cancel")
        ca.setObjectName("cancel");  ca.clicked.connect(self.reject)
        row.addWidget(ca);  row.addWidget(ok)
        lay.addLayout(row)

        self._n_channels = n_channels
        self._on_proto_change("UART")

    def _on_proto_change(self, proto):
        # Xóa cũ
        while self._ch_lay.rowCount() > 0:
            self._ch_lay.removeRow(0)
        while self._param_lay.rowCount() > 0:
            self._param_lay.removeRow(0)
        self._ch_rows.clear()
        self._param_rows.clear()

        # Channel mapping theo protocol
        ch_defs = {
            'UART': [('TX', 0)],
            'I2C': [('SCL', 0), ('SDA', 1)],
            'SPI': [('CS', 0), ('SCK', 1), ('MOSI', 2)],
            'I2S': [('SCK', 0), ('WS', 1), ('SD', 2)],
        }
        for ch_name, default in ch_defs.get(proto, []):
            combo = QtWidgets.QComboBox()
            for i in range(self._n_channels):
                combo.addItem(f"CH{i+1}")
            combo.setCurrentIndex(default)
            self._ch_lay.addRow(f"{ch_name}:", combo)
            self._ch_rows[ch_name] = combo

        # Parameters theo protocol
        if proto == 'UART':
            self._add_spin("baud_rate", "Baud rate:", 300, 10_000_000, 115200, 9600)
            self._add_spin("data_bits", "Data bits:", 5, 8, 8, 1)
            self._add_combo("parity", "Parity:", ['none', 'odd', 'even'], 'none')
            self._add_combo("stop_bits", "Stop bits:", ['1', '1.5', '2'], '1')
        elif proto == 'SPI':
            self._add_spin("mode", "Mode (0-3):", 0, 3, 0, 1)
            self._add_spin("bits_per_word", "Bits/word:", 4, 32, 8, 1)
            self._add_combo("bit_order", "Bit order:", ['msb', 'lsb'], 'msb')
        elif proto == 'I2S':
            self._add_spin("word_size", "Word size:", 8, 32, 16, 1)
            self._add_combo("format", "Format:", ['i2s', 'left_justified'], 'i2s')

        self.adjustSize()

    def _add_spin(self, key, label, min_v, max_v, default, step):
        spin = QtWidgets.QSpinBox()
        spin.setRange(min_v, max_v)
        spin.setValue(default)
        spin.setSingleStep(step)
        self._param_lay.addRow(label, spin)
        self._param_rows[key] = spin

    def _add_combo(self, key, label, items, default):
        combo = QtWidgets.QComboBox()
        combo.addItems(items)
        if default in items:
            combo.setCurrentIndex(items.index(default))
        self._param_lay.addRow(label, combo)
        self._param_rows[key] = combo

    def result_data(self):
        proto = self.proto_combo.currentText()
        channels = {name: combo.currentIndex()
                    for name, combo in self._ch_rows.items()}
        params = {}
        for key, widget in self._param_rows.items():
            if isinstance(widget, QtWidgets.QSpinBox):
                params[key] = widget.value()
            elif isinstance(widget, QtWidgets.QComboBox):
                val = widget.currentText()
                if key == 'stop_bits':
                    params[key] = float(val)
                else:
                    params[key] = val
        return dict(protocol=proto, channels=channels, params=params)


# ═══════════════════════════════════════════════════════════════════
#  Right-side Settings Panel
# ═══════════════════════════════════════════════════════════════════
PANEL_SS = """
    QWidget#rightPanel {
        background:#12151f;
        border-left:1px solid #2a3050;
    }
    QLabel       { color:#c8d8f0; font-family:Segoe UI; font-size:11px; }
    QCheckBox    { color:#c8d8f0; font-family:Segoe UI; font-size:11px; spacing:6px; }
    QCheckBox::indicator {
        width:14px; height:14px; border-radius:3px;
        border:1px solid #3a4570; background:#1e2130; }
    QCheckBox::indicator:checked { background:#3a6eff; border-color:#3a6eff; }
    QPushButton  {
        background:#1e2130; color:#8899bb; border:1px solid #2a3050;
        border-radius:5px; padding:3px 8px; font-size:11px; font-family:Segoe UI; }
    QPushButton:hover  { background:#2a3050; color:#e0e6f0; border-color:#3a6eff; }
    QPushButton:checked { background:#1a3a8f; color:#fff; border:2px solid #3a6eff; }
    QComboBox, QSpinBox, QDoubleSpinBox {
        background:#1e2130; color:#c8d8f0; border:1px solid #2a3050;
        border-radius:4px; padding:2px 5px; font-size:11px; }
    QScrollArea  { background:transparent; border:none; }
    QListWidget  {
        background:#0f1120; color:#c8d8f0; border:1px solid #2a3050;
        border-radius:4px; font-size:10px; }
    QListWidget::item:selected { background:#2a3050; color:#fff; }
    QLineEdit    {
        background:#1e2130; color:#c8d8f0; border:1px solid #2a3050;
        border-radius:4px; padding:2px 5px; font-size:11px; }
    QGroupBox    {
        color:#607090; font-size:10px; font-weight:600;
        border:1px solid #2a3050; border-radius:5px; margin-top:8px;
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
        self.setMinimumWidth(250)
        self.n_channels = n_channels
        self.colors = colors

        # main scroll
        scroll = QtWidgets.QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)

        content = QtWidgets.QWidget()
        content.setStyleSheet("background:#12151f;")
        self._content_widget = content          # keep ref for theme updates
        self._vlay = QtWidgets.QVBoxLayout(content)
        self._vlay.setContentsMargins(12, 10, 12, 14)
        self._vlay.setSpacing(4)
        scroll.setWidget(content)

        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.addWidget(scroll)

        self.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Expanding)

        self._build_device_setting()
        self._build_measurement()
        self._build_timing_marker()
        self._build_extensions()
        self._build_realtime()
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
        sub_lbl.setStyleSheet("color:#607090; font-size:11px;")
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
            "QTableWidget{background:#0f1120;color:#c8d8f0;"
            "gridline-color:#2a3050;font-size:11px;}"
            "QHeaderView::section{background:#1a1d2e;color:#607090;"
            "padding:3px;border:none;}")
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
            "color:#3a6eff; font-size:10px; padding-top:2px;")
        m_lay.addWidget(self._view_lbl)

        hint = QtWidgets.QLabel("Zoom: Ctrl + +/−  or  scroll wheel")
        hint.setStyleSheet("color:#404860; font-size:10px;")
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
        hint.setStyleSheet("color:#607090; font-size:11px;")
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
            "color:#ffdd44; font-size:13px; font-weight:700; "
            "padding:4px; background:#1a2040; border-radius:4px;")
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
            ("📦 I2S Audio Decoder",  False),
        ]
        for name, enabled in extensions:
            row = QtWidgets.QHBoxLayout()
            lbl = QtWidgets.QLabel(name)
            lbl.setStyleSheet("font-size:11px; color:#607090;")
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

    def _build_realtime(self):
        self._add(_section_title("⑤ REAL-TIME"))
        self._add(_h_line())

        rt_grp = QtWidgets.QGroupBox("Live Auto-Detect")
        rt_lay = QtWidgets.QFormLayout(rt_grp)
        rt_lay.setSpacing(6)

        self._rt_decode_cb = QtWidgets.QCheckBox("Enabled")
        rt_lay.addRow("Auto-detect:", self._rt_decode_cb)

        self._rt_interval_spin = QtWidgets.QSpinBox()
        self._rt_interval_spin.setRange(100, 5000)
        self._rt_interval_spin.setValue(500)
        self._rt_interval_spin.setSingleStep(100)
        self._rt_interval_spin.setSuffix(" ms")
        rt_lay.addRow("Interval:", self._rt_interval_spin)

        hint = QtWidgets.QLabel("Runs on live USB data with throttling to avoid UI freezes.")
        hint.setStyleSheet("color:#607090; font-size:10px;")
        hint.setWordWrap(True)
        rt_lay.addRow("", hint)

        self._add(rt_grp)
        self._add(QtWidgets.QLabel(""))

    # ══════════════════ 6. APPEARANCE ════════════════════════════════
    def _build_appearance(self):
        self._add(_section_title("⑤ APPEARANCE"))
        self._add(_h_line())

        app_grp = QtWidgets.QGroupBox("Interface Theme")
        a_lay = QtWidgets.QVBoxLayout(app_grp)
        a_lay.setSpacing(6)

        hint = QtWidgets.QLabel("Select a colour theme for the whole interface.")
        hint.setStyleSheet("color:#607090; font-size:10px;")
        hint.setWordWrap(True)
        a_lay.addWidget(hint)

        # ── One button per theme ──────────────────────────────────────────
        self._theme_btns = {}
        grid = QtWidgets.QGridLayout()
        grid.setSpacing(5)
        for idx, (name, t) in enumerate(THEMES.items()):
            btn = QtWidgets.QPushButton(name)
            btn.setCheckable(True)
            btn.setChecked(name == "🌑 Dark")   # default
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

        cards_row = QtWidgets.QHBoxLayout()
        cards_row.setSpacing(20)

        demo_btn = self._make_card(
            "1", "🎬  Demo Mode",
            "Xem tín hiệu giả lập (không cần thiết bị).\nThử nghiệm tính năng, giao diện, đo lường.",
            "#3a6eff")
        demo_btn.clicked.connect(lambda: self._choose("demo"))

        live_btn = self._make_card(
            "2", "🔌  Live Signal Mode",
            "Kết nối thiết bị thật qua USB CDC.\nHiển thị tín hiệu số thời gian thực.",
            "#00c878")
        live_btn.clicked.connect(lambda: self._choose("live"))

        cards_row.addWidget(demo_btn)
        cards_row.addWidget(live_btn)
        root.addLayout(cards_row)
        root.addStretch()

        hint = QtWidgets.QLabel("Nhấn  1  hoặc  2  trên bàn phím để chọn nhanh")
        hint.setStyleSheet("color:#3a4870; font-size:11px; font-family:Segoe UI;")
        hint.setAlignment(QtCore.Qt.AlignCenter)
        root.addWidget(hint)

    def _make_card(self, shortcut, header, body, accent):
        btn = QtWidgets.QPushButton()
        btn.setObjectName("modeBtn")
        btn.setFixedSize(240, 160)
        btn.setCursor(QtCore.Qt.PointingHandCursor)
        lay = QtWidgets.QVBoxLayout(btn)
        lay.setContentsMargins(20, 18, 20, 18)
        lay.setSpacing(10)
        badge = QtWidgets.QLabel(shortcut)
        badge.setStyleSheet(f"color:{accent}; font-size:28px; font-weight:700; font-family:'Segoe UI';")
        lay.addWidget(badge)
        head = QtWidgets.QLabel(header)
        head.setStyleSheet(f"color:{accent}; font-size:14px; font-weight:700; font-family:'Segoe UI';")
        lay.addWidget(head)
        desc = QtWidgets.QLabel(body)
        desc.setStyleSheet("color:#8090b0; font-size:11px; font-family:'Segoe UI';")
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
        self.channel_names = [
            "CH1 UART-TX", "CH2 SPI-CLK", "CH3 SPI-MOSI", "CH4 SPI-CS",
            "CH5 I2C-SCL", "CH6 I2C-SDA", "CH7 PWM", "CH8 CLK",
        ]
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
        body.setStretch(0, 1)
        body.setStretch(1, 0)

        # ── Status bar ────────────────────────────────────────────────────
        self._status = QtWidgets.QStatusBar()
        self._status.setStyleSheet(
            "QStatusBar{ background:#1a1d2e; color:#607090; font-size:12px; }")
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

        # Real-time decode panel controls
        self._panel._rt_decode_cb.toggled.connect(self._on_realtime_toggled)
        self._panel._rt_interval_spin.valueChanged.connect(self._on_realtime_interval)

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

        # ── Real-time auto-detect ─────────────────────────────────────────
        self._realtime_decode_enabled = False
        self._last_decode_time = 0
        self._decode_interval_ms = 500
        self._realtime_analyzer_items = []

        # ── Analyzers ─────────────────────────────────────────────────────
        self._analyzers      = []
        self._analyzer_items = []
        self._last_decode_results = []

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

        # ── Serial state ─────────────────────────────────────────────────────
        self._serial_mode = False
        self._serial_worker = None
        self._serial_buf = [collections.deque(maxlen=self.n_samples * 10) for _ in range(self.n_channels)]
        for ch in range(self.n_channels):
            self._serial_buf[ch].extend(self.data[ch].tolist())
        self._serial_new_data = False
        self._serial_timer = QtCore.QTimer()
        self._serial_timer.setInterval(33)  # 30 FPS instead of 60
        self._serial_timer.timeout.connect(self._serial_refresh)

        # ── Scan COM ports on startup ──────────────────────────────────
        if _HAS_SERIAL:
            self._scan_ports()

        # setGeometry moved to top of __init__

    # ═══════════════════════════════ STYLE ═══════════════════════════════ #
    def _apply_global_style(self):
        """Apply default (Dark) theme on startup."""
        self.apply_theme(list(THEMES.keys())[0])

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
                           font-family:Segoe UI; font-size:11px; }}
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
            QLabel       {{ color:{text}; font-family:Segoe UI; font-size:11px; }}
            QCheckBox    {{ color:{text}; font-family:Segoe UI;
                           font-size:11px; spacing:6px; }}
            QCheckBox::indicator {{
                width:14px; height:14px; border-radius:3px;
                border:1px solid {pb_brd}; background:{pb_bg}; }}
            QCheckBox::indicator:checked {{
                background:{accent}; border-color:{accent}; }}
            QPushButton  {{
                background:{pb_bg}; color:{subtext}; border:1px solid {pb_brd};
                border-radius:5px; padding:3px 8px;
                font-size:11px; font-family:Segoe UI; }}
            QPushButton:hover  {{
                background:{tb_bg}; color:{text}; border-color:{accent}; }}
            QPushButton:checked {{
                background:{accent}; color:#fff; border:2px solid {accent}; }}
            QComboBox, QSpinBox, QDoubleSpinBox {{
                background:{pb_bg}; color:{text}; border:1px solid {pb_brd};
                border-radius:4px; padding:2px 5px; font-size:11px; }}
            QScrollArea  {{ background:transparent; border:none; }}
            QListWidget  {{
                background:{win_bg}; color:{text}; border:1px solid {pb_brd};
                border-radius:4px; font-size:10px; }}
            QListWidget::item:selected {{ background:{tb_bg}; color:{text}; }}
            QLineEdit    {{
                background:{pb_bg}; color:{text}; border:1px solid {pb_brd};
                border-radius:4px; padding:2px 5px; font-size:11px; }}
            QGroupBox    {{
                color:{subtext}; font-size:10px; font-weight:600;
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
        bar.setStyleSheet("background:#161926; border-bottom:1px solid #2a3050;")
        h = QtWidgets.QHBoxLayout(bar)
        h.setContentsMargins(14, 4, 14, 4);  h.setSpacing(8)

        logo = QtWidgets.QLabel("⚡ Logic Analyzer")
        logo.setStyleSheet("font-size:16px; font-weight:700; color:#3a6eff;")
        h.addWidget(logo);  h.addSpacing(16)

        def vsep():
            s = QtWidgets.QFrame()
            s.setFrameShape(QtWidgets.QFrame.VLine)
            s.setStyleSheet("color:#2a3050;")
            return s

        N = """QPushButton {
            background:#1e2336; color:#8899bb; border:1px solid #2a3050;
            border-radius:6px; padding:5px 14px; font-size:13px; font-weight:600; min-width:120px;}
            QPushButton:hover {background:#2a3050;color:#c8d8f0;border-color:#3a6eff;}"""
        A = """QPushButton {
            background:#1a3a8f; color:#fff; border:2px solid #3a6eff;
            border-radius:6px; padding:5px 14px; font-size:13px; font-weight:700; min-width:120px;}"""
        self._BTN_NORMAL = N;  self._BTN_ACTIVE = A

        # ── Mode badge (Live mode only) ─────────────────────────
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
        # Live mode: ẩn nút Start Demo
        if self._mode == "live":
            self._btn_demo.hide()

        self._btn_analyzer = QtWidgets.QPushButton("🔍  Auto-Detect & Decode")
        self._btn_analyzer.setStyleSheet(N)
        self._btn_analyzer.clicked.connect(self._run_autodetect)

        self._btn_manual = QtWidgets.QPushButton("⚙  Manual Decode")
        self._btn_manual.setStyleSheet(N)
        self._btn_manual.clicked.connect(self._run_manual_decode)

        self._btn_range = QtWidgets.QPushButton("📐  Range Mgmt")
        self._btn_range.setStyleSheet(N);  self._btn_range.setCheckable(True)
        self._btn_range.clicked.connect(self._toggle_range_mode)

        self._btn_marker = QtWidgets.QPushButton("⏱  Timing Marker")
        self._btn_marker.setStyleSheet(N);  self._btn_marker.setCheckable(True)
        self._btn_marker.clicked.connect(self._toggle_marker_mode)

        self._btn_export = QtWidgets.QPushButton("💾  Export")
        self._btn_export.setStyleSheet(N)
        self._btn_export.clicked.connect(self._export_decoded_data)

        for btn in (self._btn_demo, self._btn_analyzer, self._btn_manual,
                    self._btn_range, self._btn_marker, self._btn_export):
            h.addWidget(btn);  h.addWidget(vsep())

        # ── Serial Port (USB CDC) ───────────────────────────────────────
        SCS = ("QComboBox{background:#1e2336;color:#c8d8f0;"
               "border:1px solid #2a3050;border-radius:5px;"
               "padding:3px 6px;font-size:12px;}"
               "QComboBox::drop-down{border:none;}"
               "QComboBox QAbstractItemView{background:#1e2336;"
               "color:#c8d8f0;selection-background-color:#2a3050;}")
        BSS = ("QPushButton{background:#1e2336;color:#8899bb;"
               "border:1px solid #2a3050;border-radius:5px;"
               "padding:4px 8px;font-size:13px;font-weight:600;}"
               "QPushButton:hover{background:#2a3050;color:#c8d8f0;"
               "border-color:#3a6eff;}")

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

        # Live mode: nút Connect nổi bật với màu xanh lá
        _LIVE_CONNECT_SS = (
            "QPushButton{background:#00c878;color:#000;border:none;"
            "border-radius:6px;padding:5px 14px;font-size:13px;font-weight:700;"
            "min-width:120px;}"
            "QPushButton:hover{background:#00e890;}"
        )
        self._btn_connect = QtWidgets.QPushButton("🔌 Connect")
        self._btn_connect.setFixedWidth(118)
        self._btn_connect.setStyleSheet(_LIVE_CONNECT_SS if self._mode == "live" else N)
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
            background:#1e2336;color:#8899bb;border:1px solid #2a3050;
            border-radius:5px;padding:4px 10px;font-size:14px;font-weight:700;}
            QPushButton:hover{background:#2a3050;color:#c8d8f0;border-color:#3a6eff;}"""

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
        self._trigger_info = (ch, edge)
        # Tìm vị trí trigger trên data hiện tại
        pos = self._find_trigger_position(ch, edge)
        if pos is not None:
            self._trigger_pos_ms = pos
        else:
            self._trigger_pos_ms = 0
        edge_vn = {'Rising ↑': 'cạnh lên', 'Falling ↓': 'cạnh xuống',
                   'Both ↕': 'cả 2 cạnh', 'High': 'mức HIGH', 'Low': 'mức LOW'}
        if pos is not None:
            self._status.showMessage(
                f"⚡  Trigger: CH{ch+1} {edge_vn.get(edge, edge)} "
                f"– tìm thấy tại {pos:.0f} ms  "
                f"| Nhấn ► Start Demo để phát từ điểm này")
        else:
            self._status.showMessage(
                f"Trigger set: CH{ch+1}  {edge} (không tìm thấy vị trí trên data hiện tại)")

    # ──────────────────────── TRIGGER SEARCH ─────────────────────── #
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

    def _find_trigger_sample(self, ch: int, edge: str):
        """Tìm sample đầu tiên khớp điều kiện trigger trên kênh hiện tại."""
        if not (0 <= ch < self.n_channels):
            return None
        sig = self.data[ch]
        if len(sig) < 2:
            return None

        if edge == "Rising ↑":
            hits = np.where((sig[:-1] == 0) & (sig[1:] == 1))[0]
        elif edge == "Falling ↓":
            hits = np.where((sig[:-1] == 1) & (sig[1:] == 0))[0]
        elif edge == "Both ↕":
            hits = np.where(sig[:-1] != sig[1:])[0]
        elif edge == "High":
            hits = np.where(sig == 1)[0]
        elif edge == "Low":
            hits = np.where(sig == 0)[0]
        else:
            return None

        if len(hits) == 0:
            return None
        return int(hits[0] + (1 if "↑" in edge or "↓" in edge or "↕" in edge else 0))

    # ══════════════════════════ ANALYZER ══════════════════════════════════ #
    def _run_autodetect(self):
        self._status.showMessage("Đang phân tích tín hiệu bằng Custom Decoder...")
        results = self._decode_current_buffer()
        self._last_decode_results = results
        self._clear_analyzer_items(self._analyzer_items)

        if results:
            self._status.showMessage(f"Đã tìm thấy {len(results)} giao thức. Đang vẽ annotation...")
            QtWidgets.QApplication.processEvents()

            for result in results:
                self._draw_decode_result(result, self._analyzer_items)

            self._status.showMessage(f"Auto-Detect & Decode hoàn tất: {', '.join([r.protocol for r in results])}")
        else:
            self._status.showMessage("Không tìm thấy tín hiệu giao thức nào hợp lệ.")

    def _decode_current_buffer(self):
        from analyzer import AnalyzerService
        service = AnalyzerService(sample_rate=1_000_000, num_channels=self.n_channels)
        return service.autodetect_and_decode(self._decode_current_buffer_raw())

    def _decode_current_buffer_raw(self):
        byte_data = np.zeros(self.n_samples, dtype=np.uint8)
        for i in range(self.n_channels):
            channel_data = self.data[i][:self.n_samples].astype(np.uint8)
            if len(channel_data) < self.n_samples:
                padded = np.zeros(self.n_samples, dtype=np.uint8)
                padded[:len(channel_data)] = channel_data
                channel_data = padded
            byte_data |= (channel_data << i)
        return byte_data.tobytes()

    def _clear_analyzer_items(self, items):
        for item in items:
            self.graphWidget.removeItem(item)
        items.clear()

    def _run_autodetect_realtime(self):
        try:
            results = self._decode_current_buffer()
        except Exception as e:
            self._status.showMessage(f"Lỗi Real-time Auto-Detect: {e}")
            return

        self._clear_analyzer_items(self._realtime_analyzer_items)
        for result in results:
            self._draw_decode_result(result, self._realtime_analyzer_items)

        if results:
            protocols = ', '.join(result.protocol for result in results)
            self._status.showMessage(f"Real-time detect: {protocols}")

    def _on_realtime_toggled(self, enabled):
        self._realtime_decode_enabled = enabled
        if not enabled:
            self._clear_analyzer_items(self._realtime_analyzer_items)
        self._status.showMessage(
            f"Real-time auto-detect {'ENABLED' if enabled else 'DISABLED'}")

    def _on_realtime_interval(self, value):
        self._decode_interval_ms = value
        self._status.showMessage(f"Real-time decode interval: {value} ms")

    def _draw_decode_result(self, result, item_store=None):
        """Vẽ DecodeResult lên waveform với tooltip support."""
        from analyzer import AnnotationAdapter

        if item_store is None:
            item_store = self._analyzer_items

        adapter = AnnotationAdapter()
        gui_items = adapter.to_gui_format(result)

        # Tìm channel chính từ annotations
        channel = 0
        for item in gui_items:
            if item.get('channel') is not None:
                channel = item['channel']
                break

        y_base = channel * 2 + 1.2
        row_offsets = {
            'control': 0.35,
            'data': 0.15,
            'error': -0.05,
        }

        for item in gui_items:
            start = item['start']
            row_offset = row_offsets.get(item.get('row', 'data'), 0.15)
            color = item.get('color', '#3a6eff')
            tooltip = item.get('tooltip', '')

            txt = pg.TextItem(text=f" {item['text']} ", color='#ffffff', anchor=(0, 0.5))
            txt.fill = pg.mkBrush(color)
            txt.setPos(start, y_base + row_offset)

            # Tooltip support
            if tooltip:
                txt.setToolTip(tooltip)

            self.graphWidget.addItem(txt)
            item_store.append(txt)

        # Protocol label
        label_text = f"[{result.protocol}]"
        if result.warnings:
            label_text += f" ⚠ {len(result.warnings)}"
        lbl = pg.TextItem(text=label_text, color='#ffe080', anchor=(0, 1))
        lbl.setPos(2, channel * 2 + 1.8)

        # Tooltip cho protocol label
        if result.warnings:
            warning_text = "\n".join(result.warnings[:3])
            lbl.setToolTip(f"{result.protocol}\n\nWarnings:\n{warning_text}")
        else:
            stats_text = "\n".join([f"{k}: {v}" for k, v in result.stats.items()])
            lbl.setToolTip(f"{result.protocol}\n\nStats:\n{stats_text}")

        self.graphWidget.addItem(lbl)
        item_store.append(lbl)

    def _run_manual_decode(self):
        """Mở dialog để cấu hình decoder thủ công."""
        dialog = AddAnalyzerDialog(self.n_channels, self)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return

        cfg = dialog.result_data()
        proto = cfg['protocol']
        channels = cfg['channels']
        params = cfg.get('params', {})

        self._status.showMessage(f"Đang giải mã {proto} với cấu hình thủ công...")

        # Clear old
        self._clear_analyzer_items(self._analyzer_items)

        try:
            from analyzer import AnalyzerService
            service = AnalyzerService(sample_rate=1_000_000, num_channels=self.n_channels)
            result = service.decode_with_config(self._decode_current_buffer_raw(), proto, channels, params)

            if result.annotations:
                self._draw_decode_result(result)
                self._status.showMessage(f"Decode {proto} xong: {len(result.annotations)} annotations")
            else:
                self._status.showMessage(f"Decode {proto} xong nhưng không tìm thấy annotation")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._status.showMessage(f"Lỗi decode {proto}: {e}")

    def _draw_annotations(self, channel, proto_name, annotations):
        y_pos = channel * 2 + 1.2
        for ann in annotations:
            start = ann['start']
            text = ann['text']
            txt = pg.TextItem(text=f" {text} ", color='#ffffff', anchor=(0, 0.5))
            txt.fill = pg.mkBrush('#3a6eff')
            txt.setPos(start, y_pos)
            self.graphWidget.addItem(txt)
            item_store.append(txt)

        lbl = pg.TextItem(text=f"[{proto_name}]", color='#ffe080', anchor=(0, 1))
        lbl.setPos(2, channel * 2 + 1.8)
        self.graphWidget.addItem(lbl)
        self._analyzer_items.append(lbl)

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
        ax.setStyle(tickFont=QtGui.QFont("Segoe UI", 9))
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
        """UART: idle HIGH, start-bit LOW, 8 data bits, stop-bit HIGH."""
        data_byte = 0b10100101          # 0xA5
        frame_bits = [0] + [(data_byte >> i) & 1 for i in range(8)] + [1]
        frame = np.repeat(frame_bits, bit_w)
        idle = np.ones(bit_w * 3, dtype=np.uint8)
        packet = np.concatenate([np.array(frame, dtype=np.uint8), idle])
        return np.tile(packet, n // len(packet) + 2)[:n]

    @staticmethod
    def _gen_spi_clk(n, clk_half=8):
        """SPI clock: xung vuông đều."""
        half = np.array([0]*clk_half + [1]*clk_half, dtype=np.uint8)
        return np.tile(half, n // (2*clk_half) + 1)[:n]

    @staticmethod
    def _gen_spi_mosi(n, clk_half=8):
        """SPI MOSI: byte 0b11001010 lặp lại."""
        byte_val = 0b11001010
        bits = [(byte_val >> (7-i)) & 1 for i in range(8)]
        bit_sig = np.repeat(bits, 2*clk_half).astype(np.uint8)
        return np.tile(bit_sig, n // len(bit_sig) + 1)[:n]

    @staticmethod
    def _gen_spi_cs(n, frame_len=200, idle_len=60):
        """SPI CS: active LOW trong frame, HIGH ngoài."""
        frame = np.array([1]*idle_len + [0]*frame_len + [1]*idle_len, dtype=np.uint8)
        return np.tile(frame, n // len(frame) + 1)[:n]

    @staticmethod
    def _gen_i2c_scl(n, bit_w=16, addr_bits=9, data_bits=8):
        """I2C SCL: HIGH khi idle, xung clock trong transaction."""
        total_bits = addr_bits + data_bits + 3
        clk_seq = []
        for _ in range(total_bits):
            clk_seq += [0]*bit_w + [1]*bit_w
        clk_arr = np.array(clk_seq, dtype=np.uint8)
        idle_gap = np.ones(bit_w * 8, dtype=np.uint8)
        packet = np.concatenate([np.ones(bit_w, dtype=np.uint8), clk_arr, idle_gap])
        return np.tile(packet, n // len(packet) + 1)[:n]

    @staticmethod
    def _gen_i2c_sda(n, bit_w=16):
        """I2C SDA: địa chỉ 0x27 (W) + data 0b10110100."""
        addr = 0x27
        data = 0b10110100
        addr_bits  = [(addr >> (6-i)) & 1 for i in range(7)] + [0]
        ack_addr   = [0]
        data_bits  = [(data >> (7-i)) & 1 for i in range(8)]
        ack_data   = [0]
        payload    = addr_bits + ack_addr + data_bits + ack_data
        sda_seq    = np.repeat(payload, bit_w).astype(np.uint8)
        idle_gap   = np.ones(bit_w * 8, dtype=np.uint8)
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
        """Clock nhanh: tần số cơ sở."""
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
        arr = np.frombuffer(chunk, dtype=np.uint8)
        for ch in range(self.n_channels):
            self._serial_buf[ch].extend(((arr >> ch) & 1).tolist())
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

        # Check trigger condition if set
        if self._trigger_info and self._serial_mode:
            ch, edge = self._trigger_info
            trigger_sample = self._find_trigger_sample(ch, edge)
            if trigger_sample is not None:
                # Trigger hit - center view on trigger point
                xr = self.graphWidget.viewRange()[0]
                window_width = xr[1] - xr[0]
                new_x0 = max(0, trigger_sample - window_width / 2)
                new_x1 = min(self.n_samples, new_x0 + window_width)
                self.graphWidget.setXRange(new_x0, new_x1, padding=0)
                self._status.showMessage(f"Trigger @ sample {trigger_sample}")

        xr = self.graphWidget.viewRange()[0]
        yr = self.graphWidget.viewRange()[1]
        self._plot_waveform()
        if self._realtime_decode_enabled:
            now_ms = QtCore.QDateTime.currentMSecsSinceEpoch()
            if now_ms - self._last_decode_time >= self._decode_interval_ms:
                self._last_decode_time = now_ms
                self._run_autodetect_realtime()
        self.graphWidget.setXRange(xr[0], xr[1], padding=0)
        self.graphWidget.setYRange(yr[0], yr[1], padding=0)
        self._redraw_overlays()

    # ══════════════════════════ EXPORT ════════════════════════════════════ #
    def _export_decoded_data(self):
        """Export decoded data to CSV or JSON via file dialog."""
        if not self._last_decode_results:
            # Run decode if not yet done
            self._last_decode_results = self._decode_current_buffer()

        if not self._last_decode_results:
            QtWidgets.QMessageBox.information(
                self, "Export", "Chưa có dữ liệu decode. Chạy Auto-Detect trước.")
            return

        # Ask format
        items = ["CSV (.csv)", "JSON (.json)"]
        fmt, ok = QtWidgets.QInputDialog.getItem(
            self, "Export Format", "Chọn định dạng:", items, 0, False)
        if not ok:
            return

        ext = "csv" if "CSV" in fmt else "json"
        protocols = "-".join(r.protocol for r in self._last_decode_results)
        default_name = f"decode_{protocols}.{ext}"

        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self, "Export Decoded Data",
            default_name,
            f"*.{ext} (*.{ext})")
        if not path:
            return

        try:
            from analyzer.exporter import ProtocolExporter
            sample_rate = int(1_000_000)  # default
            exporter = ProtocolExporter(sample_rate=sample_rate)
            exporter.export(self._last_decode_results, path, format=ext)
            self._status.showMessage(f"Đã export: {path}")
            QtWidgets.QMessageBox.information(
                self, "Export Thành Công",
                f"Đã lưu vào:\n{path}\n\n"
                f"Protocols: {protocols}\n"
                f"Annotations: {sum(len(r.annotations) for r in self._last_decode_results)}")
        except Exception as e:
            import traceback
            traceback.print_exc()
            self._status.showMessage(f"Lỗi export: {e}")
            QtWidgets.QMessageBox.critical(self, "Export Lỗi", str(e))


# ═══════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    # Kích hoạt tính năng tự động phóng to (High-DPI Scaling) cho màn hình nét
    if hasattr(QtCore.Qt, 'AA_EnableHighDpiScaling'):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_EnableHighDpiScaling, True)
    if hasattr(QtCore.Qt, 'AA_UseHighDpiPixmaps'):
        QtWidgets.QApplication.setAttribute(QtCore.Qt.AA_UseHighDpiPixmaps, True)

    app = QtWidgets.QApplication(sys.argv)
    app.setStyle("Fusion")

    # ── Màn hình lựa chọn mode ────────────────────────────────────────
    dlg = ModeSelectDialog()
    if dlg.exec_() != QtWidgets.QDialog.Accepted:
        sys.exit(0)          # Người dùng đóng dialog → thoát

    mode = dlg.chosen_mode   # "demo" | "live"
    window = LogicAnalyzer(mode=mode)
    window.show()
    sys.exit(app.exec_())