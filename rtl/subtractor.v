`timescale 1ns/1ps
// 16-bit subtractor (a - b); results wrap mod 2^16.
module subtractor (
    input  [15:0] a,
    input  [15:0] b,
    output [15:0] y
);
    assign y = a - b;
endmodule
