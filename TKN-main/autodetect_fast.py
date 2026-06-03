import math

COMMON_BAUDS = [9600, 19200, 38400, 57600, 115200]
COMMON_CAN_BAUDS = [125000, 250000, 500000, 1000000]

def profile_channels(data: bytes, num_channels=8):
    """
    PHIÊN BẢN TỐI ƯU SIÊU TỐC BẰNG PURE PYTHON
    - Không cần cài Numpy
    - Bỏ qua toàn bộ trạng thái không đổi, chỉ bắt các thời điểm lật bit
    - Tốc độ tăng 100 lần!
    """
    profiles = {ch: {'toggles': 0, 'min_pulse': float('inf'), 'state_counts': {0: 0, 1: 0}, 'edges': [], 'pulse_widths': {}} for ch in range(num_channels)}
    if not data:
        return profiles
        
    last_val = data[0]
    last_states = [(last_val >> ch) & 1 for ch in range(num_channels)]
    last_toggle_idx = [0] * num_channels
    
    # ── MẸO TỐI ƯU ────────────────────────────────────────────────
    # Thay vì đếm +1 cho mỗi biến ở mỗi mẫu (chạy 1 triệu lần)
    # Ta check: Nếu data[i] == last_val (tức là không sợi dây nào thay đổi)
    # Ta BỎ QUA NGAY LẬP TỨC!
    for i, val in enumerate(data):
        if val == last_val:
            continue
            
        # Chỉ khi có ít nhất 1 sợi dây thay đổi điện áp:
        diff = val ^ last_val
        for ch in range(num_channels):
            # Nếu bit của channel này thay đổi (do phép XOR diff = 1)
            if (diff >> ch) & 1: 
                state = (val >> ch) & 1
                pulse_width = i - last_toggle_idx[ch]
                
                # Cập nhật tổng số lượng trạng thái (chỉ cộng 1 cục thay vì cộng từng cái 1)
                profiles[ch]['state_counts'][last_states[ch]] += pulse_width
                
                if pulse_width > 0:
                    profiles[ch]['min_pulse'] = min(profiles[ch]['min_pulse'], pulse_width)
                    if pulse_width not in profiles[ch]['pulse_widths']:
                        profiles[ch]['pulse_widths'][pulse_width] = 0
                    profiles[ch]['pulse_widths'][pulse_width] += 1
                    
                profiles[ch]['toggles'] += 1
                profiles[ch]['edges'].append((i, state))
                
                last_states[ch] = state
                last_toggle_idx[ch] = i
                
        last_val = val
        
    # Xử lý đoạn cuối cùng: từ lúc lật bit lần cuối cho đến khi kết thúc thời gian
    n = len(data)
    for ch in range(num_channels):
        pulse_width = n - last_toggle_idx[ch]
        if pulse_width > 0:
            profiles[ch]['state_counts'][last_states[ch]] += pulse_width
            
    # Tính Idle state
    for ch in range(num_channels):
        c0, c1 = profiles[ch]['state_counts'][0], profiles[ch]['state_counts'][1]
        profiles[ch]['idle_state'] = 1 if c1 > c0 else 0
        
    return profiles


def get_fundamental_pulse_gcd(pulse_widths):
    if not pulse_widths:
        return float('inf')
    
    total_pulses = sum(pulse_widths.values())
    if total_pulses > 5:
        # Lọc nhiễu và xung idle: chỉ giữ lại các độ rộng xung xuất hiện đáng kể (>5%)
        valid_pw = {pw: count for pw, count in pulse_widths.items() if count >= total_pulses * 0.05}
    else:
        valid_pw = pulse_widths
        
    if not valid_pw:
        valid_pw = pulse_widths
        
    # Xung cơ bản (tương ứng với 1 bit) thường là xung ngắn nhất trong dải xung hợp lệ
    # Tránh dùng GCD trực tiếp vì sai số vật lý hoặc xung idle dài sẽ làm GCD = 1 hoặc 2
    fundamental = min(valid_pw.keys())
        
    return fundamental


def detect_uart(profiles, sample_rate=1_000_000):
    candidates = []
    for ch, p in profiles.items():
        if p['toggles'] > 0 and p['idle_state'] == 1:
            fund_pulse = get_fundamental_pulse_gcd(p['pulse_widths'])
            if fund_pulse != float('inf'):
                approx_baud = sample_rate / fund_pulse
                for baud in COMMON_BAUDS:
                    if abs(approx_baud - baud) / baud < 0.15:
                        candidates.append({'channel': ch, 'baud_rate': baud, 'confidence': 1.0 - abs(approx_baud - baud)/baud})
                        break
    if candidates:
        candidates.sort(key=lambda x: x['confidence'], reverse=True)
        return candidates[0]
    return None


