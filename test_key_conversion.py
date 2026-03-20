import os
from dotenv import load_dotenv

load_dotenv()
pk_str = os.getenv("ALIPAY_PRIVATE_KEY", "").replace("\\n", "\n")

try:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
    import rsa
    
    # Check if the key has headers
    if "-----BEGIN" not in pk_str:
        # We don't know if it's PKCS1 or PKCS8. Try parsing it as PKCS8 first.
        pkcs8_str = f"-----BEGIN PRIVATE KEY-----\n{pk_str}\n-----END PRIVATE KEY-----"
        
        try:
            # Try to load as PKCS8
            key = serialization.load_pem_private_key(
                pkcs8_str.encode('utf-8'),
                password=None,
                backend=default_backend()
            )
            # Dump to PKCS1
            pkcs1_pem = key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=serialization.NoEncryption()
            )
            # Now test if `rsa` can load it
            pk = rsa.PrivateKey.load_pkcs1(pkcs1_pem)
            print("Successfully converted from PKCS8 to PKCS1 and validated with rsa!")
            print(pkcs1_pem.decode('utf-8'))
        except Exception as e:
            print(f"Failed loading as PKCS8: {e}")
            
except Exception as e:
    print(f"Error: {e}")
