// Checks hls_core for every switch setting against the equations written out directly.
`timescale 1ns/1ps
module testbench;
    reg         clk = 1'b0, rst = 1'b1, step = 1'b0;
    reg  [11:0] sw = 12'd0;
    reg  [5:0]  code = 6'd0;
    wire [15:0] value;
    wire        valid, done;
    wire [7:0]  state;

    hls_core dut (.clk(clk), .rst(rst), .step(step), .sw(sw), .code(code),
                  .value(value), .valid(valid), .state(state), .done(done));

    always #5 clk = ~clk;

    // Reference: the SSA equations, 16 bits wide, with no schedule involved.
    reg [15:0] A_0, B_0, C_0, D_0, S1_1, S2_1, P1_1, P2_1, T1_1, T2_1, T3_1, U1_1, U2_1, U3_1, V1_1,
               V2_1, V3_1, V4_1, W1_1, W2_1, W3_1, W4_1, R1_1, R2_1;
    task reference;
        begin
            A_0 = sw[11:8];
            B_0 = sw[7:4];
            C_0 = sw[3:0];
            D_0 = 16'd1000;  // --set
            S1_1 = A_0 + B_0;
            S2_1 = C_0 + D_0;
            P1_1 = A_0 * B_0;
            P2_1 = C_0 * D_0;
            T1_1 = S1_1 * S2_1;
            T2_1 = P1_1 + P2_1;
            T3_1 = T1_1 - T2_1;
            U1_1 = S1_1 - C_0;
            U2_1 = S2_1 - A_0;
            U3_1 = U1_1 * U2_1;
            V1_1 = T3_1 + U3_1;
            V2_1 = T3_1 - U3_1;
            V3_1 = V1_1 * 16'd3;
            V4_1 = V2_1 * 16'd5;
            W1_1 = V3_1 + V4_1;
            W2_1 = W1_1 - P1_1;
            W3_1 = W2_1 * S1_1;
            W4_1 = W3_1 + 16'd7;
            R1_1 = W4_1 - T1_1;
            R2_1 = R1_1 * 16'd2;
        end
    endtask

    // What each observe code must show at DONE: idle units and unused codes show ----.
    reg [15:0] want_value;
    reg        want_valid;
    task expected(input [5:0] c);
        begin
            want_valid = 1'b1;
            want_value = 16'd0;
            case (c)
                6'd5: want_value = S1_1;
                6'd6: want_value = S2_1;
                6'd7: want_value = P1_1;
                6'd8: want_value = P2_1;
                6'd9: want_value = T1_1;
                6'd10: want_value = T2_1;
                6'd11: want_value = T3_1;
                6'd12: want_value = U1_1;
                6'd13: want_value = U2_1;
                6'd14: want_value = U3_1;
                6'd15: want_value = V1_1;
                6'd16: want_value = V2_1;
                6'd17: want_value = V3_1;
                6'd18: want_value = V4_1;
                6'd19: want_value = W1_1;
                6'd20: want_value = W2_1;
                6'd21: want_value = W3_1;
                6'd22: want_value = W4_1;
                6'd23: want_value = R1_1;
                6'd24: want_value = R2_1;
                6'd25: want_value = A_0;
                6'd26: want_value = B_0;
                6'd27: want_value = C_0;
                default: want_valid = 1'b0;
            endcase
        end
    endtask

    task press;
        begin
            @(negedge clk) step = 1'b1;
            @(negedge clk) step = 1'b0;
        end
    endtask

    integer    errors = 0, passed = 0;
    reg        bad;
    reg [12:0] i;
    reg [6:0]  c;

    initial begin
        for (i = 0; i < 4096; i = i + 1) begin
            bad = 1'b0;
            @(negedge clk) begin rst = 1'b1; sw = i[11:0]; end
            @(negedge clk) rst = 1'b0;
            reference;
            press;                  // leave IDLE: the inputs freeze
            sw = ~i[11:0];          // later switch changes must be ignored
            repeat (12) press;      // now in the last step, 13
            #1 if (done !== 1'b0) begin
                bad = 1'b1;
                if (errors < 5) $display("FAIL sw=%h: done is high before the last press", i[11:0]);
                errors = errors + 1;
            end
            press;                  // DONE
            #1 if (done !== 1'b1 || state !== 8'd14) begin
                bad = 1'b1;
                if (errors < 5) $display("FAIL sw=%h: not DONE after 14 presses (state %h)", i[11:0], state);
                errors = errors + 1;
            end
            for (c = 0; c < 64; c = c + 1) begin
                code = c[5:0];
                expected(c[5:0]);
                #1 if (valid !== want_valid || (want_valid && value !== want_value)) begin
                    bad = 1'b1;
                    if (errors < 5) $display("FAIL sw=%h code=%h: got %h valid=%b, expected %h valid=%b",
                                             i[11:0], c[5:0], value, valid, want_value, want_valid);
                    errors = errors + 1;
                end
            end
            if (!bad) passed = passed + 1;
        end
        if (passed == 4096) $display("PASS %0d/4096", passed);
        else $display("FAIL %0d/4096 passed", passed);
        $finish;
    end
endmodule
