# Build one run folder into top.bit: vivado -mode batch -source scripts/build.tcl -tclargs build/run1
if {[llength $argv] != 1} { error "usage: vivado -mode batch -source scripts/build.tcl -tclargs RUN_FOLDER" }
set run [file normalize [lindex $argv 0]]
set root [file normalize [file join [file dirname [info script]] ..]]
set start [clock seconds]

read_verilog [concat [glob $root/rtl/*.v] [list $run/hls_core.v]]
read_xdc $root/constraints/nexys_a7.xdc
synth_design -top top -part xc7a100tcsg324-1
opt_design
place_design
route_design
report_utilization -file $run/utilization.rpt
report_timing_summary -file $run/timing.rpt
write_bitstream -force $run/top.bit

set wns [get_property SLACK [get_timing_paths -setup -max_paths 1]]
puts "BUILD DONE: $run/top.bit in [expr {[clock seconds] - $start}] s, WNS $wns ns"
if {$wns < 0} { puts "WARNING: timing is not met (negative WNS)" }
