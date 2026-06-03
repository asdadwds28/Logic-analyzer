"""
tests/run_decoder_smoke.py — no-pytest decoder verification
Chạy: python3 tests/run_decoder_smoke.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from analyzer import AnalyzerService, AnnotationAdapter
from analyzer.models import DecodeResult, Annotation
from protocols.uart import UARTDecoder
from protocols.i2c import I2CDecoder
from protocols.spi import SPIDecoder
from protocols.i2s import I2SDecoder


def check(name, cond):
    if not cond:
        raise AssertionError(name)
    print(f"OK  {name}")


def main():
    svc = AnalyzerService(sample_rate=1_000_000, num_channels=8)
    check("AnalyzerService init", svc.sample_rate == 1_000_000)

    idle = b"\xff" * 20
    for cls, proto, kwargs in [
        (UARTDecoder, "UART", {"channel": 0, "baud_rate": 115200}),
        (I2CDecoder, "I2C", {"scl_ch": 0, "sda_ch": 1}),
        (SPIDecoder, "SPI", {"cs_ch": 0, "sck_ch": 1, "mosi_ch": 2, "miso_ch": 3}),
        (I2SDecoder, "I2S", {"sck_ch": 0, "ws_ch": 1, "sd_ch": 2}),
    ]:
        dec = cls(sample_rate=1_000_000, **kwargs)
        result = dec.decode(idle)
        check(f"{proto} returns DecodeResult", isinstance(result, DecodeResult))
        check(f"{proto} protocol name", result.protocol == proto)
        check(f"{proto} stats dict", isinstance(result.stats, dict))

    result = DecodeResult(
        protocol="UART",
        config={},
        annotations=[Annotation(start_sample=0, end_sample=10, text="TEST", row="data", kind="byte")],
        frames=[],
        stats={},
        warnings=[],
    )
    gui = AnnotationAdapter().flatten_results([result])
    check("Adapter flatten", len(gui) == 1 and gui[0]["text"] == "TEST")

    forced = svc.decode_with_config(idle, "UART", {"TX": 0}, {"baud_rate": 115200})
    check("Service forced UART", forced.protocol == "UART")

    print("\nALL SMOKE TESTS PASSED")


if __name__ == "__main__":
    main()
