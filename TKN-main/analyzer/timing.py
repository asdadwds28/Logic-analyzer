"""
analyzer/timing.py — Shared timing/signal helpers cho decoder

Utilities chung:
- bit extraction từ raw bytes
- edge detection
- sample reading
- pulse width measurements
- clock edge helpers
"""

from typing import List, Tuple, Optional


def extract_channel(raw_bytes: bytes, channel: int) -> List[int]:
    """
    Trích xuất 1 channel từ raw byte stream.

    Args:
        raw_bytes: bytes - mỗi byte chứa trạng thái 8 channel
        channel: index channel (0-7)

    Returns:
        List[int] - danh sách 0/1 cho channel đó
    """
    return [(byte >> channel) & 1 for byte in raw_bytes]


def get_sample(raw_bytes: bytes, sample_idx: int, channel: int) -> int:
    """Lấy giá trị 1 sample tại vị trí sample_idx, channel cụ thể."""
    if sample_idx < 0 or sample_idx >= len(raw_bytes):
        return 0
    return (raw_bytes[sample_idx] >> channel) & 1


def find_edges(raw_bytes: bytes, channel: int) -> List[Tuple[int, int, int]]:
    """
    Tìm tất cả cạnh lật trên 1 channel.

    Returns:
        List[(sample_idx, old_state, new_state)]
    """
    if not raw_bytes:
        return []

    edges = []
    prev = get_sample(raw_bytes, 0, channel)

    for i in range(1, len(raw_bytes)):
        curr = get_sample(raw_bytes, i, channel)
        if curr != prev:
            edges.append((i, prev, curr))
            prev = curr

    return edges


def find_rising_edges(raw_bytes: bytes, channel: int) -> List[int]:
    """Tìm tất cả cạnh lên (0 -> 1)."""
    return [i for i, old, new in find_edges(raw_bytes, channel) if old == 0 and new == 1]


def find_falling_edges(raw_bytes: bytes, channel: int) -> List[int]:
    """Tìm tất cả cạnh xuống (1 -> 0)."""
    return [i for i, old, new in find_edges(raw_bytes, channel) if old == 1 and new == 0]


def measure_pulse_widths(raw_bytes: bytes, channel: int) -> List[Tuple[int, int, int]]:
    """
    Đo độ rộng các pulse trên channel.

    Returns:
        List[(start_idx, end_idx, state)]
    """
    if not raw_bytes:
        return []

    pulses = []
    start_idx = 0
    prev = get_sample(raw_bytes, 0, channel)

    for i in range(1, len(raw_bytes)):
        curr = get_sample(raw_bytes, i, channel)
        if curr != prev:
            pulses.append((start_idx, i, prev))
            start_idx = i
            prev = curr

    pulses.append((start_idx, len(raw_bytes), prev))
    return pulses


def sample_at_bit_center(raw_bytes: bytes, start_sample: int, bit_index: int,
                         ticks_per_bit: float, channel: int) -> int:
    """
    Sample tại tâm bit thứ bit_index.

    UART example:
    - bit_index=0: start bit center = start_sample + 0.5 * ticks_per_bit
    - bit_index=1: data bit 0 center = start_sample + 1.5 * ticks_per_bit
    """
    sample_idx = int(round(start_sample + (bit_index + 0.5) * ticks_per_bit))
    return get_sample(raw_bytes, sample_idx, channel)


def clamp_sample_idx(sample_idx: int, data_len: int) -> int:
    """Giới hạn sample_idx trong khoảng [0, data_len-1]."""
    return max(0, min(sample_idx, data_len - 1))


def find_next_edge_after(edges: List[Tuple[int, int, int]], sample_idx: int) -> Optional[Tuple[int, int, int]]:
    """Tìm edge đầu tiên sau sample_idx."""
    for edge in edges:
        if edge[0] > sample_idx:
            return edge
    return None


def get_state_run(raw_bytes: bytes, start_idx: int, channel: int) -> Tuple[int, int, int]:
    """
    Lấy run hiện tại: từ start_idx đến khi đổi state.

    Returns:
        (run_start, run_end, state)
    """
    if start_idx >= len(raw_bytes):
        return start_idx, start_idx, 0

    state = get_sample(raw_bytes, start_idx, channel)
    end_idx = start_idx + 1

    while end_idx < len(raw_bytes) and get_sample(raw_bytes, end_idx, channel) == state:
        end_idx += 1

    return start_idx, end_idx, state
