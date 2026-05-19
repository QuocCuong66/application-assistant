import hashlib
import hmac
import urllib.parse
from config import VNPAY_HASH_SECRET

def generate_vnpay_signature(data: dict) -> str:
    """Generate VNPay signature using HMAC SHA512"""
    # Sort data by key
    sorted_data = sorted(data.items(), key=lambda x: x[0])
    
    # Create query string
    query_string = urllib.parse.urlencode(sorted_data)
    
    # Create HMAC SHA512 signature
    h = hmac.new(
        VNPAY_HASH_SECRET.encode("utf-8"),
        query_string.encode("utf-8"),
        hashlib.sha512
    )
    return h.hexdigest()

def verify_vnpay_signature(data: dict, vnp_SecureHash: str) -> bool:
    """Verify VNPay signature returned from VNPAY"""
    data_copy = data.copy()
    
    # Remove vnp_SecureHash and vnp_SecureHashType if present before verification
    if "vnp_SecureHash" in data_copy:
        del data_copy["vnp_SecureHash"]
    if "vnp_SecureHashType" in data_copy:
        del data_copy["vnp_SecureHashType"]
        
    calculated_hash = generate_vnpay_signature(data_copy)
    return calculated_hash == vnp_SecureHash
