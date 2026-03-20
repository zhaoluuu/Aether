import re

pkcs1_base64 = (
    "MIIEowIBAAKCAQEAuz9Wtlra0AcbeTWM6OXdxLWXixi3h1E9ODVsAxT1/kgdsNK8"
    "EZseFEMrG8bJKeBU1h3gbACninrt83YDG+2NOJQEw6DYOsyMveKlYlzKGhJd7E8H"
    "E8qHBl1iVpwrSNXUKqbgrYw4h7skH94JGjlIe0HoXSOLjWNkFzMd6awiN1CxnSQQ"
    "eiewkkDiSC8JdIq0tHbUTV8mDo8pYNCEgV5pqMZei8M+D24/54UmWSQ7oA35jISl"
    "SlPYWvWGIPab/9XEUiUEMNAunPBkRotuCZ3Q28f/DxM6eXPEnYSN5J7gPSAXGR7R"
    "k3mxKEfT+0xZrSiY4yeMDb1ttNrciwpah9LOAwIDAQABAoIBAFrJuyFvq+hxicCb"
    "VlcWHRDjezbWJSZXHXfDbzuPTjacgMjbZJSkwVDRwHUXTTIgswGeOtIi/xkFwZnp"
    "/lfsNizYl/bCZhUcWKE44zduBg/eF+wb5TKTYCSV4rhbwCDwjI6hmw6Kjl5BPqK0"
    "5XTxkVMyAZgnQ+Kp7j3Raw+BhpWKlaYtgsYCYBZQskM+v3dIrgonFipO33EeyQr+"
    "Y2TOe/DYfauxSwpjMuaPslh6pyYYg25UvetN8+TBMwWIJD/Z99MWMta7ku7JXNMA"
    "Z3x8ruOn12f4ZJ2lz4PFoZBz0IOw0vW00aGMUhCUKtrHUa0x7NyWy0ce22vN8Ntf"
    "1dQKvgECgYEA7D8/NSpLfquaFqfk0wGGSxfiZM8xJ4WMDJDQjOdT3oTIt9sLwzPD"
    "OHW7SroYUl/YiIC8kMKB/OHXXdpi3kqneut9OZjieO5vo8BmOqPoC3IjYJa/mvxs"
    "PwGP6W121sa3VGAB5Q0z/AKLDVE6QYwaV/4Jqd6hvWLzu1K0f4SIj7sCgYEAyudH"
    "RBTICXwLAya6E/vYivl6IwrmgPwB3txQi0xMRxXnnuwmJxs7KeljkQzEPpP/e9GU"
    "raqHGbYMLWCng2EmnqEQaY4ED5JunLfshzV3jG9jsSmRpwuC539tQIRj1wBS7C1R"
    "+PoLByd96JL6yp9Z1pADAiso0PmogphcrXqmIlkCgYB1CHf1jHhNzhDNfGrdJPo0"
    "JSbgLcv5+iyA5RSLWOWxbDJK8laHYxMo2xnnUP1PgW+xX6UKSXE/p1mbgt5LpMwH"
    "FrW4XMaEhgoEIwIBtsTzNp3T8ZoF21p8c/eo+bNPfq2/PLhzkfDYvSHJfR3Q7uj2"
    "AkEjR8j0GxsHB1enfC5ylQKBgBDCO4OnB8KoySwQdcwSwBbydiEQ1GsQ5YKnxctL"
    "mP1CFOhubtRKDn/us/eWC1tz0+VBMTuK2y/HdogE9LEIRC1T9kwRm8pBePtewZ2F"
    "UAN8a8qFOW+Hpt9CCh8LEEgA0diKAbxDwsdrfp3IDgjQUpZDPMxgDjX8eOuYdAcs"
    "Gy65AoGBANc5dk7z3wPvOQdm6UH1kYfDhMpe1TQcp8k094tFSisbyXTyYbfYuOTB"
    "MDWs40utsP+uxhGieHFYDLapqRW2XUfvlExR7Jowt0A/gtF3p5moEE0At8Tiv3lP"
    "8q3S+9ounY9Adl+8EKLQ8ceHRuOH3PbAAYDSBRWmxQpw+j1ABq+W"
)

with open(".env", "r") as f:
    text = f.read()

new_text = re.sub(r'ALIPAY_PRIVATE_KEY=".*?"', f'ALIPAY_PRIVATE_KEY="{pkcs1_base64}"', text)

with open(".env", "w") as f:
    f.write(new_text)

print("Key replaced")
