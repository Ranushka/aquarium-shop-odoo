/** @odoo-module */

// SEQ 37 - POS UI wiring for guided fish sales (SRD 4.12).
//
// Flow: cashier taps a fish-species product tile in the normal POS product
// grid. The product tile's onClick calls
// `pos.addProductToCurrentOrder(product)` (see
// point_of_sale/.../product_list/product_list.xml), where `pos` is the
// PosStore *service* singleton - NOT anything on ProductScreen. This file
// patches `PosStore.prototype.addProductToCurrentOrder` itself.
//
// If the product carries a `fish_species_id` (see
// models/pos_order.py ProductProduct._compute_fish_species_id, loaded into
// POS via PosSession._loader_params_product_product) -> call the backend
// `get_available_fish_tanks` RPC -> 0 tanks: block with an error, 1 tank:
// auto-select, 2+: a tank-picker popup -> a `draftPackLotLines` option is
// built directly from the chosen tank's batch (lot) NAME and passed to
// `addProductFromUi()`, bypassing `Product.getAddProductOptions()` (and
// therefore Odoo's own generic "Lot/Serial Number(s) Required" dialog)
// entirely for fish products. The chosen species/tank/batch is then stamped
// onto the newly created Orderline and serialized into the JSON Odoo sends
// on order finalization, where PosOrder._order_line_fields()
// (models/pos_order.py) picks it back up into `pos.order.line`.
//
// CORRECTED 2026-09-02: an earlier version of this file patched
// `ProductScreen.prototype.addProductToOrder`, a method that does not exist
// in this Odoo 17 build (confirmed via a live browser test: the console
// logged this file's own load-time guard, and the fish-specific flow never
// ran at all - every fish tile fell straight through to the generic lot
// dialog). The real integration point, confirmed by reading this build's
// actual `point_of_sale` source on the running container, is
// `PosStore.prototype.addProductToCurrentOrder`
// (point_of_sale/static/src/app/store/pos_store.js).

import { patch } from "@web/core/utils/patch";
import { Orderline } from "@point_of_sale/app/store/models";
import { PosStore } from "@point_of_sale/app/store/pos_store";
import { ErrorPopup } from "@point_of_sale/app/errors/popups/error_popup";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
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

patch(PosStore.prototype, {
    /**
     * Product-tile click entry point (called by ProductCard's onClick via
     * the `pos` service - see product_list.xml). Fish-species products are
     * routed through the guided tank-selection flow, which bypasses
     * `product.getAddProductOptions()` (and thus the generic lot dialog)
     * entirely; everything else falls straight through to the original
     * behaviour unchanged.
     */
    async addProductToCurrentOrder(product, options = {}) {
        if (Number.isInteger(product)) {
            product = this.db.get_product_by_id(product);
        }

        const fishSpeciesId = Array.isArray(product.fish_species_id)
            ? product.fish_species_id[0]
            : product.fish_species_id;

        if (!fishSpeciesId) {
            return super.addProductToCurrentOrder(...arguments);
        }

        this.get_order() || this.add_new_order();

        const tanks = await this.orm.call(
            "pos.order",
            "get_available_fish_tanks",
            [fishSpeciesId],
        );

        if (!tanks.length) {
            this.popup.add(ErrorPopup, {
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

        const batchId = selectedTank.batch_ids ? selectedTank.batch_ids[0] : false;
        // get_available_fish_tanks() only returns batch IDS, not their lot
        // NAME strings (which is what draftPackLotLines/newPackLotLines
        // needs) - fetch it via the standard, unmodified stock.lot model
        // rather than requiring a backend change to that RPC.
        let batchName = false;
        if (batchId) {
            const lotRecords = await this.orm.read("stock.lot", [batchId], ["name"]);
            batchName = lotRecords.length ? lotRecords[0].name : false;
        }
        if (!batchId || !batchName) {
            // eslint-disable-next-line no-console
            console.error(
                "aquarium_fish_management: get_available_fish_tanks returned a " +
                "tank with no batch_ids/batch_names - cannot build a valid " +
                "lot for this line.",
                selectedTank,
            );
            this.popup.add(ErrorPopup, {
                title: _t("No Stock"),
                body: _t("No fish batch is available for the selected tank."),
            });
            return;
        }

        // Build the lot-assignment options ourselves, in exactly the shape
        // `this.pos.getEditedPackLotLines()` would have returned from the
        // generic lot dialog, so `order.add_product()` attaches it the same
        // way - but skip ever showing that dialog.
        options = {
            ...options,
            draftPackLotLines: {
                modifiedPackLotLines: {},
                newPackLotLines: [{ lot_name: batchName }],
            },
        };

        await this.addProductFromUi(product, options);

        const order = this.get_order();
        const line = order.get_selected_orderline
            ? order.get_selected_orderline()
            : order.get_last_orderline();
        if (line) {
            line.setFishSaleData({
                fish_species_id: fishSpeciesId,
                source_tank_id: selectedTank.tank_id,
                fish_batch_id: batchId,
            });
        } else {
            // eslint-disable-next-line no-console
            console.error(
                "aquarium_fish_management: could not find the orderline just " +
                "added for a fish product; species/tank were NOT attached to " +
                "the sale. get_selected_orderline()/get_last_orderline() may " +
                "not behave as expected on this Odoo build."
            );
        }

        if (product.tracking === "serial") {
            this.selectedOrder?.selected_orderline?.set_quantity_by_lot();
        }
        this.numberBuffer.reset();
    },

    /**
     * Show the tank picker via the "popup" service (SelectionPopup, still
     * present in this Odoo 17.0 point-release alongside "dialog").
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
