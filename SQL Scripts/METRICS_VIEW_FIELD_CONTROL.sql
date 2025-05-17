with  A AS (

SELECT COUNT(DISTINCT spool) FILTER (where spool is not null)  AS total_qty_spools,
	   COUNT(fw_sw) FILTER (WHERE fw_sw = 'SW') AS weld_sw,
       COUNT(fw_sw) FILTER (WHERE fw_sw = 'FW') AS weld_fw,
	   SUM(total) AS total_diainch,
	   SUM(total) FILTER (where fw_sw = 'SW') AS budget_sw,
	   SUM(total) FILTER (where fw_sw = 'SW' and date_execut is not null) AS done_diainch_shop,
	   SUM(total) FILTER (where fw_sw = 'FW') AS budget_fw,
	   SUM(total) FILTER (where fw_sw = 'FW' and date_execut is not null) AS done_diainch_field,
	   COUNT(supportid) AS budget_pieces_support,
	   COUNT(supportid) FILTER (where rwsupportid=1) AS qty_support,
	   COUNT(is_recieved) FILTER (where is_recieved = 'True') AS qty_pieces_recieved,
	   COUNT(supportid) FILTER (where recieved = 'recieved' AND rwsupportid=1) AS qty_support_recieved,
	   COUNT(is_installed) FILTER (where is_installed='True') AS qt_pieces_installed,
	   COUNT(supportid) FILTER (where installed = 'installed' AND rwsupportid=1) AS qty_support_installed,
	   MIN(n_tp) FILTER (where n_tp != 'ANULADA') AS test_pack,
	   MIN(subsystem) AS subsystem


FROM user_01.master
GROUP BY e3did
)


SELECT  
	  SUM(total_qty_spools) AS t_qty_spools,
	  SUM(weld_sw) AS t_weld_sw,
	  SUM(weld_fw) AS t_weld_fw,
	  SUM(total_diainch) AS t_diainch,
	  SUM(done_diainch_shop) + SUM(done_diainch_field) AS t_done_diainch,
	  ROUND(
		    (100.0 * (
		        COALESCE(SUM(done_diainch_shop), 0) + COALESCE(SUM(done_diainch_field), 0)
		    ) / NULLIF(SUM(total_diainch), 0))::numeric,
		    2
	   ) AS ratio_done_diainch,
	  SUM(budget_sw) AS t_budget_sw,
	  SUM(done_diainch_shop) AS t_done_diainch_shop,
	  SUM(budget_fw) AS tolta_budget_fw,
	  SUM(done_diainch_field) AS t_done_diainch_field,
	  SUM(budget_pieces_support) AS t_budget_pieces_support,
	  SUM(qty_support) AS t_qty_support,
	  SUM(qty_pieces_recieved) AS t_qty_pieces_recieved,
	  SUM(qty_support_recieved) AS t_qty_support_recieved,
	  SUM(qt_pieces_installed) AS t_qt_pieces_installed,
	  SUM(qty_support_installed) AS t_qty_support_installed,
	  (SELECT COUNT(DISTINCT val) 
	   FROM A, 
	   LATERAL regexp_split_to_table(A.test_pack, '|') AS val) AS t_test_pack,
	  COUNT(DISTINCT subsystem) AS t_subsystem
FROM A;







SELECT DISTINCT n_tp FROM user_01.master




------------------------------------
SELECT COUNT(supportid) AS t_budget_pieces_support --IS EQUAL ADDISSEO SUPPORT
FROM user_01.source_support

SELECT DISTINCT supportid FROM  user_01.source_support
WHERE POSITION('_' IN supportid) > 0;  --NOT SUPPORTID WITH "_" THAT NOT START WITH "/SPS"

----------THIS CHECK OUT THE QTY SUPPORT RECIEVED
WITH A AS (
  SELECT DISTINCT e3did || '@' || supportid AS id_support
  FROM user_01.source_support
  WHERE recieved = 'recieved'
),
split AS (
  SELECT string_to_array(id_support, '@') AS parts
  FROM A
),

values_split AS (
SELECT
  parts[1] AS e3did,
  parts[2] AS supportid
FROM split)

SELECT e3did, supportid FROM values_split
WHERE supportid IN (SELECT DISTINCT supportid FROM user_01.source_support WHERE recieved = 'not recieved' )

----------THIS CHECK OUT THE QTY SUPPORT INSTALLED
---- FOUND TWO supportid in others e3did then is correclty
WITH A AS (
  SELECT DISTINCT e3did || '@' || supportid AS id_support
  FROM user_01.source_support
  WHERE installed = 'installed'
),
split AS (
  SELECT string_to_array(id_support, '@') AS parts
  FROM A
),

values_split AS (
SELECT
  parts[1] AS e3did,
  parts[2] AS supportid
FROM split)

SELECT e3did, supportid FROM values_split
WHERE supportid IN (SELECT DISTINCT supportid FROM user_01.source_support WHERE installed = 'not installed' )

------------------

SELECT COUNT(erected_no_rected)
FROM user_01.master
where erected_no_rected = 'True'


SELECT *  FROM user_01.source_welding_info
WHERE n_tp != 'ANULADA' and area IS NOT NULL

SELECT COUNT(DISTINCT subsystem) FROM user_01.source_welding_info

SELECT column_name, data_type
FROM information_schema.columns
WHERE table_schema = 'user_01'
  AND table_name = 'MASTER';
