from odoo import api, models


class IrConfigParameter(models.Model):
    _inherit = "ir.config_parameter"

    @api.model
    def get_param(self, key, default=False):
        """
        Compatibility method for Odoo 20 where get_param was replaced by typed accessors
        (get_str, get_bool, get_int, get_float).
        """
        val = self.get_str(key, default=None)
        if val is None:
            return default
        return val

    @api.model
    def set_param(self, key, value):
        """
        Compatibility method for Odoo 20 where set_param was replaced by typed accessors
        (set_str, set_bool, set_int, set_float).
        """
        if isinstance(value, bool):
            return self.set_bool(key, value)
        elif isinstance(value, int) and not isinstance(value, bool):
            return self.set_int(key, value)
        elif isinstance(value, float):
            return self.set_float(key, value)
        else:
            return self.set_str(key, str(value) if value is not None else "")
