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
    reg [15:0] A_0, K_1, X_1, Y_1;
    task reference;
        begin
            A_0 = sw[11:8];
            K_1 = 16'd3 * 16'd4;
            X_1 = A_0 + K_1;
            Y_1 = X_1 - 16'd5;
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
                6'd3: want_value = K_1;
                6'd4: want_value = X_1;
                6'd5: want_value = Y_1;
                6'd6: want_value = A_0;
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
            repeat (3) press;       // now in the last step, 4
            #1 if (done !== 1'b0) begin
                bad = 1'b1;
                if (errors < 5) $display("FAIL sw=%h: done is high before the last press", i[11:0]);
                errors = errors + 1;
            end
            press;                  // DONE
            #1 if (done !== 1'b1 || state !== 8'd5) begin
                bad = 1'b1;
                if (errors < 5) $display("FAIL sw=%h: not DONE after 5 presses (state %h)", i[11:0], state);
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
