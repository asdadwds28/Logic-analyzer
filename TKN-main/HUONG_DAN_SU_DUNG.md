# HƯỚNG DẪN SỬ DỤNG PHẦN MỀM TKN LOGIC ANALYZER

Tài liệu hướng dẫn chi tiết từ lúc khởi động, vận hành giao diện đến phân tích giao thức truyền thông bằng **TKN Logic Analyzer**.

---

## 1. Chuẩn Bị & Khởi Động

### Bước 1: Khởi động môi trường và chạy App
Mở Terminal tại thư mục `TKN-main` và chạy:
```bash
# Nếu dùng virtual environment (khuyến nghị)
source .venv/bin/activate
python main.py

# Nếu chạy trực tiếp bằng python hệ thống
python3 main.py
```
*Giao diện phần mềm sẽ tự động căn chỉnh kích thước tối ưu (90% màn hình laptop của bạn, tối thiểu 800x560px) để không bị tràn khung.*

---

## 2. Giao Diện & Thao Tác Waveform cơ bản

Giao diện chia làm 3 phần chính:
1. **Thanh công cụ Toolbar (Phía trên)**: Điều khiển USB Serial, Tải file dữ liệu mẫu, Nút kích hoạt Decode, Đo đạc nhanh, Xuất dữ liệu.
2. **Khung hiển thị sóng Waveform (Bên trái)**: Hiển thị tín hiệu logic 8 kênh (CH1 - CH8).
3. **Bảng điều khiển Settings Panel (Bên phải)**: Ẩn/hiện kênh, cấu hình bộ kích hoạt (Trigger), bật/tắt Đo đạc (Measurement), lưu/quản lý Marker thời gian, cài đặt Live Auto-Detect và đổi Theme màu sắc.

### Thao tác trực tiếp trên Waveform:
- **Di chuyển ngang (Pan)**: Nhấp giữ chuột trái vào đồ thị và kéo qua trái/phải.
- **Phóng to/Thu nhỏ (Zoom)**: Cuộn bánh xe chuột (Scroll wheel) hoặc dùng các phím tắt `+` (phóng to), `-` (thu nhỏ).
- **Xem thông số thời gian**: Góc dưới cùng của Waveform luôn hiển thị trục thời gian (ms).

---

## 3. Các Tính Năng Phân Tích Cơ Bản

### ① Ẩn / Hiện Kênh (Digital Channels)
- Tại góc phải trên cùng (phần **Display**), tích/bỏ tích các ô từ **CH1** đến **CH8** để ẩn hoặc hiện sóng kênh tương ứng giúp màn hình gọn hơn.

### ② Đo đạc tự động (Measurements)
1. Tại phần **② MEASUREMENTS**, chọn Kênh (ví dụ: `CH1`).
2. Chọn Thông số cần đo:
   - `Frequency (Hz)`: Tần số xung.
   - `Period (ms)`: Chu kỳ xung.
   - `Duty Cycle (%)`: Hệ số chu kỳ.
   - `PW High (ms)` / `PW Low (ms)`: Độ rộng xung mức cao / mức thấp.
3. Bấm `Add` ➔ Thông số đo thời gian thực sẽ hiển thị tại bảng phía dưới. Bấm chọn hàng và bấm `Delete` để xóa thông số đo.

### ③ Thước đo thời gian (Timing Marker)
Dùng để đo khoảng cách thời gian giữa hai sự kiện (ví dụ: khoảng cách giữa 2 sườn xung):
1. Bấm phím tắt `+` trên bàn phím (hoặc bấm nút `⊕ Add Marker (+)` ở bảng phải) ➔ Một đường thẳng đứng màu vàng (M1) sẽ xuất hiện tại vị trí con trỏ chuột.
2. Di chuyển chuột đến vị trí thứ hai, bấm `+` lần nữa ➔ Đường thẳng đứng thứ hai (M2) xuất hiện.
3. Nhìn vào ô **Δt** màu vàng ở bảng điều khiển bên phải ➔ Khoảng thời gian chính xác giữa hai điểm (tính bằng mili-giây `ms`) sẽ được tính toán ngay lập tức.
4. Bấm `✕ Clear Markers` để reset thước đo.

### ④ Tạo và Quản lý vùng chọn (Range Mode)
1. Bấm nút `📏 Range` trên Toolbar ➔ Chuyển sang chế độ khoanh vùng.
2. Nhấp giữ chuột trái trên đồ thị và kéo từ điểm đầu đến điểm cuối vùng bạn quan tâm ➔ Thả chuột để lưu vùng chọn.
3. Bấm chọn vùng trong danh sách để zoom nhanh vào vùng đó, hoặc bấm `✕ Clear` trên toolbar để xóa.

---

## 4. Kết Nối Thiết Bị USB Serial ( STM32 )

Nếu có phần cứng USB CDC cắm vào máy tính:
1. Nhìn lên Toolbar, bấm nút quét cổng `↺`.
2. Chọn cổng giao tiếp từ danh sách thả xuống (Ví dụ: `COM3` trên Windows hoặc `/dev/ttyACM0` trên Linux).
3. Bấm **Connect** ➔ Phần cứng bắt đầu đổ dữ liệu nhị phân về máy tính với tốc độ 30 FPS.
4. Tích chọn **Looping** ở bảng phải để liên tục vẽ lại dữ liệu mới nhất.

