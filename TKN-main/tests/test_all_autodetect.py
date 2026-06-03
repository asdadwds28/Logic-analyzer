import csv
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from autodetect_fast import profile_channels, detect_uart, detect_i2c, detect_spi

def load_saleae_csv(filepath, target_sample_rate=1_000_000):
    """
    Đọc file CSV xuất từ Saleae (dạng thay đổi trạng thái theo thời gian).
    Tái tạo lại mảng bytes liên tục theo target_sample_rate.
    """
    print(f"Đang đọc file {filepath} và tái tạo tín hiệu ở tần số {target_sample_rate/1_000_000} MHz...")
    data_bytes = bytearray()
    
    with open(filepath, 'r') as f:
        reader = csv.reader(f)
        header = next(reader)
        
        # Đếm số lượng kênh (trừ cột Time)
        num_channels = len(header) - 1
        
        last_sample_idx = 0
        last_byte_val = 0
        
        for row in reader:
            if not row: continue
            
            t = float(row[0])
            current_sample_idx = int(t * target_sample_rate)
            
            # Kéo dài trạng thái cũ cho đến thời điểm hiện tại
            samples_to_add = current_sample_idx - last_sample_idx
            if samples_to_add > 0:
                data_bytes.extend([last_byte_val] * samples_to_add)
            
            # Cập nhật trạng thái mới
            byte_val = 0
            for i in range(num_channels):
                val = int(row[i+1]) if row[i+1] else 0
                byte_val |= (val << i)
                
            last_byte_val = byte_val
            last_sample_idx = current_sample_idx
            
    return bytes(data_bytes), num_channels

# 1. Tải dữ liệu từ digital.csv với Sample Rate 2MHz
SAMPLE_RATE = 2_000_000
try:
    data, num_channels = load_saleae_csv(os.path.join(os.path.dirname(__file__), 'digital.csv'), target_sample_rate=SAMPLE_RATE)
    print(f"Đã tái tạo xong {len(data)} mẫu dữ liệu ({len(data)/SAMPLE_RATE:.2f} giây). Số kênh: {num_channels}")
except Exception as e:
    print(f"Lỗi đọc file: {e}")
    exit(1)

print("\n--- BẮT ĐẦU QUÉT TOÀN BỘ GIAO THỨC ---")
start_time = time.time()

# 2. Tạo profile kênh
profiles = profile_channels(data, num_channels=num_channels)

# 3. Quét UART
res_uart = detect_uart(profiles, sample_rate=SAMPLE_RATE)
if res_uart:
    print(f"[+] Tìm thấy UART ở Kênh {res_uart['channel']} | Tốc độ: {res_uart['baud_rate']} baud")
else:
    print("[-] Không tìm thấy UART")

# 4. Quét I2C
res_i2c = detect_i2c(profiles, data)
if res_i2c:
    print(f"[+] Tìm thấy I2C | SCL: Kênh {res_i2c['scl_ch']} | SDA: Kênh {res_i2c['sda_ch']}")
else:
    print("[-] Không tìm thấy I2C")

# 5. Quét SPI
res_spi = detect_spi(profiles, data)
if res_spi:
    print(f"[+] Tìm thấy SPI | CS: {res_spi['cs_ch']} | SCK: {res_spi['sck_ch']} | MOSI: {res_spi['mosi_ch']} | MISO: {res_spi['miso_ch']}")
else:
    print("[-] Không tìm thấy SPI")

end_time = time.time()
print(f"\n=> Tổng thời gian phân tích: {(end_time - start_time) * 1000:.2f} ms")
