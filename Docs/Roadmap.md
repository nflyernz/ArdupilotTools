# Version 0.1

✓ Read BIN

✓ Extract messages

✓ Export CSV

✓ Dashboard

---

# Version 0.2

Landing segmentation

Landing metrics

Landing report

---

# Version 0.3

Landing scorecard

HTML report

PDF report

---

# Version 0.4

Parameter integration

Multiple aircraft profiles

---

# Version 0.5

Flight comparison

Parameter comparison

Firmware comparison

---

# Version 0.6

Launch module

---

# Version 1.0

Public release


## v0.2.1 – ArduPlane 4.6 Compatibility

### Investigate

- [ ] Parameter loading
  - Compare 4.6.3 and 4.7 `.params` formats.
  - Determine why 4.6 parameters are not loading.

- [ ] LAND messages
  - Compare LAND message sequences between 4.6.3 and 4.7.
  - Identify any behavioural changes.

- [ ] Landing window detection
  - Investigate oversized landing windows on 4.6.3 logs.
  - Verify behaviour with go-arounds and aborted approaches.

### Validation

- [ ] Run detector suite on all available logs.
- [ ] Record observations before modifying algorithms.
- [ ] Only change detectors when supported by multiple logs.
