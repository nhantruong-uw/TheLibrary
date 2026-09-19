"""Locate the removable drive that holds the PDF corpus."""

import json
import subprocess
from pathlib import Path
from config import DRIVE_ID

def list_mounts():
    """Print all mounted block devices with their UUID and mountpoint."""
    out = subprocess.run(
        ["lsblk", "-J", "-o", "NAME,UUID,LABEL,MOUNTPOINT,FSTYPE"],
        capture_output=True, text=True,
    )
    data = json.loads(out.stdout)

    def walk(devices):
        for d in devices:
            if d.get("mountpoint"):
                print(f"UUID={d.get('uuid')!r}  LABEL={d.get('label')!r}  "
                      f"MOUNT={d.get('mountpoint')!r}  FS={d.get('fstype')!r}")
            if d.get("children"):
                walk(d["children"])

    walk(data.get("blockdevices", []))


def find_mountpoint(drive_uuid: str) -> str | None:
    """Find the current mountpoint of a drive, identified by its UUID.

    Args:
        drive_uuid: The volume UUID reported by blkid/lsblk.

    Returns:
        The mountpoint path, or None if the drive isn't mounted.
    """
    out = subprocess.run(
        ["lsblk", "-J", "-o", "UUID,MOUNTPOINT"],
        capture_output=True, text=True,
    )
    data = json.loads(out.stdout)

    def search(devices):
        for d in devices:
            if d.get("uuid") == drive_uuid and d.get("mountpoint"):
                return d["mountpoint"]
            if d.get("children"):
                found = search(d["children"])
                if found:
                    return found
        return None

    return search(data.get("blockdevices", []))


DRIVE_MOUNT = find_mountpoint(DRIVE_ID)


def resolve_corpus_root(drive_id: str) -> Path:
    """Resolve the corpus root directory from a drive UUID.

    Args:
        drive_id: The volume UUID of the drive holding the corpus.

    Returns:
        The mountpoint path of the drive.

    Raises:
        RuntimeError: If the drive is not currently mounted.
    """
    mount = find_mountpoint(drive_id)
    if mount is None:
        raise RuntimeError(f"drive {drive_id} not mounted — plug it in")
    return Path(mount)
