# Location Matching Benchmarks

This directory stores reproducible evaluation records for the current-photo to historical-record candidate search. Do not expose model metrics in the user-facing demo.

Before recording results, label each query-candidate relationship as `same_point`, `same_zone`, `nearby_reference`, or `irrelevant`. Keep source evidence for every `same_point` label.

Use the template CSV for one row per returned candidate. Store run-level configuration and aggregates in a sibling JSON file.
