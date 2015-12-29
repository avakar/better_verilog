A succint, yet expressive HDL.

Getting started
===============

Install the project using pip:

    $ pip install better_verilog

Open your favorite editor and create a new file called hello_world.bv.
Type the following.

    module hello:
        i clk
        o led

    def hello:
        on posedge clk:
            led <= not led

Run the translator:

    $ bv hello_world.bv > hello_world.v
    $ cat hello_world.v
    module hello(
        input clk,
        output reg led
        );

    always @(posedge clk) begin
        led <= !led;
    end

    endmodule

Synthetize or simulate hello_world.v.
