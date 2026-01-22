# Demo 01 - Basic spectrum survey

This demo analyzes a small multi-sweep spectrum-occupancy capture
(`sweep.csv`) covering the ISM-2.4 GHz / Wi-Fi band plus a few out-of-band
reference bins.

The capture simulates an SDR survey: each row is one frequency bin from one
sweep, with measured power in dBm and a sweep timestamp. A strong, persistent
emitter sits at ~2.437 GHz (Wi-Fi channel 6) and there is a one-off power spike
at ~2.462 GHz.

## Run it

Human-readable table:

```sh
python -m rfsurvey analyze demos/01-basic/sweep.csv
```

Machine-readable JSON (for piping into jq, dashboards, alerting):

```sh
python -m rfsurvey --format json analyze demos/01-basic/sweep.csv
```

Monitoring mode - exit non-zero when anomalies are present:

```sh
python -m rfsurvey analyze demos/01-basic/sweep.csv --fail-on-anomaly
echo "exit=$?"
```

## What to expect

- A noise-floor and squelch estimate derived from the data.
- Per-band occupancy with the busiest band being `ISM-2.4/WiFi-BT`.
- At least one `persistent` anomaly (the channel-6 emitter seen across every
  sweep) and one `spike` anomaly (the 2.462 GHz outlier).

This is a passive analysis tool: it only reads and reports on capture data. It
never transmits, tunes hardware, or controls a radio.
