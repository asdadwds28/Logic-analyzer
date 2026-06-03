# Báo Cáo Tiến Độ Dự Án: Hệ Thống Phân Tích Logic (Logic Analyzer)

---

## Phần 1: Tổng quan dự án

*   **Mục tiêu đề tài:** 
    * Xây dựng một hệ thống thiết bị phân tích logic (Logic Analyzer) hoàn chỉnh.
    * Thu thập, hiển thị, phân tích và tự động giải mã các chuẩn giao tiếp cơ bản (UART, SPI, I2C...).
*   **Thông số kỹ thuật dự kiến:**
    *   Hỗ trợ thu thập đa kênh (Ví dụ: 8 hoặc 16 kênh).
    *   Tốc độ lấy mẫu (Sample rate) dự kiến: ... MHz *(Cần cập nhật theo phần cứng)*.
    *   Phần mềm phân tích đa nền tảng, thiết kế tối ưu trên môi trường Linux/Windows.
*   **Sơ đồ khối hệ thống:**
    1.  **Khối phần cứng:** Vi điều khiển/FPGA thu thập tín hiệu.
    2.  **Khối truyền thông:** Truyền tải dữ liệu qua cổng USB tốc độ cao.
    3.  **Khối phần mềm:** Giao diện máy tính (GUI) hiển thị và phân tích dữ liệu chuyên sâu.

---

## Phần 2: Tiến độ thực hiện

*   **Kết quả phần cứng (Hardware):**
    *   Đã thiết kế và hoàn thiện mạch thu thập dữ liệu cơ bản.
    *   Thiết lập thành công kết nối và luồng dữ liệu truyền nhận với máy tính.
*   **Kết quả phần mềm (Software):**
    *   Hoàn thiện giao diện người dùng (GUI) sử dụng thư viện **PyQt5**.
    *   Tích hợp thành công mã nguồn mở **libsigrokdecode** để tận dụng bộ thư viện giải mã tín hiệu đa dạng (I2C, SPI, UART...).
    *   Phát triển và **kiểm thử thành công thuật toán tự động nhận diện (Auto-detect)** các chuẩn giao tiếp (UART, I2C, SPI) với độ chính xác và tốc độ cao trên tập dữ liệu thực tế.
*   **Những khó khăn gặp phải:**
    *   Xử lý xung đột các thư viện hệ thống (Qt platform plugins) khi triển khai phần mềm trên môi trường Linux (đã khắc phục).
    *   Tối ưu hóa hiệu năng vẽ đồ thị khi phải xử lý mảng dữ liệu tín hiệu lớn theo thời gian thực.

---

## Phần 3: Kế hoạch sắp tới

*   **Tích hợp và hoàn thiện tính năng:** 
    * Tích hợp thuật toán **Auto-detect** vào giao diện phần mềm chính để chạy phân tích trực tiếp (Real-time).
    * Bổ sung các giao thức nâng cao.
    * Tối ưu hóa mã nguồn để tăng khả năng chống nhiễu và đọc tín hiệu chính xác hơn.
*   **Tối ưu hóa đường truyền USB:** 
    * Cải thiện băng thông truyền tải dữ liệu (throughput) từ phần cứng.
    * Giảm thiểu độ trễ (latency) nhằm tránh hiện tượng rớt gói tin.
*   **Tích hợp và kiểm thử toàn hệ thống:** 
    * Tiến hành kiểm thử thực tế với các tín hiệu chuẩn từ mạch phát.
    * Đánh giá sai số so với các máy Logic Analyzer thương mại.
