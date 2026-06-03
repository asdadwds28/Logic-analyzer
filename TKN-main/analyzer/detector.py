"""
analyzer/detector.py — ProtocolDetector wrapper around autodetect_fast

Sử dụng autodetect_fast heuristics nhưng trả về DetectionCandidate
có confidence scoring, multiple candidates, evidence.
"""

from typing import List, Optional
from .models import DetectionCandidate
from .errors import DetectorError


class ProtocolDetector:
    """
    Wrapper quanh autodetect_fast heuristics.

    Trả về DetectionCandidate với confidence scoring,
    không chỉ best candidate.
    """

    def __init__(self, sample_rate: int = 1_000_000, num_channels: int = 8):
        self.sample_rate = sample_rate
        self.num_channels = num_channels

    def detect_all(self, raw_bytes: bytes) -> List[DetectionCandidate]:
        """
        Phát hiện tất cả giao thức có trong dữ liệu.

        Args:
            raw_bytes: bytes - mỗi byte chứa 8 channel states

        Returns:
            List[DetectionCandidate] - các ứng viên, sorted by confidence
        """
        if not raw_bytes or len(raw_bytes) < 10:
            return []

        from autodetect_fast import (
            profile_channels, detect_uart, detect_i2c,
            detect_spi, detect_i2s, detect_can, detect_onewire
        )

        candidates = []
        profiles = profile_channels(raw_bytes, self.num_channels)

        # 1. UART
        uart_cfg = detect_uart(profiles, self.sample_rate)
        if uart_cfg:
            candidates.append(DetectionCandidate(
                protocol="UART",
                confidence=uart_cfg.get('confidence', 0.8),
                channels={'TX': uart_cfg['channel']},
                params={'baud_rate': uart_cfg['baud_rate']},
                evidence={'profile': profiles.get(uart_cfg['channel'])}
            ))

        # 2. I2C
        i2c_cfg = detect_i2c(profiles, raw_bytes)
        if i2c_cfg:
            candidates.append(DetectionCandidate(
                protocol="I2C",
                confidence=0.9,
                channels={'SCL': i2c_cfg['scl_ch'], 'SDA': i2c_cfg['sda_ch']},
                params={},
                evidence={
                    'scl_toggles': profiles.get(i2c_cfg['scl_ch'], {}).get('toggles', 0),
                    'sda_toggles': profiles.get(i2c_cfg['sda_ch'], {}).get('toggles', 0)
                }
            ))

        # 3. SPI
        spi_cfg = detect_spi(profiles, raw_bytes)
        if spi_cfg:
            candidates.append(DetectionCandidate(
                protocol="SPI",
                confidence=0.85,
                channels={
                    'CS': spi_cfg['cs_ch'],
                    'SCK': spi_cfg['sck_ch'],
                    'MOSI': spi_cfg['mosi_ch'],
                    'MISO': spi_cfg['miso_ch']
                },
                params={'mode': 0},  # default
                evidence={'cs_idle': profiles.get(spi_cfg['cs_ch'], {}).get('idle_state', 1)}
            ))

        # 4. I2S
        i2s_cfg = detect_i2s(profiles, raw_bytes)
        if i2s_cfg:
            candidates.append(DetectionCandidate(
                protocol="I2S",
                confidence=0.8,
                channels={
                    'SCK': i2s_cfg['sck_ch'],
                    'WS': i2s_cfg['ws_ch'],
                    'SD': i2s_cfg['sd_ch']
                },
                params={'ratio': i2s_cfg.get('ratio', 32)},
                evidence={'ratio': i2s_cfg.get('ratio', 0)}
            ))

        # Sort by confidence
        candidates.sort(key=lambda c: c.confidence, reverse=True)
        return candidates

    def detect_uart(self, raw_bytes: bytes) -> Optional[DetectionCandidate]:
        """Phát hiện UART cụ thể."""
        from autodetect_fast import profile_channels, detect_uart
        profiles = profile_channels(raw_bytes, self.num_channels)
        cfg = detect_uart(profiles, self.sample_rate)
        if cfg:
            return DetectionCandidate(
                protocol="UART",
                confidence=cfg.get('confidence', 0.8),
                channels={'TX': cfg['channel']},
                params={'baud_rate': cfg['baud_rate']},
                evidence={'profile': profiles.get(cfg['channel'])}
            )
        return None

    def detect_i2c(self, raw_bytes: bytes) -> Optional[DetectionCandidate]:
        """Phát hiện I2C cụ thể."""
        from autodetect_fast import profile_channels, detect_i2c
        profiles = profile_channels(raw_bytes, self.num_channels)
        cfg = detect_i2c(profiles, raw_bytes)
        if cfg:
            return DetectionCandidate(
                protocol="I2C",
                confidence=0.9,
                channels={'SCL': cfg['scl_ch'], 'SDA': cfg['sda_ch']},
                params={},
                evidence={
                    'scl_toggles': profiles.get(cfg['scl_ch'], {}).get('toggles', 0),
                    'sda_toggles': profiles.get(cfg['sda_ch'], {}).get('toggles', 0)
                }
            )
        return None

    def detect_spi(self, raw_bytes: bytes) -> Optional[DetectionCandidate]:
        """Phát hiện SPI cụ thể."""
        from autodetect_fast import profile_channels, detect_spi
        profiles = profile_channels(raw_bytes, self.num_channels)
        cfg = detect_spi(profiles, raw_bytes)
        if cfg:
            return DetectionCandidate(
                protocol="SPI",
                confidence=0.85,
                channels={
                    'CS': cfg['cs_ch'],
                    'SCK': cfg['sck_ch'],
                    'MOSI': cfg['mosi_ch'],
                    'MISO': cfg['miso_ch']
                },
                params={'mode': 0},
                evidence={'cs_idle': profiles.get(cfg['cs_ch'], {}).get('idle_state', 1)}
            )
        return None

    def detect_i2s(self, raw_bytes: bytes) -> Optional[DetectionCandidate]:
        """Phát hiện I2S cụ thể."""
        from autodetect_fast import profile_channels, detect_i2s
        profiles = profile_channels(raw_bytes, self.num_channels)
        cfg = detect_i2s(profiles, raw_bytes)
        if cfg:
            return DetectionCandidate(
                protocol="I2S",
                confidence=0.8,
                channels={
                    'SCK': cfg['sck_ch'],
                    'WS': cfg['ws_ch'],
                    'SD': cfg['sd_ch']
                },
                params={'ratio': cfg.get('ratio', 32)},
                evidence={'ratio': cfg.get('ratio', 0)}
            )
        return None