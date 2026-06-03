"""
tests/test_decoders.py — Decoder smoke tests
Chạy: python -m pytest tests/test_decoders.py -v
"""

import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyzer import AnalyzerService
from analyzer.models import DecodeResult, Annotation, Frame


class TestAnalyzerService:
    def test_service_instantiate(self):
        svc = AnalyzerService(sample_rate=1_000_000, num_channels=8)
        assert svc.sample_rate == 1_000_000
        assert svc.num_channels == 8
        assert svc._decoders == {}

    def test_autodetect_empty(self):
        svc = AnalyzerService()
        results = svc.autodetect_and_decode(b'\xff' * 5)
        assert isinstance(results, list)


class TestUARTDecoder:
    def test_decode_idle_data(self):
        from protocols.uart import UARTDecoder
        dec = UARTDecoder(sample_rate=1_000_000, channel=0, baud_rate=115200)
        result = dec.decode(b'\xff' * 10)
        assert isinstance(result, DecodeResult)
        assert result.protocol == "UART"
        assert isinstance(result.annotations, list)
        assert isinstance(result.stats, dict)

    def test_decode_8n1_bytes(self):
        """Mã hóa byte 0x55 (0b01010101) ở 115200 8N1, sample_rate=1MHz."""
        from protocols.uart import UARTDecoder

        # ticks_per_bit = 1e6 / 115200 ≈ 8.68
        tpb = 8.68
        bits = [0] + list(reversed([int(b) for b in bin(0x55)[2:].zfill(8)])) + [1]  # start + data + stop
        n = int(len(bits) * tpb) + 20  # +20 to ensure stop bit + idle gap fit in buffer
        raw = bytearray(n)
        ch = 0
        for bit_idx, bit in enumerate(bits):
            start = int(bit_idx * tpb)
            end = min(int((bit_idx + 1) * tpb), n)
            for i in range(start, end):
                if i < n:
                    raw[i] = bit << ch
        dec = UARTDecoder(sample_rate=1_000_000, channel=ch, baud_rate=115200)
        result = dec.decode(bytes(raw))
        assert len(result.annotations) > 0

    def test_baud_rate_config(self):
        from protocols.uart import UARTDecoder
        dec = UARTDecoder(sample_rate=1_000_000, channel=0, baud_rate=9600)
        assert dec.baud_rate == 9600
        assert dec.ticks_per_bit == pytest.approx(1_000_000 / 9600)


class TestI2CDecoder:
    def test_decode_idle_data(self):
        from protocols.i2c import I2CDecoder
        dec = I2CDecoder(sample_rate=1_000_000, scl_ch=0, sda_ch=1)
        result = dec.decode(b'\xff' * 10)
        assert isinstance(result, DecodeResult)
        assert result.protocol == "I2C"

    def test_config_channels(self):
        from protocols.i2c import I2CDecoder
        dec = I2CDecoder(sample_rate=1_000_000, scl_ch=2, sda_ch=3)
        assert dec.scl_ch == 2
        assert dec.sda_ch == 3


class TestSPIDecoder:
    def test_decode_idle_data(self):
        from protocols.spi import SPIDecoder
        dec = SPIDecoder(sample_rate=1_000_000, cs_ch=0, sck_ch=1, mosi_ch=2)
        result = dec.decode(b'\xff' * 10)
        assert isinstance(result, DecodeResult)
        assert result.protocol == "SPI"

    def test_mode_config(self):
        from protocols.spi import SPIDecoder
        for mode in range(4):
            dec = SPIDecoder(sample_rate=1_000_000, cs_ch=0, sck_ch=1, mosi_ch=2, mode=mode)
            assert dec.mode == mode
            assert dec.cpol == (mode >> 1) & 1
            assert dec.cpha == mode & 1


class TestI2SDecoder:
    def test_decode_idle_data(self):
        from protocols.i2s import I2SDecoder
        dec = I2SDecoder(sample_rate=1_000_000, sck_ch=0, ws_ch=1, sd_ch=2)
        result = dec.decode(b'\xff' * 10)
        assert isinstance(result, DecodeResult)
        assert result.protocol == "I2S"

    def test_word_size_config(self):
        from protocols.i2s import I2SDecoder
        dec = I2SDecoder(sample_rate=1_000_000, sck_ch=0, ws_ch=1, sd_ch=2, word_size=24)
        assert dec.word_size == 24


class TestModels:
    def test_annotation_dataclass(self):
        ann = Annotation(start_sample=0, end_sample=10, text="TEST", row="data", kind="byte")
        assert ann.start_sample == 0
        assert ann.text == "TEST"

    def test_frame_dataclass(self):
        ann = Annotation(start_sample=0, end_sample=10, text="TEST", row="data", kind="byte")
        frame = Frame(protocol="UART", start_sample=0, end_sample=20,
                      summary="test", fields={}, annotations=[ann])
        assert frame.protocol == "UART"
        assert len(frame.annotations) == 1

    def test_decode_result(self):
        result = DecodeResult(
            protocol="UART",
            config={'channel': 0, 'baud_rate': 115200},
            annotations=[],
            frames=[],
            stats={'bytes_decoded': 0},
            warnings=[],
        )
        assert result.protocol == "UART"
        assert len(result.warnings) == 0


class TestAdapter:
    def test_flatten_results(self):
        from analyzer import AnalyzerService, AnnotationAdapter
        from analyzer.models import DecodeResult, Annotation

        result = DecodeResult(
            protocol="UART",
            config={},
            annotations=[
                Annotation(start_sample=0, end_sample=10, text="START", row="control", kind="start"),
                Annotation(start_sample=10, end_sample=80, text="0x41 'A'", row="data", kind="byte"),
            ],
            frames=[],
            stats={},
            warnings=[],
        )
        adapter = AnnotationAdapter()
        gui_list = adapter.flatten_results([result])
        assert len(gui_list) == 2
        assert gui_list[0]['text'] == "START"
        assert gui_list[1]['text'] == "0x41 'A'"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
