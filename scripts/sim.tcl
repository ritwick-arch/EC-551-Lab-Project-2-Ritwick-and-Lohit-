# Run one run folder's testbench.v in xsim: vivado -mode batch -source scripts/sim.tcl -tclargs build/run1
if {[llength $argv] != 1} { error "usage: vivado -mode batch -source scripts/sim.tcl -tclargs RUN_FOLDER" }
set run [file normalize [lindex $argv 0]]
set root [file normalize [file join [file dirname [info script]] ..]]
cd $run
exec xvlog $root/rtl/adder.v $root/rtl/subtractor.v $root/rtl/multiplier.v hls_core.v testbench.v >@stdout 2>@stderr
exec xelab testbench -s tb >@stdout 2>@stderr
exec xsim tb -R -log sim.log >@stdout 2>@stderr
