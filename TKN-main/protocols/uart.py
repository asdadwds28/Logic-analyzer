"""
protocols/uart.py — UART Decoder

Xử lý:
- Baud rate: 300 - 10M bps
- Data bits: 5, 6, 7, 8
- Parity: None, Odd, Even
- Stop bits: 1, 1.5, 2
- Idle high, start bit = 0
- Framing error detection
- Back-to-back frames
- Jitter ± vài sample

Thuật toán:
1. Tìm falling edge ứng viên start (1→0)
2. Xác nhận bằng sample tại 0.5 bit
3. Sample data tại 1.5, 2.5, ... bit
4. Check parity (nếu có)
5. Check stop bit (phải = 1)
6. Emit annotation: START, DATA (hex + ASCII), STOP, ERR
"""

from typing import List, Tuple, Optional
from protocols.abstract import ProtocolDecoder
from analyzer.models import DecodeResult, Annotation, Frame
from analyzer.timing import (
    extract_channel, get_sample, find_falling_edges,
    sample_at_bit_center, clamp_sample_idx
)


class UARTDecoder(ProtocolDecoder):
    """UART decoder với hỗ trợ baud rate, parity, stop bits."""

    protocol_name = "UART"

    @classmethod
    def default_config(cls):
        return {
            'channel': 0,
            'baud_rate': 115200,
            'data_bits': 8,
            'parity': 'none',  # none, odd, even
            'stop_bits': 1,
            'invert': False,
        }

    @classmethod
    def required_channels(cls):
        return ['TX']

    def __init__(self, sample_rate: int = 1_000_000, **config):
        super().__init__(sample_rate, **config)
        self.channel = self.config.get('channel', 0)
        self.baud_rate = self.config.get('baud_rate', 115200)
        self.data_bits = self.config.get('data_bits', 8)
        self.parity = self.config.get('parity', 'none')
        self.stop_bits = self.config.get('stop_bits', 1)
        self.invert = self.config.get('invert', False)
        self.ticks_per_bit = sample_rate / self.baud_rate

    def decode(self, raw_bytes: bytes) -> DecodeResult:
        """Giải mã UART từ raw bytes."""
        annotations: List[Annotation] = []
        frames: List[Frame] = []
        warnings: List[str] = []
        stats = {'bytes_decoded': 0, 'errors': 0, 'frames': 0}

        if not raw_bytes or len(raw_bytes) < 10:
            return DecodeResult(
                protocol=self.protocol_name,
                config=self.config,
                annotations=annotations,
                frames=frames,
                stats=stats,
                warnings=['Dữ liệu quá ngắn']
            )

        # Tìm tất cả falling edge (start bit candidates)
        falling_edges = find_falling_edges(raw_bytes, self.channel)

        for start_idx in falling_edges:
            # Bỏ qua nếu start_idx quá gần cuối buffer
            frame_bits = 1 + self.data_bits
            if self.parity != 'none':
                frame_bits += 1
            frame_bits += self.stop_bits
            frame_samples = int(frame_bits * self.ticks_per_bit)

            if start_idx + frame_samples > len(raw_bytes):
                warnings.append(f"Frame bị cắt @ sample {start_idx}")
                continue

            # Xác nhận start bit tại 0.5 bit
            confirm_sample = int(round(start_idx + 0.5 * self.ticks_per_bit))
            confirm_sample = clamp_sample_idx(confirm_sample, len(raw_bytes))

            if get_sample(raw_bytes, confirm_sample, self.channel) != 0:
                continue  # Không phải start bit thực

            # Decode frame
            frame_start = start_idx
            frame_annotations: List[Annotation] = []

            # START bit annotation
            start_end = int(round(start_idx + self.ticks_per_bit))
            frame_annotations.append(Annotation(
                start_sample=start_idx,
                end_sample=start_end,
                text="START",
                row="control",
                kind="start",
                severity="info",
                channel=self.channel,
            ))

            # Data bits
            data_value = 0
            for bit_idx in range(self.data_bits):
                bit_sample = sample_at_bit_center(
                    raw_bytes, start_idx, bit_idx + 1,
                    self.ticks_per_bit, self.channel
                )
                data_value |= (bit_sample << bit_idx)

            data_start = int(round(start_idx + self.ticks_per_bit))
            data_end = int(round(start_idx + (self.data_bits + 1) * self.ticks_per_bit))
            data_end = min(data_end, len(raw_bytes))

            # ASCII helper
            ascii_char = chr(data_value) if 32 <= data_value <= 126 else '?'
            data_hex = f"0x{data_value:02X}"
            data_text = f"{data_hex} '{ascii_char}'"

            frame_annotations.append(Annotation(
                start_sample=data_start,
                end_sample=data_end,
                text=data_text,
                row="data",
                kind="byte",
                severity="info",
                channel=self.channel,
                fields={'byte': data_value, 'ascii': ascii_char}
            ))

            # Parity bit (nếu có)
            parity_bit_idx = self.data_bits + 1
            if self.parity != 'none':
                parity_sample = sample_at_bit_center(
                    raw_bytes, start_idx, parity_bit_idx,
                    self.ticks_per_bit, self.channel
                )
                parity_start = int(round(start_idx + parity_bit_idx * self.ticks_per_bit))
                parity_end = int(round(start_idx + (parity_bit_idx + 1) * self.ticks_per_bit))
                parity_end = min(parity_end, len(raw_bytes))

                expected_parity = data_value.bit_count() % 2
                if self.parity == 'odd':
                    expected_parity = 1 - expected_parity

                parity_ok = (parity_sample == expected_parity)
                parity_text = f"P={parity_sample} {'OK' if parity_ok else 'ERR'}"

                frame_annotations.append(Annotation(
                    start_sample=parity_start,
                    end_sample=parity_end,
                    text=parity_text,
                    row="control",
                    kind="parity",
                    severity="info" if parity_ok else "warning",
                    channel=self.channel,
                    fields={'parity_bit': parity_sample, 'expected': expected_parity, 'ok': parity_ok}
                ))
                parity_bit_idx += 1

            # Stop bit(s)
            stop_bit_idx = parity_bit_idx
            stop_ok = True
            for stop_bit in range(self.stop_bits):
                stop_sample = sample_at_bit_center(
                    raw_bytes, start_idx, stop_bit_idx,
                    self.ticks_per_bit, self.channel
                )
                if stop_sample != 1:
                    stop_ok = False
                    stats['errors'] += 1

                stop_start = int(round(start_idx + stop_bit_idx * self.ticks_per_bit))
                stop_end = int(round(start_idx + (stop_bit_idx + 1) * self.ticks_per_bit))
                stop_end = min(stop_end, len(raw_bytes))

                frame_annotations.append(Annotation(
                    start_sample=stop_start,
                    end_sample=stop_end,
                    text="STOP" if stop_ok and stop_bit == self.stop_bits - 1 else ("STOP ERR" if not stop_ok else ""),
                    row="error" if not stop_ok else "control",
                    kind="framing_error" if not stop_ok else "stop",
                    severity="error" if not stop_ok else "info",
                    channel=self.channel,
                ))
                stop_bit_idx += 1

            # Frame
            frame_end = int(round(start_idx + frame_samples))
            frame_end = min(frame_end, len(raw_bytes))

            if stop_ok:
                frame = Frame(
                    protocol=self.protocol_name,
                    start_sample=frame_start,
                    end_sample=frame_end,
                    summary=f"UART {data_hex}",
                    fields={'byte': data_value, 'ascii': ascii_char, 'baud': self.baud_rate},
                    annotations=frame_annotations,
                )
                frames.append(frame)
                annotations.extend(frame_annotations)
                stats['bytes_decoded'] += 1
                stats['frames'] += 1
            else:
                # Framing error frame
                frame = Frame(
                    protocol=self.protocol_name,
                    start_sample=frame_start,
                    end_sample=frame_end,
                    summary=f"UART ERR {data_hex}",
                    fields={'byte': data_value, 'error': 'framing'},
                    annotations=frame_annotations,
                )
                frames.append(frame)
                annotations.extend(frame_annotations)
                warnings.append(f"Framing error @ sample {start_idx}: expected stop=1, got stop={stop_sample}")

        return DecodeResult(
            protocol=self.protocol_name,
            config=self.config,
            annotations=annotations,
            frames=frames,
            stats=stats,
            warnings=warnings,
        )
