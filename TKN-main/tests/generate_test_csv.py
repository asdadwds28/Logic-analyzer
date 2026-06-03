import csv

# Thông số giả lập
SAMPLE_RATE = 1_000_000  # 1 MHz
BAUD_RATE = 115200
SAMPLES_PER_BIT = int(SAMPLE_RATE / BAUD_RATE)

def generate_uart_byte(byte_val):
    # UART Frame: 1 Start bit (0), 8 Data bits (LSB first), 1 Stop bit (1)
    bits = [0] # Start bit
    for i in range(8):
        bits.append((byte_val >> i) & 1)
    bits.append(1) # Stop bit
    
    samples = []
    for bit in bits:
        samples.extend([bit] * SAMPLES_PER_BIT)
    return samples

# Tạo dữ liệu: Gửi chữ "HELLO" qua UART
data_to_send = b"HELLO"
ch0_samples = [] # Kênh 0 là TX

# Idle high
ch0_samples.extend([1] * 50)

for b in data_to_send:
    ch0_samples.extend(generate_uart_byte(b))
    ch0_samples.extend([1] * 20) # Khoảng nghỉ giữa các byte

# Idle high đoạn cuối
ch0_samples.extend([1] * 50)

# Các kênh khác mặc định bằng 0
num_samples = len(ch0_samples)

with open('sample_uart_115200.csv', 'w', newline='') as f:
    writer = csv.writer(f)
    writer.writerow(['Time [s]', 'Channel 0', 'Channel 1', 'Channel 2', 'Channel 3', 'Channel 4', 'Channel 5', 'Channel 6', 'Channel 7'])
    
    for i in range(num_samples):
        time_s = i / SAMPLE_RATE
        # Kênh 0 có data, các kênh khác = 0
        row = [f"{time_s:.6f}", ch0_samples[i], 0, 0, 0, 0, 0, 0, 0]
        writer.writerow(row)

print(f"Đã tạo file sample_uart_115200.csv với {num_samples} mẫu (Sample Rate = 1MHz, Baud = 115200)")
