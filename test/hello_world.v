module hello(
    input clk,
    output reg led
    );

always @(posedge clk) begin
    led <= !led;
end

endmodule

