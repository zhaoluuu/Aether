import os
from dotenv import load_dotenv
import rsa

load_dotenv()
pk = os.getenv("ALIPAY_PRIVATE_KEY", "").replace("\\n", "\n")

if not pk:
    print("NO KEY")
else:
    if "-----BEGIN RSA PRIVATE KEY-----" not in pk and "-----BEGIN PRIVATE KEY-----" not in pk:
        print("NO HEADERS. I will wrap it.")
        pk = f"-----BEGIN RSA PRIVATE KEY-----\n{pk}\n-----END RSA PRIVATE KEY-----"
    
    try:
        rsa.PrivateKey.load_pkcs1(pk.encode("utf-8"), format='PEM')
        print("PKCS1 SUCCESS!")
    except Exception as e1:
        print(f"PKCS1 FAIL: {e1}")
        try:
            # If it's PKCS8, we might need to convert it or let the user know.
            print("Try with PKCS8 format wrapper instead?")
        except Exception:
            pass
