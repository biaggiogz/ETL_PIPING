DROP VIEW IF EXISTS user_01.view_field_control;
CREATE OR REPLACE VIEW user_01.view_field_control AS
WITH layerA AS (
    SELECT 
        e3did,
        MIN(line_id) AS line_id,  
        MIN(area) AS area,
        MIN(dn) AS dn,            
        MIN(line_fluid) AS line_fluid,
        MIN(id_line) AS id_line,  
        MIN(ins_trac_tren) AS ins_trac_tren,
        MIN(specification) AS specification,
        
        COUNT(spool) AS qty_spools,
        COUNT(DISTINCT spool) FILTER (WHERE spool IS NOT NULL) AS qty_spools_unique,
        COUNT(fw_sw) FILTER (WHERE fw_sw = 'SW') AS qty_weld_sw,
        COUNT(fw_sw) FILTER (WHERE fw_sw = 'FW') AS qty_weld_fw,
        
        SUM(total) AS total_diainch,
        SUM(total) FILTER (WHERE fw_sw = 'SW') AS budget_diainch_sw,
        SUM(total) FILTER (WHERE fw_sw = 'SW' AND date_execut IS NOT NULL) AS done_diainch_shop,
        
        SUM(total) FILTER (WHERE fw_sw = 'FW') AS budget_diainch_fw,
        SUM(total) FILTER (WHERE fw_sw = 'FW' AND date_execut IS NOT NULL) AS done_diainch_field,
        
        MAX(EXTRACT(WEEK FROM date_execut)) FILTER (WHERE fw_sw = 'SW') AS max_week_sw,
        MAX(EXTRACT(WEEK FROM date_execut)) FILTER (WHERE fw_sw = 'FW') AS max_week_fw,
        
        STRING_AGG(DISTINCT nmrev, '/') AS qty_std_support_ten_teiga,  
        
        COUNT(supportid) AS budget_support_pieces,
        COUNT(supportid) FILTER (WHERE rwsupportid = 1) AS qty_support, 
        COUNT(is_recieved) FILTER (WHERE is_recieved = 'True') AS t_pieces_support_recieved,
        COUNT(supportid) FILTER (WHERE recieved = 'recieved' AND rwsupportid = 1) AS qty_support_recieved,
        COUNT(CASE WHEN estadodefabricacionnuevoformato = 'FABRICADO' THEN 1 ELSE NULL END) AS fabricated,
        COUNT(is_installed) FILTER (WHERE is_installed = 'True') AS t_pieces_support_installed,
        COUNT(supportid) FILTER (WHERE installed = 'installed' AND rwsupportid = 1) AS qty_support_installed,
        
        STRING_AGG(specialsupportnumber, '|') AS sps,
        STRING_AGG(status_fabricated_in_site, '|') AS status,
        STRING_AGG(
            CASE WHEN erected_no_rected ILIKE '%True%' THEN '1' ELSE '0' END,
            '|' 
        ) FILTER (WHERE erected_no_rected = 'True') AS status_sps_1_erected, 
        
        MIN(n_tp) AS test_pack,
        MIN(subsystem) AS subsystem,
        MIN(category_ped) AS category_ped,
        MIN(test_pressure) AS test_pressure_max_barg
    FROM user_01.master
    GROUP BY e3did
),
layerB AS (
    SELECT 
        e3did, 
        line_id, 
        area, 
        dn, 
        line_fluid, 
        id_line, 
        specification, 
        split_part(ins_trac_tren, '_', 1) AS insulation,
        split_part(ins_trac_tren, '_', 2) AS train,
        qty_spools, 
        qty_spools_unique, 
        (qty_weld_sw + qty_weld_fw) AS t_welds,
        qty_weld_sw, 
        qty_weld_fw, 
        total_diainch,
        
        COALESCE(done_diainch_shop, 0) + COALESCE(done_diainch_field, 0) AS t_done_diainch,
        
        ROUND(
            (100.0 * (COALESCE(done_diainch_shop, 0) + COALESCE(done_diainch_field, 0)) / NULLIF(total_diainch, 0))::numeric, 2
        ) AS ratio_done_diainch,
        
        budget_diainch_sw,
        done_diainch_shop,
        
        ROUND(
            (100.0 * COALESCE(done_diainch_shop, 0) / NULLIF(budget_diainch_sw, 0))::numeric, 2
        ) AS ratio_done_shop_diainch,
        
        budget_diainch_fw, 
        done_diainch_field,
        
        ROUND(
            (100.0 * COALESCE(done_diainch_field, 0) / NULLIF(budget_diainch_fw, 0))::numeric, 2
        ) AS ratio_done_field_diainch,
        
        max_week_sw,
        max_week_fw,
        
        COALESCE(qty_std_support_ten_teiga, 'NOT APPLY') AS qty_std_support_ten_teiga,
        
        ROUND(
            (100.0 * COALESCE(t_pieces_support_recieved, 0) / NULLIF(budget_support_pieces, 0))::numeric, 2
        ) AS "100% at site",
        
        budget_support_pieces, 
        qty_support,
        
        ROUND(
            (100.0 * COALESCE(t_pieces_support_recieved, 0) / NULLIF(budget_support_pieces, 0))::numeric, 2
        ) AS progress_delievered_site,
        
        t_pieces_support_recieved,
        qty_support_recieved,
        fabricated,
        
        t_pieces_support_installed, 
        qty_support_installed,
        
        ROUND(
            (100.0 * COALESCE(t_pieces_support_installed, 0) / NULLIF(budget_support_pieces, 0))::numeric, 2
        ) AS progress_erected,
        
        COALESCE(sps, 'NOT APPLY') AS sps,
        status,  
        status_sps_1_erected, 
        test_pack, 
        subsystem,
        category_ped, 
        test_pressure_max_barg
    FROM layerA
)

