/** @odoo-module */

// SEQ 37 - minimal POS UI hook for fish sales.
//
// This is intentionally small: it adds a "Sell Fish" control to the POS
// Product Screen. Tapping it opens a simple selection popup (species,
// quantity, source tank when more than one tank has stock) and adds a POS
// order line carrying fish_species_id / source_tank_id / fish_batch_id.
// The heavy lifting (which tanks have stock, batch selection) is delegated
// to the aquarium.pos.order model method get_available_fish_tanks() on the
// backend - see models/pos_order.py.
//
// NOT built: a dedicated fish-category product grid, barcode-driven tank
// selection, or an inline low-stock/mortality warning banner in POS. See
// the module README for the complete "what's stubbed" list.

import { patch } from "@web/core/utils/patch";
import { ProductScreen } from "@point_of_sale/app/screens/product_screen/product_screen";
import { AlertDialog } from "@web/core/confirmation_dialog/confirmation_dialog";
import { SelectionPopup } from "@point_of_sale/app/utils/input_popups/selection_popup";
import { useService } from "@web/core/utils/hooks";

patch(ProductScreen.prototype, {
    setup() {
        super.setup(...arguments);
        this.orm = useService("orm");
        this.popup = useService("popup") || null;
        this.dialog = useService("dialog");
    },

    /**
     * Called when a product tagged as a fish species is clicked, or from a
     * dedicated "Sell Fish" button added via the ProductScreen template
     * (see static/src/xml/pos_fish_sale.xml).
     */
    async onClickFishProduct(product) {
        const fishSpeciesId = product.aquarium_fish_species_id;
        if (!fishSpeciesId) {
            return this._super ? this._super(...arguments) : undefined;
        }

        const tanks = await this.orm.call(
            "pos.order",
            "get_available_fish_tanks",
            [fishSpeciesId],
        );

        if (!tanks.length) {
            this.dialog.add(AlertDialog, {
                title: "No Stock",
                body: "No tank currently has stock for this fish species.",
            });
            return;
        }

        let selectedTank = tanks[0];
        if (tanks.length > 1 && this.popup) {
            const { confirmed, payload } = await this.popup.add(SelectionPopup, {
                title: "Select Source Tank",
                list: tanks.map((t) => ({
                    id: t.tank_id,
                    label: `${t.tank_code || t.tank_name} (${t.quantity} available)`,
                    item: t,
                })),
            });
            if (!confirmed) {
                return;
            }
            selectedTank = payload;
        }

        const order = this.pos.get_order();
        const line = order.add_product(product, { quantity: 1 });
        if (line) {
            line.aquarium_is_fish_line = true;
            line.aquarium_fish_species_id = fishSpeciesId;
            line.aquarium_source_tank_id = selectedTank.tank_id;
            line.aquarium_fish_batch_id = selectedTank.batch_ids
                ? selectedTank.batch_ids[0]
                : false;
        }
    },
});
