# Auto-Detect Algorithm — Chi Tiết

## 1. Overview

Auto-detect chạy 2 lớp:
1. **Heuristic layer** (`autodetect_fast.py`) — profile channels, detect candidates per protocol
2. **Service layer** (`analyzer/detector.py`) — wrap heuristics, build `DetectionCandidate` objects, sort by confidence

```
GUI → AnalyzerService.autodetect_and_decode(raw_bytes)
       → ProtocolDetector.detect_all(raw_bytes)
          → profile_channels(raw_bytes, num_channels)
          → detect_uart(profiles, sample_rate)
          → detect_i2c(profiles, raw_bytes)
          → detect_spi(profiles, raw_bytes)
          → detect_i2s(profiles, raw_bytes)
       → List[DetectionCandidate] (sorted by confidence)
       → decode_with_config() per candidate
       → List[DecodeResult]
```

---

## 2. Channel Profiling — `profile_channels()`

**File:** `autodetect_fast.py`

### Purpose
Build statistical profile cho từng channel (0–7): toggle count, pulse widths, idle state, edges.

### Optimization
Skip unchanged samples — chỉ xử lý sample có thay đổi (XOR diff):
```python
for i, val in enumerate(data):
    if val == last_val: continue
    diff = val ^ last_val
    for ch in range(num_channels):
        if (diff >> ch) & 1:  # channel ch changed
            ...
```

### Per-Channel Output
```python
{
    "toggles": int,             # total number of edge transitions
    "min_pulse": float,         # minimum pulse width in samples
    "state_counts": {0: n0, 1: n1},  # total samples high vs low
    "edges": [(sample_idx, new_state), ...],
    "pulse_widths": {width: count, ...},  # histogram of pulse widths
    "idle_state": 0 or 1        # 1 if samples_high > samples_low else 0
}
```

### Idle State Logic
```
if state_counts[1] > state_counts[0]: idle_state = 1
else:                                  idle_state = 0
```

---

## 3. Fundamental Pulse Estimation — `get_fundamental_pulse_gcd()`

### Purpose
Tìm xung cơ bản (fundamental pulse width) từ histogram pulse widths.

### Algorithm
```
1. if total pulses < 5: use all pulse_widths
   else: filter to widths appearing >= 5% of total pulses

2. fundamental = min(valid pulse widths)
```

### Why min?
Shortest recurring pulse = 1 bit-period trong hầu hết protocols.
UART: 1 baud period. SPI: 1 SCK period. I2C: 1 SCL half-period.

### Threshold
```python
threshold = max(total_pulses * 0.05, 1)
valid_pw = {w: c for w, c in pulse_widths.items() if c >= threshold}
```

---

## 4. UART Detection — `detect_uart()`

### Criteria
| Property | Requirement |
|----------|-------------|
| Idle state | Must be HIGH (UART idle = mark) |
| Toggles | > 0 |
| Baud match | Approx baud ±15% of standard baud |

### Algorithm
```
for each channel profile:
    if toggles > 0 AND idle_state == 1:
        fund_pulse = get_fundamental_pulse_gcd(pulse_widths)
        approx_baud = sample_rate / fund_pulse
        for baud in COMMON_BAUDS = [9600, 19200, 38400, 57600, 115200]:
            if |approx_baud - baud| / baud < 0.15:
                confidence = 1.0 - |approx_baud - baud| / baud
                candidate = {channel, baud_rate, confidence}

return best candidate (sorted by confidence descending) or None
```

### Key Insight
UART TX có idle high → channel phải có `idle_state == 1`. Fundamental pulse width = 1 bit period. Baud rate = `sample_rate / bit_period`.

### Example
```
sample_rate = 1 000 000
fund_pulse = 8.68 samples
approx_baud = 1 000 000 / 8.68 ≈ 115 207
closest standard = 115 200
error = |115 207 - 115 200| / 115 200 ≈ 0.006% → confidence ≈ 0.9994
```

---

## 5. I2C Detection — `detect_i2c()`

### Criteria
| Property | SCL | SDA |
|----------|-----|-----|
| Toggles | ≥ 4 | ≥ 2 |
| Relation | SCL toggles > SDA toggles | — |
| SDA edges while SCL high | Count as START/STOP evidence | — |

