# Web Coherence Report

Deterministic component-aware coherence audit of a web page contract.

**page**: operations-dashboard

**score**: 100.0%

**status**: coherent

All 11 web coherence checks passed across 5 components.

## Checks

| check | status | detail | remediation |
| --- | --- | --- | --- |
| zone_component_coverage | pass | every component references an existing zone |  |
| component_ids_unique | pass | component ids are unique |  |
| component_type_supported | pass | all component types are supported |  |
| form_controls_present | pass | forms declare fields and actions |  |
| data_grid_columns_present | pass | data grids declare columns and a data source |  |
| chart_axes_present | pass | charts declare x and y axes |  |
| gauge_range_present | pass | gauges declare value, min, and max |  |
| html_component_traceability | pass | HTML preserves every component id |  |
| css_component_ownership | pass | CSS owns zone placement and component classes |  |
| svg_component_representation | pass | SVG draws every component |  |
| a11y_labels | pass | interactive components carry accessible labels |  |

## Components

| component_id | component_type | zone_id | label |
| --- | --- | --- | --- |
| component-operations-dashboard | page | operations-dashboard-page | OPERATIONS DASHBOARD |
| component-filters | form | filters-form | FILTERS |
| component-delivery-health | gauge | delivery-health-gauge | DELIVERY HEALTH |
| component-runs | data_grid | runs-data-grid | RUNS |
| component-success-trend | chart_line | success-trend-chart-line | SUCCESS TREND |
