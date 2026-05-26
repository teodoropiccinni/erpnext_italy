frappe.ui.form.on('Sales Order Item', {
	custom_pricing_rule: function(frm, cdt, cdn) {
		_apply_it_pricing_rule(frm, cdt, cdn);
	}
});

function _apply_it_pricing_rule(frm, cdt, cdn) {
	let child = locals[cdt][cdn];
	if (!child.custom_pricing_rule) {
		frappe.model.set_value(cdt, cdn, 'discount_percentage', 0);
		frappe.model.set_value(cdt, cdn, 'discount_amount', 0);
		if (child.price_list_rate) {
			frappe.model.set_value(cdt, cdn, 'rate', child.price_list_rate);
		}
		frm.refresh_field('items');
		return;
	}
	frappe.call({
		method: 'frappe.client.get',
		args: { doctype: 'Pricing Rule', name: child.custom_pricing_rule },
		callback: function(r) {
			if (!r.message) return;
			let rule = r.message;
			if (rule.discount_percentage) {
				frappe.model.set_value(cdt, cdn, 'discount_percentage', rule.discount_percentage);
			} else if (rule.discount_amount) {
				frappe.model.set_value(cdt, cdn, 'discount_amount', rule.discount_amount);
			} else if (rule.rate) {
				frappe.model.set_value(cdt, cdn, 'rate', rule.rate);
			}
			frm.refresh_field('items');
		}
	});
}
