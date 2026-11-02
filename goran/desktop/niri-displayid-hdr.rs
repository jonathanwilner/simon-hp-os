//! CTA HDR metadata embedded in DisplayID 2.0, omitted by libdisplay-info 0.3.
//! Read only checksum-valid, bounded DisplayID CTA collections. Never infer HDR
//! from panel type, bit depth, or an output configuration override.
#[derive(Debug, Default, PartialEq)]
pub struct HdrMetadata {
    pub pq: bool,
    pub bt2020_rgb: bool,
    pub max_luminance: u16,
    pub min_luminance: u16,
    pub max_frame_avg_luminance: u16,
}

fn checksum(bytes: &[u8]) -> bool {
    bytes.iter().fold(0u8, |sum, b| sum.wrapping_add(*b)) == 0
}

fn luminance(code: u8) -> f64 {
    if code == 0 { 0.0 } else { 50.0 * 2f64.powf(f64::from(code) / 32.0) }
}

fn field(value: f64) -> u16 {
    value.round().clamp(0.0, f64::from(u16::MAX)) as u16
}

fn cta_collection(mut data: &[u8], result: &mut HdrMetadata) -> Option<()> {
    while !data.is_empty() {
        let tag = data[0] >> 5;
        let length = usize::from(data[0] & 31);
        let payload = data.get(1..1 + length)?;
        data = data.get(1 + length..)?;
        if tag != 7 || payload.is_empty() { continue; }
        match payload[0] {
            5 if payload.len() >= 3 => result.bt2020_rgb |= payload[1] & 0x80 != 0,
            6 if payload.len() >= 3 => {
                result.pq |= payload[1] & 4 != 0;
                let max = payload.get(3).copied().map(luminance).unwrap_or(0.0);
                let avg = payload.get(4).copied().map(luminance).unwrap_or(0.0);
                let min = payload.get(5).copied().map(|code| {
                    max * (f64::from(code) / 255.0).powi(2) / 100.0
                }).unwrap_or(0.0);
                result.max_luminance = result.max_luminance.max(field(max));
                result.max_frame_avg_luminance = result.max_frame_avg_luminance.max(field(avg));
                result.min_luminance = result.min_luminance.max(field(min * 10000.0));
            }
            _ => {}
        }
    }
    Some(())
}

pub fn parse(data: &[u8]) -> HdrMetadata {
    let mut result = HdrMetadata::default();
    let Some(base) = data.get(..128) else { return result; };
    if base[..8] != [0, 255, 255, 255, 255, 255, 255, 0] || !checksum(base) {
        return result;
    }
    for extension in data[128..].chunks_exact(128).take(usize::from(base[126])) {
        if extension[0] != 0x70 || extension[1] != 0x20 || !checksum(extension) {
            continue;
        }
        let end = 5 + usize::from(extension[2]);
        if end >= 127 || !checksum(&extension[1..=end]) { continue; }
        let mut blocks = &extension[5..end];
        let mut embedded = HdrMetadata::default();
        let mut valid = true;
        while !blocks.is_empty() {
            let Some(header) = blocks.get(..3) else { valid = false; break; };
            let length = usize::from(header[2]);
            let Some(payload) = blocks.get(3..3 + length) else { valid = false; break; };
            if header[0] == 0x81 && header[1] & 7 == 0 && cta_collection(payload, &mut embedded).is_none() {
                valid = false;
                break;
            }
            blocks = &blocks[3 + length..];
        }
        if valid {
            result.pq |= embedded.pq;
            result.bt2020_rgb |= embedded.bt2020_rgb;
            result.max_luminance = result.max_luminance.max(embedded.max_luminance);
            result.min_luminance = result.min_luminance.max(embedded.min_luminance);
            result.max_frame_avg_luminance = result.max_frame_avg_luminance.max(embedded.max_frame_avg_luminance);
        }
    }
    result
}

#[cfg(test)]
mod tests {
    use super::*;
    const EDID: &[u8] = include_bytes!("samsung-sdc4257.edid");
    fn repair_checksums(data: &mut [u8]) {
        let block = &mut data[256..384];
        let end = 5 + usize::from(block[2]);
        block[end] = 0u8.wrapping_sub(block[1..end].iter().fold(0u8, |s, b| s.wrapping_add(*b)));
        block[127] = 0u8.wrapping_sub(block[..127].iter().fold(0u8, |s, b| s.wrapping_add(*b)));
    }
    #[test]
    fn actual_samsung_displayid_cta() {
        assert_eq!(parse(EDID), HdrMetadata { pq: true, bt2020_rgb: true, max_luminance: 1107, min_luminance: 39857, max_frame_avg_luminance: 497 });
    }
    #[test]
    fn invalid_extension_checksum_is_rejected() {
        let mut data = EDID.to_vec(); data[300] ^= 1;
        assert_eq!(parse(&data), HdrMetadata::default());
    }
    #[test]
    fn invalid_displayid_checksum_is_rejected() {
        let mut data = EDID.to_vec(); data[300] ^= 1; data[383] ^= 1;
        assert_eq!(parse(&data), HdrMetadata::default());
    }
    #[test]
    fn truncated_and_bad_block_lengths_are_rejected() {
        for length in 0..EDID.len() { assert!(!parse(&EDID[..length]).pq); }
        let mut data = EDID.to_vec(); data[287] = 127; repair_checksums(&mut data);
        assert_eq!(parse(&data), HdrMetadata::default());
    }
    #[test]
    fn sdr_eotf_does_not_advertise_pq() {
        let mut data = EDID.to_vec(); data[314] = 1; repair_checksums(&mut data);
        assert!(!parse(&data).pq);
    }
    #[test]
    fn undeclared_extensions_are_ignored() {
        let mut data = EDID.to_vec(); data[126] = 1;
        data[127] = 0u8.wrapping_sub(data[..127].iter().fold(0u8, |s, b| s.wrapping_add(*b)));
        assert!(!parse(&data).pq);
    }
}
