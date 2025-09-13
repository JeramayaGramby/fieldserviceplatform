import logging
from io import BytesIO
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import padding as asym_padding
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
import os
from datetime import datetime


# Load RSA private key from PEM bytes, assert if invalid
def load_private_key(pem_bytes: bytes, password: bytes | None = None):
    try:
        key = serialization.load_pem_private_key(
            pem_bytes,
            password=password,
            backend=default_backend()
        )
        # Basic sanity check: ensure it has private numbers (i.e., it's a private key)
        _ = key.private_numbers()
        return key
    except Exception as e:
        logging.error("Invalid private key file. Must be a PEM RSA private key.")
        raise AssertionError("Uploaded key file is not a valid RSA private key.") from e

# Decrypt small payload with RSA private key (env content should be envelope-key + symmetric scheme in real prod)
# For demo simplicity: RSA-OAEP over the entire content (adequate for small .env).
def rsa_decrypt_env(private_key, encrypted_bytes: bytes) -> bytes:
    try:
        plaintext = private_key.decrypt(
            encrypted_bytes,
            asym_padding.OAEP(
                mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                algorithm=hashes.SHA256(),
                label=None,
            )
        )
        return plaintext
    except Exception as e:
        logging.error("Failed to decrypt .env.enc with provided private key.")
        raise AssertionError("Decryption failed. Ensure the .env.enc matches this private key.") from e

class EncryptedLogger:
    def __init__(self, public_key):
        """
        public_key: an RSA public key object from cryptography.hazmat
        """
        self.public_key = public_key
        self.log_dir = ".log"
        os.makedirs(self.log_dir, exist_ok=True)

    def save_log(self, log_content: str):
        """
        Encrypts and saves the log content to a timestamped file in .log/
        """
        if not isinstance(log_content, bytes):
            log_content = log_content.encode("utf-8")

        # Encrypt with RSA public key
        try:
            encrypted = self.public_key.encrypt(
                log_content,
                asym_padding.OAEP(
                    mgf=asym_padding.MGF1(algorithm=hashes.SHA256()),
                    algorithm=hashes.SHA256(),
                    label=None,
                )
            )
        except Exception as e:
            raise AssertionError(f"Failed to encrypt log: {e}")

        # Save to timestamped file
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(self.log_dir, f"log_{ts}.log")
        with open(filename, "wb") as f:
            f.write(encrypted)
        return filename


class EncryptedLogHandler(logging.Handler):
    """
    A logging.Handler that encrypts each log record and writes it to .log/ using RSA public key encryption.
    """
    def __init__(self, public_key):
        super().__init__()
        self.logger = EncryptedLogger(public_key)

    def emit(self, record):
        try:
            msg = self.format(record)
            self.logger.save_log(msg)
        except Exception as e:
            # We don't want logging failures to crash the app
            logging.getLogger(__name__).warning(f"Failed to encrypt log: {e}")
