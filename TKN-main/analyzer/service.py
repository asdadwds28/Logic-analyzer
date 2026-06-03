"""
analyzer/service.py — AnalyzerService facade

Entry point chính cho GUI. Quản lý:
- ProtocolDetector (phát hiện giao thức)
- Decoder registry (UART, I2C, SPI, I2S)
- decode_with_config() / autodetect_and_decode()

Usage:
    from analyzer import AnalyzerService
    service = AnalyzerService(sample_rate=1_000_000)
    results = service.autodetect_and_decode(raw_bytes)
"""

from typing import List, Dict, Any, Optional
from .models import DecodeResult, DetectionCandidate
from .detector import ProtocolDetector
from .adapters import AnnotationAdapter
from .exporter import ProtocolExporter


# Decoder registry - explicit mapping, không dynamic scan
DECODER_REGISTRY = {
    'UART': 'protocols.uart.UARTDecoder',
    'I2C': 'protocols.i2c.I2CDecoder',
    'SPI': 'protocols.spi.SPIDecoder',
    'I2S': 'protocols.i2s.I2SDecoder',
}


def _import_decoder(path: str):
    """Import decoder class từ dotted path."""
    module_path, class_name = path.rsplit('.', 1)
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


class AnalyzerService:
    """
    Facade chính cho Logic Analyzer GUI.

    Cung cấp:
    - autodetect_and_decode(): auto-detect + decode tất cả protocol
    - decode_with_config(): decode theo cấu hình cụ thể
    """

    def __init__(self, sample_rate: int = 1_000_000, num_channels: int = 8):
        self.sample_rate = sample_rate
        self.num_channels = num_channels
        self.detector = ProtocolDetector(sample_rate=sample_rate, num_channels=num_channels)
        self.adapter = AnnotationAdapter()
        self._decoders: Dict[str, Any] = {}

    def _get_decoder_class(self, protocol: str):
        """Lấy decoder class từ registry."""
        if protocol in self._decoders:
            return self._decoders[protocol]

        if protocol not in DECODER_REGISTRY:
            raise ValueError(f"Protocol {protocol} không được hỗ trợ")

        decoder_class = _import_decoder(DECODER_REGISTRY[protocol])
        self._decoders[protocol] = decoder_class
        return decoder_class

    def autodetect_and_decode(
        self,
        raw_bytes: bytes,
        enabled_protocols: List[str] = None
    ) -> List[DecodeResult]:
        """
        Phát hiện và giải mã tất cả giao thức trong dữ liệu.

        Args:
            raw_bytes: bytes - dữ liệu thô
            enabled_protocols: list - các protocol được phép (None = tất cả)

        Returns:
            List[DecodeResult] - kết quả decode cho từng protocol
        """
        if enabled_protocols is None:
            enabled_protocols = list(DECODER_REGISTRY.keys())

        results = []

        # Phát hiện tất cả protocol
        candidates = self.detector.detect_all(raw_bytes)

        for candidate in candidates:
            if candidate.protocol not in enabled_protocols:
                continue

            try:
                result = self.decode_with_config(
                    raw_bytes,
                    candidate.protocol,
                    candidate.channels,
                    candidate.params,
                )
                if result.annotations:
                    results.append(result)
            except Exception as e:
                # Skip protocol nếu decode lỗi
                pass

        return results

    def decode_with_config(
        self,
        raw_bytes: bytes,
        protocol: str,
        channels: Dict[str, int],
        params: Dict[str, Any] = None,
    ) -> DecodeResult:
        """
        Giải mã với cấu hình cụ thể.

        Args:
            raw_bytes: bytes - dữ liệu thô
            protocol: str - tên protocol (UART, I2C, SPI, I2S)
            channels: dict - ánh xạ channel name -> index
            params: dict - tham số bổ sung

        Returns:
            DecodeResult - kết quả decode
        """
        decoder_class = self._get_decoder_class(protocol)
        params = params or {}

        # Build config cho decoder
        if protocol == 'UART':
            tx_ch = channels.get('TX', 0)
            config = {
                'channel': tx_ch,
                'baud_rate': params.get('baud_rate', 115200),
                'data_bits': params.get('data_bits', 8),
                'parity': params.get('parity', 'none'),
                'stop_bits': params.get('stop_bits', 1),
            }

        elif protocol == 'I2C':
            config = {
                'scl_ch': channels.get('SCL', 0),
                'sda_ch': channels.get('SDA', 1),
            }

        elif protocol == 'SPI':
            config = {
                'cs_ch': channels.get('CS', 0),
                'sck_ch': channels.get('SCK', 1),
                'mosi_ch': channels.get('MOSI'),
                'miso_ch': channels.get('MISO'),
                'mode': params.get('mode', 0),
                'bits_per_word': params.get('bits_per_word', 8),
                'bit_order': params.get('bit_order', 'msb'),
            }

        elif protocol == 'I2S':
            config = {
                'sck_ch': channels.get('SCK', 0),
                'ws_ch': channels.get('WS', 1),
                'sd_ch': channels.get('SD', 2),
                'word_size': params.get('word_size', 16),
                'format': params.get('format', 'i2s'),
            }

        else:
            config = {}

        decoder = decoder_class(sample_rate=self.sample_rate, **config)
        return decoder.decode(raw_bytes)

    def detect_only(self, raw_bytes: bytes) -> List[DetectionCandidate]:
        """Chỉ phát hiện protocol, không decode."""
        return self.detector.detect_all(raw_bytes)

    def decode_only(
        self,
        raw_bytes: bytes,
        protocol: str,
        **config
    ) -> DecodeResult:
        """
        Giải mã với cấu hình đầy đủ.

        Args:
            raw_bytes: bytes
            protocol: str
            **config: tham số decoder cụ thể
        """
        decoder_class = self._get_decoder_class(protocol)
        decoder = decoder_class(sample_rate=self.sample_rate, **config)
        return decoder.decode(raw_bytes)

    def decode_to_gui(
        self,
        raw_bytes: bytes,
        enabled_protocols: List[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Decode và trả về annotation list sẵn cho GUI.

        Returns:
            List[dict] - [{start, end, text, protocol, row, kind, ...}]
        """
        results = self.autodetect_and_decode(raw_bytes, enabled_protocols)
        return self.adapter.flatten_results(results)