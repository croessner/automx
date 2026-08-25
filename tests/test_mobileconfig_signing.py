from __future__ import annotations

import plistlib
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from asn1crypto import cms
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import pkcs7
from cryptography.x509.oid import NameOID
from fastapi.testclient import TestClient

from automx.app import create_app
from automx.cli import main
from automx.commands import probe
from automx.configuration import ConfigurationError, ConfigurationRepository
from automx.documents import mobileconfig_document_result
from automx.mobileconfig_signing import MobileconfigSigningError, inspect_mobileconfig


def _write_signing_identity(
    tmp_path: Path,
    *,
    password: bytes = b"synthetic-passphrase",
) -> tuple[rsa.RSAPrivateKey, x509.Certificate]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "automx.test signer")])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(subject)
        .issuer_name(subject)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(days=1))
        .add_extension(
            x509.KeyUsage(
                digital_signature=True,
                content_commitment=False,
                key_encipherment=False,
                data_encipherment=False,
                key_agreement=False,
                key_cert_sign=False,
                crl_sign=False,
                encipher_only=None,
                decipher_only=None,
            ),
            critical=True,
        )
        .sign(key, hashes.SHA256())
    )
    (tmp_path / "signer.pem").write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_path = tmp_path / "signer-key.pem"
    key_path.write_bytes(
        key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.BestAvailableEncryption(password),
        )
    )
    key_path.chmod(0o600)
    password_path = tmp_path / "signer-password"
    password_path.write_bytes(password + b"\n")
    password_path.chmod(0o600)
    return key, certificate


def _write_config(tmp_path: Path, *, signing: bool = True) -> Path:
    signing_options = (
        """
mobileconfig_sign = yes
mobileconfig_signing_certificate = signer.pem
mobileconfig_signing_key = signer-key.pem
mobileconfig_signing_key_password_file = signer-password
"""
        if signing
        else ""
    )
    config = tmp_path / "automx.conf"
    config.write_text(
        f"""
[automx]
provider = example.test
domains = example.test
{signing_options}
[global]
backend = static
account_name = Example Mail
imap = yes
imap_server = imap.example.test
imap_port = 993
imap_encryption = ssl
imap_auth = plaintext
smtp = yes
smtp_server = smtp.example.test
smtp_port = 465
smtp_encryption = ssl
smtp_auth = plaintext
""",
        encoding="utf-8",
    )
    return config


def test_mobileconfig_signing_is_in_process_and_cryptographically_verified(
    tmp_path: Path,
) -> None:
    _write_signing_identity(tmp_path)
    repository = ConfigurationRepository.from_path(_write_config(tmp_path))

    result = mobileconfig_document_result(
        repository,
        "user@example.test",
        common_name="Example User",
    )
    inspected = inspect_mobileconfig(result.body)
    profile = plistlib.loads(inspected.content)

    assert result.signature.signed is True
    assert result.signature.integrity_valid is True
    assert inspected == result.signature
    assert inspected.signer_sha256 is not None
    mail_payload = profile["PayloadContent"][0]
    assert mail_payload["EmailAccountName"] == "Example User"
    assert "IncomingPassword" not in mail_payload
    assert "OutgoingPassword" not in mail_payload


def test_render_mobileconfig_reports_signature_without_contaminating_stdout(
    tmp_path: Path,
    capsysbinary: pytest.CaptureFixture[bytes],
) -> None:
    _write_signing_identity(tmp_path)
    config = _write_config(tmp_path)

    assert (
        main(
            [
                "render",
                "mobileconfig",
                "--config",
                str(config),
                "--email",
                "user@example.test",
                "--signature-status",
            ]
        )
        == 0
    )
    captured = capsysbinary.readouterr()

    assert inspect_mobileconfig(captured.out).integrity_valid is True
    assert b"signature: valid" in captured.err
    assert b"trust: device-dependent" in captured.err


def test_mobileconfig_signature_inspection_rejects_modified_profile_bytes(
    tmp_path: Path,
) -> None:
    _write_signing_identity(tmp_path)
    repository = ConfigurationRepository.from_path(_write_config(tmp_path))
    result = mobileconfig_document_result(
        repository,
        "user@example.test",
        common_name="Example User",
    )
    tampered = bytearray(result.body)
    offset = result.body.index(b"Example User")
    tampered[offset] = ord("A")

    with pytest.raises(MobileconfigSigningError, match="signature is invalid"):
        inspect_mobileconfig(bytes(tampered))


