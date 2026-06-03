from autodetect_fast import profile_channels, detect_uart, detect_i2c, detect_spi, detect_can, detect_i2s, detect_onewire
from analyzer import AnalyzerService, AnnotationAdapter


class Analyzer:
    """Wrapper quanh AnalyzerService để tương thích với GUI cũ."""

    def __init__(self, sample_rate=1_000_000, num_channels=8):
        self.sample_rate = sample_rate
        self.num_channels = num_channels
        self.data = None
        self._service = AnalyzerService(sample_rate=sample_rate, num_channels=num_channels)
        self._adapter = AnnotationAdapter()
        self._last_results = []
        self._decoders = {}

    def load_data(self, data: bytes):
        """Load raw byte array data. Each byte represents states for channels 0-7."""
        self.data = data

    def auto_detect_channels(self):
        """
        Phát hiện protocol và cấu hình channel.
        Trả về dict mapping protocol -> config.
        Dùng detect_* từ autodetect_fast + build channels cho service.
        """
        if not self.data:
            return {}

        profiles = profile_channels(self.data, self.num_channels)
        identified = {}

        # 1. I2C
        i2c_config = detect_i2c(profiles, self.data)
        if i2c_config:
            identified['I2C'] = {
                'protocol': 'I2C',
                'channels': {'SCL': i2c_config['scl_ch'], 'SDA': i2c_config['sda_ch']},
                'params': {},
            }
            profiles.pop(i2c_config['scl_ch'], None)
            profiles.pop(i2c_config['sda_ch'], None)

        # 2. SPI
        spi_config = detect_spi(profiles, self.data)
        if spi_config:
            identified['SPI'] = {
                'protocol': 'SPI',
                'channels': {
                    'CS': spi_config['cs_ch'],
                    'SCK': spi_config['sck_ch'],
                    'MOSI': spi_config.get('mosi_ch'),
                    'MISO': spi_config.get('miso_ch'),
                },
                'params': {},
            }
            profiles.pop(spi_config['cs_ch'], None)
            profiles.pop(spi_config['sck_ch'], None)
            if spi_config.get('mosi_ch') is not None:
                profiles.pop(spi_config['mosi_ch'], None)
            if spi_config.get('miso_ch') is not None:
                profiles.pop(spi_config['miso_ch'], None)

        # 3. UART
        uart_config = detect_uart(profiles, self.sample_rate)
        if uart_config:
            identified['UART'] = {
                'protocol': 'UART',
                'channels': {'TX': uart_config['channel']},
                'params': {
                    'baud_rate': uart_config.get('baud_rate', 115200),
                },
            }
            profiles.pop(uart_config['channel'], None)

        # 4. CAN
        can_config = detect_can(profiles, self.sample_rate)
        if can_config:
            identified['CAN'] = {
                'protocol': 'CAN',
                'channels': {'TX': can_config['channel']},
                'params': {'baud_rate': can_config.get('baud_rate', 500000)},
            }
            profiles.pop(can_config['channel'], None)

        # 5. 1-Wire
        onewire_ch = detect_onewire(profiles, self.sample_rate)
        if onewire_ch is not None:
            identified['1-Wire'] = {
                'protocol': '1-Wire',
                'channels': {'DQ': onewire_ch},
                'params': {},
            }
            profiles.pop(onewire_ch, None)

        # 6. I2S
        i2s_config = detect_i2s(profiles, self.data)
        if i2s_config:
            identified['I2S'] = {
                'protocol': 'I2S',
                'channels': {
                    'SCK': i2s_config['sck_ch'],
                    'WS': i2s_config['ws_ch'],
                    'SD': i2s_config.get('sd_ch'),
                },
                'params': {},
            }
            profiles.pop(i2s_config['sck_ch'], None)
            profiles.pop(i2s_config['ws_ch'], None)
            if i2s_config.get('sd_ch') is not None:
                profiles.pop(i2s_config['sd_ch'], None)

        self._decoders = identified
        return self._decoders

    def decode_all(self):
        """Giải mã tất cả protocol đã phát hiện, trả về list DecodeResult."""
        results = []
        for proto, cfg in self._decoders.items():
            try:
                result = self._service.decode_with_config(
                    self.data,
                    cfg['protocol'],
                    cfg['channels'],
                    cfg.get('params'),
                )
                results.append(result)
            except Exception as e:
                print(f"Decode error for {proto}: {e}")
        self._last_results = results
        return results

    def analyze(self, force_protocol="AutoDetect"):
        """
        Entry point chính.
        - AutoDetect: auto_detect_channels() + decode_all()
        - force_protocol: decode với protocol cụ thể
        """
        if force_protocol == "AutoDetect":
            self.auto_detect_channels()
            return self.decode_all()

        # Decode một protocol cụ thể
        enabled = [force_protocol] if force_protocol in ['UART', 'I2C', 'SPI', 'I2S'] else None
        results = self._service.autodetect_and_decode(self.data, enabled_protocols=enabled)
        self._last_results = results
        return results

    def decode_to_gui(self, enabled_protocols=None):
        """Trả về annotation list định dạng cho GUI."""
        if not self._last_results:
            return []
        return self._adapter.flatten_results(self._last_results)