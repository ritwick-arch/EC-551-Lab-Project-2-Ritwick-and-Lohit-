`timescale 1ns/1ps
// Scans the 8-digit display: each digit shows a hex nibble or a dash, with an optional decimal point.
module sevenseg (
    input            clk,
    input     [31:0] digits,   // digit 7 (leftmost) in bits 31:28
    input     [7:0]  dash,     // 1 = show '-' instead of the digit
    input     [7:0]  dot,      // 1 = light the decimal point
    output reg [7:0] an,       // active low
    output reg [6:0] seg,      // {g,f,e,d,c,b,a}, active low
    output reg       dp        // active low
);
    reg [19:0] scan = 0;
    wire [2:0] i = scan[19:17];   // each digit is lit for about 1.3 ms
    wire [3:0] nibble = digits[i*4 +: 4];

    always @(posedge clk) begin
        scan <= scan + 1'b1;
        an <= ~(8'b1 << i);
        dp <= ~dot[i];
        if (dash[i])
            seg <= 7'b0111111;
        else
            case (nibble)
                4'h0: seg <= 7'b1000000;
                4'h1: seg <= 7'b1111001;
                4'h2: seg <= 7'b0100100;
                4'h3: seg <= 7'b0110000;
                4'h4: seg <= 7'b0011001;
                4'h5: seg <= 7'b0010010;
                4'h6: seg <= 7'b0000010;
                4'h7: seg <= 7'b1111000;
                4'h8: seg <= 7'b0000000;
                4'h9: seg <= 7'b0010000;
                4'hA: seg <= 7'b0001000;
                4'hB: seg <= 7'b0000011;
                4'hC: seg <= 7'b1000110;
                4'hD: seg <= 7'b0100001;
                4'hE: seg <= 7'b0000110;
                default: seg <= 7'b0001110;
            endcase
    end
endmodule
