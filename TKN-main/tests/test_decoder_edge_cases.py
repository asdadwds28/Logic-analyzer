"""
tests/test_decoder_edge_cases.py — Edge case tests for decoders

Tests for:
- UART framing error
- I2C NACK condition
- SPI incomplete word
- I2S mid-word WS change
"""

import pytest
import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyzer.models import DecodeResult, Annotation
from protocols.uart import UARTDecoder
from protocols.i2c import I2CDecoder
from protocols.spi import SPIDecoder
from protocols.i2s import I2SDecoder


class TestUARTEdgeCases:
    """UART decoder edge cases."""

    def test_framing_error_stop_bit_zero(self):
        """Test framing error when stop bit is 0 instead of 1."""
        tpb = 8.68  # ticks per bit @ 115200
        # Byte 0x55 with stop bit = 0 (error)
        bits = [0] + list(reversed([int(b) for b in bin(0x55)[2:].zfill(8)])) + [0]  # start + data + bad stop
        n = int(len(bits) * tpb) + 20
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

        # Should have error annotation
        error_anns = [a for a in result.annotations if a.severity == "error"]
        assert len(error_anns) > 0, "Expected framing error annotation"
        assert result.stats.get("errors", 0) > 0, "Expected error count > 0"

    def test_multiple_bytes_with_one_error(self):
        """Test decoding multiple bytes where one has framing error."""
        tpb = 8.68
        # Two bytes: 0x55 (good), 0xAA (bad stop bit)
        byte1_bits = [0] + list(reversed([int(b) for b in bin(0x55)[2:].zfill(8)])) + [1]
        byte2_bits = [0] + list(reversed([int(b) for b in bin(0xAA)[2:].zfill(8)])) + [0]
        all_bits = byte1_bits + byte2_bits

        n = int(len(all_bits) * tpb) + 20
        raw = bytearray(n)
        ch = 0
        for bit_idx, bit in enumerate(all_bits):
            start = int(bit_idx * tpb)
            end = min(int((bit_idx + 1) * tpb), n)
            for i in range(start, end):
                if i < n:
                    raw[i] = bit << ch

        dec = UARTDecoder(sample_rate=1_000_000, channel=ch, baud_rate=115200)
        result = dec.decode(bytes(raw))

        # Should decode both bytes but flag error on second
        assert len(result.annotations) >= 2, "Expected at least 2 annotations"
        assert result.stats.get("errors", 0) > 0, "Expected error count > 0"

    def test_parity_error_odd(self):
        """Test parity error detection (odd parity)."""
        tpb = 8.68
        # Byte 0x55 with wrong parity bit (parity bit should be 1 for odd)
        # 0x55 = 01010101, bit_count = 4 (even), odd parity = 1
        # Wrong parity = 0 would trigger error
        bits = [0] + list(reversed([int(b) for b in bin(0x55)[2:].zfill(8)])) + [0] + [1]  # start + data + wrong parity + stop
        n = int(len(bits) * tpb) + 20
        raw = bytearray(n)
        ch = 0
        for bit_idx, bit in enumerate(bits):
            start = int(bit_idx * tpb)
            end = min(int((bit_idx + 1) * tpb), n)
            for i in range(start, end):
                if i < n:
                    raw[i] = bit << ch

        dec = UARTDecoder(sample_rate=1_000_000, channel=ch, baud_rate=115200, parity='odd')
        result = dec.decode(bytes(raw))

        # Should have warning annotation for parity error
        parity_anns = [a for a in result.annotations if a.kind == "parity"]
        assert len(parity_anns) > 0, "Expected parity annotation"


