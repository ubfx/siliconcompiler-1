import os
import subprocess
import re
import sys
import siliconcompiler

from siliconcompiler.schema import schema_path

################################
# Setup Tool (pre executable)
################################

def setup_tool(chip, step):
    ''' Per tool function that returns a dynamic options string based on
    the dictionary settings.
    '''

    # Standard Setup
    tool = 'morty'
    chip.add('eda', tool, step, 'threads', '4')
    chip.add('eda', tool, step, 'format', 'cmdline')
    chip.add('eda', tool, step, 'copy', 'false')
    chip.add('eda', tool, step, 'exe', 'morty')
    chip.add('eda', tool, step, 'vendor', 'morty')

    # output single file to `morty.v`
    chip.add('eda', tool, step, 'option', '-o morty.v')
    # write additional information to `manifest.json`
    chip.add('eda', tool, step, 'option', '--manifest manifest.json')

    chip.add('eda', tool, step, 'option', '-I ../../../')

    for value in chip.cfg['ydir']['value']:
        chip.add('eda', tool, step, 'option', '--library-dir ' + schema_path(value))
    for value in chip.cfg['vlib']['value']:
        chip.add('eda', tool, step, 'option', '--library-file ' + schema_path(value))
    for value in chip.cfg['idir']['value']:
        chip.add('eda', tool, step, 'option', '-I ' + schema_path(value))
    for value in chip.cfg['define']['value']:
        chip.add('eda', tool, step, 'option', '-D ' + schema_path(value))
    for value in chip.cfg['source']['value']:
        # only pickle Verilog or SystemVerilog files
        if value.endswith('.v') or value.endswith('.vh') or \
                value.endswith('.sv') or value.endswith('.svh'):
            chip.add('eda', tool, step, 'option', schema_path(value))

################################
# Post_process (post executable)
################################

def post_process(chip, step):
    ''' Tool specific function to run after step execution
    '''

    # detect top module by reading the manifest generated by morty
    top = chip.get('design')
    if top == "" and os.isfile("manifest.json"):
        with open("manifest.json", "r") as manifest:
            data = json.load(manifest)
            if len(data["tops"]) > 1:
                chip.logger.error('Multiple top-level modules found during \
                        import, but sc_design was not set')
                sys.exit()
            if len(data["tops"]) <= 0:
                chip.logger.error('No top-level modules found during \
                        import, and sc_design was not set')
                sys.exit()
            top = data["tops"]

    # Hand off `morty.v` and `manifest.json` to the next step
    subprocess.run("cp morty.v " + "outputs/" + top + ".v", shell=True)
    subprocess.run("cp manifest.json " + "outputs/", shell=True)

    return 0

##################################################
if __name__ == "__main__":

    # File being executed
    prefix = os.path.splitext(os.path.basename(__file__))[0]
    output = prefix + '.json'

    # create a chip instance
    chip = siliconcompiler.Chip(defaults=False)
    # load configuration
    setup_tool(chip, step='import')
    # write out results
    chip.writecfg(output)
