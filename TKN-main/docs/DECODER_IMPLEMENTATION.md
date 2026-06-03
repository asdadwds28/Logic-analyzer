# Chi Tiết Cách Hoạt Động Của 4 Decoder: UART, I2C, SPI, I2S

## Mục lục

1. [Tổng quan](#tổng-quan)
2. [UART Decoder](#uart-decoder)
3. [I2C Decoder](#i2c-decoder)
4. [SPI Decoder](#spi-decoder)
5. [I2S Decoder](#i2s-decoder)
6. [Luồng xử lý chung](#luồng-xử-lý-chung)

---

## Tổng quan

### Định dạng dữ liệu đầu vào

Tất cả decoder nhận dữ liệu dạng:
```
raw_bytes: bytes
```

Mỗi byte = 1 sample, bit n = trạng thái channel n:
```
byte = 0b CCCCCCCC
       bit 7 6 5 4 3 2 1 0
       ch  8 7 6 5 4 3 2 1
```

Ví dụ: `byte = 0b00000101` → CH1=1, CH2=0, CH3=1, CH4-8=0

### Tham số chung

- `sample_rate`: tần số lấy mẫu (Hz), mặc định 1 MHz
- `channel`: index kênh (0–7)

### Đầu ra chung

Tất cả decoder trả về `DecodeResult`:
```python
@dataclass
class DecodeResult:
    protocol: str                    # "UART", "I2C", "SPI", "I2S"
    config: Dict[str, Any]          # cấu hình đã dùng
    annotations: List[Annotation]   # danh sách annotation nhỏ
    frames: List[Frame]             # danh sách frame logic
    stats: Dict[str, int]           # thống kê (bytes_decoded, errors, etc.)
    warnings: List[str]             # cảnh báo (frame cắt, lỗi, etc.)
```

---

## UART Decoder

**File:** `protocols/uart.py`

### Cấu hình

```python
{
    'channel': 0,           # kênh TX
    'baud_rate': 115200,    # tốc độ baud
    'data_bits': 8,         # 5–8 bits
    'parity': 'none',       # 'none', 'odd', 'even'
    'stop_bits': 1,         # 1, 1.5, 2
    'invert': False,        # đảo tín hiệu
}
```

### Nguyên lý hoạt động

#### 1. Tính toán timing

```
ticks_per_bit = sample_rate / baud_rate
```

Ví dụ: `1_000_000 / 115200 ≈ 8.68` sample/bit

#### 2. Tìm start bit

Quét toàn bộ dữ liệu tìm **falling edge** (1→0) trên kênh TX:

```python
falling_edges = find_falling_edges(raw_bytes, channel)
```

Mỗi falling edge là ứng viên start bit.

#### 3. Xác nhận start bit

Tại vị trí `start_idx + 0.5 * ticks_per_bit`, sample phải = 0:

```python
confirm_idx = int(start_idx + 0.5 * ticks_per_bit)
if get_sample(raw_bytes, confirm_idx, channel) != 0:
    continue  # không phải start bit thực
```

Điều này tránh nhầm với noise/glitch.

#### 4. Decode data bits

Sample tại tâm mỗi bit (bit center):

```python
for bit_idx in range(data_bits):
    sample_idx = int(start_idx + (bit_idx + 1.5) * ticks_per_bit)
    bit_value = get_sample(raw_bytes, sample_idx, channel)
    data_value |= (bit_value << bit_idx)  # LSB-first
```

Ví dụ với byte `0x55 = 0b01010101`:
- bit 0 (LSB) = 1
- bit 1 = 0
- ...
- bit 7 (MSB) = 0

#### 5. Kiểm tra parity (nếu có)

```python
expected_parity = data_value.bit_count() % 2
if parity == 'odd':
    expected_parity = 1 - expected_parity

if parity_bit != expected_parity:
    severity = "warning"  # không phải error, chỉ cảnh báo
```

#### 6. Kiểm tra stop bit

Stop bit phải = 1. Nếu không → **framing error**:

```python
for stop_bit_idx in range(stop_bits):
    stop_sample = sample_at_bit_center(...)
    if stop_sample != 1:
        stats['errors'] += 1
        emit annotation (kind="framing_error", severity="error")
```

#### 7. Emit annotation

Mỗi byte tạo 3–4 annotation:
- START (kind="start", row="control")
- DATA (kind="byte", row="data", text="0xHH 'C'")
- PARITY (nếu có, kind="parity", row="control")
- STOP (kind="stop", row="control")

### Ví dụ thực tế

**Input:** 600 sample từ CSV, UART 115200 8N1

```
Ticks per bit: 8.68
Frame bits: 1 (start) + 8 (data) + 1 (stop) = 10 bits
Frame samples: 10 * 8.68 ≈ 87 sample

Falling edge @ sample 17 → start bit candidate
Confirm @ 17 + 0.5*8.68 = 21.34 → sample=0 ✓
Data bits @ 26, 35, 43, 52, 60, 69, 77, 86 → 0xD5
Stop bit @ 95 → sample=1 ✓

Annotation:
  START: 17–26
  DATA:  26–95 (0xD5 '?')
  STOP:  95–104
```

### Edge case

- **Inverted signal**: `invert=True` → flip bit trước sample
- **Jitter**: ±1–2 sample OK vì sample tại center
- **Back-to-back frames**: tìm falling edge tiếp theo ngay sau stop bit
- **Truncated frame**: warning "Frame bị cắt @ sample X"

---

## I2C Decoder

**File:** `protocols/i2c.py`

### Cấu hình

```python
{
    'scl_ch': 0,  # kênh SCL (clock)
    'sda_ch': 1,  # kênh SDA (data)
}
```

### Nguyên lý hoạt động

#### 1. Điều kiện START/STOP

**START condition:**
```
SCL = 1 (stable)
SDA: 1 → 0 (falling edge)
```

**STOP condition:**
```
SCL = 1 (stable)
SDA: 0 → 1 (rising edge)
```

**Repeated START:**
```
START khi đã in_frame = True
```

#### 2. Sample data bit

Sample SDA tại **rising edge SCL**:

```python
for i in range(1, len(raw_bytes)):
    scl_prev, scl_curr = get_sample(..., i-1), get_sample(..., i)
    sda_curr = get_sample(..., i)
    
    if scl_prev == 0 and scl_curr == 1:  # rising edge SCL
        bits.append(sda_curr)
```

#### 3. Gom 8 bits thành byte

```python
if len(bits) == 8:
    byte_value = 0
    for bit in bits:
        byte_value = (byte_value << 1) | bit  # MSB-first
    
    # Parse address nếu byte đầu tiên
    if len(frame_bytes) == 0:
        addr = byte_value >> 1
        rw = 'R' if (byte_value & 1) else 'W'
        text = f"0x{addr:02X} {rw}"
    else:
        text = f"0x{byte_value:02X}"
    
    frame_bytes.append(byte_value)
    bits.clear()
```

#### 4. ACK/NACK (bit 9)

Sau 8 data bits, bit 9 là ACK/NACK:

```python
elif len(bits) == 9:
    ack_bit = bits[-1]
    if ack_bit == 0:
        text = "ACK"
        severity = "info"
    else:
        text = "NACK"
        severity = "warning"  # device không acknowledge
    
    bits.clear()
```

#### 5. Frame structure

```
START → ADDR (7-bit) + R/W → ACK/NACK
     → DATA (8-bit) → ACK/NACK
     → DATA (8-bit) → ACK/NACK
     → ...
     → STOP
```

Hoặc:

```
START → ADDR → ACK → RESTART → ADDR → ACK → DATA → ACK → STOP
```

### Ví dụ thực tế

**Input:** Saleae CSV I2C, 2 kênh

```
SCL toggles: 200
SDA toggles: 80
START/STOP count: 4
Valid data clocks: 196

Score = 4*10 + 196 = 236 → high confidence

Detected: SCL=CH1, SDA=CH0

Frame 1:
  START @ 100
  ADDR: 0x50 W (slave address 0x50, write)
  ACK @ 150
  DATA: 0xA5
  ACK @ 200
  STOP @ 250
```

### Edge case

- **Missing STOP**: warning "Frame chưa đóng (missing STOP)"
- **Clock stretching**: SCL held low → không sample SDA
- **Repeated START**: không close frame, emit RESTART annotation
- **NACK**: không phải error, chỉ warning (device intentional)

---

## SPI Decoder

**File:** `protocols/spi.py`

### Cấu hình

```python
{
    'cs_ch': 0,           # kênh CS (chip select)
    'sck_ch': 1,          # kênh SCK (clock)
    'mosi_ch': 2,         # kênh MOSI (master out)
    'miso_ch': 3,         # kênh MISO (master in)
    'mode': 0,            # 0–3 (CPOL, CPHA)
    'bits_per_word': 8,   # 8, 16, 24, 32
    'bit_order': 'msb',   # 'msb' hoặc 'lsb'
    'cs_active': 0,       # 0 (active-low) hoặc 1 (active-high)
}
```

### Mode (CPOL, CPHA)

```
mode = (CPOL << 1) | CPHA

Mode 0: CPOL=0, CPHA=0 → sample on rising edge
Mode 1: CPOL=0, CPHA=1 → sample on falling edge
Mode 2: CPOL=1, CPHA=0 → sample on falling edge
Mode 3: CPOL=1, CPHA=1 → sample on rising edge
```

### Nguyên lý hoạt động

#### 1. Frame boundary (CS)

**CS active** (CS = cs_active):
```python
if prev_cs != cs_active and curr_cs == cs_active:
    in_frame = True
    frame_start = i
    emit annotation (kind="cs_active")
```

**CS inactive** (CS ≠ cs_active):
```python
if prev_cs == cs_active and curr_cs != cs_active:
    close frame
    emit annotation (kind="cs_inactive")
    in_frame = False
```

#### 2. Sample edge

Tùy mode, sample tại rising hoặc falling edge SCK:

```python
sample_on_rising = (CPOL == CPHA)

if in_frame:
    is_rising = (prev_sck == 0 and sck == 1)
    is_falling = (prev_sck == 1 and sck == 0)
    should_sample = (is_rising if sample_on_rising else is_falling)
    
    if should_sample:
        mosi_bits.append(get_sample(raw_bytes, i, mosi_ch))
        miso_bits.append(get_sample(raw_bytes, i, miso_ch))
```

#### 3. Word assembly

```python
if len(mosi_bits) >= bits_per_word:
    mosi_word = bits_to_word(mosi_bits[:bits_per_word], bit_order)
    miso_word = bits_to_word(miso_bits[:bits_per_word], bit_order)
    
    text = f"MOSI 0x{mosi_word:02X} | MISO 0x{miso_word:02X}"
    emit annotation (kind="word", row="data")
    
    mosi_bits = mosi_bits[bits_per_word:]
    miso_bits = miso_bits[bits_per_word:]
    stats['words_decoded'] += 1
```

#### 4. Bit order

**MSB-first:**
```python
value = 0
for bit in bits:
    value = (value << 1) | bit
```

**LSB-first:**
```python
value = 0
for i, bit in enumerate(bits):
    value |= (bit << i)
```

### Ví dụ thực tế

**Input:** SPI mode 0, 8-bit word, MSB-first

```
CS active @ 50
SCK rising edges @ 60, 70, 80, 90, 100, 110, 120, 130
MOSI bits @ rising: 1, 0, 1, 0, 1, 0, 1, 0 → 0xAA
MISO bits @ rising: 0, 1, 0, 1, 0, 1, 0, 1 → 0x55

Annotation:
  CS ACTIVE: 50–51
  WORD: 60–130 (MOSI 0xAA | MISO 0x55)
  CS INACTIVE: 140–141
```

### Edge case

- **MOSI-only / MISO-only**: `mosi_ch=None` hoặc `miso_ch=None` → omit từ text
- **Incomplete word**: partial bits kept, warning on EOF
- **CS always inactive**: no frames decoded
- **Mode mismatch**: garbled data (no explicit error)

---

## I2S Decoder

**File:** `protocols/i2s.py`

### Cấu hình

```python
{
    'sck_ch': 0,      # kênh SCK (bit clock)
    'ws_ch': 1,       # kênh WS (word select / frame sync)
    'sd_ch': 2,       # kênh SD (serial data)
    'word_size': 16,  # 16, 24, 32 bits
    'format': 'i2s',  # 'i2s' hoặc 'left_justified'
}
```

### Nguyên lý hoạt động

#### 1. WS transition (channel boundary)

**WS = 0** → Left channel (L)
**WS = 1** → Right channel (R)

```python
if prev_ws != ws:
    # Kết thúc sample trước đó
    if sd_bits:
        sample_value = bits_to_word(sd_bits)
        emit annotation (kind="sample_l" or "sample_r")
        stats['samples_decoded'] += 1
    
    # Bắt đầu channel mới
    current_channel = 'L' if ws == 0 else 'R'
    sd_bits.clear()
```

#### 2. Sample SD tại rising edge SCK

```python
if prev_sck == 0 and sck == 1:
    if not sd_bits:
        sample_start = i
    
    sd_bits.append(get_sample(raw_bytes, i, sd_ch))
```

#### 3. Word assembly

```python
if len(sd_bits) >= word_size:
    sample_value = bits_to_word(sd_bits[:word_size])
    channel_label = 'L' if current_channel == 'L' else 'R'
    text = f"{channel_label}: 0x{sample_value:04X}"
    
    emit annotation (kind="sample_l" or "sample_r")
    stats['samples_decoded'] += 1
    
    sd_bits = sd_bits[word_size:]
```

#### 4. Frame structure

```
Standard I2S (16-bit):
  WS=0 (L): SCK 0→1 (16 times) → 16-bit L sample
  WS=1 (R): SCK 0→1 (16 times) → 16-bit R sample
  WS=0 (L): ...
```

Ratio SCK:WS ≈ word_size * 2 (vì 2 channel)

### Ví dụ thực tế

**Input:** I2S 16-bit, 2 kênh

```
WS @ 0: L channel
SCK rising @ 10, 20, 30, ..., 170 (16 times)
SD bits @ rising: 1,0,1,0,1,0,1,0,1,0,1,0,1,0,1,0 → 0xAAAA

Annotation:
  WS L: 0–1
  SAMPLE L: 10–170 (0xAAAA)

WS @ 180: R channel
SCK rising @ 190, 200, ..., 350 (16 times)
SD bits: 0,1,0,1,0,1,0,1,0,1,0,1,0,1,0,1 → 0x5555

Annotation:
  WS R: 180–181
  SAMPLE R: 190–350 (0x5555)
```

### Edge case

- **Incomplete sample**: fewer than word_size bits → warning
- **WS edge mid-word**: buffer flush on each WS change
- **Extra SCK pulses**: accumulated bits discarded on WS change
- **Left-justified format**: WS changes at start of frame, no MSB alignment

---

## Luồng xử lý chung

### 1. GUI → Decode

```
User click "Auto-Detect & Decode"
  ↓
Pack self.data[ch] → raw_bytes
  ↓
AnalyzerService.autodetect_and_decode(raw_bytes)
  ↓
ProtocolDetector.detect_all(raw_bytes)
  ├─ profile_channels()
  ├─ detect_uart() / detect_i2c() / detect_spi() / detect_i2s()
  └─ List[DetectionCandidate]
  ↓
For each candidate:
  decode_with_config(raw_bytes, protocol, channels, params)
  ↓
List[DecodeResult]
  ↓
AnnotationAdapter.to_gui_format()
  ↓
Draw TextItem on waveform
```

### 2. Annotation → GUI

```
Annotation:
  start_sample: 100
  end_sample: 200
  text: "0x55"
  row: "data"
  kind: "byte"
  channel: 0

GUI:
  y_base = channel * 2 + 1.2
  row_offset = {"data": 0.15, "control": 0.35, "error": -0.05}[row]
  y = y_base + row_offset
  
  TextItem(text, pos=(start_sample, y))
  color = protocol_color or severity_color
```

### 3. Error handling

```
Mỗi decoder:
  - Emit warning (không stop)
  - Emit error annotation (severity="error")
  - stats['errors'] += 1
  - Tiếp tục decode frame tiếp theo
```

Ví dụ:
- UART framing error → emit annotation, continue
- I2C missing STOP → warning, close frame as incomplete
- SPI incomplete word → warning, discard partial bits

---

## Tóm tắt

| Decoder | Start | Sample | Bit order | Frame boundary | Key check |
|---------|-------|--------|-----------|-----------------|-----------|
| UART | Falling edge | Bit center | LSB-first | Start + Stop | Stop bit = 1 |
| I2C | SDA 1→0 @ SCL=1 | Rising SCL | MSB-first | START + STOP | ACK/NACK |
| SPI | CS active | SCK edge | MSB/LSB | CS active/inactive | Mode (CPOL/CPHA) |
| I2S | WS transition | Rising SCK | MSB-first | WS change | Word size × 2 ratio |

