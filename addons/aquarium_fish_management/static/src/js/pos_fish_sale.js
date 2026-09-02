/** @odoo-module */

// SEQ 37 - POS UI wiring for guided fish sales (SRD 4.12).
//
// Flow: cashier taps a fish-species product tile in the normal POS product
// grid -> if the product carries a `fish_species_id` (see
// models/pos_order.py ProductProduct._compute_fish_species_id, loaded into
// POS via PosSession._loader_params_product_product) -> call the backend
// `get_available_fish_tanks` RPC -> 0 tanks: block with an error, 1 tank:
// auto-select, 2+: a tank-picker popup -> the chosen species/tank/batch is
// stamped onto the newly created Orderline and serialized into the JSON
// Odoo sends on order finalization, where PosOrder._order_line_fields()
// (models/pos_order.py) picks it back up into `pos.order.line`.
//
// VERSION-SENSITIVE, NOT LIVE-TESTED - see the "Confidence / what to test"
// section of the module README before relying on this in production. The
// two riskiest assumptions, both because no live Odoo 17 runtime was
// available to check the actual point_of_sale source against:
//   1. `ProductScreen.prototype.addProductToOrder(product)` is the method
//      that fires on a product-tile click in this exact 17.0 point-release
//      (older/newer builds have used `_clickProduct` instead - a
//      load-time console.error below flags it immediately if missing).
//   2. The `popup` service (`SelectionPopup`) is still registered in this
//      point-release rather than having been fully replaced by `dialog`
//      everywhere - guarded with a fallback below.

import { patch } from "@web/core/utils/patch";
import { Orderline } from "@point_of_sale/app/store/models";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { useService } from "@web/core/utils/hooks";
import { _t } from "@web/core/l10n/translation";

// --- Orderline: round-trip the fish-sale selection through order JSON ---
//
// Odoo 17's POS order/orderline data layer (`@point_of_sale/app/store/models`)
// is still the pre-18 plain-JS-class model (constructor + export_as_JSON /
// init_from_JSON), not a reactive OWL data model - so patching these two
// methods is the standard way to add custom fields to the payload that
// reaches `pos.order.create()` on the backend.
patch(Orderline.prototype, {
    export_as_JSON() {
        const json = super.export_as_JSON(...arguments);
        json.is_fish_line = this.is_fish_line || false;
        json.fish_species_id = this.fish_species_id || false;
        json.source_tank_id = this.source_tank_id || false;
        json.fish_batch_id = this.fish_batch_id || false;
        return json;
    },
    init_from_JSON(json) {
        super.init_from_JSON(...arguments);
        this.is_fish_line = json.is_fish_line || false;
        this.fish_species_id = json.fish_species_id || false;
        this.source_tank_id = json.source_tank_id || false;
        this.fish_batch_id = json.fish_batch_id || false;
    },
    /**
     * Attach the cashier's species/tank/batch choice to this orderline.
     * Called once, right after the line is created for a fish product.
     */
    setFishSaleData({ fish_species_id, source_tank_id, fish_batch_id }) {
        this.is_fish_line = true;
        this.fish_species_id = fish_species_id || false;
        this.source_tank_id = source_tank_id || false;
        this.fish_batch_id = fish_batch_id || false;
    },
});

if (typeof ProductScreen.prototype.addProductToOrder !== "function") {
    // eslint-disable-next-line no-console
    console.error(
        "aquarium_fish_management: ProductScreen.prototype.addProductToOrder " +
        "was not found on this Odoo build. The fish-sale tank-picker patch " +
        "in pos_fish_sale.js targets that method name for Odoo 17.0 " +
        "mainline; if this point-release renamed it (e.g. back to " +
        "_clickProduct), update the patch target in pos_fish_sale.js - " +
        "fish products will otherwise add to the order as plain products " +
        "with no species/tank captured, and no error will be shown at " +
        "the point of sale itself."
    );
}

patch(ProductScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        this.dialog = useService("dialog");
        // Odoo 17.0 still ships the "popup" service (SelectionPopup et al)
        // alongside the newer "dialog" service; some 17.0 point-releases
        // have trimmed it. Look it up defensively rather than assuming.
        this.popup = this.env.services.popup || null;
    },

    /**
     * Product-tile click entry point. Fish-species products are routed
     * through the guided tank-selection flow; everything else falls
     * straight through to the original behaviour.
     */
    async addProductToOrder(product) {
        const fishSpeciesId = Array.isArray(product.fish_species_id)
            ? product.fish_species_id[0]
            : product.fish_species_id;
        if (!fishSpeciesId) {
            return super.addProductToOrder(...arguments);
        }

        const tanks = await this.orm.call(
            "pos.order",
            "get_available_fish_tanks",
            [fishSpeciesId],
        );

        if (!tanks.length) {
            this.dialog.add(AlertDialog, {
                title: _t("No Stock"),
                body: _t("No tank currently has stock for this fish species."),
            });
            return;
        }

        let selectedTank = tanks[0];
        if (tanks.length > 1) {
            selectedTank = await this._selectFishTank(tanks);
            if (!selectedTank) {
                // Cashier cancelled the tank picker - do not add a line.
                return;
            }
        }

        const result = await super.addProductToOrder(...arguments);

        const order = this.pos.get_order();
        const line =
            (order.get_selected_orderline && order.get_selected_orderline()) ||
            order.get_last_orderline();
        if (line) {
            line.setFishSaleData({
                fish_species_id: fishSpeciesId,
                source_tank_id: selectedTank.tank_id,
                fish_batch_id: selectedTank.batch_ids ? selectedTank.batch_ids[0] : false,
            });
        } else {
            // eslint-disable-next-line no-console
            console.error(
                "aquarium_fish_management: could not find the orderline just " +
                "added for a fish product; species/tank were NOT attached to " +
                "the sale. addProductToOrder()'s return value or " +
                "get_selected_orderline()/get_last_orderline() may not behave " +
                "as expected on this Odoo build."
            );
        }
        return result;
    },

    /**
     * Show the tank picker via the "popup" service when available; if this
     * point-release only has "dialog", fall back to the first tank rather
     * than failing the sale, and say so loudly in the console so it gets
     * noticed and ported.
     */
    async _selectFishTank(tanks) {
        if (this.popup && typeof this.popup.add === "function") {
            const { confirmed, payload } = await this.popup.add(SelectionPopup, {
                title: _t("Select Source Tank"),
                list: tanks.map((t) => ({
                    id: t.tank_id,
                    label: `${t.tank_code || t.tank_name} (${t.quantity} available)`,
                    item: t,
                })),
            });
            return confirmed ? payload : null;
        }
        // eslint-disable-next-line no-console
        console.error(
            "aquarium_fish_management: POS 'popup' service is unavailable in " +
            "this Odoo build; falling back to the first available tank " +
            "instead of prompting the cashier. Port _selectFishTank() in " +
            "pos_fish_sale.js to the 'dialog' service's makeAwaitable() " +
            "pattern for this build - see module README (SEQ 37)."
        );
        return tanks[0];
    },
});
