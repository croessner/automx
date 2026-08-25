"""In-process CMS signing and integrity inspection for Apple configuration profiles."""

from __future__ import annotations

import plistlib
import stat
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from asn1crypto import cms
from asn1crypto import x509 as asn1_x509
from cryptography import x509
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import pkcs7

MAX_SIGNING_MATERIAL_BYTES = 1_048_576


class MobileconfigSigningError(RuntimeError):
    """Signing material or a CMS-signed profile violates the security contract."""


@dataclass(frozen=True, slots=True)
class MobileconfigInspection:
    """Verified inner profile bytes and the integrity status of their CMS wrapper."""

    content: bytes
    signed: bool
    integrity_valid: bool
    signer_sha256: str | None = None


def _read_bounded(path: Path, *, label: str, private: bool = False) -> bytes:
    if not path.is_file():
        raise MobileconfigSigningError(f"{label} does not exist")
    if private and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise MobileconfigSigningError(f"{label} must have owner-only permissions")
    try:
        with path.open("rb") as source:
            value = source.read(MAX_SIGNING_MATERIAL_BYTES + 1)
    except OSError as exc:
        raise MobileconfigSigningError(f"{label} cannot be read") from exc
    if len(value) > MAX_SIGNING_MATERIAL_BYTES:
        raise MobileconfigSigningError(f"{label} exceeds 1 MiB")
    return value


def _validate_certificate(certificate: x509.Certificate) -> None:
    now = datetime.now(UTC)
    if not certificate.not_valid_before_utc <= now <= certificate.not_valid_after_utc:
        raise MobileconfigSigningError("mobileconfig signing certificate is not currently valid")
    try:
        key_usage = certificate.extensions.get_extension_for_class(x509.KeyUsage).value
    except x509.ExtensionNotFound:
        return
    if not key_usage.digital_signature:
        raise MobileconfigSigningError(
            "mobileconfig signing certificate does not permit digital signatures"
        )


def _profile(content: bytes) -> dict[str, object]:
    try:
        parsed: object = plistlib.loads(content)
    except plistlib.InvalidFileException as exc:
        raise MobileconfigSigningError("mobileconfig payload is not a valid property list") from exc
    if not isinstance(parsed, dict) or parsed.get("PayloadType") != "Configuration":
        raise MobileconfigSigningError("mobileconfig payload is not a configuration profile")
    return parsed


def _hash_algorithm(name: str) -> hashes.HashAlgorithm:
    algorithms: dict[str, hashes.HashAlgorithm] = {
        "sha256": hashes.SHA256(),
        "sha384": hashes.SHA384(),
        "sha512": hashes.SHA512(),
    }
    try:
        return algorithms[name]
    except KeyError as exc:
        raise MobileconfigSigningError("mobileconfig CMS uses an unsupported digest") from exc


def _signed_attributes_input(signer_info: Any, content: bytes) -> bytes:
    signed_attributes: Any = signer_info["signed_attrs"]
    if signed_attributes.native is None:
        return content
    attributes: dict[str, object] = {}
    for attribute in signed_attributes:
        name: Any = attribute["type"].native
        values: Any = attribute["values"]
        if name in {"content_type", "message_digest"}:
            if name in attributes or len(values) != 1:
                raise MobileconfigSigningError("mobileconfig CMS has ambiguous signed attributes")
            attributes[name] = values[0].native
    if attributes.get("content_type") != "data":
        raise MobileconfigSigningError("mobileconfig CMS has an invalid content type attribute")
    digest_algorithm = _hash_algorithm(signer_info["digest_algorithm"]["algorithm"].native)
    digest = hashes.Hash(digest_algorithm)
    digest.update(content)
    if attributes.get("message_digest") != digest.finalize():
        raise MobileconfigSigningError("mobileconfig CMS content digest is invalid")
    return cast(bytes, signed_attributes.untag().dump())


