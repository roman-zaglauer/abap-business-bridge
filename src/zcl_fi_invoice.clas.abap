CLASS zcl_fi_invoice DEFINITION PUBLIC FINAL CREATE PUBLIC.
  PUBLIC SECTION.
    METHODS: create_invoice IMPORTING iv_amount TYPE p,
             post_to_gl     IMPORTING iv_account TYPE string.
ENDCLASS.

CLASS zcl_fi_invoice IMPLEMENTATION.
  METHOD create_invoice.
    " Create a new invoice document
    DATA: lv_doc_number TYPE string.
    lv_doc_number = 'INV-001'.
  ENDMETHOD.

  METHOD post_to_gl.
    " Post invoice to General Ledger
    WRITE: 'Posted to GL account:', iv_account.
  ENDMETHOD.
ENDCLASS.
