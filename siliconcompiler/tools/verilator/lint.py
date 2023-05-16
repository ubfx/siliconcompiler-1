from siliconcompiler.tools.verilator.verilator import setup as setup_tool


def setup(chip):
    '''
    Lints Verilog source. Results of linting can be programatically queried
    using errors/warnings metrics.
    '''

    # Generic tool setup.
    setup_tool(chip)

    tool = 'verilator'
    step = chip.get('arg', 'step')
    index = chip.get('arg', 'index')
    task = chip._get_task(step, index)

    chip.add('tool', tool, 'task', task, 'option', ['--lint-only'],
             step=step, index=index)
