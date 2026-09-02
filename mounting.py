import subprocess
import json
from pathlib import Path

def list_mounts():
    """Show all mounted block devices with their UUID and current mountpoint."""
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

DRIVE_ID = "029B-2C3A"
DRIVE_MOUNT = find_mountpoint(DRIVE_ID)

def resolve_corpus_root(drive_id: str) -> Path:
    mount = find_mountpoint(drive_id)
    if mount is None:
        raise RuntimeError(f"drive {drive_id} not mounted — plug it in")
    return Path(mount)
