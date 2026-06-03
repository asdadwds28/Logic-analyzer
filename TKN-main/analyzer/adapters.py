"""
analyzer/adapters.py — Chuyển DecodeResult sang format GUI

AnnotationAdapter flatten DecodeResult/Frame thành dict list cho PyQt graph rendering.
"""

from typing import List, Dict, Any
from .models import DecodeResult, Annotation


PROTOCOL_COLORS = {
    'UART': '#3a6eff',
    'I2C': '#00b894',
    'SPI': '#fdcb6e',
    'I2S': '#e17055',
}

SEVERITY_COLORS = {
    'info': None,
    'warning': '#f39c12',
    'error': '#e74c3c',
}


class AnnotationAdapter:
    """Chuyển DecodeResult thành list annotation dict cho GUI."""

    def to_gui_format(self, result: DecodeResult) -> List[Dict[str, Any]]:
        """
        Chuyển DecodeResult thành format GUI.

        Returns:
            List[dict] - mỗi dict có:
            - start, end, text
            - protocol, row, kind, severity
            - color, tooltip, channel
        """
        color = PROTOCOL_COLORS.get(result.protocol, '#ffffff')
        gui_items = []

        for ann in result.annotations:
            ann_color = SEVERITY_COLORS.get(ann.severity) or color
            tooltip = self._make_tooltip(result.protocol, ann)

            gui_items.append({
                'start': ann.start_sample,
                'end': ann.end_sample,
                'text': ann.text,
                'protocol': result.protocol,
                'row': ann.row,
                'kind': ann.kind,
                'severity': ann.severity,
                'channel': ann.channel,
                'color': ann_color,
                'tooltip': tooltip,
                'fields': ann.fields,
            })

        return gui_items

    def flatten_results(self, results: List[DecodeResult]) -> List[Dict[str, Any]]:
        """Flatten nhiều DecodeResult thành 1 list cho GUI."""
        all_items = []
        for result in results:
            all_items.extend(self.to_gui_format(result))
        all_items.sort(key=lambda item: (item['start'], item['protocol'], item['row']))
        return all_items

    def _make_tooltip(self, protocol: str, ann: Annotation) -> str:
        """Tạo tooltip text cho annotation."""
        parts = [f"{protocol} - {ann.kind}"]
        if ann.channel is not None:
            parts.append(f"CH{ann.channel + 1}")
        parts.append(f"Samples: {ann.start_sample}-{ann.end_sample}")
        if ann.fields:
            for key, value in ann.fields.items():
                parts.append(f"{key}: {value}")
        return "\n".join(parts)
