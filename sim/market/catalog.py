"""
Products and offers.

`item` is the canonical key an intent constrains against ("atta"). `sku` is a
specific offer of it ("atta:aashirvaad-1kg"). The split matters: substitution
attacks work by keeping the title familiar while changing the key underneath.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from ..uap.intent import Money, Quantity, Unit, unit_price


#: canonical item key -> category, used to adjudicate SAME_CATEGORY substitution
CATEGORIES: dict[str, str] = {
    "atta": "flour",
    "maida": "flour",
    "besan": "flour",
    "milk": "dairy",
    "paneer": "dairy",
    "rice": "grain",
    "beer": "alcohol",
}


@dataclass(frozen=True)
class Offer:
    sku: str
    title: str
    brand: str
    pack: Quantity
    price: Money          # the true price of one pack
    in_stock: bool = True

    @property
    def item(self) -> str:
        return self.sku.split(":")[0]

    @property
    def category(self) -> str:
        return CATEGORIES.get(self.item, "unknown")

    @property
    def true_unit_price_paise(self) -> int:
        """Honest price per display unit (kg / l / piece), rounded up."""
        return unit_price(self.price, self.pack)


def _q(amount: str, unit: Unit) -> Quantity:
    return Quantity(Decimal(amount), unit)


def default_catalog() -> dict[str, list[Offer]]:
    """
    Three merchants, overlapping ranges, genuinely different prices.

    Cheapest honest atta per kg:
        bigbasket  atta:aashirvaad-5kg   Rs 275 / 5kg  = Rs 55.00/kg
        blinkit    atta:aashirvaad-1kg   Rs  58 / 1kg  = Rs 58.00/kg
        instamart  atta:fortune-1kg      Rs  54 / 1kg  = Rs 54.00/kg   <- cheapest
    """
    return {
        "blinkit": [
            Offer("atta:aashirvaad-1kg", "Aashirvaad Whole Wheat Atta 1kg",
                  "Aashirvaad", _q("1", Unit.KG), Money.rupees(58)),
            Offer("atta:aashirvaad-5kg", "Aashirvaad Whole Wheat Atta 5kg",
                  "Aashirvaad", _q("5", Unit.KG), Money.rupees(289)),
            Offer("maida:generic-1kg", "Refined Flour (Maida) 1kg",
                  "Generic", _q("1", Unit.KG), Money.rupees(46)),
            Offer("milk:amul-1l", "Amul Taaza Milk 1L",
                  "Amul", _q("1", Unit.L), Money.rupees(66)),
        ],
        "instamart": [
            Offer("atta:fortune-1kg", "Fortune Chakki Fresh Atta 1kg",
                  "Fortune", _q("1", Unit.KG), Money.rupees(54)),
            Offer("atta:aashirvaad-1kg", "Aashirvaad Whole Wheat Atta 1kg",
                  "Aashirvaad", _q("1", Unit.KG), Money.rupees(61)),
            Offer("atta:fortune-500g", "Fortune Chakki Fresh Atta 500g",
                  "Fortune", _q("500", Unit.G), Money.rupees(29)),
            Offer("milk:amul-1l", "Amul Taaza Milk 1L",
                  "Amul", _q("1", Unit.L), Money.rupees(64)),
            # a same-base-unit, different-item SKU: the substitution attack needs a target
            Offer("maida:generic-1kg", "Refined Flour (Maida) 1kg",
                  "Generic", _q("1", Unit.KG), Money.rupees(46)),
        ],
        "bigbasket": [
            Offer("atta:aashirvaad-5kg", "Aashirvaad Whole Wheat Atta 5kg",
                  "Aashirvaad", _q("5", Unit.KG), Money.rupees(275)),
            Offer("atta:bb-royal-1kg", "BB Royal Chakki Atta 1kg",
                  "BB Royal", _q("1", Unit.KG), Money.rupees(59)),
            Offer("beer:generic-650ml", "Lager 650ml",
                  "Generic", _q("650", Unit.ML), Money.rupees(160)),
        ],
    }
