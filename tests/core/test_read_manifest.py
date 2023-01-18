# Copyright 2020 Silicon Compiler Authors. All Rights Reserved.
import os
import siliconcompiler
import copy
import json
from siliconcompiler import _metadata

import pytest

def test_read_manifest_fields():
    '''Ensure that changes to fields other than 'value' are reflected by read_manifest()'''

    chip = siliconcompiler.Chip('foo')
    chip.set('input', 'rtl', 'verilog', False, field='copy')
    chip.add('input', 'rtl', 'verilog', 'foo.v')
    chip.write_manifest('tmp.json')

    # fresh chip, so we don't retain anything from `chip` in-memory
    chip2 = siliconcompiler.Chip('foo')
    chip2.read_manifest('tmp.json')
    assert chip2.get('input', 'rtl', 'verilog', field='copy') is False


def test_read_sup():
    '''Test compressed read/write'''

    chip = siliconcompiler.Chip('foo')
    chip.add('input', 'rtl', 'verilog', 'foo.v')
    chip.write_manifest('tmp.sup.gz')

    chip2 = siliconcompiler.Chip('foo')
    chip2.read_manifest('tmp.sup.gz')
    assert chip2.get('input', 'rtl', 'verilog') == ['foo.v']

def test_read_defaults(datadir):
    '''Make sure read/write operaton doesn't modify manifest'''

    DEBUG = False

    # gets defaul from schema
    chip = siliconcompiler.Chip('test')

    # check that read/write doesn't modify
    chip.write_manifest("actual.json", prune=False)
    chip.read_manifest("actual.json")

    # independent dump of schema
    with open("actual.json", 'w') as f:
        print(json.dumps(chip.schema.cfg, indent=4, sort_keys=True), file=f)
    with open("actual.json", 'r') as f:
        actual = json.load(f)

    # expected
    with open(os.path.join(datadir, 'defaults.json'), 'r') as f:
        expected = json.load(f)

    # special case (initialized in constructor)
    expected['design']['value'] = 'test'

    assert actual == expected

def test_read_history():
    '''Make sure that history gets included in manifest read.'''
    chip = siliconcompiler.Chip('foo')
    chip.add('input', 'rtl', 'verilog', 'foo.v')
    chip.schema.record_history()
    chip.write_manifest('tmp.json')

    chip2 = siliconcompiler.Chip('foo')
    chip2.read_manifest('tmp.json')
    assert chip.get('input', 'rtl', 'verilog', job='job0') == ['foo.v']

def test_read_job():
    '''Make sure that we can read a manifest into a non-default job'''
    chip = siliconcompiler.Chip('foo')
    chip.add('input', 'rtl', 'verilog', 'foo.v')
    chip.write_manifest('tmp.json')

    chip2 = siliconcompiler.Chip('foo')
    chip2.read_manifest('tmp.json', job='job1')
    assert chip2.get('input', 'rtl', 'verilog', job='job1') == ['foo.v']

#########################
if __name__ == "__main__":
    from tests.fixtures import datadir
    test_read_defaults(datadir(__file__))
    test_read_sup()
