"""Utilities for extracting and base64-encoding H.264 Codec Specific Data (CSD / SPS / PPS)."""

import base64
from typing import Tuple, Optional, List


def split_nal_units(annex_b_data: bytes) -> List[bytes]:
    """Splits an Annex B byte stream into individual NAL units."""
    nals: List[bytes] = []
    length = len(annex_b_data)
    i = 0
    start_indices: List[int] = []

    while i < length - 3:
        if annex_b_data[i] == 0 and annex_b_data[i+1] == 0:
            if annex_b_data[i+2] == 1:
                start_indices.append(i + 3)
                i += 3
                continue
            elif annex_b_data[i+2] == 0 and annex_b_data[i+3] == 1:
                start_indices.append(i + 4)
                i += 4
                continue
        i += 1

    for idx in range(len(start_indices)):
        start = start_indices[idx]
        end = start_indices[idx + 1] if idx + 1 < len(start_indices) else length
        # Strip trailing zeroes if preceding next start code
        nal = annex_b_data[start:end].rstrip(b"\x00")
        if nal:
            nals.append(nal)

    return nals


def extract_h264_sps_pps(annex_b_data: bytes) -> Tuple[Optional[str], Optional[str]]:
    """Extracts Base64-encoded SPS (csd-0) and PPS (csd-1) from H.264 Annex B stream.
    
    In H.264:
      NAL type 7 = SPS (Sequence Parameter Set)
      NAL type 8 = PPS (Picture Parameter Set)
    """
    sps_b64: Optional[str] = None
    pps_b64: Optional[str] = None

    nals = split_nal_units(annex_b_data)
    for nal in nals:
        if not nal:
            continue
        nal_type = nal[0] & 0x1F
        if nal_type == 7 and sps_b64 is None:
            # Include Annex B start code prefix (00 00 00 01) if required or pure NAL
            sps_b64 = base64.b64encode(nal).decode("ascii")
        elif nal_type == 8 and pps_b64 is None:
            pps_b64 = base64.b64encode(nal).decode("ascii")

    return sps_b64, pps_b64
