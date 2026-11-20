import io
import json
import tarfile
from hashlib import sha256
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.request import urlopen

from .wordnet_adapter import AUX_FILES, CORE_FILES, VERSION, WordNet

URL = "https://wordnetcode.princeton.edu/3.0/WordNet-3.0.tar.gz"
ARCHIVE_SHA256 = "640db279c949a88f61f851dd54ebbb22d003f8b90b85267042ef85a3781d3a52"
MAX_BYTES = 20 * 1024 * 1024


def load_checksums(path: Path) -> dict[str, str]:
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(manifest, dict):
        raise TypeError("WordNet checksum manifest must be an object")
    return manifest


def install_wordnet(directory: Path, archive: Path | None = None) -> dict:
    if directory.exists():
        manifest = load_checksums(directory / "sha256.json")
        if set(manifest) != CORE_FILES | AUX_FILES | {"LICENSE"}:
            raise ValueError(
                "Existing directory does not contain a complete installed snapshot"
            )
        WordNet(directory, manifest, "wordnet-3.0")
        if (
            sha256((directory / "LICENSE").read_bytes()).hexdigest()
            != manifest["LICENSE"]
        ):
            raise ValueError("WordNet license checksum mismatch")
        return {"version": VERSION, "directory": str(directory), "files": manifest}

    if archive is None:
        with urlopen(URL, timeout=60) as response:
            content = response.read(MAX_BYTES + 1)
    else:
        with archive.open("rb") as file:
            content = file.read(MAX_BYTES + 1)
    if sha256(content).hexdigest() != ARCHIVE_SHA256:
        raise ValueError("WordNet 3.0 archive SHA256 mismatch")

    directory.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(dir=directory.parent) as temp:
        staged = Path(temp) / "wordnet30"
        staged.mkdir()
        manifest = {}
        with tarfile.open(fileobj=io.BytesIO(content), mode="r:gz") as bundle:
            for name in sorted(CORE_FILES | AUX_FILES | {"LICENSE"}):
                path = name if name == "LICENSE" else f"dict/{name}"
                member = bundle.getmember(f"WordNet-3.0/{path}")
                if not member.isfile():
                    raise ValueError(f"Unexpected WordNet archive member: {path}")
                with bundle.extractfile(member) as source:
                    data = source.read()
                (staged / name).write_bytes(data)
                manifest[name] = sha256(data).hexdigest()
        WordNet(staged, manifest, "wordnet-3.0")
        (staged / "sha256.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        staged.rename(directory)
    return {
        "version": VERSION,
        "directory": str(directory),
        "files": manifest,
        "source_url": URL,
        "archive_sha256": ARCHIVE_SHA256,
    }
