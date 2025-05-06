# Lambdas_Java


- Module: ExcelSupportFunction

| lambda name                         | name sam template      | config name sam   | s3 source folder            | s3 destination fodler                       | Book Excel                                              |
|-------------------------------------|------------------------|-------------------|-----------------------------|---------------------------------------------|---------------------------------------------------------|
| lambda-java-sheet-estandar-x86-64   | lambdas_support.yaml   | lambdas_support   | support/source/             | support/destination/sheet/estandar/         | TEIGA TMI - ADISSEO - CONTROL AVANCE SOPORTACION_MASTER |
| lambda-java-sheet-especiales-x86-64 | lambdas_support.yaml   | lambdas_support   | support/source/             | support/destination/sheet/especiales/       | TEIGA TMI - ADISSEO - CONTROL AVANCE SOPORTACION_MASTER |
| lambda-java-excel-wb-x86-64         | lambda_wb.yaml         | wb_excel          | weldingbook/source/         | weldingbook/destination/                    | TEIGA-00000-ML-B1304-6800-0711-0001_MASTER              |
| lambda-java-sheet-isos-x86-64       | lambda_sheet_isos.yaml | lambda_sheet_isos | wb_tp_precom_master/source/ | wb_tp_precom_master/destination/sheet/isos/ | WB_TP_PRECOM_MASTER                                     |
