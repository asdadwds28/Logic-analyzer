"""
analyzer/models.py — Data models chuẩn cho decoder

Các dataclass dùng chung cho:
- DetectionCandidate: kết quả từ ProtocolDetector
- Annotation: đơn vị nhỏ nhất của decode output
- Frame: nhóm các annotation thành frame logic
- DecodeResult: toàn bộ kết quả decode của một protocol
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class DetectionCandidate:
    """
    Kết quả từ ProtocolDetector - một ứng viên giao thức được phát hiện.

    Attributes:
        protocol: Tên giao thức (UART, I2C, SPI, I2S)
        confidence: Độ tin cậy từ 0.0 đến 1.0
        channels: Ánh xạ channel name -> index (VD: {'scl': 5, 'sda': 4})
        params: Tham số sơ bộ (baud, mode, etc.)
        evidence: Dấu hiệu hỗ trợ phát hiện (dùng cho debug/scoring)
    """
    protocol: str
    confidence: float
    channels: Dict[str, Optional[int]]
    params: Dict[str, Any]
    evidence: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Annotation:
    """
    Đơn vị nhỏ nhất của decode output - một sự kiện giao thức.

    Attributes:
        start_sample: Vị trí bắt đầu (sample index)
        end_sample: Vị trí kết thúc (sample index)
        text: Văn bản hiển thị (hex, ASCII, label)
        row: Phân loại (data, control, error)
        kind: Loại annotation (byte, start, stop, ack, nack, error, etc.)
        severity: Mức độ (info, warning, error)
        channel: Channel liên quan (nếu có)
        fields: Dữ liệu bổ sung (byte value, frame type, etc.)
    """
    start_sample: int
    end_sample: int
    text: str
    row: str = "data"
    kind: str = "byte"
    severity: str = "info"
    channel: Optional[int] = None
    fields: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration_samples(self) -> int:
        """Số sample của annotation này."""
        return self.end_sample - self.start_sample

    @property
    def duration_ms(self) -> float:
        """Thời gian annotation (ms) dựa trên sample_rate."""
        if self.duration_samples <= 0:
            return 0.0
        return self.duration_samples / 1_000_000  # default sample_rate = 1MHz


@dataclass
class Frame:
    """
    Một frame logic - nhóm các annotation thành một đơn vị có nghĩa.

    Ví dụ:
    - I2C START + ADDR + DATA + ACK + STOP = 1 frame
    - SPI CS active + MOSI + MISO + CS inactive = 1 frame

    Attributes:
        protocol: Tên giao thức
        start_sample: Vị trí bắt đầu frame
        end_sample: Vị trí kết thúc frame
        summary: Mô tả ngắn gọn frame
        fields: Dữ liệu frame (address, data bytes, etc.)
        annotations: Danh sách annotation trong frame
        children: Frame con (nếu có nested frames)
    """
    protocol: str
    start_sample: int
    end_sample: int
    summary: str
    fields: Dict[str, Any]
    annotations: List[Annotation]
    children: List["Frame"] = field(default_factory=list)

    @property
    def duration_samples(self) -> int:
        return self.end_sample - self.start_sample


@dataclass
class DecodeResult:
    """
    Toàn bộ kết quả decode của một protocol trên dữ liệu.

    Attributes:
        protocol: Tên giao thức đã decode
        config: Cấu hình decoder sử dụng
        annotations: Danh sách annotation chi tiết
        frames: Danh sách frame logic
        stats: Thống kê decode (byte count, error count, etc.)
        warnings: Danh sách cảnh báo (truncated, glitch, etc.)
    """
    protocol: str
    config: Dict[str, Any]
    annotations: List[Annotation]
    frames: List[Frame]
    stats: Dict[str, Any]
    warnings: List[str]

    @property
    def total_bytes(self) -> int:
        """Tổng số byte được decode."""
        return self.stats.get("bytes_decoded", 0)

    @property
    def error_count(self) -> int:
        """Số lượng lỗi."""
        return self.stats.get("errors", 0)

    @property
    def has_errors(self) -> bool:
        """Có lỗi trong decode không."""
        return self.error_count > 0
