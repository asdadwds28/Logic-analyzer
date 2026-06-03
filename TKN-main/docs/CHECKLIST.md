# Checklist Hoàn Thiện Dự Án Logic Analyzer

## Mục lục

1. [Trạng thái hiện tại](#trạng-thái-hiện-tại)
2. [Checklist theo module](#checklist-theo-module)
3. [Testing với phần cứng thật](#testing-với-phần-cứng-thật)
4. [Tối ưu hóa và polish](#tối-ưu-hóa-và-polish)
5. [Packaging và deployment](#packaging-và-deployment)
6. [Tài liệu](#tài-liệu)

---

## Trạng thái hiện tại

### ✅ Đã hoàn thành

- [x] GUI chính với PyQt5 + pyqtgraph
- [x] Hiển thị 8 kênh digital waveform
- [x] Zoom/pan, timing markers, range management
- [x] Kết nối USB CDC serial (STM32)
- [x] SerialWorker QThread non-blocking
- [x] 4 decoder: UART, I2C, SPI, I2S
- [x] Auto-detect heuristic (autodetect_fast.py)
- [x] Manual decode với channel mapping
- [x] Real-time decode integration
- [x] USB throughput optimization (NumPy vectorization)
- [x] Unit tests (15 tests pass)
- [x] CSV smoke tests (UART + I2C detection)
- [x] README đầy đủ
- [x] Tài liệu thuật toán decoder
- [x] Theme system (6 themes)
- [x] Settings panel với 5 tabs

### ⚠️ Cần kiểm tra

- [ ] Real-time decode stability với dữ liệu liên tục
- [ ] Memory leak khi chạy lâu dài
- [ ] Edge case handling trong decoder
- [ ] GUI responsiveness với sample rate cao (>2 MHz)

### ❌ Chưa làm

- [ ] Testing với phần cứng thật (STM32 + sensors)
- [ ] Export decoded data (CSV, JSON)
- [ ] Trigger system (start/stop capture on condition)
- [ ] Protocol-specific filtering
- [ ] Packaging (executable, installer)

---

## Checklist theo module

### 1. GUI (main.py)

#### Core functionality
- [x] Waveform display với 8 kênh
- [x] Zoom/pan với mouse wheel + drag
- [x] Timing markers (2 markers, Δt measurement)
- [x] Range management (save/load time ranges)
- [x] Measurement panel (Frequency, Period, PW, Duty Cycle)
- [x] Theme system (6 themes)
- [ ] **TODO**: Export waveform as image (PNG/SVG)
- [ ] **TODO**: Print waveform
- [ ] **TODO**: Undo/redo for annotations

#### Serial connection
- [x] Port scanning
- [x] Connect/disconnect
- [x] Baud rate 2 MHz
- [x] Non-blocking read (QThread)
- [x] Buffer management (10 seconds @ 1 MHz)
- [ ] **TODO**: Auto-reconnect on disconnect
- [ ] **TODO**: Serial port settings UI (baud, format)
- [ ] **TODO**: Flow control (RTS/CTS)

#### Real-time decode
- [x] Enable/disable checkbox
- [x] Interval throttle (100–5000 ms)
- [x] Auto-detect on serial stream
- [x] Annotation rendering
- [ ] **TODO**: Protocol filter (show only UART, hide I2C, etc.)
- [ ] **TODO**: Decode statistics overlay (bytes/sec, errors)
- [ ] **TODO**: Pause/resume decode without stopping serial

#### Performance
- [x] NumPy vectorization in `_on_serial_data()`
- [x] Buffer expansion (10x)
- [x] Refresh rate reduction (33 ms)
- [ ] **TODO**: Profile with `cProfile` under load
- [ ] **TODO**: Optimize `_plot_waveform()` (reuse curve items)
- [ ] **TODO**: Lazy rendering (only visible region)

---

### 2. Decoder (protocols/)

#### UART (uart.py)
- [x] Start bit detection (falling edge)
- [x] Start bit confirmation (sample @ 0.5 tpb)
- [x] Data bits (5–8, LSB-first)
- [x] Parity (none/odd/even)
- [x] Stop bits (1/1.5/2)
- [x] Framing error detection
- [x] Inverted signal support
- [ ] **TODO**: Break condition detection
- [ ] **TODO**: Multi-byte frame grouping (packet detection)
- [ ] **TODO**: ASCII/hex display toggle

#### I2C (i2c.py)
- [x] START condition (SDA 1→0 @ SCL=1)
- [x] STOP condition (SDA 0→1 @ SCL=1)
- [x] Repeated START
- [x] Address parsing (7-bit + R/W)
- [x] ACK/NACK detection
- [x] Missing STOP warning
- [ ] **TODO**: 10-bit address support
- [ ] **TODO**: Clock stretching visualization
- [ ] **TODO**: Multi-master arbitration detection
- [ ] **TODO**: SMBus PEC (Packet Error Code)

#### SPI (spi.py)
- [x] Mode 0–3 (CPOL/CPHA)
- [x] CS active-low/high
- [x] MOSI/MISO full-duplex
- [x] MSB/LSB bit order
- [x] Word size (8/16/24/32)
- [x] Incomplete word warning
- [ ] **TODO**: Multi-slave CS detection
- [ ] **TODO**: Quad SPI (4-bit data)
- [ ] **TODO**: Frame protocol overlay (e.g., SD card commands)

#### I2S (i2s.py)
- [x] WS transition (L/R channel)
- [x] SCK rising edge sampling
- [x] Word size (16/24/32)
- [x] Standard I2S format
- [x] Left-justified format
- [ ] **TODO**: Right-justified format
- [ ] **TODO**: PCM short/long frame
- [ ] **TODO**: TDM (Time Division Multiplexing)
- [ ] **TODO**: Audio waveform preview (plot sample values)

---

### 3. Auto-detect (autodetect_fast.py)

#### Current implementation
- [x] `profile_channels()` (toggle count, idle state, pulse stats)
- [x] `detect_uart()` (fundamental pulse → baud rate)
- [x] `detect_i2c()` (START/STOP count, SCL/SDA correlation)
- [x] `detect_spi()` (CS/SCK/MOSI/MISO pattern)
- [x] `detect_i2s()` (SCK:WS ratio, word size estimation)
- [x] Confidence scoring

#### Improvements needed
- [ ] **TODO**: Multi-protocol detection (e.g., UART + I2C on same capture)
- [ ] **TODO**: Adaptive threshold (handle noisy signals)
- [ ] **TODO**: Baud rate refinement (try ±5% around detected rate)
- [ ] **TODO**: I2C address extraction during detection (show likely slaves)
- [ ] **TODO**: SPI mode auto-detect (try all 4 modes, pick best)

---

### 4. Testing

#### Unit tests (tests/test_decoders.py)
- [x] 15 tests pass
- [x] UART 8N1 basic
- [x] UART parity
- [x] I2C START/STOP
- [x] SPI mode 0
- [x] I2S L/R channel
- [ ] **TODO**: Add edge case tests:
  - [ ] UART framing error
  - [ ] I2C NACK
  - [ ] SPI incomplete word
  - [ ] I2S mid-word WS change
- [ ] **TODO**: Add parametrized tests (pytest.mark.parametrize)
- [ ] **TODO**: Add property-based tests (hypothesis)

#### CSV smoke tests
- [x] `test_csv_autodetect.py` (UART 115200)
- [x] `test_all_autodetect.py` (I2C Saleae CSV)
- [ ] **TODO**: Add SPI CSV test
- [ ] **TODO**: Add I2S CSV test
- [ ] **TODO**: Add multi-protocol CSV test

#### Integration tests
- [ ] **TODO**: Test GUI launch (headless with Xvfb)
- [ ] **TODO**: Test serial connection (mock serial port)
- [ ] **TODO**: Test real-time decode (inject data, verify annotations)
- [ ] **TODO**: Test theme switching
- [ ] **TODO**: Test marker/range management

#### Hardware tests (với STM32 thật)
- [ ] **TODO**: UART loopback (TX → RX)
- [ ] **TODO**: I2C với sensor (e.g., BME280, MPU6050)
- [ ] **TODO**: SPI với flash memory (e.g., W25Q32)
- [ ] **TODO**: I2S với audio codec (e.g., PCM5102)
- [ ] **TODO**: Stress test: 8 kênh @ 2 MHz, 10 phút liên tục
- [ ] **TODO**: Verify timing accuracy (compare with oscilloscope)

---

### 5. Tối ưu hóa và polish

#### Performance
- [ ] **TODO**: Profile với `cProfile` + `snakeviz`
- [ ] **TODO**: Optimize `_plot_waveform()` (reuse PlotCurveItem)
- [ ] **TODO**: Lazy annotation rendering (only visible region)
- [ ] **TODO**: Reduce memory footprint (circular buffer, not deque)
- [ ] **TODO**: Multi-threaded decode (decode each protocol in parallel)

#### UX improvements
- [ ] **TODO**: Keyboard shortcuts (Ctrl+O open, Ctrl+S save, etc.)
- [ ] **TODO**: Drag-and-drop CSV file to load
- [ ] **TODO**: Context menu on waveform (right-click → decode, export, etc.)
- [ ] **TODO**: Status bar (show sample count, decode status, errors)
- [ ] **TODO**: Progress bar for long operations (decode, export)
- [ ] **TODO**: Tooltips on annotations (hover → show full frame data)

#### Error handling
- [ ] **TODO**: Graceful serial disconnect (show warning, don't crash)
- [ ] **TODO**: Handle corrupted CSV files
- [ ] **TODO**: Validate user input (baud rate, channel mapping)
- [ ] **TODO**: Log errors to file (not just console)

---

### 6. Features mới

#### Export
- [ ] **TODO**: Export decoded data as CSV (timestamp, protocol, data, annotation)
- [ ] **TODO**: Export decoded data as JSON
- [ ] **TODO**: Export waveform as image (PNG/SVG)
- [ ] **TODO**: Export raw bytes (binary file)

#### Trigger system
- [ ] **TODO**: Start capture on condition (e.g., UART byte = 0x55)
- [ ] **TODO**: Stop capture on condition
- [ ] **TODO**: Trigger on protocol event (e.g., I2C START)
- [ ] **TODO**: Pre-trigger buffer (capture N samples before trigger)

#### Protocol-specific features
- [ ] **TODO**: UART: ASCII terminal view (show decoded text in real-time)
- [ ] **TODO**: I2C: Device database (recognize common slave addresses)
- [ ] **TODO**: SPI: Command decoder (e.g., SD card, flash memory)
- [ ] **TODO**: I2S: Audio player (play decoded samples)

#### Advanced analysis
- [ ] **TODO**: Protocol statistics (bytes/sec, error rate, etc.)
- [ ] **TODO**: Timing histogram (visualize jitter)
- [ ] **TODO**: Eye diagram (for signal quality analysis)
- [ ] **TODO**: Compare captures (diff two waveforms)

---

### 7. Packaging và deployment

#### Executable
- [ ] **TODO**: PyInstaller bundle (single .exe for Windows)
- [ ] **TODO**: AppImage for Linux
- [ ] **TODO**: .app bundle for macOS
- [ ] **TODO**: Test on clean VM (no Python installed)

#### Installer
- [ ] **TODO**: NSIS installer for Windows
- [ ] **TODO**: .deb package for Debian/Ubuntu
- [ ] **TODO**: .rpm package for Fedora/RHEL
- [ ] **TODO**: Homebrew formula for macOS

#### Distribution
- [ ] **TODO**: GitHub releases (tag, changelog, binaries)
- [ ] **TODO**: PyPI package (pip install logic-analyzer)
- [ ] **TODO**: Docker image (for headless use)

---

### 8. Tài liệu

#### User documentation
- [x] README.md (setup, run, features)
- [x] DECODER_IMPLEMENTATION.md (algorithm details)
- [ ] **TODO**: User guide (screenshots, step-by-step)
- [ ] **TODO**: FAQ
- [ ] **TODO**: Video tutorial (YouTube)

#### Developer documentation
- [x] Algorithm docs (autodetect, decoders)
- [ ] **TODO**: Architecture diagram (modules, data flow)
- [ ] **TODO**: API reference (docstrings → Sphinx)
- [ ] **TODO**: Contributing guide (code style, PR process)
- [ ] **TODO**: Changelog (CHANGELOG.md)

#### Hardware documentation
- [ ] **TODO**: STM32 firmware guide (how to build, flash)
- [ ] **TODO**: Hardware schematic (logic level shifters, connectors)
- [ ] **TODO**: BOM (Bill of Materials)
- [ ] **TODO**: PCB design files (KiCad)

---

## Testing với phần cứng thật

### Chuẩn bị

1. **STM32 firmware**:
   - [ ] Flash firmware lên STM32 (USB CDC + 8-channel sampling)
   - [ ] Verify sample rate (1 MHz, 2 MHz)
   - [ ] Verify byte format (bit n = CH n+1)

2. **Test setup**:
   - [ ] Breadboard + jumper wires
   - [ ] Logic level shifters (nếu cần)
   - [ ] Sensors/devices:
     - [ ] UART: USB-to-serial adapter (loopback)
     - [ ] I2C: BME280 hoặc MPU6050
     - [ ] SPI: W25Q32 flash hoặc SD card
     - [ ] I2S: PCM5102 DAC hoặc INMP441 mic

### Test cases

#### UART
- [ ] **Test 1**: Loopback @ 9600 baud, 8N1
  - [ ] Gửi "Hello World", verify decode
  - [ ] Check timing accuracy (±1% tolerance)
- [ ] **Test 2**: Loopback @ 115200 baud, 8E1
  - [ ] Gửi 256 bytes random, verify parity
- [ ] **Test 3**: Framing error
  - [ ] Disconnect TX mid-byte, verify error annotation

#### I2C
- [ ] **Test 4**: BME280 read (address 0x76)
  - [ ] Read chip ID (register 0xD0), verify START/STOP/ACK
  - [ ] Check address parsing (0x76 R/W)
- [ ] **Test 5**: MPU6050 write (address 0x68)
  - [ ] Write to PWR_MGMT_1, verify data bytes
- [ ] **Test 6**: NACK condition
  - [ ] Read from non-existent address, verify NACK annotation

#### SPI
- [ ] **Test 7**: W25Q32 read ID (mode 0)
  - [ ] Send 0x9F, read 3-byte ID, verify MOSI/MISO
  - [ ] Check CS active/inactive timing
- [ ] **Test 8**: SD card init (mode 0)
  - [ ] Send CMD0, verify response
- [ ] **Test 9**: Mode 3 test
  - [ ] Change to mode 3, verify sample edge

#### I2S
- [ ] **Test 10**: PCM5102 playback (16-bit, 44.1 kHz)
  - [ ] Play sine wave, verify L/R channel
  - [ ] Check word size (16-bit)
- [ ] **Test 11**: INMP441 record (24-bit, 48 kHz)
  - [ ] Record audio, verify sample values
  - [ ] Check WS transition timing

### Stress test
- [ ] **Test 12**: 8 kênh @ 2 MHz, 10 phút
  - [ ] Monitor CPU usage (< 50%)
  - [ ] Monitor memory usage (< 500 MB)
  - [ ] Verify no dropped samples
  - [ ] Verify no GUI freeze

---

## Tối ưu hóa và polish

### Performance profiling

1. **Profile decode**:
   ```bash
   python3 -m cProfile -o profile.stats main.py
   python3 -m snakeviz profile.stats
   ```
   - [ ] Identify bottlenecks
   - [ ] Optimize hot paths

2. **Memory profiling**:
   ```bash
   python3 -m memory_profiler main.py
   ```
   - [ ] Check for memory leaks
   - [ ] Optimize buffer management

### Code quality

- [ ] **TODO**: Run `pylint` (target score > 8.0)
- [ ] **TODO**: Run `mypy` (type checking)
- [ ] **TODO**: Run `black` (code formatting)
- [ ] **TODO**: Run `isort` (import sorting)
- [ ] **TODO**: Add pre-commit hooks

### Security

- [ ] **TODO**: Validate user input (prevent injection)
- [ ] **TODO**: Sanitize file paths (prevent directory traversal)
- [ ] **TODO**: Check dependencies for vulnerabilities (`pip-audit`)

---

## Packaging và deployment

### Build executable

1. **Windows**:
   ```bash
   pip install pyinstaller
   pyinstaller --onefile --windowed --name LogicAnalyzer main.py
   ```
   - [ ] Test on Windows 10/11
   - [ ] Check file size (< 100 MB)

2. **Linux**:
   ```bash
   pip install pyinstaller
   pyinstaller --onefile --name LogicAnalyzer main.py
   # Hoặc dùng AppImage
   ```
   - [ ] Test on Ubuntu 22.04, Fedora 38
   - [ ] Check dependencies (ldd)

3. **macOS**:
   ```bash
   pyinstaller --onefile --windowed --name LogicAnalyzer main.py
   # Tạo .app bundle
   ```
   - [ ] Test on macOS 12+
   - [ ] Code sign (nếu distribute)

### Create installer

- [ ] **Windows**: NSIS script
- [ ] **Linux**: .deb + .rpm
- [ ] **macOS**: .dmg

### Release checklist

- [ ] Version bump (semantic versioning)
- [ ] Update CHANGELOG.md
- [ ] Tag release (git tag v1.0.0)
- [ ] Build binaries (Windows, Linux, macOS)
- [ ] Upload to GitHub Releases
- [ ] Announce (Twitter, Reddit, Hacker News)

---

## Tóm tắt ưu tiên

### Ưu tiên cao (cần làm ngay)
1. **Testing với phần cứng thật** (UART, I2C, SPI, I2S)
2. **Edge case tests** (framing error, NACK, incomplete word)
3. **Export decoded data** (CSV, JSON)
4. **Performance profiling** (cProfile, memory_profiler)

### Ưu tiên trung bình (làm sau)
5. **Trigger system** (start/stop on condition)
6. **Protocol-specific features** (ASCII terminal, device database)
7. **Packaging** (PyInstaller, AppImage)
8. **User guide** (screenshots, video)

### Ưu tiên thấp (nice-to-have)
9. **Advanced analysis** (eye diagram, timing histogram)
10. **Multi-protocol detection** (UART + I2C cùng lúc)
11. **Quad SPI, TDM, PCM formats**
12. **Audio player** (I2S playback)

---

## Kết luận

Dự án đã hoàn thành **~70%**:
- ✅ Core GUI, decoders, auto-detect, real-time decode
- ⚠️ Cần test với phần cứng thật
- ❌ Thiếu export, trigger, packaging

**Next steps**:
1. Test với STM32 + sensors (UART, I2C, SPI, I2S)
2. Fix bugs phát hiện từ hardware testing
3. Add export CSV/JSON
4. Profile + optimize
5. Package thành executable
6. Release v1.0.0

**Estimated time to v1.0.0**: 2–3 tuần (nếu làm full-time)
