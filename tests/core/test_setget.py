# Copyright 2020 Silicon Compiler Authors. All Rights Reserved.
import siliconcompiler
import re

def test_setget():
    '''API test for set/get methods

    Performs set or add based on API example for each entry in schema and
    ensures that we can recover the same value back. Also tests that keypaths in
    schema examples are valid.
    '''

    chip = siliconcompiler.Chip()
    error = 0

    allkeys = chip.getkeys()
    for key in allkeys:
        sctype = chip.get(*key, field='type')
        examples = chip.get(*key, field='example')
        for example in examples:
            match = re.match(r'api\:\s+chip.(set|add|get)\((.*)\)', example)
            if match is not None:
                break

        assert match is not None, f'Illegal example for keypath {key}'

        if match.group(1) == 'get':
            continue

        argstring = re.sub(r'[\'\s]', '', match.group(2))
        tuplematch = re.match(r'(.*?),\((.*,.*)\)', argstring)
        if tuplematch:
            keypath = tuplematch.group(1).split(',')
            tuplestr = tuplematch.group(2)
            if '(str,str)' in sctype:
                tuplestr = re.sub(r'[\(\)\'\s]','',tuplestr)
                value = tuple(tuplestr.split(','))
            else:
                value = tuple(map(float, tuplestr.split(',')))
            if re.match(r'\[',sctype):
                value = [value]
            args =  keypath + [value]
        else:
            keypath =  argstring.split(',')[:-1]
            value = argstring.split(',')[-1]
            if sctype == "float":
                value = float(value)
            elif sctype == "bool":
                    value = bool(sctype=='true')
            elif sctype == "int":
                value = int(value)
            if re.match(r'\[',sctype):
                value = [value]
            args = keypath + [value]

        if match.group(1) == 'set':
            chip.set(*args, clobber=True)
        elif match.group(1) == 'add':
            chip.add(*args)

        result = chip.get(*keypath)
        assert result == value, f'Expected value {value} from keypath {keypath}. Got {result}.'

    chip.write_manifest('allvals.json')

    assert(error==0)

#########################
if __name__ == "__main__":
    test_setget()
