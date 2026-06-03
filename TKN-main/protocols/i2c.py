"""
protocols/i2c.py — I2C Decoder

Xử lý:
- START/STOP condition (SDA đổi khi SCL=1)
- Data bits (8 bits/byte)
- ACK/NACK (bit 9)
- 7-bit addressing
- Repeated START
- Clock stretching
- Missing STOP
- Partial frame cuối buffer

Thuật toán:
1. Phát hiện START: SDA 1→0 khi SCL=1
2. Phát hiện STOP: SDA 0→1 khi SCL=1
3. Sample SDA tại rising edge SCL
4. Gom 8 bits → byte
5. Bit 9 = ACK (SDA=0) hay NACK (SDA=1)
6. Parse address + R/W bit
"""

from typing import List, Tuple, Optional
from protocols.abstract import ProtocolDecoder
from analyzer.models import DecodeResult, Annotation, Frame
from analyzer.timing import get_sample, find_edges


class I2CDecoder(ProtocolDecoder):
    """I2C decoder với START/STOP/ACK/NACK/address parsing."""

    protocol_name = "I2C"

    @classmethod
    def default_config(cls):
        return {
            'scl_ch': 0,
            'sda_ch': 1,
        }

    @classmethod
    def required_channels(cls):
        return ['SCL', 'SDA']

    def __init__(self, sample_rate: int = 1_000_000, **config):
        super().__init__(sample_rate, **config)
        self.scl_ch = self.config.get('scl_ch', 0)
        self.sda_ch = self.config.get('sda_ch', 1)

    def decode(self, raw_bytes: bytes) -> DecodeResult:
        """Giải mã I2C từ raw bytes."""
        annotations: List[Annotation] = []
        frames: List[Frame] = []
        warnings: List[str] = []
        stats = {'bytes_decoded': 0, 'errors': 0, 'frames': 0, 'start_count': 0, 'stop_count': 0}

        if not raw_bytes or len(raw_bytes) < 10:
            return DecodeResult(
                protocol=self.protocol_name,
                config=self.config,
                annotations=annotations,
                frames=frames,
                stats=stats,
                warnings=['Dữ liệu quá ngắn']
            )

        n = len(raw_bytes)
        prev_scl = get_sample(raw_bytes, 0, self.scl_ch)
        prev_sda = get_sample(raw_bytes, 0, self.sda_ch)

        in_frame = False
        frame_start = 0
        frame_annotations: List[Annotation] = []
        bits: List[int] = []
        bit_starts: List[int] = []
        current_byte_start = 0
        frame_bytes: List[int] = []

        for i in range(1, n):
            scl = get_sample(raw_bytes, i, self.scl_ch)
            sda = get_sample(raw_bytes, i, self.sda_ch)

            # START condition: SDA 1→0 khi SCL=1
            if prev_scl == 1 and scl == 1 and prev_sda == 1 and sda == 0:
                if in_frame:
                    # Repeated START
                    frame_annotations.append(Annotation(
                        start_sample=i,
                        end_sample=i + 1,
                        text="RESTART",
                        row="control",
                        kind="restart",
                        severity="info",
                        channel=self.sda_ch,
                    ))
                else:
                    # START mới
                    frame_start = i
                    frame_annotations = []
                    frame_bytes = []
                    in_frame = True
                    bits = []
                    bit_starts = []

                    frame_annotations.append(Annotation(
                        start_sample=i,
                        end_sample=i + 1,
                        text="START",
                        row="control",
                        kind="start",
                        severity="info",
                        channel=self.sda_ch,
                    ))
                    stats['start_count'] += 1

            # STOP condition: SDA 0→1 khi SCL=1
            elif prev_scl == 1 and scl == 1 and prev_sda == 0 and sda == 1:
                frame_annotations.append(Annotation(
                    start_sample=i,
                    end_sample=i + 1,
                    text="STOP",
                    row="control",
                    kind="stop",
                    severity="info",
                    channel=self.sda_ch,
                ))
                stats['stop_count'] += 1

                # Kết thúc frame
                if in_frame:
                    frame = Frame(
                        protocol=self.protocol_name,
                        start_sample=frame_start,
                        end_sample=i + 1,
                        summary=f"I2C {len(frame_bytes)} bytes",
                        fields={'bytes': frame_bytes},
                        annotations=frame_annotations,
                    )
                    frames.append(frame)
                    annotations.extend(frame_annotations)
                    stats['frames'] += 1

                in_frame = False
                bits = []
                bit_starts = []
                frame_bytes = []

            # Sample SDA tại rising edge SCL
            elif in_frame and prev_scl == 0 and scl == 1:
                bits.append(sda)
                bit_starts.append(i)

                # 8 bits = 1 byte
                if len(bits) == 8:
                    byte_value = 0
                    for bit in bits:
                        byte_value = (byte_value << 1) | bit

                    byte_start = bit_starts[0]
                    byte_end = i

                    # Parse address nếu là byte đầu tiên
                    if len(frame_bytes) == 0:
                        addr = byte_value >> 1
                        rw = 'R' if (byte_value & 1) else 'W'
                        text = f"0x{addr:02X} {rw}"
                        kind = "address"
                    else:
                        text = f"0x{byte_value:02X}"
                        kind = "data"

                    frame_annotations.append(Annotation(
                        start_sample=byte_start,
                        end_sample=byte_end,
                        text=text,
                        row="data",
                        kind=kind,
                        severity="info",
                        channel=self.sda_ch,
                        fields={'byte': byte_value}
                    ))

                    frame_bytes.append(byte_value)
                    stats['bytes_decoded'] += 1
                    current_byte_start = byte_start

                # Bit 9 = ACK/NACK
                elif len(bits) == 9:
                    ack_bit = bits[-1]
                    ack_start = bit_starts[-1]
                    ack_end = i

                    if ack_bit == 0:
                        text = "ACK"
                        kind = "ack"
                        severity = "info"
                    else:
                        text = "NACK"
                        kind = "nack"
                        severity = "warning"

                    frame_annotations.append(Annotation(
                        start_sample=ack_start,
                        end_sample=ack_end,
                        text=text,
                        row="control",
                        kind=kind,
                        severity=severity,
                        channel=self.sda_ch,
                    ))

                    # Reset cho byte tiếp theo
                    bits = []
                    bit_starts = []

            prev_scl = scl
            prev_sda = sda

        # Nếu còn frame chưa đóng (missing STOP)
        if in_frame:
            warnings.append(f"Frame chưa đóng (missing STOP) @ sample {frame_start}")
            frame = Frame(
                protocol=self.protocol_name,
                start_sample=frame_start,
                end_sample=n,
                summary=f"I2C {len(frame_bytes)} bytes (incomplete)",
                fields={'bytes': frame_bytes, 'incomplete': True},
                annotations=frame_annotations,
            )
            frames.append(frame)
            annotations.extend(frame_annotations)
            stats['frames'] += 1

        return DecodeResult(
            protocol=self.protocol_name,
            config=self.config,
            annotations=annotations,
            frames=frames,
            stats=stats,
            warnings=warnings,
        )