---

## 5. Giải Mã Giao Thức (Protocol Decoding)

Đây là tính năng cốt lõi hỗ trợ 4 giao thức phổ biến: **UART, I2C, SPI, I2S**.

### Cách 1: Tự Động Nhận Diện (Auto-Detect & Decode) - *Khuyên dùng*
1. Có dữ liệu sóng trên màn hình (dữ liệu demo hoặc dữ liệu thực tế từ USB).
2. Bấm nút `🔍 Auto-Detect` trên Toolbar.
3. Thuật toán thông minh sẽ tự động phân tích tần số xung, số lượng đường truyền và đưa ra dự đoán chính xác nhất.
4. **Kết quả**: Các nhãn giải mã (ví dụ: giá trị byte dạng Hex `0x55`, bit Start, Stop, ACK/NACK) sẽ hiển thị đè trực tiếp lên sườn sóng tương ứng.

### Cách 2: Tự Động Nhận Diện Thời Gian Thực (Live Auto-Detect)
1. Đảm bảo đã kết nối cổng USB (nút Connect chuyển sang màu xanh).
2. Cuộn xuống phần **⑤ REAL-TIME** ở bảng bên phải.
3. Tích chọn **Enabled**.
4. Thiết lập **Interval** (mặc định 500 ms) ➔ Cứ mỗi 0.5 giây, app sẽ tự lấy dữ liệu luồng USB để tự động decode và vẽ kết quả lên màn hình mà không cần bạn phải bấm nút thủ công.

### Cách 3: Giải Mã Thủ Công (Manual Decode)
Nếu muốn tự cấu hình chính xác theo sơ đồ phần cứng của bạn:
1. Bấm nút `⚙️ Manual Decode` trên Toolbar.
2. Một hộp thoại hiện ra, hãy chọn giao thức bạn muốn giải mã:
   - **UART**: Map chân `TX`, chọn Baud rate (ví dụ `115200`), Parity, Stop bit.
   - **I2C**: Map chân `SCL` và `SDA`.
   - **SPI**: Map chân `CS`, `SCK`, `MOSI`, `MISO`. Chọn Mode SPI (0, 1, 2, 3).
   - **I2S**: Map chân `SCK` (Serial Clock), `WS` (Word Select), `SD` (Serial Data).
3. Bấm **Decode** ➔ Kết quả giải mã sẽ lập tức hiển thị.

---

## 6. Kích Hoạt Bộ Kích (Trigger Setting)

Bộ kích hoạt giúp bạn bắt được đúng khoảnh khắc tín hiệu xảy ra thay vì phải ngồi cuộn tìm thủ công:
1. Cuộn đến phần **Trigger** trong bảng điều khiển.
2. Chọn Kênh cần theo dõi (ví dụ: `CH1`).
3. Chọn điều kiện kích hoạt:
   - `Rising ↑`: Kích hoạt khi tín hiệu chuyển từ 0 lên 1 (Sườn lên).
   - `Falling ↓`: Kích hoạt khi tín hiệu chuyển từ 1 xuống 0 (Sườn xuống).
   - `Both ↕`: Bất kỳ sự thay đổi trạng thái nào.
   - `High` / `Low`: Kích hoạt theo mức điện áp.
4. Khi dữ liệu USB đổ về thỏa mãn điều kiện, đồ thị sẽ tự động nhảy (Pan) và căn lề chính giữa màn hình đúng vào điểm sườn xung đó.

---

## 7. Xuất Dữ Liệu Giải Mã (Export)

Sau khi giải mã thành công dữ liệu trên màn hình:
1. Bấm nút `💾 Export` trên Toolbar.
2. Lựa chọn định dạng lưu file:
   - **CSV**: Xuất ra dạng bảng tính gồm các cột: *Timestamp (ms), Protocol, Channel, Frame Type, Hex Data, Text Annotation, Severity*. Phù hợp để import vào Excel/MATLAB.
   - **JSON**: Xuất toàn bộ cấu trúc cây dữ liệu thô phục vụ cho lập trình hoặc lưu vết phân tích sâu.
3. Nhập tên file và bấm **Save**.

---

## 8. Tùy Biến Giao Diện (Theme)

Nếu màn hình quá chói hoặc khó nhìn trong tối:
- Cuộn xuống mục cuối cùng ở bảng bên phải (**⑤ APPEARANCE**).
- Chọn một trong các theme màu sắc được cấu hình sẵn:
  - `🌑 Dark`: Giao diện tối chuyên nghiệp (mặc định).
  - `☀️ Light`: Giao diện sáng rõ ràng.
  - `🌊 Ocean`: Xanh đại dương mát mắt.
  - `🌲 Forest`: Xanh lá cây tự nhiên.
  - `🌅 Sunset`: Màu hoàng hôn ấm áp.
  - `👾 Hacker`: Phong cách ma trận đen-xanh lá.
