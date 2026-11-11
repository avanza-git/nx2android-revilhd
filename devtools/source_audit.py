"""Check versionable source for private data, binaries, broken doc links and lost notices.

Ignored local build outputs are not release source. Never print matching secret values.
"""
import re
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN = {'.apk', '.nsp', '.nsz', '.xci', '.xcz', '.nca', '.nso', '.nro', '.dmsv', '.spv', '.metallib', '.dll', '.dylib', '.so', '.a', '.exe', '.keystore', '.pem', '.p12', '.keys', '.pyc'}
PRIVATE_PARTS = {'.gamedump', '.venv', 'tools', 'work', 'build', '__pycache__', '.claude', '.codex', '.aws'}
SECRETS = [re.compile(rb'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----'),
           re.compile(rb'\b(?:AKIA|ASIA)[A-Z0-9]{16}\b'),
           re.compile(rb'\bgh[pousr]_[A-Za-z0-9]{30,}\b'),
           re.compile(rb'(?im)^\s*(?:master_key_[0-9a-f]+|titlekek_[0-9a-f]+|key_area_key_[a-z_0-9]+)\s*=\s*[0-9a-f]{32,}\s*$')]


def main():
    result = subprocess.run(['git', '-C', str(ROOT), 'ls-files', '--cached', '--others', '--exclude-standard', '-z'], capture_output=True, text=True, check=True)
    paths = sorted(set(filter(None, result.stdout.split('\0'))))
    errors = []
    for name in paths:
        p = ROOT / name
        if p.is_symlink():
            errors.append(f'{name}: symlink excluded from source export'); continue
        # Nested source tools directories are expected; only root private folders are forbidden.
        if p.suffix.lower() in FORBIDDEN or Path(name).parts[0] in PRIVATE_PARTS or p.name in {'device.json', 'signing-key.json', 'AGENTS.md', 'CLAUDE.md'} or p.name.endswith('-signing-key.json'):
            errors.append(f'{name}: private/generated file'); continue
        data = p.read_bytes()
        if data.startswith((b'\x7fELF', b'MZ', b'\xcf\xfa\xed\xfe', b'\xfe\xed\xfa\xcf', b'\x03\x02\x23\x07')):
            errors.append(f'{name}: compiled binary')
        if any(pattern.search(data) for pattern in SECRETS): errors.append(f'{name}: potential secret (value suppressed)')
        if re.search(rb'/(?:Users|Volumes)/[^\s\x00\'"<>]+', data): errors.append(f'{name}: absolute personal filesystem path')
        if p.suffix == '.md':
            for link in re.findall(r'!?\[[^\]]*\]\(([^\s)]+)(?:\s+[^)]*)?\)', data.decode('utf-8')):
                if '://' in link or link.startswith(('#', 'mailto:')): continue
                target = unquote(link.split('#', 1)[0])
                if target and not (p.parent / target).exists(): errors.append(f'{name}: broken local link {target}')
    for name in ['LICENSE', 'ATTRIBUTION.md', 'nxnative/LICENSE', 'nxnative/dm/third_party/README.md']:
        if name not in paths: errors.append(f'{name}: missing notice')
    vendor = ROOT / 'nxnative/dm/third_party'
    for component in vendor.iterdir():
        if component.is_dir() and not any(p.is_file() and (p.name.startswith(('LICENSE', 'COPYING')) or p.name == 'OFL.txt') for p in component.rglob('*')):
            errors.append(f'{component.relative_to(ROOT)}: missing license')
    workflows = ROOT / '.github/workflows'
    if workflows.exists():
        for p in workflows.glob('*.yml'):
            if re.search(r'gh\s+(?:release|repo)|contents:\s*write|on:\s*release', p.read_text()): errors.append(f'{p.name}: publishing workflow')
    if errors:
        print('\n'.join(errors)); return 1
    print(f'Source audit passed: {len(paths)} versionable files; no flagged binaries, secrets, personal paths, broken local Markdown links, or missing dependency licenses.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
