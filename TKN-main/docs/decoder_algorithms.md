# Decoder Algorithms — UART / I2C / SPI / I2S

## 1. Shared Foundation

### Raw Sample Format
- `raw_bytes: bytes` — each byte = one sample; bit *n* = state of channel *n*.
- `sample_rate: int` — samples per second (e.g. 1 000 000).

### Output Types
```
Annotation  — start_sample, end_sample, text, row ("control"|"data"|"error"), kind, severity, channel, fields
Frame       — protocol, start_sample, end_sample, summary, fields, annotations, children
DecodeResult— protocol, config, annotations: List[Annotation], frames: List[Frame], stats: dict, warnings: List[str]
```

### Shared Timing Helpers (`analyzer/timing.py`)
```
extract_channel(raw_bytes, ch)      → List[int] of 0/1
get_sample(raw_bytes, idx, ch)      → int 0/1 (clamped)
find_edges(raw_bytes, ch)           → List[(idx, old, new)]
find_rising_edges(raw_bytes, ch)    → List[idx]
find_falling_edges(raw_bytes, ch)   → List[idx]
measure_pulse_widths(raw_bytes, ch) → List[(start, end, state)]
sample_at_bit_center(raw_bytes, start, bit_idx, tpb, ch) → int 0/1
clamp_sample_idx(idx, n)           → int
find_next_edge_after(edges, idx)   → (idx, old, new) | None
get_state_run(raw_bytes, start, ch) → (start, end, state)
```

---

## 2. UART Decoder
**File:** `protocols/uart.py`
**Required channels:** `TX`
**Config:** `channel`, `baud_rate`, `data_bits` (5–8), `parity` ("none"|"odd"|"even"), `stop_bits` (1|1.5|2), `invert`

### Parameters
```
ticks_per_bit = sample_rate / baud_rate
frame_bits    = 1 (start) + data_bits [+ 1 parity] + stop_bits
frame_samples = frame_bits * ticks_per_bit
```

### Algorithm
```
1. Edge scan
   → find_falling_edges(raw_bytes, tx_ch) → List[start_idx]

2. For each candidate start_idx
   2a. Validate: frame must not exceed buffer
        if start_idx + frame_samples > len(raw_bytes):
            warnings.append(f"Frame bị cắt @ sample {start_idx}"); continue

   2b. Confirm start bit (half-bit sample must be 0)
        confirm_idx = clamp(start_idx + 0.5 * tpb)
        if get(raw_bytes, confirm_idx, tx_ch) != 0: continue

   2c. Emit START annotation (kind="start", row="control")

   2d. Sample data bits LSB-first, at bit center
        for bit_idx in range(data_bits):
            bit = sample_at_bit_center(raw_bytes, start_idx, bit_idx+1, tpb, tx_ch)
            data |= bit << bit_idx

   2e. Parity check (if parity ≠ "none")
        expected_parity = data.bit_count() % 2
        if parity == "odd": expected_parity = 1 - expected_parity
        parity_ok = (parity_bit == expected_parity)
        if not parity_ok: severity = warning

   2f. Stop bits must be 1; if not → framing error
        if stop_bit != 1:
            stats["errors"] += 1
            emit annotation (kind="framing_error", row="error", severity="error")
            warning: "Framing error @ sample {start_idx}: expected stop=1, got {stop_bit}"

   2g. Emit DATA annotation: text = "0xHH 'C'" (hex + ASCII char if printable)
        kind="byte", row="data"

   2h. stats["bytes_decoded"] += 1; stats["frames"] += 1
```

### Edge Cases
- **Short buffer** → warning "Dữ liệu quá ngắn"
- **Truncated frame** → warning + skip
- **Start bit not 0** → skip candidate silently
- **Framing error** → annotation with severity=error, keep decoding
- **Inverted signal** → `invert` flag flips raw bit before sampling

### Stats
```python
{"bytes_decoded": 0, "errors": 0, "frames": 0}
```

---

## 3. I2C Decoder
**File:** `protocols/i2c.py`
**Required channels:** `SCL`, `SDA`
**Config:** `scl_ch`, `sda_ch`

### Key Conditions
```
START  : SCL=1 AND SDA 1→0
STOP   : SCL=1 AND SDA 0→1
RESTART: SCL=1 AND SDA 1→0 while in_frame
SAMPLE : SCL 0→1 (sample SDA on rising SCL)
```

