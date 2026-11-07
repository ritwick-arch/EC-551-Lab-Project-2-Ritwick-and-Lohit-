`timescale 1ns/1ps
// 16-bit multiplier; keeps the low 16 bits of the product.
module multiplier (
    input  [15:0] a,
    input  [15:0] b,
    output [15:0] y
);
    assign y = a * b;
endmodule
