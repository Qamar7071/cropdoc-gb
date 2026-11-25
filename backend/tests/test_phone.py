"""Phone mode: a self-signed certificate that covers this computer's Wi-Fi address."""

from __future__ import annotations

import ipaddress

from cryptography import x509

from app.phone import ensure_certificate, lan_addresses


def san_ips(cert_path):
    cert = x509.load_pem_x509_certificate(cert_path.read_bytes())
    names = cert.extensions.get_extension_for_class(x509.SubjectAlternativeName).value
    return {str(ip) for ip in names.get_values_for_type(x509.IPAddress)}, names.get_values_for_type(
        x509.DNSName
    )


def test_certificate_covers_lan_address_and_localhost(tmp_path):
    cert, key = ensure_certificate(tmp_path, ["192.168.1.20"])
    ips, dns = san_ips(cert)
    assert {"192.168.1.20", "127.0.0.1"} <= ips and "localhost" in dns
    assert b"PRIVATE KEY" in key.read_bytes()


def test_certificate_is_reused_until_the_address_changes(tmp_path):
    cert, _ = ensure_certificate(tmp_path, ["192.168.1.20"])
    first = cert.read_bytes()
    ensure_certificate(tmp_path, ["192.168.1.20"])
    assert cert.read_bytes() == first  # same Wi-Fi: phone does not have to accept a new certificate
    ensure_certificate(tmp_path, ["10.0.0.7"])
    assert cert.read_bytes() != first
    assert "10.0.0.7" in san_ips(cert)[0]


def test_lan_addresses_are_private_ipv4():
    for address in lan_addresses():
        ip = ipaddress.ip_address(address)
        assert ip.version == 4 and ip.is_private and not ip.is_loopback