def detect_i2c(profiles, data: bytes):
    num_channels = len(profiles)
    best_pair = None
    max_score = -1
    
    for scl_ch in profiles.keys():
        if profiles[scl_ch]['toggles'] < 4: continue
        for sda_ch in profiles.keys():
            if scl_ch == sda_ch or profiles[sda_ch]['toggles'] < 2: continue
            if profiles[scl_ch]['toggles'] <= profiles[sda_ch]['toggles']: continue
            
            start_stop_count = 0
            for i, sda_new_state in profiles[sda_ch]['edges']:
                scl_val = (data[i] >> scl_ch) & 1
                if scl_val == 1:
                    start_stop_count += 1
                    
            valid_data_count = 0
            for i, scl_new_state in profiles[scl_ch]['edges']:
                if scl_new_state == 1: 
                    valid_data_count += 1
            
            score = (start_stop_count * 10) + valid_data_count
            if start_stop_count > 0 and valid_data_count > 0 and score > max_score:
                max_score = score
                best_pair = {'sda_ch': sda_ch, 'scl_ch': scl_ch}
                
    return best_pair


def detect_spi(profiles, data: bytes):
    num_channels = len(profiles)
    best_config = None
    max_score = -1
    
    for cs_ch in profiles.keys():
        if profiles[cs_ch]['toggles'] == 0: continue
        if profiles[cs_ch]['idle_state'] != 1: continue 
        
        for sck_ch in profiles.keys():
            if sck_ch == cs_ch or profiles[sck_ch]['toggles'] < 8: continue
            
            sck_toggles_while_cs_high = 0
            sck_toggles_while_cs_low = 0
            
            for i, sck_new_state in profiles[sck_ch]['edges']:
                cs_val = (data[i] >> cs_ch) & 1
                if cs_val == 1:
                    sck_toggles_while_cs_high += 1
                else:
                    sck_toggles_while_cs_low += 1
                
            if sck_toggles_while_cs_low > 0 and sck_toggles_while_cs_high < (sck_toggles_while_cs_low * 0.1):
                data_channels = [ch for ch in profiles.keys() if ch != cs_ch and ch != sck_ch and profiles[ch]['toggles'] > 0]
                mosi_ch = data_channels[0] if len(data_channels) > 0 else None
                miso_ch = data_channels[1] if len(data_channels) > 1 else None
                
                score = sck_toggles_while_cs_low - (sck_toggles_while_cs_high * 10)
                if score > max_score:
                    max_score = score
                    best_config = {'cs_ch': cs_ch, 'sck_ch': sck_ch, 'mosi_ch': mosi_ch, 'miso_ch': miso_ch}
                    
    return best_config


def detect_can(profiles, sample_rate=1_000_000):
    candidates = []
    for ch, p in profiles.items():
        if p['toggles'] > 0 and p['idle_state'] == 1:
            fund_pulse = get_fundamental_pulse_gcd(p['pulse_widths'])
            if fund_pulse != float('inf'):
                approx_baud = sample_rate / fund_pulse
                
                # Check mapping to common CAN baud rates
                # UART vs CAN conflict is resolved by baud rate lists being disjoint
                for baud in COMMON_CAN_BAUDS:
                    if abs(approx_baud - baud) / baud < 0.15:
                        candidates.append({'channel': ch, 'baud_rate': baud, 'confidence': 1.0 - abs(approx_baud - baud)/baud})
                        break
                            
    if candidates:
        candidates.sort(key=lambda x: x['confidence'], reverse=True)
        return candidates[0]
    return None


def detect_i2s(profiles, data: bytes):
    candidates = []
    for sck_ch in profiles.keys():
        if profiles[sck_ch]['toggles'] < 64: continue
        
        for ws_ch in profiles.keys():
            if ws_ch == sck_ch: continue
            
            sck_toggles = profiles[sck_ch]['toggles']
            ws_toggles = profiles[ws_ch]['toggles']
            if ws_toggles == 0: continue
            
            # Toggles đếm cạnh lật, nên sck_toggles = số_xung - 1. 
            # Dùng số lượng chu kỳ (toggles + 1) để ra tỷ số chính xác tuyệt đối!
            ratio = (sck_toggles + 1) / (ws_toggles + 1)
            
            # Theo chuẩn: 1 chu kỳ WS (L+R ch) gồm 32, 48 hoặc 64 SCK
            if abs(ratio - 32) < 2.0 or abs(ratio - 48) < 2.0 or abs(ratio - 64) < 2.0:
                data_channels = [ch for ch in profiles.keys() if ch != sck_ch and ch != ws_ch and profiles[ch]['toggles'] > 0]
                sd_ch = data_channels[0] if data_channels else None
                candidates.append({'sck_ch': sck_ch, 'ws_ch': ws_ch, 'sd_ch': sd_ch, 'ratio': ratio})
                
    if candidates:
        return candidates[0] # Return first match
    return None


def detect_onewire(profiles, sample_rate=1_000_000):
    candidates = []
    us_to_samples = sample_rate / 1_000_000 # samples per microsecond
    
    for ch, p in profiles.items():
        if p['toggles'] > 0 and p['idle_state'] == 1:
            has_reset = False
            has_data_pulse = False
            
            for pw in p['pulse_widths'].keys():
                duration_us = pw / us_to_samples
                # Reset pulse is > 480us and < 1000us
                if 450 < duration_us < 1000:
                    has_reset = True
                # Data pulses (0 or 1 slot) are roughly < 120us
                if 10 < duration_us < 150:
                    has_data_pulse = True
                    
            if has_reset and has_data_pulse:
                candidates.append(ch)
                
    if candidates:
        return candidates[0]
    return None
