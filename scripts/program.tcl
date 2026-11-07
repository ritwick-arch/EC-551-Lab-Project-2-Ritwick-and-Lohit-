# Program the board with one run folder's top.bit: vivado -mode batch -source scripts/program.tcl -tclargs build/run1
if {[llength $argv] != 1} { error "usage: vivado -mode batch -source scripts/program.tcl -tclargs RUN_FOLDER" }
set bit [file normalize [file join [lindex $argv 0] top.bit]]
catch {set_param labtools.enable_cs_server false}
open_hw_manager
connect_hw_server
open_hw_target
set dev [lindex [get_hw_devices xc7a100t*] 0]
current_hw_device $dev
set_property PROGRAM.FILE $bit $dev
program_hw_devices $dev
close_hw_manager
puts "PROGRAMMED: $bit"
