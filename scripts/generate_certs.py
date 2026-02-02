#!/usr/bin/env python3
"""
SSL Certificate Generation Script for HoneyGrid
Generates CA, server, and agent certificates for mutual TLS authentication.
"""

import os
import sys
from pathlib import Path
from datetime import datetime, timedelta, timezone
import ipaddress
from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def generate_private_key():
    """Generate RSA private key."""
    return rsa.generate_private_key(
        public_exponent=65537,
        key_size=2048,
    )


def save_private_key(key, filepath, password=None):
    """Save private key to file."""
    encryption = serialization.NoEncryption()
    if password:
        encryption = serialization.BestAvailableEncryption(password.encode())

    with open(filepath, "wb") as f:
        f.write(
            key.private_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PrivateFormat.TraditionalOpenSSL,
                encryption_algorithm=encryption,
            )
        )
    print(f"✓ Saved private key: {filepath}")


def save_certificate(cert, filepath):
    """Save certificate to file."""
    with open(filepath, "wb") as f:
        f.write(cert.public_bytes(serialization.Encoding.PEM))
    print(f"✓ Saved certificate: {filepath}")


def create_ca(cert_dir):
    """Create Certificate Authority."""
    print("\n[1/3] Creating Certificate Authority...")

    # Generate CA private key
    ca_key = generate_private_key()

    # Create CA certificate
    subject = issuer = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "UK"),
            x509.NameAttribute(NameOID.STATE_OR_PROVINCE_NAME, "England"),
            x509.NameAttribute(NameOID.LOCALITY_NAME, "Coventry"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "HoneyGrid Project"),
            x509.NameAttribute(NameOID.COMMON_NAME, "HoneyGrid Root CA"),
        ]
    )

    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(issuer)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=3650))  # 10 years
        .add_extension(
            x509.BasicConstraints(ca=True, path_length=0),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_cert_sign=True,
                crl_sign=True,
                key_encipherment=False,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )

    # Save CA files
    save_private_key(ca_key, cert_dir / "ca.key")
    save_certificate(ca_cert, cert_dir / "ca.crt")

    return ca_key, ca_cert


def create_server_cert(cert_dir, ca_key, ca_cert, hostname="localhost"):
    """Create server certificate signed by CA."""
    print(f"\n[2/3] Creating server certificate for '{hostname}'...")

    # Generate server private key
    server_key = generate_private_key()

    # Create server certificate
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "UK"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "HoneyGrid Project"),
            x509.NameAttribute(NameOID.COMMON_NAME, hostname),
        ]
    )

    server_cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(server_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))  # 1 year
        .add_extension(
            x509.SubjectAlternativeName(
                [
                    x509.DNSName(hostname),
                    x509.DNSName("localhost"),
                    x509.IPAddress(ipaddress.IPv4Address("127.0.0.1")),
                ]
            ),
            critical=False,
        )
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                key_cert_sign=False,
                crl_sign=False,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )

    # Save server files
    save_private_key(server_key, cert_dir / "server.key")
    save_certificate(server_cert, cert_dir / "server.crt")

    return server_key, server_cert


def create_agent_cert(cert_dir, ca_key, ca_cert, agent_id="client-001"):
    """Create agent certificate signed by CA."""
    print(f"\n[3/3] Creating agent certificate for '{agent_id}'...")

    # Generate agent private key
    agent_key = generate_private_key()

    # Create agent certificate
    subject = x509.Name(
        [
            x509.NameAttribute(NameOID.COUNTRY_NAME, "UK"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, "HoneyGrid Project"),
            x509.NameAttribute(NameOID.COMMON_NAME, agent_id),
        ]
    )

    agent_cert = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(ca_cert.subject)
        .public_key(agent_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(timezone.utc))
        .not_valid_after(datetime.now(timezone.utc) + timedelta(days=365))  # 1 year
        .add_extension(
            x509.BasicConstraints(ca=False, path_length=None),
            critical=True,
        )
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                key_encipherment=True,
                key_cert_sign=False,
                crl_sign=False,
                content_commitment=False,
                data_encipherment=False,
                key_agreement=False,
                encipher_only=False,
                decipher_only=False,
            ),
            critical=True,
        )
        .add_extension(
            x509.ExtendedKeyUsage([ExtendedKeyUsageOID.CLIENT_AUTH]),
            critical=True,
        )
        .sign(ca_key, hashes.SHA256())
    )

    # Save agent files
    save_private_key(agent_key, cert_dir / f"client_{agent_id}.key")
    save_certificate(agent_cert, cert_dir / f"client_{agent_id}.crt")

    return agent_key, agent_cert


def main():
    """Main certificate generation workflow."""
    print("=" * 60)
    print("HoneyGrid SSL Certificate Generator")
    print("=" * 60)

    # Get project root
    project_root = Path(__file__).parent.parent
    cert_dir = project_root / "certs"

    # Create certs directory
    cert_dir.mkdir(exist_ok=True)
    print(f"\nCertificate directory: {cert_dir}")

    # Generate certificates
    ca_key, ca_cert = create_ca(cert_dir)
    server_key, server_cert = create_server_cert(cert_dir, ca_key, ca_cert)
    agent_key, agent_cert = create_agent_cert(cert_dir, ca_key, ca_cert, "agent-001")

    # Generate additional agent certificates if requested
    if len(sys.argv) > 1:
        try:
            num_agents = int(sys.argv[1])
            for i in range(2, num_agents + 1):
                create_agent_cert(cert_dir, ca_key, ca_cert, f"agent-{i:03d}")
        except ValueError:
            print("\nWarning: Invalid number of agents specified")

    print("\n" + "=" * 60)
    print("✓ Certificate generation complete!")
    print("=" * 60)
    print("\nGenerated files:")
    print(f"  • CA Certificate:     {cert_dir / 'ca.crt'}")
    print(f"  • Server Certificate: {cert_dir / 'server.crt'}")
    print(f"  • Agent Certificate:  {cert_dir / 'client_agent-001.crt'}")
    print("\nUsage:")
    print("  Server: Use server.crt, server.key, ca.crt")
    print("  Agent:  Use client_*.crt, client_*.key, ca.crt")
    print("\nTo generate additional agent certificates:")
    print(f"  python {Path(__file__).name} <num_agents>")
    print()


if __name__ == "__main__":
    main()
