/// Find the largest index <= `pos` that falls on a UTF-8 char boundary.
pub fn snap_to_char_floor(s: &str, pos: usize) -> usize {
    let pos = pos.min(s.len());
    let mut i = pos;
    while i > 0 && !s.is_char_boundary(i) {
        i -= 1;
    }
    i
}

/// Find the smallest index >= `pos` that falls on a UTF-8 char boundary.
pub fn snap_to_char_ceil(s: &str, pos: usize) -> usize {
    let pos = pos.min(s.len());
    let mut i = pos;
    while i < s.len() && !s.is_char_boundary(i) {
        i += 1;
    }
    i
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn floor_on_ascii() {
        assert_eq!(snap_to_char_floor("hello", 3), 3);
    }

    #[test]
    fn floor_clamps_to_len() {
        assert_eq!(snap_to_char_floor("hi", 100), 2);
    }

    #[test]
    fn floor_snaps_back_on_multibyte() {
        let s = "aüb"; // 'ü' is 2 bytes: positions 1..3
        assert_eq!(snap_to_char_floor(s, 2), 1); // mid-ü snaps back to start of ü
    }

    #[test]
    fn ceil_on_ascii() {
        assert_eq!(snap_to_char_ceil("hello", 3), 3);
    }

    #[test]
    fn ceil_clamps_to_len() {
        assert_eq!(snap_to_char_ceil("hi", 100), 2);
    }

    #[test]
    fn ceil_snaps_forward_on_multibyte() {
        let s = "aüb"; // 'ü' is 2 bytes: positions 1..3
        assert_eq!(snap_to_char_ceil(s, 2), 3); // mid-ü snaps forward past ü
    }
}
