"""Seed the tested WIN Mini microphone level before the first desktop login."""
import configparser
import os
from pathlib import Path


MICROPHONE_ROUTE = 'alsa_card.pci-0000_63_00.6:input:analog-input-internal-mic:'


def seed_microphone_level(user, dmi=Path('/sys/class/dmi/id')):
    # This route and gain were tested on the WIN Mini 2023, not other codecs.
    try:
        model = tuple((dmi / name).read_text().strip()
                      for name in ('sys_vendor', 'product_name'))
    except OSError:
        return False
    if model != ('GPD', 'G1617-01'):
        return False

    target = Path(user.pw_dir) / '.local/state/wireplumber/default-routes'
    text = target.read_text() if target.exists() else ''
    state = configparser.ConfigParser(interpolation=None, delimiters=('=',))
    state.optionxform = str
    state.read_string(text)
    # WirePlumber restores saved volumes ahead of defaults. Retain preferences,
    # even when the user deliberately chose a level different from ours.
    if any(state.has_option('default-routes', MICROPHONE_ROUTE + key)
           for key in ('channelVolumes', 'volume')):
        return False

    # WirePlumber 0.4 stores linear amplitudes; PulseAudio's 10% is 0.1**3.
    # On this codec that selects Capture 0 dB and Internal Mic Boost 0 dB.
    setting = MICROPHONE_ROUTE + 'channelVolumes=0.001;0.001;\n'
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        if line.lstrip().startswith('[default-routes]'):
            lines[index] = line.rstrip('\r\n') + '\n' + setting
            break
    else:
        lines.append(('\n' if text and not text.endswith('\n') else '')
                     + '[default-routes]\n' + setting)

    missing = []
    directory = target.parent
    while not directory.exists():
        missing.append(directory)
        directory = directory.parent
    target.parent.mkdir(parents=True, exist_ok=True)
    for directory in missing:
        os.chown(directory, user.pw_uid, user.pw_gid)
    temporary = target.with_name(target.name + '.minion.tmp')
    temporary.write_text(''.join(lines))
    temporary.chmod(0o600)
    os.chown(temporary, user.pw_uid, user.pw_gid)
    temporary.replace(target)
    return True