def inspect_mobileconfig(body: bytes) -> MobileconfigInspection:
    """Validate a plain profile or verify one attached DER-CMS signature."""

    try:
        _profile(body)
    except MobileconfigSigningError:
        pass
    else:
        return MobileconfigInspection(
            content=body,
            signed=False,
            integrity_valid=False,
        )

    try:
        content_info: Any = cms.ContentInfo.load(body)
        if content_info.dump() != body:
            raise MobileconfigSigningError("mobileconfig CMS is not canonical DER")
        if content_info["content_type"].native != "signed_data":
            raise MobileconfigSigningError("mobileconfig CMS is not SignedData")
        signed_data: Any = content_info["content"]
        if signed_data["encap_content_info"]["content_type"].native != "data":
            raise MobileconfigSigningError("mobileconfig CMS does not contain data")
        content: Any = signed_data["encap_content_info"]["content"].native
        signer_infos: Any = signed_data["signer_infos"]
    except (TypeError, ValueError, KeyError) as exc:
        raise MobileconfigSigningError(
            "mobileconfig is neither a plain profile nor valid CMS"
        ) from exc
    if not isinstance(content, bytes):
        raise MobileconfigSigningError("mobileconfig CMS has no attached profile content")
    _profile(content)
    if len(signer_infos) != 1:
        raise MobileconfigSigningError("mobileconfig CMS must contain exactly one signer")

    signer_info: Any = signer_infos[0]
    if signer_info["signature_algorithm"]["algorithm"].native != "rsassa_pkcs1v15":
        raise MobileconfigSigningError("mobileconfig CMS uses an unsupported signature algorithm")
    sid: Any = signer_info["sid"]
    if sid.name != "issuer_and_serial_number":
        raise MobileconfigSigningError("mobileconfig CMS uses an unsupported signer identifier")
    serial_number = sid.chosen["serial_number"].native
    issuer = sid.chosen["issuer"].dump()
    try:
        certificates = pkcs7.load_der_pkcs7_certificates(body)
    except ValueError as exc:
        raise MobileconfigSigningError("mobileconfig CMS certificates are malformed") from exc
    certificate = next(
        (
            item
            for item in certificates
            if item.serial_number == serial_number
            and asn1_x509.Certificate.load(item.public_bytes(serialization.Encoding.DER))[
                "tbs_certificate"
            ]["issuer"].dump()
            == issuer
        ),
        None,
    )
    if certificate is None:
        raise MobileconfigSigningError("mobileconfig CMS signer certificate is missing")
    _validate_certificate(certificate)
    public_key = certificate.public_key()
    if not isinstance(public_key, rsa.RSAPublicKey):
        raise MobileconfigSigningError("mobileconfig CMS signer must use RSA")

    signed_input = _signed_attributes_input(signer_info, content)
    digest_algorithm = _hash_algorithm(signer_info["digest_algorithm"]["algorithm"].native)
    signature: Any = signer_info["signature"].native
    if not isinstance(signature, bytes):
        raise MobileconfigSigningError("mobileconfig CMS signature is malformed")
    try:
        public_key.verify(signature, signed_input, padding.PKCS1v15(), digest_algorithm)
    except InvalidSignature as exc:
        raise MobileconfigSigningError("mobileconfig CMS signature is invalid") from exc

    return MobileconfigInspection(
        content=content,
        signed=True,
        integrity_valid=True,
        signer_sha256=certificate.fingerprint(hashes.SHA256()).hex(),
    )


class MobileconfigSigner:
    """Validated RSA identity that creates attached DER-CMS Apple profiles."""

    def __init__(
        self,
        certificate: x509.Certificate,
        private_key: rsa.RSAPrivateKey,
        chain: tuple[x509.Certificate, ...],
    ) -> None:
        self._certificate = certificate
        self._private_key = private_key
        self._chain = chain
        self.fingerprint_sha256 = certificate.fingerprint(hashes.SHA256()).hex()

    @classmethod
    def from_files(
        cls,
        certificate_path: Path,
        key_path: Path,
        password_path: Path | None,
    ) -> MobileconfigSigner:
        """Load and validate a PEM certificate bundle and owner-only RSA key."""

        certificate_bytes = _read_bounded(
            certificate_path,
            label="mobileconfig signing certificate",
        )
        key_bytes = _read_bounded(
            key_path,
            label="mobileconfig signing key",
            private=True,
        )
        password: bytes | None = None
        if password_path is not None:
            password = _read_bounded(
                password_path,
                label="mobileconfig signing key password file",
                private=True,
            ).rstrip(b"\r\n")
            if not password or b"\n" in password or b"\r" in password:
                raise MobileconfigSigningError(
                    "mobileconfig signing key password file must contain one non-empty line"
                )
        try:
            certificates = x509.load_pem_x509_certificates(certificate_bytes)
        except ValueError as exc:
            raise MobileconfigSigningError("mobileconfig signing certificate is malformed") from exc
        if not certificates:
            raise MobileconfigSigningError("mobileconfig signing certificate is missing")
        certificate, *chain = certificates
        _validate_certificate(certificate)
        try:
            private_key = serialization.load_pem_private_key(key_bytes, password=password)
        except (TypeError, ValueError) as exc:
            raise MobileconfigSigningError("mobileconfig signing key cannot be decrypted") from exc
        if not isinstance(private_key, rsa.RSAPrivateKey):
            raise MobileconfigSigningError("mobileconfig signing key must use RSA")
        if private_key.key_size < 2048:
            raise MobileconfigSigningError(
                "mobileconfig signing RSA key must be at least 2048 bits"
            )
        certificate_public = certificate.public_key()
        if not isinstance(certificate_public, rsa.RSAPublicKey):
            raise MobileconfigSigningError("mobileconfig signing certificate must use RSA")
        if certificate_public.public_numbers() != private_key.public_key().public_numbers():
            raise MobileconfigSigningError(
                "mobileconfig signing key does not match the signing certificate"
            )
        return cls(certificate, private_key, tuple(chain))

    def sign(self, content: bytes) -> tuple[bytes, MobileconfigInspection]:
        """Create attached DER-CMS and verify its exact embedded profile before return."""

        _profile(content)
        _validate_certificate(self._certificate)
        builder = (
            pkcs7.PKCS7SignatureBuilder()
            .set_data(content)
            .add_signer(self._certificate, self._private_key, hashes.SHA256())
        )
        for certificate in self._chain:
            builder = builder.add_certificate(certificate)
        body = builder.sign(
            serialization.Encoding.DER,
            [pkcs7.PKCS7Options.Binary, pkcs7.PKCS7Options.NoAttributes],
        )
        inspected = inspect_mobileconfig(body)
        if inspected.content != content or inspected.signer_sha256 != self.fingerprint_sha256:
            raise MobileconfigSigningError("mobileconfig CMS verification did not preserve input")
        return body, inspected
