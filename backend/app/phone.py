"""Phone mode: serve the app over HTTPS on the local Wi-Fi so a phone can use the live camera.

Why HTTPS? Browsers only give a web page access to the camera on a *secure* origin: ``https://``
or ``localhost``. A laptop opening ``http://127.0.0.1`` is fine, but a phone opening
``http://192.168.x.x`` is not, so the live scanner would be blocked there.

We create a self-signed certificate once (saved in ``data/app/certs``). The phone shows a
"connection not private" warning the first time, because no public authority signed it; the
farmer taps "Advanced → Proceed" once. Traffic stays inside the local network.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import ipaddress
import socket
from pathlib import Path


def lan_addresses() -> list[str]:
    """IPv4 addresses of this computer on the local network (best effort, no internet needed)."""
    found: list[str] = []
    try:  # the address the OS would use for outgoing traffic; UDP "connect" sends no packet
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.connect(("10.255.255.255", 1))
            found.append(sock.getsockname()[0])
    except OSError:
        pass
    with contextlib.suppress(OSError):
        found.extend(socket.gethostbyname_ex(socket.gethostname())[2])
    usable = []
    for address in found:
        ip = ipaddress.ip_address(address)
        if ip.is_private and not ip.is_loopback and not ip.is_link_local and address not in usable:
            usable.append(address)
    return usable


def ensure_certificate(folder: Path, addresses: list[str]) -> tuple[Path, Path]:
    """Return (cert, key) paths; create a new self-signed certificate if missing or if an address changed."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ec
    from cryptography.x509.oid import NameOID

    folder.mkdir(parents=True, exist_ok=True)
    cert_path, key_path = folder / "cert.pem", folder / "key.pem"
    wanted = {ipaddress.ip_address(a) for a in [*addresses, "127.0.0.1"]}

    if cert_path.exists() and key_path.exists():
        try:
            existing = x509.load_pem_x509_certificate(cert_path.read_bytes())
            names = existing.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
            still_valid = existing.not_valid_after_utc > dt.datetime.now(dt.UTC) + dt.timedelta(days=7)
            if still_valid and wanted <= set(names.get_values_for_type(x509.IPAddress)):
                return cert_path, key_path
        except (ValueError, x509.ExtensionNotFound):
            pass  # unreadable or old format: make a new one

    key = ec.generate_private_key(ec.SECP256R1())
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "CropDoc GB (local)")])
    now = dt.datetime.now(dt.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - dt.timedelta(minutes=5))
        .not_valid_after(now + dt.timedelta(days=825))
        .add_extension(
            x509.SubjectAlternativeName([x509.DNSName("localhost"), *(x509.IPAddress(ip) for ip in wanted)]),
            critical=False,
        )
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
    )
    cert_path.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    return cert_path, key_path