### Algorithm
```
1. Scan sample-by-sample through raw_bytes
   Track: prev_scl, prev_sda, in_frame, bits[], bit_starts[], frame_bytes[], frame_start

2. START condition detected
   if not in_frame:
       in_frame = True
       frame_start = i
       emit START (kind="start", row="control")
       stats["start_count"] += 1
   else:
       emit RESTART (kind="restart", row="control")
       frame_bytes.clear()

3. STOP condition detected
   if in_frame:
       close frame: summary=f"I2C {len(frame_bytes)} bytes"
       stats["stop_count"] += 1
   emit STOP (kind="stop", row="control")

4. Sample SDA on rising SCL (while in_frame)
   bits.append(sda); bit_starts.append(i)
   when len(bits) == 8:
       build byte MSB-first: byte_val = 0; for b in bits: byte_val = (byte_val<<1) | b
       frame_bytes.append(byte_val)
       if first byte:
           addr = byte_val >> 1; rw = "R" if (byte_val&1) else "W"
           text = f"0x{addr:02X} {rw}"; kind = "address"
       else:
           text = f"0x{byte_val:02X}"; kind = "data"
       emit annotation; bits.clear()

5. 9th bit (ACK/NACK) after 8 data bits
   ack_bit = bits[-1]
   if ack_bit == 0: text="ACK"; kind="ack"; severity="info"
   else:            text="NACK"; kind="nack"; severity="warning"
   emit; bits.clear()

6. Missing STOP at EOF
   if in_frame and frame_bytes:
       warning: "Frame chưa đóng (missing STOP) @ sample {frame_start}"
       close frame with fields={"incomplete": True}
```

### Edge Cases
- **Missing STOP** → warning + close frame as incomplete
- **Truncated byte** (buffer ends mid-byte) → warning + skip partial
- **NACK** → severity warning, not error (device may NACK intentionally)
- **Repeated START** → emit RESTART, reuse same frame context

### Stats
```python
{"bytes_decoded": 0, "errors": 0, "frames": 0, "start_count": 0, "stop_count": 0}
```

---

## 4. SPI Decoder
**File:** `protocols/spi.py`
**Required channels:** `CS`, `SCK`, `MOSI`, `MISO`
**Config:** `cs_ch`, `sck_ch`, `mosi_ch`, `miso_ch`, `mode` (0–3), `bits_per_word` (8|16|24|32), `bit_order` ("msb"|"lsb"), `cs_active` (0|1)

### CPOL/CPHA Derivation
```
cpol = (mode >> 1) & 1   # clock idle polarity
cpha = mode & 1         # sample on 1st/2nd edge
sample_on_rising = (cpol == cpha)
```

### Algorithm
```
1. Scan sample-by-sample through raw_bytes
   Track: prev_sck, prev_cs, in_frame, mosi_bits[], miso_bits[], frame_start

2. CS active → begin frame
   if cs_active and not in_frame:
       in_frame = True; frame_start = i
       emit CS ACTIVE (kind="cs_active", row="control")
       stats["words_decoded"] = 0

3. CS inactive → end frame
   if cs_inactive and in_frame:
       emit CS INACTIVE (kind="cs_inactive", row="control")
       close frame: summary=f"SPI {stats['words_decoded']} words"
       in_frame = False

4. While in_frame — detect SCK edge
   is_rising  = prev_sck==0 AND sck==1
   is_falling = prev_sck==1 AND sck==0
   should_sample = is_rising if sample_on_rising else is_falling
   if should_sample:
       if mosi_ch: mosi_bits.append(get_sample(raw_bytes, i, mosi_ch))
       if miso_ch: miso_bits.append(get_sample(raw_bytes, i, miso_ch))

5. Word assembly
   when len(mosi_bits) >= bits_per_word (or len(miso_bits) >= bits_per_word):
       build MOSI value via _bits_to_word()
       build MISO value via _bits_to_word()
       text = f"MOSI 0xHH | MISO 0xHH"
       emit WORD annotation (kind="word", row="data")
       trim consumed bits
       stats["words_decoded"] += 1

6. EOF while in_frame
   warning: "SPI frame chưa đóng @ sample {frame_start}"
   close frame fields={"incomplete": True}
```

### `_bits_to_word()`
```
if lsb: value = Σ(bit[i] << i)          for i in range(len(bits))
if msb: value = ((...(bit0<<1)|bit1)<<1)|bit2...
```