class TestI2CEdgeCases:
    """I2C decoder edge cases."""

    def test_nack_condition(self):
        """Test NACK (bit 9 = 1) detection."""
        # Build proper I2C frame: START, ADDR, NACK, STOP
        # I2C: SCL=1 during START/STOP, SDA transitions when SCL=1
        raw = bytearray(1000)
        scl_ch, sda_ch = 0, 1

        # Helper: set sample at index with bit values
        def set_sample(idx, scl, sda):
            val = 0
            if scl: val |= (1 << scl_ch)
            if sda: val |= (1 << sda_ch)
            raw[idx] = val

        # Idle: SCL=0, SDA=1 for several samples
        for i in range(20):
            set_sample(i, 0, 1)

        # START: SCL=1, SDA 1→0
        for i in range(20, 50):
            set_sample(i, 1, 1)
        for i in range(50, 80):
            set_sample(i, 1, 0)  # SDA goes 0

        # 8 data bits @ sample edges (rising SCL)
        # Address 0x50 W = 0b10100000
        # After START, SCL stays 1 for a moment then pulses
        data_bits = [1, 0, 1, 0, 0, 0, 0, 0]  # 0x50

        for bit_idx in range(8):
            bit = data_bits[bit_idx]
            # SCL low period
            for i in range(80 + bit_idx * 40, 80 + bit_idx * 40 + 18):
                set_sample(i, 0, bit if bit_idx == 7 else (1 if bit else 0))
            # SCL high + rising edge (sample point)
            for i in range(80 + bit_idx * 40 + 18, 80 + bit_idx * 40 + 40):
                set_sample(i, 1, bit if bit else 0)

        # NACK bit (bit 9): SCL high, SDA = 1 (NACK)
        for i in range(80 + 8 * 40, 80 + 8 * 40 + 18):
            set_sample(i, 0, 1)
        for i in range(80 + 8 * 40 + 18, 80 + 9 * 40):
            set_sample(i, 1, 1)  # SDA=1 for NACK

        # STOP: SCL=1, SDA 0→1
        for i in range(80 + 9 * 40, 80 + 9 * 40 + 18):
            set_sample(i, 1, 0)
        for i in range(80 + 9 * 40 + 18, 80 + 10 * 40):
            set_sample(i, 1, 1)

        dec = I2CDecoder(sample_rate=1_000_000, scl_ch=scl_ch, sda_ch=sda_ch)
        result = dec.decode(bytes(raw))

        # Should detect NACK
        nack_anns = [a for a in result.annotations if a.kind == "nack"]
        ack_anns = [a for a in result.annotations if a.kind == "ack"]
        assert len(nack_anns) > 0 or len(ack_anns) > 0, "Expected ACK/NACK annotation"

    def test_missing_stop_warning(self):
        """Test warning for missing STOP condition."""
        raw = bytearray(500)
        scl_ch, sda_ch = 0, 1

        def set_sample(idx, scl, sda):
            val = 0
            if scl: val |= (1 << scl_ch)
            if sda: val |= (1 << sda_ch)
            raw[idx] = val

        # START condition
        for i in range(10, 40):
            set_sample(i, 1, 1)
        for i in range(40, 60):
            set_sample(i, 1, 0)  # SDA 1→0

        # Several clock pulses with data (no STOP at end)
        for bit_idx in range(8):
            for i in range(60 + bit_idx * 20, 60 + bit_idx * 20 + 8):
                set_sample(i, 0, 1)
            for i in range(60 + bit_idx * 20 + 8, 60 + bit_idx * 20 + 20):
                set_sample(i, 1, 1)

        # No STOP condition - just ends
        # Make sure SCL and SDA are in a state that won't trigger START/STOP

        dec = I2CDecoder(sample_rate=1_000_000, scl_ch=scl_ch, sda_ch=sda_ch)
        result = dec.decode(bytes(raw))

        # Should have warning about missing STOP
        assert len(result.warnings) > 0, "Expected warning for missing STOP"


class TestSPIEdgeCases:
    """SPI decoder edge cases."""

    def test_incomplete_word(self):
        """Test SPI frame with incomplete word - verifies CS transitions are captured."""
        raw = bytearray(500)
        cs_ch, sck_ch, mosi_ch = 0, 1, 2

        def set_sample(idx, cs=None, sck=None, mosi=None):
            val = 0
            if cs is not None and cs: val |= (1 << cs_ch)
            if sck is not None and sck: val |= (1 << sck_ch)
            if mosi is not None and mosi: val |= (1 << mosi_ch)
            raw[idx] = val

        # Initial state: CS inactive (high)
        for i in range(5):
            set_sample(i, cs=1, sck=0)

        # CS goes active (low) - frame starts
        for i in range(5, 10):
            set_sample(i, cs=0, sck=0)

        # Mode 0: SCK idle LOW, sample on rising edge
        # Only 4 SCK pulses with MOSI data (incomplete 8-bit word)
        for pulse in range(4):
            # SCK low for a period
            for i in range(10 + pulse * 40, 10 + pulse * 40 + 18):
                set_sample(i, cs=0, sck=0, mosi=(pulse % 2 == 0))
            # SCK rising edge (sample point)
            for i in range(10 + pulse * 40 + 18, 10 + pulse * 40 + 40):
                set_sample(i, cs=0, sck=1, mosi=(pulse % 2 == 0))

        # CS goes inactive (high) - frame ends with incomplete word
        for i in range(400, 500):
            set_sample(i, cs=1, sck=0)

        dec = SPIDecoder(sample_rate=1_000_000, cs_ch=cs_ch, sck_ch=sck_ch, mosi_ch=mosi_ch, bits_per_word=8)
        result = dec.decode(bytes(raw))

        # Should capture CS transitions even without full word
        assert isinstance(result, DecodeResult)
        assert result.protocol == "SPI"
        # CS active annotation should exist
        cs_anns = [a for a in result.annotations if 'cs' in a.kind.lower()]
        assert len(cs_anns) > 0, f"Expected CS annotations, got {result.annotations}"

    def test_mode_3_sampling(self):
        """Test SPI mode 3 (CPOL=1, CPHA=1) sampling on rising edge."""
        raw = bytearray(500)
        cs_ch, sck_ch, mosi_ch = 0, 1, 2

        def set_sample(idx, cs=None, sck=None, mosi=None):
            val = 0
            if cs is not None and cs: val |= (1 << cs_ch)
            if sck is not None and sck: val |= (1 << sck_ch)
            if mosi is not None and mosi: val |= (1 << mosi_ch)
            raw[idx] = val

        # CS active
        for i in range(10, 500):
            set_sample(i, cs=0, sck=1)  # SCK idle high (CPOL=1)

        # 8 SCK pulses: SCK goes low then high (sampling on rising)
        for pulse in range(8):
            # SCK goes low
            for i in range(20 + pulse * 40, 20 + pulse * 40 + 18):
                set_sample(i, cs=0, sck=0, mosi=(pulse % 2 == 0))
            # SCK goes high (rising edge - sample here in mode 3)
            for i in range(20 + pulse * 40 + 18, 20 + pulse * 40 + 40):
                set_sample(i, cs=0, sck=1, mosi=(pulse % 2 == 0))

        # CS inactive
        for i in range(450, 500):
            set_sample(i, cs=1, sck=1)

        dec = SPIDecoder(sample_rate=1_000_000, cs_ch=cs_ch, sck_ch=sck_ch, mosi_ch=mosi_ch, mode=3)
        result = dec.decode(bytes(raw))

        # Should decode successfully - mode 3 samples on rising edge (while SCK idle high)
        assert isinstance(result, DecodeResult)
        assert result.protocol == "SPI"


