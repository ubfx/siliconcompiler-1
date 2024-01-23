
proc legalize_flops { feature_set } {

    set legalize_flop_types []

    if { ( [lsearch -exact $feature_set enable] >= 0 ) && \
             ( [lsearch -exact $feature_set async_set] >= 0 ) && \
             ( [lsearch -exact $feature_set async_reset] >= 0 ) } {
        lappend legalize_flop_types \$_DFF_P_
        lappend legalize_flop_types \$_DFF_PN?_
        lappend legalize_flop_types \$_DFFE_PP_
        lappend legalize_flop_types \$_DFFE_PN?P_
        lappend legalize_flop_types \$_DFFSR_PNN_
        lappend legalize_flop_types \$_DFFSRE_PNNP_
    } elseif { ( [lsearch -exact $feature_set enable] >= 0 ) && \
                   ( [lsearch -exact $feature_set async_set] >= 0 ) } {
        lappend legalize_flop_types \$_DFF_P_
        lappend legalize_flop_types \$_DFF_PN1_
        lappend legalize_flop_types \$_DFFE_PP_
        lappend legalize_flop_types \$_DFFE_PN1P_
    } elseif { ( [lsearch -exact $feature_set enable] >= 0 ) && \
                   ( [lsearch -exact $feature_set async_reset] >= 0 ) } {
        lappend legalize_flop_types \$_DFF_P_
        lappend legalize_flop_types \$_DFF_PN0_
        lappend legalize_flop_types \$_DFFE_PP_
        lappend legalize_flop_types \$_DFFE_PN0P_
    } elseif { ( [lsearch -exact $feature_set enable] >= 0 ) } {
        lappend legalize_flop_types \$_DFF_P_
        lappend legalize_flop_types \$_DFF_P??_
        lappend legalize_flop_types \$_DFFE_PP_
        lappend legalize_flop_types \$_DFFE_P??P_
    } elseif { ( [lsearch -exact $feature_set async_set] >= 0 ) && \
                   ( [lsearch -exact $feature_set async_reset] >= 0 ) } {
        lappend legalize_flop_types \$_DFF_P_
        lappend legalize_flop_types \$_DFF_PN?_
        lappend legalize_flop_types \$_DFFSR_PNN_
    } elseif { ( [lsearch -exact $feature_set async_set] >= 0 ) } {
        lappend legalize_flop_types \$_DFF_P_
        lappend legalize_flop_types \$_DFF_PN1_
    } elseif { ( [lsearch -exact $feature_set async_reset] >= 0 ) } {
        lappend legalize_flop_types \$_DFF_P_
        lappend legalize_flop_types \$_DFF_PN0_
    } else {
        # Choose to legalize to async resets even though they
        # won't tech map.  Goal is to get the user to fix
        # their code and put in synchronous resets
        lappend legalize_flop_types \$_DFF_P_
        lappend legalize_flop_types \$_DFF_P??_
    }

    set legalize_list []
    foreach flop_type $legalize_flop_types {
        lappend legalize_list -cell $flop_type 01
    }
    yosys log "Legalize list: $legalize_list"
    yosys dfflegalize {*}$legalize_list
}

proc get_dsp_options { sc_syn_dsp_options } {

    set option_text [ list ]
    foreach dsp_option $sc_syn_dsp_options {
        lappend option_text -D $dsp_option
    }
    return $option_text
}

set sc_partname [dict get $sc_cfg fpga partname]
set build_dir [dict get $sc_cfg option builddir]
set job_name [dict get $sc_cfg option jobname]
set step [dict get $sc_cfg arg step]
set index [dict get $sc_cfg arg index]

set sc_syn_lut_size \
    [dict get $sc_cfg fpga $sc_partname lutsize]

if {[dict exists $sc_cfg fpga $sc_partname var feature_set]} {
    set sc_syn_feature_set \
        [dict get $sc_cfg fpga $sc_partname var feature_set]
} else {
    set sc_syn_feature_set [ list ]
}

if {[dict exists $sc_cfg fpga $sc_partname var dsp_options]} {
    yosys log "Process DSP techmap options."
    set sc_syn_dsp_options \
        [dict get $sc_cfg fpga $sc_partname var dsp_options]
    yosys log "DSP techmap options = $sc_syn_dsp_options"
} else {
    set sc_syn_dsp_options [ list ]
}

if {[dict exists $sc_cfg fpga $sc_partname var dsp_extract_options]} {
    yosys log "Process DSP extract options."
    set sc_syn_dsp_extract_options \
        [dict get $sc_cfg fpga $sc_partname var dsp_extract_options]
    yosys log "DSP extract options = $sc_syn_dsp_extract_options"
} else {
    set sc_syn_dsp_extract_options [ list ]
}

if {[dict exists $sc_cfg fpga $sc_partname var dsp_blackbox_options]} {
    yosys log "Process DSP blackbox options."
    set sc_syn_dsp_blackbox_options \
        [dict get $sc_cfg fpga $sc_partname var dsp_blackbox_options]
    yosys log "DSP blackbox options = $sc_syn_dsp_blackbox_options"
} else {
    set sc_syn_dsp_blackbox_options [ list ]
}

# TODO: add logic that remaps yosys built in name based on part number

# Run this first to handle module instantiations in generate blocks -- see
# comment in syn_asic.tcl for longer explanation.
yosys hierarchy -top $sc_design