### Edge Cases
- **MOSI-only / MISO-only** → `mosi_ch=None` or `miso_ch=None` allowed; omit from text
- **Incomplete word** → partial bits kept, warning on EOF
- **CS always inactive** → no frames decoded; `stats["words_decoded"] == 0`
- **Mode mismatch** → incorrect sampling edge → garbled data; no explicit error (device level)

### Stats
```python
{"words_decoded": 0, "frames": 0, "errors": 0}
```

---

## 5. I2S Decoder
**File:** `protocols/i2s.py`
**Required channels:** `SCK`, `WS`, `SD`
**Config:** `sck_ch`, `ws_ch`, `sd_ch`, `word_size` (16|24|32), `format` ("i2s"|"lj"|"rj")

### Key Condition
```
WS transitions: ws changes → left/right channel boundary
SCK rising:    sample SD bit
```

### Algorithm
```
1. Scan sample-by-sample through raw_bytes
   Track: prev_sck, prev_ws, current_channel ('L'|'R'), sd_bits[], bit_starts[], sample_start

2. WS transition detected (prev_ws != ws)
   2a. If sd_bits exist from previous channel:
           value = _bits_to_word(sd_bits)
           channel_label = current_channel
           text = f"{channel_label}: 0x{value:04X}"
           emit SAMPLE annotation (kind="sample_l"|"sample_r", row="data")
           stats["samples_decoded"] += 1
           sd_bits.clear(); bit_starts.clear()

   2b. Determine new channel:
           current_channel = 'L' if ws == 0 else 'R'
           emit WS annotation (kind="ws_l"|"ws_r", row="control")

3. Sample SD on rising SCK
   if prev_sck==0 AND sck==1:
       if not sd_bits: sample_start = i
       sd_bits.append(sd); bit_starts.append(i)

4. When len(sd_bits) >= word_size:
       value = _bits_to_word(sd_bits[:word_size])
       text = f"{current_channel}: 0x{value:04X}"
       emit SAMPLE annotation
       trim: sd_bits = sd_bits[word_size:]; bit_starts = bit_starts[word_size:]

5. EOF buffer
   if sd_bits: warning: "I2S sample chưa đủ @ sample {sample_start}: {len(sd_bits)}/{word_size} bits"
              close frame fields={"incomplete": True}
```

### WS Alignment Notes
- **Standard I2S**: WS changes one SCK cycle before first data bit (MSB-first).
- **Left-justified**: WS changes at start of frame, no MSB-first alignment.
- **Right-justified**: LSB aligned to WS edge; LSBs arrive first.

### Edge Cases
- **Incomplete sample** (fewer than `word_size` bits) → warning + close as incomplete
- **WS edge mid-word** → buffer flush on each WS change handles this correctly
- **Inverted SCK** → treated as different channel pair; not auto-detected
- **Extra SCK pulses** → accumulated bits discarded on WS change

### Stats
```python
{"samples_decoded": 0, "errors": 0, "frames": 0}
```

---

## 6. Annotation-to-GUI Mapping
**File:** `analyzer/adapters.py`

Each `DecodeResult` passes through `AnnotationAdapter` before rendering:

| Field      | Usage                                              |
|------------|----------------------------------------------------|
| `text`     | TextItem label text                                |
| `start`    | X position (`setPos(start, y)`)                   |
| `row`      | Y offset: `control→+0.35`, `data→+0.15`, `error→-0.05` |
| `color`    | Protocol color + severity override                 |
| `tooltip`  | Fields summary, errors, stats                      |

Protocol colors:
```
UART #3a6eff   I2C #00b894   SPI #fdcb6e   I2S #e17055
```

Severity override: `warning → #f39c12`, `error → #e74c3c`.

---

## 7. Key Reference
| Function | File |
|----------|------|
| `sample_at_bit_center` | `analyzer/timing.py` |
| `find_falling_edges`  | `analyzer/timing.py` |
| `get_sample`          | `analyzer/timing.py` |
| `extract_channel`    | `analyzer/timing.py` |
| `find_edges`          | `analyzer/timing.py` |
| `UARTDecoder`        | `protocols/uart.py` |
| `I2CDecoder`         | `protocols/i2c.py` |
| `SPIDecoder`         | `protocols/spi.py` |
| `I2SDecoder`         | `protocols/i2s.py` |
| `DecodeResult`       | `analyzer/models.py` |
| `Annotation`         | `analyzer/models.py` |
| `Frame`              | `analyzer/models.py` |
| `AnalyzerService`     | `analyzer/service.py` |