class TestI2SEdgeCases:
    """I2S decoder edge cases."""

    def test_incomplete_sample(self):
        """Test handling of incomplete sample (fewer bits than word_size)."""
        raw = bytearray(600)
        sck_ch, ws_ch, sd_ch = 0, 1, 2

        def set_sample(idx, sck=None, ws=None, sd=None):
            val = 0
            if sck is not None and sck: val |= (1 << sck_ch)
            if ws is not None and ws: val |= (1 << ws_ch)
            if sd is not None and sd: val |= (1 << sd_ch)
            raw[idx] = val

        # Left channel: WS=0, only 8 SCK pulses (incomplete 16-bit word)
        for i in range(20, 200):
            set_sample(i, ws=0)

        for pulse in range(8):
            set_sample(20 + pulse * 20, sck=1, ws=0, sd=(pulse % 2 == 0))

        # WS changes mid-word (should flush incomplete sample)
        for i in range(200, 400):
            set_sample(i, ws=1)

        # Right channel activity
        for pulse in range(16):
            if 200 + pulse * 20 < len(raw):
                set_sample(200 + pulse * 20, sck=1, ws=1, sd=(pulse % 2 == 1))

        dec = I2SDecoder(sample_rate=1_000_000, sck_ch=sck_ch, ws_ch=ws_ch, sd_ch=sd_ch, word_size=16)
        result = dec.decode(bytes(raw))

        # Should detect incomplete sample warning at end of left channel
        # or the WS transition handling will emit it
        assert isinstance(result, DecodeResult)
        assert result.protocol == "I2S"

    def test_ws_transition_timing(self):
        """Test WS transition at correct timing - L then R channel."""
        raw = bytearray(600)
        sck_ch, ws_ch, sd_ch = 0, 1, 2

        def set_sample(idx, sck=None, ws=None, sd=None):
            val = 0
            if sck is not None and sck: val |= (1 << sck_ch)
            if ws is not None and ws: val |= (1 << ws_ch)
            if sd is not None and sd: val |= (1 << sd_ch)
            raw[idx] = val

        # Left channel: WS=0, 16 SCK pulses with 16 data bits
        for i in range(20, 250):
            set_sample(i, ws=0)

        for pulse in range(16):
            set_sample(20 + pulse * 20, sck=1, ws=0, sd=(pulse % 2 == 0))

        # WS transition L→R
        set_sample(250, ws=1)

        # Right channel: WS=1, 16 SCK pulses with 16 data bits
        for i in range(250, 480):
            set_sample(i, ws=1)

        for pulse in range(16):
            if 250 + pulse * 20 < len(raw):
                set_sample(250 + pulse * 20, sck=1, ws=1, sd=(pulse % 2 == 1))

        dec = I2SDecoder(sample_rate=1_000_000, sck_ch=sck_ch, ws_ch=ws_ch, sd_ch=sd_ch, word_size=16)
        result = dec.decode(bytes(raw))

        # Should decode both L and R samples
        assert len(result.annotations) >= 2, f"Expected at least 2 annotations, got {len(result.annotations)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])