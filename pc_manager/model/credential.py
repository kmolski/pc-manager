from io import StringIO

from paramiko.dsskey import DSSKey
from paramiko.ecdsakey import ECDSAKey
from paramiko.ed25519key import Ed25519Key
from paramiko.rsakey import RSAKey
from sqlalchemy_utils.types.encrypted.encrypted_type import (
    AesEngine,
    StringEncryptedType,
)

from app import db, SECRET_KEY


class Credential(db.Model):
    __tablename__ = "credential"
    __mapper_args__ = {"polymorphic_on": "type"}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(127), unique=True)
    type = db.Column(db.String(31))

    username = db.Column(StringEncryptedType(db.String, SECRET_KEY, AesEngine, "pkcs5"))
    secret = db.Column(StringEncryptedType(db.String, SECRET_KEY, AesEngine, "pkcs5"))


class SshCredential(Credential):
    KEY_TYPES = {"ed25519": Ed25519Key, "ecdsa": ECDSAKey, "dss": DSSKey, "rsa": RSAKey}

    key = db.Column(StringEncryptedType(db.String, SECRET_KEY, AesEngine, "pkcs5"))
    key_type = db.Column(
        db.Enum(*KEY_TYPES.keys(), name="ssh_key_type", validate_strings=True)
    )

    def get_ssh_credentials(self):
        raise NotImplementedError()

    @classmethod
    def get_pkey(cls, key_text, key_type, password=None):
        key_file = StringIO(key_text)
        pkey_cls = cls.KEY_TYPES[key_type]
        return pkey_cls.from_private_key(key_file, password)


class Password(SshCredential):
    PROVIDER_NAME = "password"
    READABLE_NAME = "Username and password"

    REQUIRES_PASSWORD = True
    REQUIRES_KEY = False

    __mapper_args__ = {"polymorphic_identity": PROVIDER_NAME}

    def __init__(self, name, username, secret, id=None):
        self.id = id
        self.name = name
        self.username = username
        self.secret = secret

    def get_ssh_credentials(self):
        return self.username, self.secret, None


class SshKeyNoPassword(SshCredential):
    PROVIDER_NAME = "ssh_no_passwd"
    READABLE_NAME = "SSH key with no password"

    REQUIRES_PASSWORD = False
    REQUIRES_KEY = True

    __mapper_args__ = {"polymorphic_identity": PROVIDER_NAME}

    def __init__(self, name, username, key, key_type, id=None):
        self.id = id
        self.name = name
        self.username = username
        self.key = key
        self.key_type = key_type

    def get_ssh_credentials(self):
        pkey = self.get_pkey(self.key, self.key_type)
        return self.username, None, pkey


class SshKeyWithPassword(SshCredential):
    PROVIDER_NAME = "ssh_with_passwd"
    READABLE_NAME = "SSH key with password"

    REQUIRES_PASSWORD = True
    REQUIRES_KEY = True

    __mapper_args__ = {"polymorphic_identity": PROVIDER_NAME}

    def __init__(self, name, username, secret, key, key_type, id=None):
        self.id = id
        self.name = name
        self.username = username
        self.secret = secret
        self.key = key
        self.key_type = key_type

    def get_ssh_credentials(self):
        pkey = self.get_pkey(self.key, self.key_type, self.secret)
        return self.username, self.secret, pkey