def test_mobileconfig_signature_inspection_rejects_mislabelled_algorithm(
    tmp_path: Path,
) -> None:
    _write_signing_identity(tmp_path)
    signed = mobileconfig_document_result(
        ConfigurationRepository.from_path(_write_config(tmp_path)),
        "user@example.test",
    ).body
    content_info = cms.ContentInfo.load(signed)
    content_info["content"]["signer_infos"][0]["signature_algorithm"]["algorithm"] = "rsassa_pss"

    with pytest.raises(MobileconfigSigningError, match="unsupported signature algorithm"):
        inspect_mobileconfig(content_info.dump())


def test_valid_pre_signed_static_mobileconfig_is_preserved(tmp_path: Path) -> None:
    _write_signing_identity(tmp_path)
    signing_config = _write_config(tmp_path)
    signed = mobileconfig_document_result(
        ConfigurationRepository.from_path(signing_config),
        "user@example.test",
    ).body
    (tmp_path / "profile.mobileconfig").write_bytes(signed)
    signing_config.write_text(
        """
[automx]
provider = example.test
domains = example.test
[global]
backend = file
mobileconfig = profile.mobileconfig
""",
        encoding="utf-8",
    )

    result = mobileconfig_document_result(
        ConfigurationRepository.from_path(signing_config),
        "user@example.test",
    )

    assert result.body == signed
    assert result.signature.signed is True
    assert result.signature.integrity_valid is True


def test_historical_cms_signed_attributes_are_verified(tmp_path: Path) -> None:
    key, certificate = _write_signing_identity(tmp_path)
    unsigned = mobileconfig_document_result(
        ConfigurationRepository.from_path(_write_config(tmp_path, signing=False)),
        "user@example.test",
    ).body
    signed = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(unsigned)
        .add_signer(certificate, key, hashes.SHA256())
        .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.Binary])
    )

    inspected = inspect_mobileconfig(signed)

    assert inspected.content == unsigned
    assert inspected.signed is True
    assert inspected.integrity_valid is True


def test_remote_probe_accepts_and_reports_signed_mobileconfig(tmp_path: Path) -> None:
    _write_signing_identity(tmp_path)
    client = TestClient(create_app(config_path=_write_config(tmp_path)))

    class LocalClient:
        def request(
            self,
            path: str,
            *,
            body: bytes | None = None,
            content_type: str | None = None,
            expected_status: int = 200,
        ) -> bytes:
            headers = {"content-type": content_type} if content_type else {}
            response = (
                client.post(path, content=body, headers=headers)
                if body is not None
                else client.get(path, headers=headers)
            )
            assert response.status_code == expected_status
            return response.content

    results = probe.probe_autodiscover(
        LocalClient(),  # type: ignore[arg-type]
        "user@example.test",
        False,
    )

    mobileconfig = next(result for result in results if result.name == "mobileconfig")
    assert "signature integrity is valid" in mobileconfig.detail


def test_signing_configuration_fails_closed_for_missing_or_exposed_keys(
    tmp_path: Path,
) -> None:
    missing = _write_config(tmp_path)
    with pytest.raises(ConfigurationError, match="signing certificate"):
        ConfigurationRepository.from_path(missing)

    _write_signing_identity(tmp_path)
    (tmp_path / "signer-key.pem").chmod(0o644)
    with pytest.raises(ConfigurationError, match="owner-only permissions"):
        ConfigurationRepository.from_path(missing)


def test_signing_options_require_explicit_enablement(tmp_path: Path) -> None:
    config = _write_config(tmp_path, signing=False)
    content = config.read_text(encoding="utf-8").replace(
        "domains = example.test",
        "domains = example.test\nmobileconfig_signing_certificate = signer.pem",
    )
    config.write_text(content, encoding="utf-8")

    with pytest.raises(ConfigurationError, match="mobileconfig_sign=yes"):
        ConfigurationRepository.from_path(config)
