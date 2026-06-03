"""
analyzer/errors.py — Custom exceptions cho decoder

Dùng để phân biệt các loại lỗi khác nhau:
- DecodeError: lỗi khi decode dữ liệu
- DetectorError: lỗi khi phát hiện giao thức
"""


class AnalyzerError(Exception):
    """Base exception cho tất cả lỗi analyzer."""
    pass


class DecodeError(AnalyzerError):
    """
    Lỗi xảy ra trong quá trình decode.

    Attributes:
        protocol: Giao thức đang decode
        sample_idx: Vị trí sample gây lỗi (nếu có)
        details: Mô tả chi tiết lỗi
    """
    def __init__(self, message: str, protocol: str = None, sample_idx: int = None, **kwargs):
        super().__init__(message)
        self.protocol = protocol
        self.sample_idx = sample_idx
        self.details = kwargs


class DetectorError(AnalyzerError):
    """
    Lỗi xảy ra trong quá trình phát hiện giao thức.

    Attributes:
        message: Mô tả lỗi
        protocol: Giao thức đang detect
    """
    pass


class ConfigError(AnalyzerError):
    """Lỗi cấu hình decoder không hợp lệ."""
    pass


class DataError(AnalyzerError):
    """Lỗi dữ liệu đầu vào (không đủ data, format sai, etc.)."""
    pass