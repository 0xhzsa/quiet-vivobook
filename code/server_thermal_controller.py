#!/usr/bin/env python3
"""
server_thermal_controller.py - command line for the 8-GPU thermal model.

This file used to hold a second copy of the thermal model plus an EKF class
plus an MPC class, none of which anything called. The physics now lives in
thermal_model.py and the controller lives in closed_loop.py. This is the
entry point.

    uv run --no-project python code/server_thermal_controller.py --selftest
    uv run --no-project python code/server_thermal_controller.py
    uv run --no-project python code/server_thermal_controller.py --target-temp 83
"""

from __future__ import annotations

import argparse

import closed_loop
import fanlaw
import thermal_model as tm


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--load", type=float, default=0.80,
                    help="GPU load fraction")
    ap.add_argument("--ambient", type=float, default=tm.AMBIENT_C,
                    help="inlet ambient temperature, C")
    ap.add_argument("--target-temp", type=float, default=tm.THROTTLE_START_C,
                    help="max die temperature, C")
    ap.add_argument("--tray-w", type=float, default=tm.FAN_TRAY_W,
                    help="fan tray wattage at 100%% duty")
    args = ap.parse_args()

    if args.selftest:
        closed_loop.selftest()
        tm.selftest()
        return

    node = tm.make_gpu8(ambient=args.ambient, fan_w=args.tray_w)
    p = node.n_gpus * node.gpu_tdp_w * args.load

    print("=" * 78)
    print("8-GPU AIR-COOLED NODE - fan duty vs GPU load, at steady state")
    print("=" * 78)
    print("fan law      calibrated to a measured 120 W -> 15 W (87.5 %%)")
    print("             that calibration carries a %.1f-point band" %
          (100 * (fanlaw.saving_band(0.95, 0.353).high
                  - fanlaw.saving_band(0.95, 0.353).low)))
    print("thermal      3-node lumped model, die / heatsink / case air")
    print("duty         the LOWEST duty that holds the die at the target")
    print()

    print("  %-6s %8s %9s %8s %9s %9s %14s" %
          ("load", "GPU_W", "min_duty", "die_C", "fan_W", "saved_W", "band"))
    print("  " + "-" * 74)
    for load in (0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0):
        node2 = tm.make_gpu8(ambient=args.ambient, fan_w=args.tray_w)
        pp = node2.n_gpus * node2.gpu_tdp_w * load
        r = tm.operating_point(node2, pp)
        lo, hi = r["saved_pct_band"]
        print("  %-6.0f%% %8.0f %8.1f%% %8.1f %9.1f %9.1f %6.1f-%.1f%%" %
              (100 * load, pp, 100 * r["min_duty"], r["die_temp"],
               r["ctrl_fan_w"], r["saved_w"], lo, hi))
    print()
    print("  The saving is not a constant. It is a function of GPU load AND of")
    print("  inlet temperature, and both of those are measurable on a real")
    print("  node with a BMC trace. That is the ask.")
    print()

    op = tm.operating_point(node, p, args.target_temp)
    lo, hi = op["saved_pct_band"]
    kind = ("full-boost safe" if args.target_temp <= tm.THROTTLE_START_C
            else "throttle knee")
    print("  OPERATING POINT at %.0f%% GPU load, %.0f C ambient (%s):" %
          (100 * args.load, args.ambient, kind))
    print("    duty          %.1f %%" % (100 * op["min_duty"]))
    print("    die temp      %.1f C (target %.1f C)" % (op["die_temp"], op["max_die_temp"]))
    print("    fan power     %.1f W (from %.1f W)" % (op["ctrl_fan_w"], op["base_fan_w"]))
    print("    saved         %.1f W = %.1f %%  (band %.1f-%.1f %%)" %
          (op["saved_w"], op["saved_pct"], lo, hi))
    print("    throughput    %.2f %% cost" % (100 * op["throughput_cost"]))
    print()

    print("  CONSISTENCY CHECK against the upstream measurement.")
    print("  The fan law is fitted to quiet-lab's measured 120 W -> 15 W on a")
    print("  64-core server. The thermal model is an independent construction.")
    print("  At the 83 C knee, where the thermal model sets the duty and the")
    print("  fan law sets the percentage:")
    knee = tm.operating_point(node, p, tm.THROTTLE_KNEE_C)
    print("    quiet-lab measured 120 W -> 15 W on a 64-core server: 87.5 %")
    print("    this model at %.0f %% GPU load:                      %.2f %%" %
          (100 * args.load, knee["saved_pct"]))
    print("    gap: %.2f points" % abs(knee["saved_pct"] - 87.5))
    print()
    print("  That is a CONSISTENCY CHECK, not an independent validation: the")
    print("  fan law was fitted to the measurement it is being compared with.")
    print("  The thermal model is the independent part, and it was tuned to")
    print("  put the die at a plausible full-duty temperature, which is what")
    print("  makes the duty land where it does.")


if __name__ == "__main__":
    main()
