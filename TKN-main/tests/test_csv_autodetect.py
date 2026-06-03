import csv
import time
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from autodetect_fast import profile_channels, detect_uart

# 1. Đọc file CSV và chuyển thành mảng bytes giả lập
def load_csv_to_bytes(filepath):
    data_bytes = bytearray()
    with open(filepath, 'r') as f:
        reader = csv.reader(f)
        next(reader)  # Bỏ qua header
        
        for row in reader:
            # Lấy 8 kênh từ cột 1 đến 8 (cột 0 là time)
            ch_vals = [int(x) for x in row[1:9]]
            
            # Gộp 8 kênh thành 1 byte
            byte_val = 0
            for i in range(8):
                byte_val |= (ch_vals[i] << i)
                
            data_bytes.append(byte_val)
            
    return bytes(data_bytes)

print("Đang đọc file CSV...")
data = load_csv_to_bytes(os.path.join(os.path.dirname(__file__), 'sample_uart_115200.csv'))
print(f"Đã nạp {len(data)} mẫu dữ liệu.")

print("\n--- BẮT ĐẦU TEST THUẬT TOÁN AUTO-DETECT ---")
start_time = time.time()

# 2. Chạy thuật toán của bạn
profiles = profile_channels(data, num_channels=8)
result_uart = detect_uart(profiles, sample_rate=1_000_000)

end_time = time.time()

# 3. In kết quả
print(f"Thời gian chạy thuật toán: {(end_time - start_time) * 1000:.2f} ms")

if result_uart:
    print("\n[THÀNH CÔNG] Thuật toán phát hiện được UART:")
    print(f" - Kênh (Channel): {result_uart['channel']}")
    print(f" - Tốc độ (Baud rate): {result_uart['baud_rate']}")
    print(f" - Độ tin cậy (Confidence): {result_uart['confidence']*100:.2f}%")
else:
    print("\n[THẤT BẠI] Không phát hiện ra tín hiệu UART nào.")
