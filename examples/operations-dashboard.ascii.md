+----------------------------------------------------------+
| OPERATIONS DASHBOARD [page]                              |
+---------------------------+------------------------------+
| FILTERS [form]            | DELIVERY HEALTH [gauge]      |
| fields: date,status,team  | value: delivery_health       |
| action: apply_filters     | min: 0 max: 100              |
+---------------------------+------------------------------+
| RUNS [data_grid]                                         |
| data: runs[]                                             |
| columns: id,status,owner,duration                        |
+----------------------------------------------------------+
| SUCCESS TREND [chart_line]                               |
| x: day y: success_rate                                   |
+----------------------------------------------------------+
