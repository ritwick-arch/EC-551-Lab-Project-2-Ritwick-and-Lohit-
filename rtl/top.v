`timescale 1ns/1ps
// Board wrapper: buttons, page counter, hls_core and the SS.CC.VVVV display.
module top (
    input        CLK100MHZ,
    input        CPU_RESETN,
    input        BTNC,          // step
    input        BTNU,          // next observe page
    input  [15:0] SW,           // SW15-12 observe code, SW11-0 input slots
    output [0:0] LED,           // LED0 = done
    output       CA, CB, CC, CD, CE, CF, CG, DP,
    output [7:0] AN
);
    reg [1:0] rst_sync = 2'b11;   // reset is held for two cycles at power-up
    always @(posedge CLK100MHZ) rst_sync <= {rst_sync[0], ~CPU_RESETN};
    wire rst = rst_sync[1];

    wire step, next_page;
    debounce db_step (.clk(CLK100MHZ), .btn(BTNC), .pulse(step));
    debounce db_page (.clk(CLK100MHZ), .btn(BTNU), .pulse(next_page));

    reg [1:0] page = 2'd0;
    always @(posedge CLK100MHZ)
        if (rst) page <= 2'd0;
        else if (next_page) page <= page + 2'd1;

    wire [5:0]  code = {page, SW[15:12]};
    wire [15:0] value;
    wire        valid, done;
    wire [7:0]  state;
    hls_core core (
        .clk(CLK100MHZ), .rst(rst), .step(step), .sw(SW[11:0]), .code(code),
        .value(value), .valid(valid), .state(state), .done(done)
    );

    assign LED[0] = done;

    sevenseg display (
        .clk(CLK100MHZ),
        .digits({state, 2'b00, code, value}),
        .dash({4'b0000, {4{~valid}}}),
        .dot(8'b0101_0000),   // SS.CC.VVVV
        .an(AN),
        .seg({CG, CF, CE, CD, CC, CB, CA}),
        .dp(DP)
    );
endmodule