if {[string match {ice*} $sc_partname]} {
    yosys synth_ice40 -top $sc_design -json "${sc_design}_netlist.json"
} else {

    #Collect DSP mapping options from configuration if a DSP techmap is
    #provided
    set sc_syn_dsp_map_method \
        [dict get $sc_cfg tool $sc_tool task $sc_task var dsp_map_method]

    # Pre-processing step:  if DSPs instance are hard-coded into
    # the user's design, we can use a blackbox flow for DSP mapping
    # as follows:

    if { $sc_syn_dsp_map_method == "blackbox" } {
        if {[dict exists $sc_cfg fpga $sc_partname file yosys_dsp_techmap]} {
            set sc_syn_dsp_library \
                [dict get $sc_cfg fpga $sc_partname file yosys_dsp_blackboxlib]

            # Note that the techlib may be designed such that there
            # is a +define macro that turns on blackboxing or other
            # options, so be sure to pick up any DSP options specified for
            # the FPGA part as part of this scheme
            yosys log "Use Blackbox flow for DSP Blocks"
            set formatted_dsp_options \
                [get_dsp_options $sc_syn_dsp_blackbox_options]
            yosys read_verilog {*}$formatted_dsp_options $sc_syn_dsp_library
        }
    }

    # Match VPR reference flow's hierarchy check, including their comments

    # Here are the notes from the VPR developers
    # These commands follow the generic `synth'
    # command script inside Yosys
    # The -libdir argument allows Yosys to search the current
    # directory for any definitions to modules it doesn't know
    # about, such as hand-instantiated (not inferred) memories

    yosys hierarchy -check -auto-top

    #Rename top level module to match selected design name;
    #This allows us to enforce some naming consistency in
    #automated flows
    yosys rename -top ${sc_design}

    yosys proc
    #select -module ${sc_design}
    #flatten -wb
    #flatten

    #Match the optimization passes of the VTR reference yosys flow
    yosys opt_expr
    yosys opt_clean
    yosys check
    yosys opt -nodffe -nosdff
    yosys fsm
    yosys opt
    yosys wreduce
    yosys peepopt
    yosys opt_clean
    yosys share
    yosys opt
    yosys memory -nomap
    yosys opt -full

    #Do our own thing from here

    #Map DSP blocks before doing anything else,
    #so that we don't convert any math blocks
    #into other primitives

    # Note there are two possibilities for how mapping might be done:
    # using the extract command (to pattern match user RTL against
    # the techmap) or using the techmap command.  The latter is better
    # for mapping simple multipliers; the former is better (for now)
    # for mapping more complex DSP blocks (MAC, pipelined blocks, etc).
    # make the user specify an extract flag to use extract instead of
    # regular techmapping

    if {$sc_syn_dsp_map_method == "extract"} {
        if {[dict exists $sc_cfg fpga $sc_partname file yosys_dsp_extractlib]} {
            set sc_syn_dsp_library \
                [dict get $sc_cfg fpga $sc_partname file yosys_dsp_extractlib]
            yosys log "Use Extract flow for DSP Blocks"
            set formatted_dsp_options \
                [get_dsp_options $sc_syn_dsp_extract_options]
            yosys extract -map $sc_syn_dsp_library {*}$formatted_dsp_options
        }
    } else {
        if {[dict exists $sc_cfg fpga $sc_partname file yosys_dsp_techmap]} {
            set sc_syn_dsp_library \
                [dict get $sc_cfg fpga $sc_partname file yosys_dsp_techmap]
            yosys log "Use Techmap flow for DSP Blocks"
            set formatted_dsp_options [get_dsp_options $sc_syn_dsp_options]
            yosys techmap -map +/mul2dsp.v -map $sc_syn_dsp_library \
                {*}$formatted_dsp_options
        }
    }

    yosys techmap -map +/techmap.v

    if {[dict exists $sc_cfg fpga $sc_partname file yosys_memory_libmap]} {

        set sc_syn_memory_libmap \
            [dict get $sc_cfg fpga $sc_partname file yosys_memory_libmap]

        yosys memory_libmap -lib $sc_syn_memory_libmap
        # ***HACK:  Eliminate $reduce_or with this mapping here
        #           until we have a cleaner solution
        yosys simplemap
    }

    if {[dict exists $sc_cfg fpga $sc_partname file yosys_memory_techmap]} {

        set sc_syn_memory_library \
            [dict get $sc_cfg fpga $sc_partname file yosys_memory_techmap]
        yosys techmap -map $sc_syn_memory_library

        # perform techmap in case previous techmaps introduced constructs
        # that need techmapping
        yosys techmap
        # Quick optimization
        yosys opt -purge
    }

    legalize_flops $sc_syn_feature_set

    #Perform preliminary buffer insertion before passing to ABC to help reduce
    #the overhead of final buffer insertion downstream
    yosys insbuf

    yosys abc -lut $sc_syn_lut_size -dff

    yosys flatten
    yosys clean

    if {[dict exists $sc_cfg fpga $sc_partname file yosys_flop_techmap]} {
        set sc_syn_flop_library \
            [dict get $sc_cfg fpga $sc_partname file yosys_flop_techmap]
        yosys techmap -map $sc_syn_flop_library

        # perform techmap in case previous techmaps introduced constructs
        # that need techmapping
        yosys techmap
        # Quick optimization
        yosys opt -purge
    }

}

yosys echo off
yosys tee -o ./reports/stat.json stat -json -top $sc_design
yosys echo on