### Algorithm
```
for each (scl_ch, sda_ch) pair where scl_ch ≠ sda_ch:
    if SCL toggles < 4 OR SDA toggles < 2: skip
    if SCL toggles <= SDA toggles: skip

    # Count START/STOP evidence (SDA changes while SCL=1)
    start_stop_count = count of SDA edges while SCL == 1

    # Count valid data clocks (SCL rising while SDA stable)
    valid_data_count = count of SCL rising edges

    score = (start_stop_count * 10) + valid_data_count

    candidate = {scl_ch, sda_ch, score}

return best pair (highest score) or None
```

### Key Insight
I2C đặc biệt ở: SDA **chỉ** thay đổi khi SCL LOW (normal data) hoặc khi SCL HIGH (START/STOP).
START/STOP count cao = strong evidence I2C.
SCL > SDA toggle count vì SCL toggle mỗi bit, SDA toggle ít hơn (nhiều bit giống nhau).

### Scoring Weight
```
START/STOP × 10  +  valid_data × 1
```
START/STOP rất đặc trưng I2C → weight cao hơn.

---

## 6. SPI Detection — `detect_spi()`

### Criteria
| Property | CS | SCK | MOSI/MISO |
|----------|-----|-----|-----------|
| Idle state | HIGH (1) | — | — |
| Toggles | ≠ 0 | ≥ 8 | any |
| Correlation | — | SCK mostly toggles when CS low | — |

### Algorithm
```
for each (cs_ch, sck_ch) pair where cs_ch ≠ sck_ch:
    if CS toggles == 0: skip
    if CS idle_state != 1: skip     # CS active-low, idle = high
    if SCK toggles < 8: skip

    # Verify SCK toggles mostly during CS active
    sck_toggles_cs_low  = count SCK edges while CS == 0
    sck_toggles_cs_high = count SCK edges while CS == 1

    if sck_toggles_cs_low == 0: skip
    if sck_toggles_cs_high > sck_toggles_cs_low * 0.1: skip
    # → SCK noise when CS high must be < 10%

    score = sck_toggles_cs_low - (sck_toggles_cs_high * 10)

    # Data channels = remaining active channels (≠ CS, ≠ SCK)
    data_channels = [ch for ch in profiles if ch != cs_ch and ch != sck_ch
                     and profiles[ch]['toggles'] > 0]
    mosi_ch = data_channels[0] if len(data_channels) > 0 else None
    miso_ch = data_channels[1] if len(data_channels) > 1 else None

    candidate = {cs_ch, sck_ch, mosi_ch, miso_ch, score}

return best candidate or None
```

### Key Insight
SPI đặc biệt ở: SCK **chỉ** toggle khi CS active (low).
Nếu SCK toggle nhiều khi CS high → không phải SPI.
CS idle = high (active-low).

### Scoring Weight
```
SCK_low × 1  -  SCK_high × 10
```
SCK toggling when CS high = strong anti-evidence → penalty 10×.

---

## 7. I2S Detection — `detect_i2s()`

### Criteria
| Property | SCK | WS | SD |
|----------|-----|-----|-----|
| Toggles | ≥ 64 | — | — |
| Ratio SCK:WS | ≈ 32 or 48 or 64 | — | — |

### Algorithm
```
for each (sck_ch, ws_ch) pair where sck_ch ≠ ws_ch:
    sck_toggles = profiles[sck_ch]['toggles']
    ws_toggles  = profiles[ws_ch]['toggles']

    if sck_toggles < 64: skip

    ratio = (sck_toggles + 1) / (ws_toggles + 1)

    # Standard I2S ratios (word_size * 2 channels)
    # 16-bit: SCK/WS ≈ 32
    # 24-bit: SCK/WS ≈ 48
    # 32-bit: SCK/WS ≈ 64
    if |ratio - 32| < 2.0 OR |ratio - 48| < 2.0 OR |ratio - 64| < 2.0:
        # SD = first remaining active channel
        sd_ch = first ch in profiles where ch ≠ sck_ch, ch ≠ ws_ch,
                and profiles[ch]['toggles'] > 0
        candidate = {sck_ch, ws_ch, sd_ch, ratio}
        break

return candidate or None
```

### Key Insight
I2S đặc biệt ở: SCK/WS ratio ≈ `word_size × 2`.
WS toggles mỗi frame (left/right), SCK toggles mỗi bit.
16-bit I2S: 16 bits × 2 channels = 32 SCK per WS period → ratio ≈ 32.

### Ratio Thresholds
```
|ratio - 32| < 2.0   → 16-bit word
|ratio - 48| < 2.0   → 24-bit word
|ratio - 64| < 2.0   → 32-bit word
```
Tolerance ±2 accounts for sampling jitter and non-integer edges.

