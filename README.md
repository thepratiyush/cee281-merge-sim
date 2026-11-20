# cee281-merge-sim

Microsimulation of a freeway on-ramp merge for UCLA CEE C181/C281 (Fall 2026), by Pratiyush and Colin. It tests how ramp metering, driver time gaps, merge geometry and incidents affect throughput and safety. The car-following model is IDM, the lane-change model is MOBIL, and the merge uses a zipper rule.

## Repository layout

| Path | What it is |
| --- | --- |
| `stage1_one_lane_road/` | Stage 1: a one-lane road with IDM car following (browser simulator) |
| `stage2_zipper_merge/` | Stage 2: a one-lane road with an on-ramp, a ramp meter and a zipper merge |
| `stage3_two_lane_merge/` | Stage 3: a two-lane freeway merge with MOBIL lane changes and detectors, plus `stage3_tests.ipynb` (model checks) |
| `simtools/` | Runs the Stage 3 HTML model headless from Python (`bridge.py` → `sim_runner.js`), plus parameters and theory checks |
| `reports/midterm/` | `midterm_figures.ipynb` builds every midterm figure and table; `sweeps.py` defines the parameter sweeps |

## Run

Open any `.html` file in a browser to watch the simulation interactively.

To run the model from Python, you need Python 3.10+ and Node.js 18+. Node runs the same JavaScript the browser uses, without a browser.

```bash
pip install -r requirements.txt
jupyter notebook reports/midterm/midterm_figures.ipynb
```

```python
from simtools.bridge import run_stage3
out = run_stage3({"flow": 2800, "ramp": 600, "meter": 4.5}, duration_s=3600, seed=1)
```

Sweep results are cached in `reports/midterm/tables/`. Delete a `sweep_*.csv` file to rerun that sweep.
