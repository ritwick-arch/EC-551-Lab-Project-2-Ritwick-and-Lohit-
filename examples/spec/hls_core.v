`timescale 1ns/1ps
// Hand-written stand-in for the generator's output: the spec example under ASAP, all ops 1 step.
//   X_1 = A_0 + B_0   step 1, add0
//   Y_1 = X_1 + A_0   step 2, add0
//   Z_1 = X_1 - B_0   step 2, sub0
//   Q_1 = B_0 * Z_1   step 3, mul0
module hls_core (
    input             clk,
    input             rst,
    input             step,
    /* verilator lint_off UNUSED */
    input      [11:0] sw,      // input slots: A_0 = SW11-8, B_0 = SW7-4, SW3-0 unused
    /* verilator lint_on UNUSED */
    input      [5:0]  code,    // observe code
    output reg [15:0] value,
    output reg        valid,   // 0 = show ----
    output reg [7:0]  state,   // 0 = IDLE, 1-3 = steps, 4 = DONE
    output            done
);
    localparam DONE = 8'd4;

    reg [15:0] A_0, B_0, X_1, Y_1, Z_1, Q_1;

    // FSM outputs.
    reg add0_sel_a, add0_sel_b;
    reg add0_busy, sub0_busy, mul0_busy;
    reg X_1_we, Y_1_we, Z_1_we, Q_1_we;

    // Units and their input muxes.
    reg  [15:0] add0_a, add0_b;
    wire [15:0] add0_y, sub0_y, mul0_y;

    adder      add0 (.a(add0_a), .b(add0_b), .y(add0_y));
    subtractor sub0 (.a(X_1),    .b(B_0),    .y(sub0_y));
    multiplier mul0 (.a(B_0),    .b(Z_1),    .y(mul0_y));

    always @* begin
        case (add0_sel_a)
            1'd0:    add0_a = A_0;
            default: add0_a = X_1;
        endcase
        case (add0_sel_b)
            1'd0:    add0_b = B_0;
            default: add0_b = A_0;
        endcase
    end

    // Sequencer: one state per step pulse, stopping at DONE.
    always @(posedge clk)
        if (rst) state <= 8'd0;
        else if (step && state != DONE) state <= state + 8'd1;

    assign done = (state == DONE);

    always @* begin
        add0_sel_a = 1'd0; add0_sel_b = 1'd0;
        add0_busy = 1'b0; sub0_busy = 1'b0; mul0_busy = 1'b0;
        X_1_we = 1'b0; Y_1_we = 1'b0; Z_1_we = 1'b0; Q_1_we = 1'b0;
        case (state)
            8'd1: begin add0_sel_a = 1'd0; add0_sel_b = 1'd0; add0_busy = 1'b1; X_1_we = 1'b1; end
            8'd2: begin add0_sel_a = 1'd1; add0_sel_b = 1'd1; add0_busy = 1'b1; sub0_busy = 1'b1; Y_1_we = 1'b1; Z_1_we = 1'b1; end
            8'd3: begin mul0_busy = 1'b1; Q_1_we = 1'b1; end
            default: ;
        endcase
    end

    // Inputs follow the switches in IDLE; results are written on the step pulse that ends their step.
    always @(posedge clk)
        if (rst) begin
            A_0 <= 16'd0; B_0 <= 16'd0;
            X_1 <= 16'd0; Y_1 <= 16'd0; Z_1 <= 16'd0; Q_1 <= 16'd0;
        end else begin
            if (state == 8'd0) begin
                A_0 <= {12'd0, sw[11:8]};
                B_0 <= {12'd0, sw[7:4]};
            end
            if (step && X_1_we) X_1 <= add0_y;
            if (step && Y_1_we) Y_1 <= add0_y;
            if (step && Z_1_we) Z_1 <= sub0_y;
            if (step && Q_1_we) Q_1 <= mul0_y;
        end

    // Observe codes: units, then results in equation order, then inputs.
    always @* begin
        value = 16'd0; valid = 1'b0;
        case (code)
            6'd0: begin value = add0_y; valid = add0_busy; end
            6'd1: begin value = sub0_y; valid = sub0_busy; end
            6'd2: begin value = mul0_y; valid = mul0_busy; end
            6'd3: begin value = X_1; valid = state > 8'd1; end
            6'd4: begin value = Y_1; valid = state > 8'd2; end
            6'd5: begin value = Z_1; valid = state > 8'd2; end
            6'd6: begin value = Q_1; valid = state > 8'd3; end
            6'd7: begin value = A_0; valid = 1'b1; end
            6'd8: begin value = B_0; valid = 1'b1; end
            default: ;
        endcase
    end
endmodule
