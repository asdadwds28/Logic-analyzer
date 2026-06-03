"""
protocols/i2s.py — I2S Decoder

Xử lý:
- SCK/WS/SD
- Left/right frames
- Word length 16/24/32 bits
- WS transition alignment
- Incomplete sample
- Mono stream

Thuật toán:
1. Phát hiện WS edge (L→R hoặc R→L)
2. Lấy mẫu SD tại cạnh lên SCK
3. Gom bits theo word size
4. Emit L/R sample
"""

from typing import List, Optional
from protocols.abstract import ProtocolDecoder
from analyzer.models import DecodeResult, Annotation, Frame
from analyzer.timing import get_sample


class I2SDecoder(ProtocolDecoder):
    """I2S decoder với hỗ trợ word size, L/R channel, WS alignment."""

    protocol_name = "I2S"

    @classmethod
    def default_config(cls):
        return {
            'sck_ch': 0,
            'ws_ch': 1,
            'sd_ch': 2,
            'word_size': 16,
            'format': 'i2s',  # i2s, left_justified
        }

    @classmethod
    def required_channels(cls):
        return ['SCK', 'WS', 'SD']

    def __init__(self, sample_rate: int = 1_000_000, **config):
        super().__init__(sample_rate, **config)
        self.sck_ch = self.config.get('sck_ch', 0)
        self.ws_ch = self.config.get('ws_ch', 1)
        self.sd_ch = self.config.get('sd_ch', 2)
        self.word_size = self.config.get('word_size', 16)
        self.format = self.config.get('format', 'i2s')

    def decode(self, raw_bytes: bytes) -> DecodeResult:
        """Giải mã I2S từ raw bytes."""
        annotations: List[Annotation] = []
        frames: List[Frame] = []
        warnings: List[str] = []
        stats = {'samples_decoded': 0, 'errors': 0, 'frames': 0}

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
        prev_sck = get_sample(raw_bytes, 0, self.sck_ch)
        prev_ws = get_sample(raw_bytes, 0, self.ws_ch)

        sd_bits: List[int] = []
        bit_starts: List[int] = []
        current_channel = 'L'  # L or R
        sample_start = 0
        frame_annotations: List[Annotation] = []
        frame_start = 0
        in_frame = False

        for i in range(1, n):
            sck = get_sample(raw_bytes, i, self.sck_ch)
            ws = get_sample(raw_bytes, i, self.ws_ch)
            sd = get_sample(raw_bytes, i, self.sd_ch)

            # WS transition: channel change
            if prev_ws != ws:
                # Kết thúc sample trước đó nếu có
                if sd_bits and len(sd_bits) > 0:
                    sample_value = self._bits_to_word(sd_bits)
                    sample_hex = f"0x{sample_value:04X}"
                    channel_label = 'L' if current_channel == 'L' else 'R'
                    text = f"{channel_label}: {sample_hex}"

                    frame_annotations.append(Annotation(
                        start_sample=sample_start,
                        end_sample=i,
                        text=text,
                        row="data",
                        kind=f"sample_{channel_label.lower()}",
                        severity="info",
                        channel=self.sd_ch,
                        fields={'channel': channel_label, 'sample': sample_value, 'bits': len(sd_bits)}
                    ))
                    stats['samples_decoded'] += 1
                    sd_bits = []
                    bit_starts = []

                # Bắt đầu channel mới
                current_channel = 'L' if ws == 0 else 'R'
                channel_label = 'L' if current_channel == 'L' else 'R'

                if not in_frame:
                    in_frame = True
                    frame_start = i
                    frame_annotations = []

                frame_annotations.append(Annotation(
                    start_sample=i,
                    end_sample=i + 1,
                    text=f"WS {channel_label}",
                    row="control",
                    kind="ws_transition",
                    severity="info",
                    channel=self.ws_ch,
                    fields={'channel': channel_label}
                ))

            # Sample SD tại rising edge SCK
            if prev_sck == 0 and sck == 1:
                if not sd_bits:
                    sample_start = i

                sd_bits.append(sd)
                bit_starts.append(i)

                # Đủ word size
                if len(sd_bits) >= self.word_size:
                    sample_value = self._bits_to_word(sd_bits[:self.word_size])
                    sample_hex = f"0x{sample_value:04X}"
                    channel_label = 'L' if current_channel == 'L' else 'R'
                    text = f"{channel_label}: {sample_hex}"

                    frame_annotations.append(Annotation(
                        start_sample=sample_start,
                        end_sample=i,
                        text=text,
                        row="data",
                        kind=f"sample_{channel_label.lower()}",
                        severity="info",
                        channel=self.sd_ch,
                        fields={'channel': channel_label, 'sample': sample_value, 'bits': self.word_size}
                    ))
                    stats['samples_decoded'] += 1

                    # Reset cho sample tiếp theo
                    sd_bits = sd_bits[self.word_size:]
                    bit_starts = bit_starts[self.word_size:]

            prev_sck = sck
            prev_ws = ws

        # Frame chưa đóng
        if in_frame:
            if sd_bits:
                warnings.append(f"I2S sample chưa đủ @ sample {sample_start}: {len(sd_bits)}/{self.word_size} bits")

            frame = Frame(
                protocol=self.protocol_name,
                start_sample=frame_start,
                end_sample=n,
                summary=f"I2S {stats['samples_decoded']} samples",
                fields={'word_size': self.word_size, 'incomplete': True},
                annotations=frame_annotations,
            )
            frames.append(frame)
            annotations.extend(frame_annotations)
            stats['frames'] += 1
        elif frame_annotations:
            frame = Frame(
                protocol=self.protocol_name,
                start_sample=frame_start,
                end_sample=n,
                summary=f"I2S {stats['samples_decoded']} samples",
                fields={'word_size': self.word_size},
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

    def _bits_to_word(self, bits: List[int]) -> int:
        """Chuyển list bit thành word int (MSB-first)."""
        value = 0
        for bit in bits:
            value = (value << 1) | bit
        return value
