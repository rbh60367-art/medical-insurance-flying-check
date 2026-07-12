from __future__ import annotations

from typing import Any


SQL_TEMPLATES: dict[str, str] = {
    "gender_limit_v1": """
SELECT
  sm.fixmedins_code AS institution_code,
  md5(sm.psn_no) AS patient_id_masked,
  sm.mdtrt_id AS encounter_id,
  fd.hilist_code AS item_code,
  fd.hilist_name AS item_name,
  sm.gend AS patient_gender,
  SUM(fd.det_item_fee_sumamt) AS amount
FROM settlement_main sm
JOIN fee_detail fd ON sm.setl_id = fd.setl_id
WHERE fd.hilist_code = ANY(:item_codes)
  AND fd.fee_ocur_time >= :date_start
  AND fd.fee_ocur_time < :date_end
  AND sm.gend <> :allowed_gender
GROUP BY sm.fixmedins_code, sm.psn_no, sm.mdtrt_id, fd.hilist_code, fd.hilist_name, sm.gend
""",
    "age_limit_v1": """
SELECT
  sm.fixmedins_code AS institution_code,
  md5(sm.psn_no) AS patient_id_masked,
  sm.mdtrt_id AS encounter_id,
  fd.hilist_code AS item_code,
  fd.hilist_name AS item_name,
  sm.age AS patient_age,
  SUM(fd.det_item_fee_sumamt) AS amount
FROM settlement_main sm
JOIN fee_detail fd ON sm.setl_id = fd.setl_id
WHERE fd.hilist_code = ANY(:item_codes)
  AND fd.fee_ocur_time >= :date_start
  AND fd.fee_ocur_time < :date_end
  AND (:min_age IS NULL OR sm.age >= :min_age)
  AND (:max_age IS NULL OR sm.age <= :max_age)
GROUP BY sm.fixmedins_code, sm.psn_no, sm.mdtrt_id, fd.hilist_code, fd.hilist_name, sm.age
""",
    "duplicate_charge_v1": """
SELECT
  sm.fixmedins_code AS institution_code,
  md5(sm.psn_no) AS patient_id_masked,
  sm.mdtrt_id AS encounter_id,
  fd.hilist_code AS item_code,
  fd.hilist_name AS item_name,
  COUNT(*) AS charge_count,
  SUM(fd.det_item_fee_sumamt) AS amount
FROM settlement_main sm
JOIN fee_detail fd ON sm.setl_id = fd.setl_id
WHERE fd.hilist_code = ANY(:item_codes)
  AND fd.fee_ocur_time >= :date_start
  AND fd.fee_ocur_time < :date_end
GROUP BY sm.fixmedins_code, sm.psn_no, sm.mdtrt_id, fd.hilist_code, fd.hilist_name
HAVING COUNT(*) > :threshold
""",
}


def render_template(template_id: str, parameters: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    if template_id not in SQL_TEMPLATES:
        raise KeyError(f"Unknown SQL template: {template_id}")
    return SQL_TEMPLATES[template_id].strip(), parameters
