`timescale 1ns/1ps
// Synchronizes a button, samples it every TICK cycles and pulses for one cycle on each press.
module debounce #(
    parameter TICK = 1000000   // 10 ms at 100 MHz
) (
    input      clk,
    input      btn,
    output reg pulse
);
    reg [1:0] sync = 2'b00;
    reg [$clog2(TICK)-1:0] count = 0;
    reg level = 1'b0;

    always @(posedge clk) begin
        sync <= {sync[0], btn};
        pulse <= 1'b0;
        if (count == TICK - 1) begin
            count <= 0;
            level <= sync[1];
            pulse <= sync[1] & ~level;
        end else begin
            count <= count + 1'b1;
        end
    end
endmodule
