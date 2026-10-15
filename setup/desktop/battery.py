"""Merge the handheld's low-battery policy into UPower's system configuration."""
import configparser
import os
from pathlib import Path
import re
import tempfile

POLICY = {
    'UsePercentageForPolicy': 'true',
    'PercentageLow': '20',
    'PercentageCritical': '10',
    'PercentageAction': '5',
    'CriticalPowerAction': 'PowerOff',
}


def install(path=Path('/etc/UPower/UPower.conf')):
    if path.is_symlink():
        raise ValueError('Refusing a symlinked UPower configuration')
    original = path.read_text() if path.exists() else ''
    parser = configparser.ConfigParser(interpolation=None, strict=False)
    parser.optionxform = str
    parser.read_string(original)
    remaining = dict(POLICY)
    lines, section = [], None
    for line in original.splitlines(keepends=True):
        heading = re.match(r'^\s*\[([^]]+)\]', line)
        if heading:
            if section == 'UPower':
                lines.extend(f'{key}={value}\n' for key, value in remaining.items())
                remaining.clear()
            section = heading[1]
        option = re.match(r'^\s*([^#;\s=]+)\s*=', line)
        if section == 'UPower' and option and option[1] in POLICY:
            key = option[1]
            lines.append(f'{key}={POLICY[key]}\n')
            remaining.pop(key, None)
        else:
            lines.append(line if line.endswith('\n') else line + '\n')
    if remaining:
        if section != 'UPower':
            lines.append('\n[UPower]\n')
        lines.extend(f'{key}={value}\n' for key, value in remaining.items())
    prepared = ''.join(lines)
    if prepared == original:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
        stream.write(prepared)
        temporary = Path(stream.name)
    try:
        temporary.chmod(0o644)
        os.chown(temporary, 0, 0)
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)
    return True
