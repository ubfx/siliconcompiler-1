import siliconcompiler                       # import python package
syn_np = 4
chip = siliconcompiler.Chip()                # create chip object
chip.node('import', 'surelog')               # create import task
chip.node('syn', 'yosys', n=syn_np)          # create 4 syn tasks
chip.node('synmin', 'minimum')               # select minimum
for i in range(syn_np):
    chip.edge('import', 'syn', head_index=i) # broadcast
    chip.edge('syn', 'synmin', tail_index=i) # merge
chip.write_flowgraph("pattern_forkjoin.png") # write out flowgraph picture
