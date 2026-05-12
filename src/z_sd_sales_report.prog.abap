REPORT z_sd_sales_report.
* Sales order overview report
SELECT * FROM vbak INTO TABLE @DATA(lt_orders).
LOOP AT lt_orders INTO DATA(ls_order).
  WRITE: / ls_order-vbeln, ls_order-erdat.
ENDLOOP.
