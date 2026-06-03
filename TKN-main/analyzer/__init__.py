"""
analyzer/ — Backend decode nội bộ cho Logic Analyzer

Cung cấp:
- ProtocolDetector: phát hiện giao thức từ tín hiệu
- ProtocolDecoder: giải mã tín hiệu theo từng protocol
- AnnotationAdapter: chuyển đổi kết quả sang format GUI
- AnalyzerService: facade cho GUI
"""

from .models import Annotation, Frame, DecodeResult, DetectionCandidate
from .detector import ProtocolDetector
from .service import AnalyzerService
from .adapters import AnnotationAdapter
from .exporter import ProtocolExporter
from .errors import DecodeError, DetectorError

__all__ = [
    'Annotation',
    'Frame',
    'DecodeResult',
    'DetectionCandidate',
    'ProtocolDetector',
    'AnalyzerService',
    'AnnotationAdapter',
    'ProtocolExporter',
    'DecodeError',
    'DetectorError',
]
