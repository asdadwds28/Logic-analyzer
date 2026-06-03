"""
protocols/abstract.py — Base class chuẩn hóa cho tất cả decoder

Interface chuẩn:
- decode(raw_bytes: bytes) -> DecodeResult
- default_config() -> dict
- required_channels() -> list[str]
- validate_config() -> list[str]
"""

from typing import Any, Dict, List, Optional
from analyzer.models import DecodeResult, Annotation, Frame


class ProtocolDecoder:
    """
    Base class cho tất cả decoder.

    Interface chuẩn:
    - decode(raw_bytes) -> DecodeResult
    - default_config() -> dict
    - required_channels() -> list[str]
    - validate_config() -> list[str]
    """

    protocol_name: str = "Unknown"

    @classmethod
    def default_config(cls) -> Dict[str, Any]:
        """Trả về cấu hình mặc định cho decoder này."""
        return {}

    @classmethod
    def required_channels(cls) -> List[str]:
        """
        Trả về danh sách tên channel cần cho decoder này.

        Ví dụ:
        - UART: ['TX']
        - I2C: ['SCL', 'SDA']
        - SPI: ['CS', 'SCK', 'MOSI', 'MISO']
        - I2S: ['SCK', 'WS', 'SD']
        """
        return []

    def __init__(self, sample_rate: int = 1_000_000, **config):
        """
        Khởi tạo decoder.

        Args:
            sample_rate: Tần số lấy mẫu (Hz)
            **config: Các tham số cấu hình cụ thể
        """
        self.sample_rate = sample_rate
        self.config = {**self.default_config(), **config}
        self._validate_config()

    def _validate_config(self) -> List[str]:
        """
        Validate cấu hình.

        Returns:
            List[str] - danh sách lỗi (rỗng nếu OK)
        """
        return []

    def decode(self, raw_bytes: bytes) -> DecodeResult:
        """
        Giải mã dữ liệu thô.

        Args:
            raw_bytes: bytes - mỗi byte chứa trạng thái 8 kênh (bit 0-7)

        Returns:
            DecodeResult - toàn bộ kết quả decode

        Raises:
            ValueError: Nếu dữ liệu không hợp lệ
        """
        raise NotImplementedError

    def decode_pretty(self, raw_bytes: bytes) -> List[Dict[str, Any]]:
        """
        Giải mã và trả về danh sách annotation dạng dễ đọc.

        Đây là wrapper quanh decode() để tương thích với GUI cũ.

        Returns:
            List[dict] - [{start, end, text, row, kind, severity}, ...]
        """
        result = self.decode(raw_bytes)
        return [
            {
                'start': ann.start_sample,
                'end': ann.end_sample,
                'text': ann.text,
                'row': ann.row,
                'kind': ann.kind,
                'severity': ann.severity,
                'channel': ann.channel,
            }
            for ann in result.annotations
        ]