---

## 8. CAN & 1-Wire Detection (present but not used in current registry)

### CAN — `detect_can()`
- Similar to UART: find channel with idle high.
- Match baud from `COMMON_CAN_BAUDS = [125000, 250000, 500000, 1000000]`.
- No custom CAN decoder in current registry; detection exists for future use.

### 1-Wire — `detect_onewire()`
- Detect channel with specific pulse patterns (reset pulse ~480µs, presence pulse).
- No custom 1-Wire decoder in current registry; detection exists for future use.

---

## 9. Service Layer — `ProtocolDetector`

**File:** `analyzer/detector.py`

### Role
Wrap `autodetect_fast` functions into `DetectionCandidate` objects:
```python
@dataclass
class DetectionCandidate:
    protocol: str
    confidence: float      # 0.0–1.0
    channels: Dict[str, int]
    params: Dict[str, Any]
    evidence: Dict[str, Any] = field(default_factory=dict)
```

### Flow
```
1. profile_channels(raw_bytes, num_channels)

2. For each protocol, call detect_*():
   - detect_uart(profiles, sample_rate) → candidate | None
   - detect_i2c(profiles, raw_bytes)    → candidate | None
   - detect_spi(profiles, raw_bytes)    → candidate | None
   - detect_i2s(profiles, raw_bytes)    → candidate | None

3. Convert each raw candidate to DetectionCandidate
   - UART: confidence from baud match quality
   - I2C:  confidence from score / max_possible
   - SPI:  confidence from score / max_possible
   - I2S:  confidence = 1.0 if ratio matched (binary)

4. Sort by confidence descending
   return List[DetectionCandidate]
```

### Channel Deduplication
Sau khi detect 1 protocol, remove used channels khỏi profile pool để tránh trùng:
```python
# In logic_analyzer.py:Analyzer.auto_detect_channels()
profiles.pop(used_channel, None)  # remove claimed channels
```

---

## 10. Confidence Scoring Summary

| Protocol | Score Basis | Range |
|----------|-------------|-------|
| UART | Baud match accuracy | 0.0–1.0 |
| I2C | `(start_stop×10 + valid_data) / max` | 0.0–1.0 |
| SPI | `sck_low - sck_high×10` normalized | 0.0–1.0 |
| I2S | Binary: 1.0 if ratio matched | 0.0 or 1.0 |

---

## 11. End-to-End Example

```
Input: 1000 samples, 4 channels, sample_rate=1MHz
Channel 0: UART TX at 115200 baud → idle high, toggles with ~8.68 sample pulses
Channel 1: I2C SCL → regular clock
Channel 2: I2C SDA → data changing on SCL edges

profile_channels → profiles[0..3]

detect_uart:
  ch0: idle=1, fund_pulse=8.68, approx_baud=115207 → match 115200, confidence=0.9994

detect_i2c:
  pair(1,2): SCL toggles=200, SDA toggles=80
             start_stop_count=4, valid_data=196
             score = 40 + 196 = 236

detect_spi:
  No CS with idle=1 → no candidate

detect_i2s:
  No channel with toggles ≥ 64 → no candidate

Results: [DetectionCandidate(UART, 0.999, {TX:0}, {baud:115200}),
          DetectionCandidate(I2C, 0.85, {SCL:1, SDA:2}, {})]
```

---

## 12. Key Reference

| Function | File | Purpose |
|----------|------|---------|
| `profile_channels` | `autodetect_fast.py` | Build per-channel statistics |
| `get_fundamental_pulse_gcd` | `autodetect_fast.py` | Estimate base pulse width |
| `detect_uart` | `autodetect_fast.py` | UART candidate detection |
| `detect_i2c` | `autodetect_fast.py` | I2C candidate detection |
| `detect_spi` | `autodetect_fast.py` | SPI candidate detection |
| `detect_i2s` | `autodetect_fast.py` | I2S candidate detection |
| `detect_can` | `autodetect_fast.py` | CAN candidate detection (unused) |
| `detect_onewire` | `autodetect_fast.py` | 1-Wire detection (unused) |
| `ProtocolDetector` | `analyzer/detector.py` | Service wrapper, candidate objects |
| `DetectionCandidate` | `analyzer/models.py` | Candidate dataclass |
| `AnalyzerService` | `analyzer/service.py` | Top-level facade for GUI |