SELECT 
    e3did AS "Isometric", 
    line_id AS "LINE ID", 
    area AS "Design Area", 
    dn AS "DN", 
    line_fluid AS "FLUIDO", 
    id_line AS "SEQ", 
    insulation AS "INSULATION", 
    train AS "TRAIN", 
    specification AS "SPEC",
    
    qty_spools AS "QTY Spools", 
    qty_spools_unique AS "QTY Spools Unique", 
    t_welds AS "Total Welds",
    qty_weld_sw AS "QTY Welds Shop (SW)", 
    qty_weld_fw AS "QTY Welds Field (FW)",
    
    total_diainch AS "TOTAL DIAINCH", 
    t_done_diainch AS "TOTAL DONE DIAINCH", 
    ratio_done_diainch AS "RATIO DONE DIAINCH (%)",
    
    CASE 
        WHEN ratio_done_diainch >= 90.0 THEN '90-100%' 
        ELSE NULL
    END AS "ISO TOTAL SW & FW 90-100%",
    
    budget_diainch_sw AS "BUDGET DIAINCH SHOP", 
    done_diainch_shop AS "DONE DIAINCH SHOP",
    ratio_done_shop_diainch AS "RATIO DONE SHOP DIAINCH (%)",
    
    CASE 
        WHEN ratio_done_shop_diainch >= 90.0 THEN '90-100%' 
        ELSE NULL 
    END AS "ISO SHOP 90-100%",
    
    budget_diainch_fw AS "BUDGET DIAINCH FIELD", 
    done_diainch_field AS "DONE DIAINCH FIELD",
    ratio_done_field_diainch AS "RATIO DONE FIELD DIAINCH (%)",
    
    CASE 
        WHEN ratio_done_field_diainch >= 90.0 THEN '90-100%'
        WHEN budget_diainch_fw IS NULL THEN 'NOT REQUIRED'
        ELSE 'Not Finished'
    END AS "ISO FIELD 90-100%",
    
    CASE 
        WHEN ratio_done_shop_diainch >= 90.0 THEN max_week_sw::VARCHAR
        ELSE 'Not Finished'
    END AS "ISO SW END BY WEEK",
    
    CASE 
        WHEN ratio_done_field_diainch >= 90.0 THEN max_week_fw::VARCHAR
        WHEN budget_diainch_fw IS NULL THEN 'NOT REQUIRED'
        ELSE 'Not Finished'
    END AS "ISO FW END BY WEEK",
    
    qty_std_support_ten_teiga AS "QTY STD Supports TEN/TEIGA", 
    "100% at site",
    
    budget_support_pieces AS "BUDGET SUPPORT PIECES", 
    qty_support AS "QTY SUPPORT",
    progress_delievered_site AS "% PROGRESS DELIVERY IN SITE",
    
    CASE 
        WHEN progress_delievered_site >= 90.0 THEN '90-100%'
        ELSE NULL
    END AS "SUPPORTS DELIVERED 90-100%",
    
    t_pieces_support_recieved AS "TOTAL PIECES SUPPORT RECIEVED", 
    qty_support_recieved AS "QTY SUPPORT RECIEVED", 
    fabricated AS "FABRICADO",   
    
    t_pieces_support_installed AS "TOTAL PIECES SUPPORT INSTALLED", 
    qty_support_installed AS "QTY SUPPORT INSTALLED", 
    progress_erected AS "% PROGRESS ERECTED",
    
    sps AS "SPS", 
    status AS "STATUS", 
    status_sps_1_erected AS "STATUS SPS 1 = erected",
    
    CASE
        WHEN 
            (CASE WHEN ratio_done_shop_diainch = 100.00 THEN 1 ELSE 0 END) +
            (CASE 
                WHEN ratio_done_field_diainch = 100.00 THEN 2
                WHEN budget_diainch_fw IS NULL THEN 2
                ELSE 0
            END) +
            (CASE WHEN progress_erected = 100.00 THEN 3 ELSE 0 END) +
            (CASE 
                WHEN sps ILIKE '%NOT APPLY%' THEN 4
                WHEN status_sps_1_erected ILIKE '%1%' THEN 4
                ELSE 0
            END) = 10
        THEN 'Ready for Dossier'
        ELSE NULL
    END AS "PreCOM",
    
    (CASE 
        WHEN ratio_done_shop_diainch = 100.00 THEN 1 ELSE 0 END) +
    (CASE 
        WHEN ratio_done_field_diainch = 100.00 THEN 2
        WHEN budget_diainch_fw IS NULL THEN 2
        ELSE 0
    END) +
    (CASE WHEN progress_erected = 100.00 THEN 3 ELSE 0 END) +
    (CASE 
        WHEN sps ILIKE '%NOT APPLY%' THEN 4
        WHEN status_sps_1_erected ILIKE '%1%' THEN 4
        ELSE 0
    END) AS "MESSURE",
    
    test_pack AS "TEST PACK", 
    subsystem AS "SUBSYSTEM", 
    category_ped AS "CATEGORY PED", 
    test_pressure_max_barg AS "TEST PRESSURE MAX (BAR G)",
    
    COALESCE(
        CASE
            WHEN budget_diainch_fw IS NULL AND budget_support_pieces = 0 THEN ratio_done_shop_diainch
            WHEN budget_diainch_fw IS NULL THEN (ratio_done_shop_diainch * 0.5 + progress_erected * 0.5)
            WHEN budget_support_pieces = 0 THEN (ratio_done_shop_diainch * 0.5 + ratio_done_field_diainch * 0.5)
            ELSE (ratio_done_shop_diainch * 0.4 + ratio_done_field_diainch * 0.3 + progress_erected * 0.3)
        END,
    0) AS "CONSTRUC COORD PROGRESS",    
    
    COALESCE(
        CASE
            WHEN budget_diainch_fw IS NULL THEN ratio_done_shop_diainch
            ELSE (ratio_done_shop_diainch * 0.5 + ratio_done_field_diainch * 0.5)
        END,
    0) AS "PROGRESS SW+FW (%)"
FROM layerB
WHERE area IS NOT NULL;
