"""
patch_vba_binary.py
Direct binary patch of vbaProject.bin inside the XLSM zip.
OLD pattern (82 chars) is replaced with NEW padded to same length with spaces.
VBA ignores trailing spaces on a line, so this is safe.
No Excel or COM needed.
"""
import zipfile, shutil, os, struct
from pathlib import Path

XLSM = r'C:\tr_dash-main\work\TR5_PreOp_Gantt_20260415\excel\TR5_PreOp_Gantt_20260415_162140.xlsm'
BACKUP = XLSM + '.bak_vba'
VBA_PATH_IN_ZIP = 'xl/vbaProject.bin'

# The exact string in VBA source (as it appears in the module)
OLD_STR = "RefreshGanttExactRange ws, DateSerial(2026, 4, 27), DateSerial(2026, 5, 17), False"
NEW_STR = "RefreshGantt ws, False"

# Pad NEW to match OLD length with trailing spaces (VBA ignores them)
assert len(NEW_STR) <= len(OLD_STR), "NEW must be shorter or equal to OLD"
NEW_PADDED = NEW_STR.ljust(len(OLD_STR))  # same byte length

print(f"OLD len={len(OLD_STR)}: {OLD_STR!r}")
print(f"NEW len={len(NEW_PADDED)}: {NEW_PADDED!r}")
assert len(OLD_STR) == len(NEW_PADDED), "Length mismatch!"

OLD_BYTES = OLD_STR.encode('utf-8')
NEW_BYTES = NEW_PADDED.encode('utf-8')

# Backup original
shutil.copy2(XLSM, BACKUP)
print(f"Backup: {BACKUP}")

# Extract vbaProject.bin, patch it, repack
with zipfile.ZipFile(XLSM, 'r') as zin:
    vba_data = zin.read(VBA_PATH_IN_ZIP)
    all_names = zin.namelist()

print(f"vbaProject.bin size: {len(vba_data):,} bytes")

# Count occurrences in the binary
count = vba_data.count(OLD_BYTES)
print(f"Occurrences of OLD pattern: {count}")

if count == 0:
    # Try with different encodings (VBA may store as UTF-16 in some sections)
    OLD_UTF16 = OLD_STR.encode('utf-16-le')
    count_utf16 = vba_data.count(OLD_UTF16)
    print(f"UTF-16LE occurrences: {count_utf16}")
    if count_utf16 > 0:
        NEW_UTF16 = NEW_PADDED.encode('utf-16-le')
        assert len(OLD_UTF16) == len(NEW_UTF16)
        patched = vba_data.replace(OLD_UTF16, NEW_UTF16)
        count = count_utf16
        encoding_used = 'utf-16-le'
    else:
        print("[ERROR] Pattern not found in binary. Manual COM patch required.")
        # Restore backup
        shutil.copy2(BACKUP, XLSM)
        raise SystemExit(1)
else:
    patched = vba_data.replace(OLD_BYTES, NEW_BYTES)
    encoding_used = 'utf-8'

print(f"Patched {count} occurrences (encoding: {encoding_used})")

# Verify
remaining = patched.count(OLD_BYTES)
print(f"Remaining: {remaining}")

# Write patched data back into the XLSM zip
tmp = XLSM + '.tmp'
with zipfile.ZipFile(XLSM, 'r') as zin:
    with zipfile.ZipFile(tmp, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
        for item in zin.infolist():
            if item.filename == VBA_PATH_IN_ZIP:
                zout.writestr(item, patched)
                print(f"  Wrote patched {VBA_PATH_IN_ZIP} ({len(patched):,} bytes)")
            else:
                zout.writestr(item, zin.read(item.filename))

os.replace(tmp, XLSM)
print(f"XLSM updated: {XLSM}")
print("Done.")
