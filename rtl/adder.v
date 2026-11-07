`timescale 1ns/1ps
// 16-bit adder; results wrap mod 2^16.
module adder (
    input  [15:0] a,
    input  [15:0] b,
    output [15:0] y
);
    assign y = a + b;
endmodule
