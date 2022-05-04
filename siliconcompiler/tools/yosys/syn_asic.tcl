####################
# DESIGNER's CHOICE
####################

set sc_targetlibs  [dict get $sc_cfg asic logiclib]
set sc_macrolibs   [dict get $sc_cfg asic macrolib]
set sc_mainlib     [lindex [dict get $sc_cfg asic logiclib] 0]
set sc_delaymodel  [dict get $sc_cfg asic delaymodel]
set sc_tie         [dict get $sc_cfg library $sc_mainlib asic cells tie]
set sc_buf         [dict get $sc_cfg library $sc_mainlib asic cells buf]
set sc_scenarios   [dict keys [dict get $sc_cfg constraint]]


########################################################
# Read Libraries
########################################################

set stat_libs ""
foreach item $sc_scenarios {
    set libcorner [dict get $sc_cfg constraint $item libcorner]
    foreach lib $sc_targetlibs {
	puts "$item $libcorner $sc_delaymodel $lib"
        set lib_file [dict get $sc_cfg library $lib model timing $sc_delaymodel $libcorner]
        yosys read_liberty -lib $lib_file
    }
    foreach lib $sc_macrolibs {
        if [dict exists dict get $sc_cfg library $lib model timing $sc_delaymodel $libcorner] {
            set lib_file [dict get $sc_cfg library $lib model timing $sc_delaymodel $libcorner]
            yosys read_liberty -lib $lib_file
            append stat_libs "-liberty $lib_file "
        }
    }
}
puts "HELLO $sc_mode"
########################################################
# Synthesis
########################################################

# Although the `synth` command also runs `hierarchy`, we run it here without the
# `-check` flag first in order to resolve parameters before looking for missing
# modules. This works around the fact that Surelog doesn't pickle modules that
# are instantiated inside generate blocks that will get eliminated. This seems
# to give us the same behavior as passing the `-defer` flag to read_verilog, but
# `-defer` gave us different post-synth results on one of our test cases (while
# this appears to result in no differences). Note this must be called after the
# read_liberty calls for it to not affect synthesis results.
yosys hierarchy -top $sc_design

yosys synth "-flatten" -top $sc_design

yosys opt -purge

########################################################
# Technology Mapping
########################################################
if [dict exists dict get $sc_cfg library $sc_mainlib asic "file" $sc_tool techmap] {
    set sc_techmap     [dict get $sc_cfg library $sc_mainlib asic "file" $sc_tool techmap]
    foreach mapfile $sc_techmap {
	yosys techmap -map $mapfile
    }
}

#TODO: Fix better
set libcorner    [dict get $sc_cfg constraint [lindex $sc_scenarios 0] libcorner]
set mainlib      [dict get $sc_cfg library $sc_mainlib model timing $sc_delaymodel $libcorner]

yosys dfflibmap -liberty $mainlib

yosys opt

source "$sc_refdir/syn_strategies.tcl"

set script ""
if {[dict exists $sc_cfg eda $sc_tool variable $sc_step $sc_index strategy]} {
    set sc_strategy [dict get $sc_cfg eda $sc_tool variable $sc_step $sc_index strategy]
    if { [dict exists $syn_strategies $sc_strategy] } {
        set script [dict get $syn_strategies $sc_strategy]
    } else {
        puts "Warning: no such synthesis strategy $sc_strategy"
    }
}

# TODO: other abc flags passed in by OpenLANE we can adopt:
# -D: clock period
# -constr: in the case of OpenLANE, an autogenerated SDC that includes a
#   set_driving_cell and set_load call (but perhaps we should just pass along a
#   user-provided constraint)

if {$script != ""} {
    yosys abc -liberty $mainlib -script $script
} else {
    yosys abc -liberty $mainlib
}

yosys stat -liberty $mainlib {*}$stat_libs

########################################################
# Cleanup
########################################################

yosys setundef -zero

if {[llength $sc_tie] == 2} {
    set sc_tiehi [split [lindex $sc_tie 0] /]
    set sc_tielo [split [lindex $sc_tie 1] /]

    yosys hilomap -hicell {*}$sc_tiehi -locell {*}$sc_tielo
}

if {[llength $sc_buf] == 1} {
    set sc_buf_split [split $sc_buf /]
    yosys insbuf -buf {*}$sc_buf_split
}

yosys splitnets

yosys clean
