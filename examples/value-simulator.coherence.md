# Layout Coherence Report

Deterministic coherence audit of a layout zone taxonomy.

**page**: value-simulator

**score**: 100.0%

**status**: coherent

10/10 coherence checks passed across 7 zones.

## Checks

| check | status | detail |
| --- | --- | --- |
| sketch_present | pass | ASCII source sketch is recorded |
| zones_detected | pass | 7 zones detected |
| unique_zone_ids | pass | all zone ids are unique |
| zones_have_labels | pass | every zone has a label |
| zones_have_layout_role | pass | every zone has a layout role |
| zones_have_bounds | pass | every zone has positive bounds |
| reading_order_preserved | pass | zones follow band/column reading order |
| html_preserves_zones | pass | every zone renders to an HTML section |
| css_owns_zones | pass | every zone owns a CSS rule |
| svg_preserves_zones | pass | every zone draws an SVG box |

## Zones

| zone_id | layout_role | label |
| --- | --- | --- |
| hero | full_width | HERO: Estimate the value of governed AI engineering |
| segment-picker | split_left | SEGMENT PICKER |
| value-simulator | split_right | VALUE SIMULATOR |
| formula-assumptions | full_width | FORMULA + ASSUMPTIONS |
| market-citations | split_left | MARKET CITATIONS |
| loc-evidence-chain | split_right | LOC EVIDENCE CHAIN |
| limitations-transformation-review-cta | full_width | LIMITATIONS + TRANSFORMATION REVIEW CTA |
