"""
analyzer/exporter.py — Export decoded data to CSV/JSON

Hỗ trợ xuất DecodeResult thành:
- CSV: timestamp, protocol, channel, frame_data, annotation
- JSON: structured format với metadata
"""

import json
import csv
from typing import List, Dict, Any
from datetime import datetime
from .models import DecodeResult, Annotation, Frame


class ExportFormat:
    """Export format constants."""
    CSV = "csv"
    JSON = "json"


class ProtocolExporter:
    """Export DecodeResult to various formats."""

    def __init__(self, sample_rate: int = 1_000_000):
        self.sample_rate = sample_rate

    def _sample_to_time_ms(self, sample_idx: int) -> float:
        """Convert sample index to time in milliseconds."""
        return (sample_idx / self.sample_rate) * 1000

    def export_to_csv(self, results: List[DecodeResult], filepath: str) -> None:
        """
        Export DecodeResult list to CSV.

        CSV columns:
        - timestamp_ms: Time in milliseconds
        - protocol: Protocol name (UART, I2C, SPI, I2S)
        - channel: Channel index
        - frame_type: Type of frame/annotation (byte, start, stop, ack, etc.)
        - data_hex: Hex representation of data
        - data_ascii: ASCII representation (if applicable)
        - annotation_text: Full annotation text
        - severity: info, warning, error
        - sample_start: Start sample index
        - sample_end: End sample index
        """
        rows = []

        for result in results:
            protocol = result.protocol
            config = result.config

            # Add annotation rows
            for ann in result.annotations:
                time_ms = self._sample_to_time_ms(ann.start_sample)

                # Extract data from fields if available
                data_hex = ""
                data_ascii = ""

                if "byte_value" in ann.fields:
                    byte_val = ann.fields["byte_value"]
                    data_hex = f"0x{byte_val:02X}"
                    if 32 <= byte_val <= 126:
                        data_ascii = chr(byte_val)

                channel = ann.channel if ann.channel is not None else ""

                rows.append({
                    "timestamp_ms": f"{time_ms:.3f}",
                    "protocol": protocol,
                    "channel": channel,
                    "frame_type": ann.kind,
                    "data_hex": data_hex,
                    "data_ascii": data_ascii,
                    "annotation_text": ann.text,
                    "severity": ann.severity,
                    "sample_start": ann.start_sample,
                    "sample_end": ann.end_sample,
                    "row": ann.row,
                })

        # Write CSV
        if not rows:
            return

        fieldnames = [
            "timestamp_ms", "protocol", "channel", "frame_type",
            "data_hex", "data_ascii", "annotation_text", "severity",
            "sample_start", "sample_end", "row"
        ]

        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    def export_to_json(self, results: List[DecodeResult], filepath: str) -> None:
        """
        Export DecodeResult list to JSON.

        Structure:
        {
            "metadata": {
                "export_time": "2026-05-21T06:38:16Z",
                "sample_rate": 1000000,
                "protocols": ["UART", "I2C"]
            },
            "results": [
                {
                    "protocol": "UART",
                    "config": {...},
                    "stats": {...},
                    "warnings": [...],
                    "annotations": [...],
                    "frames": [...]
                }
            ]
        }
        """
        export_data = {
            "metadata": {
                "export_time": datetime.utcnow().isoformat() + "Z",
                "sample_rate": self.sample_rate,
                "protocols": list(set(r.protocol for r in results)),
                "total_results": len(results),
            },
            "results": []
        }

        for result in results:
            result_dict = {
                "protocol": result.protocol,
                "config": result.config,
                "stats": result.stats,
                "warnings": result.warnings,
                "annotations": [
                    {
                        "start_sample": ann.start_sample,
                        "end_sample": ann.end_sample,
                        "start_time_ms": self._sample_to_time_ms(ann.start_sample),
                        "end_time_ms": self._sample_to_time_ms(ann.end_sample),
                        "text": ann.text,
                        "kind": ann.kind,
                        "severity": ann.severity,
                        "row": ann.row,
                        "channel": ann.channel,
                        "fields": ann.fields,
                    }
                    for ann in result.annotations
                ],
                "frames": [
                    {
                        "protocol": frame.protocol,
                        "start_sample": frame.start_sample,
                        "end_sample": frame.end_sample,
                        "start_time_ms": self._sample_to_time_ms(frame.start_sample),
                        "end_time_ms": self._sample_to_time_ms(frame.end_sample),
                        "summary": frame.summary,
                        "fields": frame.fields,
                        "annotation_count": len(frame.annotations),
                    }
                    for frame in result.frames
                ],
            }
            export_data["results"].append(result_dict)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

    def export(
        self,
        results: List[DecodeResult],
        filepath: str,
        format: str = ExportFormat.CSV
    ) -> None:
        """
        Export DecodeResult to file.

        Args:
            results: List of DecodeResult
            filepath: Output file path
            format: "csv" or "json"
        """
        if format == ExportFormat.CSV:
            self.export_to_csv(results, filepath)
        elif format == ExportFormat.JSON:
            self.export_to_json(results, filepath)
        else:
            raise ValueError(f"Unsupported format: {format}")
