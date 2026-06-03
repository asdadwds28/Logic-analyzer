# USB Logic Analyzer

Phần mềm Logic Analyzer dùng PyQt5/pyqtgraph để hiển thị tín hiệu số, đọc dữ liệu USB CDC từ STM32, tự động nhận diện và giải mã UART, I2C, SPI, I2S.

## Tính năng

- Hiển thị 8 kênh digital waveform.
- Kéo để pan, cuộn chuột để zoom, Ctrl + +/- để zoom nhanh.
- Timing marker: đặt 2 marker và đo Δt.
- Range management: chọn và lưu vùng thời gian.
- Measurement: đo Frequency, Period, PW-High, PW-Low, Duty Cycle.
- Kết nối phần cứng qua USB CDC/serial.
- Auto-Detect & Decode: tự nhận diện UART, I2C, SPI, I2S.
- Manual Decode: chọn protocol, channel mapping, tham số decode thủ công.
- Nhiều theme giao diện: Dark, Light, Ocean, Forest, Sunset, Hacker.

## Cấu trúc dữ liệu tín hiệu

Mỗi byte là 1 sample:

```text
bit 0 = CH1
bit 1 = CH2
...
bit 7 = CH8
```

Ví dụ byte `0b00000101` nghĩa là CH1=1, CH2=0, CH3=1, các kênh còn lại =0.

## Yêu cầu

- Linux/Windows
- Python 3.14+ hoặc Python 3.10+
- Thiết bị USB CDC xuất raw bytes theo format trên

Thư viện Python:

```bash
pip install PyQt5 pyqtgraph numpy pyserial pytest
```

Nếu hệ thống Linux chặn cài global package, dùng virtual environment:

```bash
python3 -m venv .venv
.venv/bin/pip install PyQt5 pyqtgraph numpy pyserial pytest
```

## Chạy ứng dụng

Từ thư mục repo:

```bash
python3 main.py
```

Nếu dùng virtual environment:

```bash
.venv/bin/python main.py
```

## Kết nối phần cứng

1. Cắm thiết bị USB CDC.
2. Mở app.
3. Bấm nút quét cổng `↺`.
4. Chọn cổng COM/tty tương ứng.
5. Bấm `Connect`.

Cấu hình serial mặc định trong `main.py`:

```text
baudrate: 2_000_000
format:   8N1
chunk:    4096 bytes
```

## Sử dụng decode

### Auto-Detect & Decode

Bấm `Auto-Detect & Decode`. App sẽ:

1. Pack dữ liệu đang hiển thị thành raw bytes.
2. Chạy `AnalyzerService.autodetect_and_decode()`.
3. Detect protocol bằng heuristic trong `autodetect_fast.py`.
4. Decode bằng decoder tương ứng.
5. Vẽ annotation lên waveform.

### Manual Decode

Bấm `Manual Decode`, chọn protocol và map channel:

| Protocol | Channel cần chọn | Tham số |
|---|---|---|
| UART | TX | baud_rate, data_bits, parity, stop_bits |
| I2C | SCL, SDA | — |
| SPI | CS, SCK, MOSI | mode, bits_per_word, bit_order |
| I2S | SCK, WS, SD | word_size, format |

## Protocol được hỗ trợ

### UART

- Idle high
- Start bit = 0
- Data bits 5–8
- Parity: none/odd/even
- Stop bits: 1/1.5/2
- Baud auto-detect: 9600, 19200, 38400, 57600, 115200

### I2C

- START: SDA 1→0 khi SCL=1
- STOP: SDA 0→1 khi SCL=1
- Address 7-bit + R/W
- ACK/NACK
- Repeated START
- Missing STOP warning

### SPI

- Mode 0–3
- CPOL/CPHA
- MSB/LSB bit order
- CS active-low
- MOSI/MISO full-duplex
- Partial/incomplete frame warning

### I2S

- SCK/WS/SD
- Left/right channel
- Word size 16/24/32
- Standard I2S và left-justified option

## Kiến trúc code

```text
main.py
  ├─ GUI PyQt5 + pyqtgraph
  ├─ SerialWorker đọc USB CDC trên QThread
  ├─ SettingsPanel
  └─ gọi AnalyzerService

analyzer/
  ├─ service.py      facade chính cho GUI
  ├─ detector.py     wrapper auto-detect
  ├─ models.py       DetectionCandidate, DecodeResult, Annotation, Frame
  ├─ adapters.py     convert DecodeResult sang GUI items
  ├─ timing.py       helper đọc bit, edge, sample timing
  └─ errors.py

protocols/
  ├─ uart.py
  ├─ i2c.py
  ├─ spi.py
  └─ i2s.py

autodetect_fast.py
  └─ heuristic detect nhanh bằng pure Python
```

Luồng auto-detect:

```text
GUI
 → AnalyzerService.autodetect_and_decode(raw_bytes)
 → ProtocolDetector.detect_all(raw_bytes)
 → profile_channels(raw_bytes)
 → detect_uart / detect_i2c / detect_spi / detect_i2s
 → decode_with_config()
 → DecodeResult
 → AnnotationAdapter
 → waveform annotations
```

## Chạy test

Tạo virtual environment và cài pytest:

```bash
python3 -m venv .venv
.venv/bin/pip install pytest
```

Chạy unit tests:

```bash
.venv/bin/python -m pytest tests/test_decoders.py -v
```

Chạy smoke test:

```bash
.venv/bin/python tests/run_decoder_smoke.py
```

Chạy CSV auto-detect tests:

```bash
.venv/bin/python tests/test_csv_autodetect.py
.venv/bin/python tests/test_all_autodetect.py
```

Kết quả hiện tại:

```text
15 passed in tests/test_decoders.py
ALL SMOKE TESTS PASSED
UART CSV detect: CH0, 115200 baud, ~91.49% confidence
Saleae CSV detect: I2C SCL=CH1, SDA=CH0
```

## Tài liệu thuật toán

- `docs/autodetect_algorithm.md`: chi tiết heuristic auto-detect.
- `docs/decoder_algorithms.md`: chi tiết thuật toán UART/I2C/SPI/I2S decoder.
- `tests/bao_cao_tien_do.md`: báo cáo tiến độ dự án.

## Troubleshooting

### `python: command not found`

Dùng `python3` thay vì `python`:

```bash
python3 main.py
```

### `No module named pytest`

Cài pytest trong venv:

```bash
python3 -m venv .venv
.venv/bin/pip install pytest
```

### Không thấy cổng COM

- Kiểm tra thiết bị đã cắm chưa.
- Bấm `↺` để quét lại.
- Linux: kiểm tra quyền truy cập serial, ví dụ user thuộc group `dialout`.

### GUI không mở do thiếu PyQt5

```bash
.venv/bin/pip install PyQt5 pyqtgraph numpy pyserial
```

### Auto-detect không tìm thấy protocol

- Kiểm tra sample rate có đúng không.
- Đảm bảo raw byte format đúng: bit n = channel n.
- Với UART, tín hiệu cần idle high.
- Với SPI, SCK nên chỉ toggle khi CS active-low.
- Với I2C, SDA phải có START/STOP khi SCL high.

## Trạng thái dự án

Đã hoàn thành:

- GUI chính.
- Backend analyzer service.
- Decoder UART/I2C/SPI/I2S.
- Auto-detect heuristic.
- Test cơ bản và CSV smoke tests.

Đang mở rộng:

- Real-time auto-detect trực tiếp khi stream USB CDC.
- Tối ưu throughput/latency khi dữ liệu lớn.
