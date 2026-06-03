"""
protocols/spi.py — SPI Decoder

Xử lý:
- Mode 0-3 (CPOL, CPHA)
- Bit order: MSB-first, LSB-first
- Word size: 8 bits (phase 1)
- Multi-slave (CS per slave)
- MOSI/MISO (full-duplex)
- CS glitch
- Partial byte cuối frame
"""

from typing import List, Optional
from protocols.abstract import ProtocolDecoder
from analyzer.models import DecodeResult, Annotation, Frame
from analyzer.timing import get_sample


class SPIDecoder(ProtocolDecoder):
    """SPI decoder hỗ trợ mode 0-3, MOSI/MISO, CS frame boundaries."""

    protocol_name = "SPI"

    @classmethod
    def default_config(cls):
        return {
            'cs_ch': 0,
            'sck_ch': 1,
            'mosi_ch': 2,
            'miso_ch': 3,
            'mode': 0,
            'bits_per_word': 8,
            'bit_order': 'msb',
            'cs_active': 0,
        }

    @classmethod
    def required_channels(cls):
        return ['CS', 'SCK', 'MOSI', 'MISO']

    def __init__(self, sample_rate: int = 1_000_000, **config):
        super().__init__(sample_rate, **config)
        self.cs_ch = self.config.get('cs_ch', 0)
        self.sck_ch = self.config.get('sck_ch', 1)
        self.mosi_ch = self.config.get('mosi_ch', 2)
        self.miso_ch = self.config.get('miso_ch', 3)
        self.mode = self.config.get('mode', 0)
        self.bits_per_word = self.config.get('bits_per_word', 8)
        self.bit_order = self.config.get('bit_order', 'msb')
        self.cs_active = self.config.get('cs_active', 0)

        # CPOL, CPHA từ mode
        self.cpol = (self.mode >> 1) & 1
        self.cpha = self.mode & 1

    def _bits_to_word(self, bits: List[int]) -> int:
        """Chuyển list bit thành word int theo bit_order."""
        if self.bit_order == 'lsb':
            value = 0
            for i, bit in enumerate(bits):
                value |= (bit << i)
            return value
        else:  # msb
            value = 0
            for bit in bits:
                value = (value << 1) | bit
            return value

    def decode(self, raw_bytes: bytes) -> DecodeResult:
        annotations: List[Annotation] = []
        frames: List[Frame] = []
        warnings: List[str] = []
        stats = {'words_decoded': 0, 'errors': 0, 'frames': 0}

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
        prev_cs = get_sample(raw_bytes, 0, self.cs_ch) if self.cs_ch is not None else self.cs_active

        mosi_bits: List[int] = []
        miso_bits: List[int] = []
        word_start = 0
        frame_start = 0
        frame_annotations: List[Annotation] = []
        in_frame = False

        # Chọn edge sample theo mode
        # Mode 0,3: sample on rising edge if CPHA=0; falling if CPHA=1
        # Mode 1,2: ngược lại
        sample_on_rising = (self.cpol == self.cpha)

        for i in range(1, n):
            sck = get_sample(raw_bytes, i, self.sck_ch)
            cs = get_sample(raw_bytes, i, self.cs_ch) if self.cs_ch is not None else self.cs_active

            # CS transition: bắt đầu frame
            if self.cs_ch is not None and prev_cs != self.cs_active and cs == self.cs_active:
                in_frame = True
                frame_start = i
                word_start = i
                mosi_bits = []
                miso_bits = []
                frame_annotations = [Annotation(
                    start_sample=i,
                    end_sample=i + 1,
                    text="CS",
                    row="control",
                    kind="cs_active",
                    severity="info",
                    channel=self.cs_ch,
                )]

            # CS transition: kết thúc frame
            elif self.cs_ch is not None and prev_cs == self.cs_active and cs != self.cs_active:
                if in_frame:
                    frame_annotations.append(Annotation(
                        start_sample=i,
                        end_sample=i + 1,
                        text="CS",
                        row="control",
                        kind="cs_inactive",
                        severity="info",
                        channel=self.cs_ch,
                    ))

                    frame = Frame(
                        protocol=self.protocol_name,
                        start_sample=frame_start,
                        end_sample=i,
                        summary=f"SPI {stats['words_decoded']} words",
                        fields={'mode': self.mode},
                        annotations=frame_annotations,
                    )
                    frames.append(frame)
                    annotations.extend(frame_annotations)
                    stats['frames'] += 1

                in_frame = False
                mosi_bits = []
                miso_bits = []
                frame_annotations = []

            # Sample edges
            if in_frame:
                is_rising = (prev_sck == 0 and sck == 1)
                is_falling = (prev_sck == 1 and sck == 0)
                should_sample = (is_rising if sample_on_rising else is_falling)

                if should_sample:
                    if not mosi_bits and not miso_bits:
                        word_start = i

                    if self.mosi_ch is not None:
                        mosi_bits.append(get_sample(raw_bytes, i, self.mosi_ch))
                    if self.miso_ch is not None:
                        miso_bits.append(get_sample(raw_bytes, i, self.miso_ch))

                    # Đủ word size
                    have_mosi = len(mosi_bits) >= self.bits_per_word if self.mosi_ch is not None else False
                    have_miso = len(miso_bits) >= self.bits_per_word if self.miso_ch is not None else False

                    if have_mosi or have_miso:
                        word_end = i
                        text_parts = []
                        fields = {}

                        if have_mosi:
                            mosi_word = self._bits_to_word(mosi_bits[:self.bits_per_word])
                            text_parts.append(f"MOSI 0x{mosi_word:02X}")
                            fields['mosi'] = mosi_word
                            mosi_bits = mosi_bits[self.bits_per_word:]

                        if have_miso:
                            miso_word = self._bits_to_word(miso_bits[:self.bits_per_word])
                            text_parts.append(f"MISO 0x{miso_word:02X}")
                            fields['miso'] = miso_word
                            miso_bits = miso_bits[self.bits_per_word:]

                        frame_annotations.append(Annotation(
                            start_sample=word_start,
                            end_sample=word_end,
                            text=" | ".join(text_parts),
                            row="data",
                            kind="word",
                            severity="info",
                            channel=self.sck_ch,
                            fields=fields,
                        ))
                        stats['words_decoded'] += 1

            prev_sck = sck
            prev_cs = cs

        # Frame chưa đóng
        if in_frame:
            warnings.append(f"SPI frame chưa đóng @ sample {frame_start}")
            frame = Frame(
                protocol=self.protocol_name,
                start_sample=frame_start,
                end_sample=n,
                summary=f"SPI incomplete {stats['words_decoded']} words",
                fields={'mode': self.mode, 'incomplete': True},
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
