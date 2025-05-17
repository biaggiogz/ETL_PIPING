SELECT COUNT("Isometric") AS total_iso ,
	ROUND((SUM("CONSTRUC COORD PROGRESS") /  COUNT("Isometric")),2) AS tp_construct_progress, 
	 unnest(string_to_array("TEST PACK", '|')) AS test_pack
FROM user_01.view_field_control 
GROUP BY unnest(string_to_array("TEST PACK", '|'))

