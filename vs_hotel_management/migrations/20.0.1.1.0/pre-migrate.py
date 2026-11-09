# -*- coding: utf-8 -*-
"""
Migration: 20.0.1.1.0
1. Remove the old single 'privilege_hotel_management' privilege record so the
   new 6-privilege structure can be loaded cleanly.
2. Clear stale cross-privilege implied_ids for group_hotel_manager and
   group_hotel_admin — the new XML uses (6,0,[...]) replace mode, but that
   only works cleanly if stale DB rows are gone before the XML applies.

This runs BEFORE the module XML is reloaded.
"""


def migrate(cr, version):
    # -----------------------------------------------------------------------
    # Step A: Remove old single 'privilege_hotel_management' privilege (if any)
    # -----------------------------------------------------------------------
    cr.execute("""
        SELECT res_id FROM ir_model_data
        WHERE module = 'vs_hotel_management'
          AND name = 'privilege_hotel_management'
          AND model = 'res.groups.privilege'
        LIMIT 1
    """)
    row = cr.fetchone()
    if row:
        old_privilege_id = row[0]
        cr.execute("""
            UPDATE res_groups
            SET privilege_id = NULL
            WHERE privilege_id = %s
        """, (old_privilege_id,))
        cr.execute("DELETE FROM res_groups_privilege WHERE id = %s", (old_privilege_id,))
        cr.execute("""
            DELETE FROM ir_model_data
            WHERE module = 'vs_hotel_management'
              AND name = 'privilege_hotel_management'
        """)

    # -----------------------------------------------------------------------
    # Step B: Clear all implied_ids for group_hotel_manager and
    #         group_hotel_admin so the XML (6,0,[...]) replace mode
    #         produces the correct final set without stale cross-privilege links.
    # -----------------------------------------------------------------------
    for xmlid_name in ('group_hotel_manager', 'group_hotel_admin',
                       'group_hotel_gm_bridge', 'group_hotel_admin_bridge'):
        cr.execute("""
            SELECT res_id FROM ir_model_data
            WHERE module = 'vs_hotel_management' AND name = %s
            LIMIT 1
        """, (xmlid_name,))
        row = cr.fetchone()
        if row:
            group_id = row[0]
            cr.execute("""
                DELETE FROM res_groups_implied_rel
                WHERE gid = %s
            """, (group_id,))

