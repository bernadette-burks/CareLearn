# CareLearn Agent Prototype 👩‍⚕️

A local, synthetic-data-only prototype of a risk-based EHR documentation training agent.

## Run

Requires Python 3.14.7 or newer. No third-party packages are required.

- Windows: double-click `run.bat` (requires the Python Launcher `py`).
- Or run `python app.py` from a terminal. The browser opens at `http://127.0.0.1:8765`.
- Stop the server with Ctrl+C in the terminal.

The app binds to localhost only. Data is held in memory and is discarded when the server stops or Reset is clicked.

## EHR interaction visual demo

The interface uses a single left-side dashboard for scenario controls, events, reasoning, adaptation feedback, and audit history, with a separate video-only panel at right. The dashboard is designed to fit a desktop viewport without page scrolling; narrow screens stack the panels. The header icon is a blue brain with a red heart accent. The right panel includes a silent 20-second looping animation. It shows a clearly synthetic, Epic-style EHR screen with a nurse entering a low-risk misspelling and receiving a quick-tip notification, followed by a separate critical vital-sign example that pauses automation and transitions to a supervisor review screen. Use Pause/Resume or Replay below the animation. The display is a locally drawn UI simulation, not a recording or connection to Epic, and contains only fictional identifiers and values.

## Demonstrated behaviors

1. **Autonomous planning:** checks chart eligibility, filters open/draft/disputed events, applies a risk-first route, checks recurrence thresholds, and chooses monitoring, a training recommendation, or supervisor escalation.
2. **Multi-step reasoning:** the UI shows a human-readable ordered policy trace and concise decision summary, not hidden chain-of-thought.
3. **Tool use:** the trace names the called demo tools (eligibility check, event filter, risk classifier, pattern lookup, threshold policy, training catalog, supervisor escalation).
4. **Adaptation:** imports a labeled CSV, recalibrates recurrence thresholds from confirmed examples, and accepts dispute feedback that removes an event from active counts and calibration.
5. **Failure handling:** validates CSV columns and values, rejects empty/bad data and oversized requests, holds open/draft charts, and routes medium/high risk to a human checkpoint. High-risk review always has a threshold of one.

## Ready-to-upload synthetic examples

Four fictional CSV files are included in `sample_data/`:

- `carelearn_low_risk_training.csv` — repeated low-risk typo pattern; reaches the training threshold.
- `carelearn_medium_risk_escalation.csv` — repeated medium-risk pattern; routes to supervisor review.
- `carelearn_high_risk_escalation.csv` — one high-risk event; routes immediately to supervisor review.
- `carelearn_open_chart_hold.csv` — an open chart; held by the eligibility gate.

All records use fictional demo staff and descriptions and include the exact required headers.

## Labeled CSV format

Required headers: `staff,category,risk,description,chart_status,confirmed`

Allowed `risk`: `low`, `medium`, `high`. Allowed `chart_status`: `closed`, `signed`, `open`, `draft`. `confirmed` accepts `true/false`, `yes/no`, or `1/0`.

Example:

```csv
staff,category,risk,description,chart_status,confirmed
Nurse X,common_typo,low,Misspelled assessment term,closed,true
Nurse X,common_typo,low,Misspelled assessment term,closed,true
```

This is threshold calibration on labeled examples, not a trained clinical ML model. Imported records, including filenames and demo audit entries, stay in memory only.

## EPIC FHIR and Knack

The current prototype does **not** connect to Epic or Knack. Epic's FHIR sandbox provides synthetic test patients for integration testing. A later adapter could read authorized sandbox FHIR R4 resources and map closed Encounter/Observation data into a candidate-event schema, then require human annotations before calibration. FHIR resources alone are not ground-truth labels for documentation errors. Keep this local demo separate from any real EHR.

The current prototype does not require Knack. Knack can be evaluated later for a UI/backend integration, but its public pricing distinguishes the ordinary Starter plan from HIPAA offerings; its free trial must not receive PHI. No PHI should be entered into this prototype or a non-HIPAA Knack trial.

## Known limitations

- Rule-based, fictional cases only; it does not make clinical decisions, inspect narratives for clinical contradictions, send notifications, or assign actual training.
- Risk labels in imported CSV are reviewer-provided, not inferred from raw FHIR.
- It is not validated, production-ready, or HIPAA-compliant. It has no authentication, authorization, persistent audit storage, TLS, external service integrations, or security review.
- The supplied prototype demonstrates the coursework workflow; it is not suitable for patient-care or employee-performance use.
