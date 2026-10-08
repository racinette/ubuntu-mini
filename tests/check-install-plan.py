#!/usr/bin/env python3
"""Exercise the real standalone installer planner without touching disks."""
import copy
from pathlib import Path
import types

source = Path(__file__).resolve().parents[1] / 'install.sh'
payload = source.read_text().split("<<'MINI_OS_INSTALL_PYTHON'\n", 1)[1].rsplit('\nMINI_OS_INSTALL_PYTHON', 1)[0]
installer = types.ModuleType('installer')
exec(compile(payload, str(source), 'exec'), installer.__dict__)
G = installer.GIB
S = 512
table = dict(label='gpt', id='fixture', device='/dev/nvme0n1', unit='sectors',
             firstlba=34, lastlba=1000215182, sectorsize=S, partitions=[])
# Actual handoff geometry before the three Ubuntu partitions were created.
for n, start, size, ptype in (
        (1, 2048, 204800, installer.ESP),
        (2, 206848, 262144, 'E3C9E316-0B5C-4DB8-817D-F92DF00215AE'),
        (3, 468992, 524288000, 'EBD0A0A2-B9E5-4433-87C0-68B6B72699C7'),
        (4, 966660096, 33554432, 'DE94BBA4-06D1-4D40-A16A-BFD50179D6AC')):
    table['partitions'].append(dict(node=f'/dev/nvme0n1p{n}', start=start, size=size,
                                   type=ptype, uuid=f'uuid-{n}', name='arbitrary'))
table['partitions'][3]['attrs'] = 'RequiredPartition GUID:63'
original = copy.deepcopy(table)
plan = installer.make_plan(table)
assert table == original
assert [p['number'] for p in plan['new']] == [5, 6, 7]
assert plan['new'][0]['offset'] >= (468992 + 524288000) * S
assert plan['new'][-1]['offset'] + plan['new'][-1]['size'] <= 966660096 * S
assert 209 * G < plan['allocation'] < 211 * G
assert plan['remaining_in_gap'] == 0
sized = installer.make_plan(table, installer.size_bytes('200G'))
assert sized['allocation'] == 200 * G and sized['remaining_in_gap'] > 0
assert installer.size_bytes('250GB') == 250_000_000_000 // installer.MIB * installer.MIB
assert installer.size_bytes('16GiB') == 16 * G


def refused(table, size=None):
    try:
        installer.make_plan(table, size)
    except ValueError:
        return
    raise AssertionError('Unsafe or impossible plan was accepted')


refused(table, 250 * G)
refused(table, 15 * G)
occupied = copy.deepcopy(table)
for p in plan['new']:
    occupied['partitions'].append(dict(node=f'/dev/nvme0n1p{p["number"]}',
        start=p['offset'] // S, size=p['size'] // S, type=p['type']))
refused(occupied)
overlap = copy.deepcopy(table)
overlap['partitions'][2]['start'] = 2048
refused(overlap)
# Fragmented space cannot satisfy a request by summing separate gaps.
fragmented = dict(label='gpt', id='fixture', device='/dev/vda', unit='sectors',
                 firstlba=2048, lastlba=40*G//S-1, sectorsize=S,
                 partitions=[dict(node='/dev/vda1', start=10*G//S, size=20*G//S, type=installer.LINUX)])
refused(fragmented, 16 * G)
# 4 KiB sectors and holes in partition numbering are handled independently.
fourk = copy.deepcopy(table)
fourk['sectorsize'] = 4096
fourk['firstlba'] = 6
fourk['lastlba'] //= 8
for p in fourk['partitions']:
    p['start'] //= 8
    p['size'] //= 8
assert installer.make_plan(fourk)['allocation'] == plan['allocation']
holes = copy.deepcopy(table)
for p, number in zip(holes['partitions'], (1, 3, 7, 11)):
    p['node'] = f'/dev/nvme0n1p{number}'
assert [p['number'] for p in installer.make_plan(holes)['new']] == [2, 4, 5]
actions = installer.storage_actions(plan, '/run/private.key')
existing = [a for a in actions if a['id'].startswith('existing-')]
assert len(existing) == 4 and all(a['preserve'] and not a['grub_device'] for a in existing)
assert all('wipe' not in a and 'resize' not in a for a in actions)
assert {a['volume'] for a in actions if a['type'] == 'format'} == {'efi', 'boot', 'crypt'}
assert [a['id'] for a in actions if a.get('grub_device')] == ['efi']
assert all('key' not in a for a in actions)
# Exercise target selection as well as geometry. None of these mocks can run
# a disk command; a mounted disk or active mapping must never reach sfdisk.
from types import SimpleNamespace
def node(path='/dev/nvme0n1', **changes):
    value = dict(path=path, type='disk', ro=False, rm=False, tran='nvme', size=512*G,
                 mountpoints=[None], serial='fixture', model='fixture')
    value.update(changes)
    return value
tree = [node()]
def fake_run(*args, **kwargs):
    if args[0]=='lsblk':
        import json
        return SimpleNamespace(stdout=json.dumps(dict(blockdevices=tree)))
    raise AssertionError('Unexpected external command')
installer.run = fake_run
installer.table_for = lambda path: dict(copy.deepcopy(table), device=path)
assert installer.inventory()['disk']=='/dev/nvme0n1'
for blocked in (node(ro=True),node(rm=True),node(tran='usb'),node(mountpoints=['/']),
                node(children=[dict(path='/dev/nvme0n1p3',type='part',mountpoints=['[SWAP]'])]),
                node(children=[dict(path='/dev/dm-99',type='crypt',mountpoints=[None])])):
    tree = [blocked]
    try:
        installer.inventory()
    except ValueError:
        pass
    else:
        raise AssertionError('Unsafe target was selected')
tree = [node(),node('/dev/nvme1n1')]
try:
    installer.inventory()
except ValueError:
    pass
else:
    raise AssertionError('Ambiguous target was selected')
assert installer.inventory('/dev/nvme0n1')['disk']=='/dev/nvme0n1'
print('Passed: actual middle-gap geometry, exact/max allocation, occupied/fragmented/undersized '
      'refusals, 4K sectors, preservation-only actions, and mounted/mapped/removable/ambiguous target refusals.')
