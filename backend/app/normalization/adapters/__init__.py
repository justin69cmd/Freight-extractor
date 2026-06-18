"""Pattern-specific normalization adapters.

One adapter per PricingPattern (open/closed: a 10th pattern = a 10th file here,
nothing else changes). The registry wires pattern -> adapter for the dispatcher.
"""
from __future__ import annotations

from app.core.enums import PricingPattern
from app.normalization.adapters.air_rate import AirRateAdapter
from app.normalization.adapters.cold_chain import ColdChainAdapter
from app.normalization.adapters.courier_rate import CourierRateAdapter
from app.normalization.adapters.lane_matrix import LaneMatrixAdapter
from app.normalization.adapters.per_kg import PerKgAdapter
from app.normalization.adapters.route_table import RouteTableAdapter
from app.normalization.adapters.vehicle_matrix import VehicleMatrixAdapter
from app.normalization.adapters.zone_matrix import ZoneMatrixAdapter

REGISTRY = {
    PricingPattern.ROUTE_TABLE: RouteTableAdapter(),
    PricingPattern.VEHICLE_MATRIX: VehicleMatrixAdapter(),
    PricingPattern.LANE_MATRIX: LaneMatrixAdapter(),
    PricingPattern.PER_KG_RATE: PerKgAdapter(),
    PricingPattern.AIR_RATE: AirRateAdapter(),
    PricingPattern.COURIER_RATE: CourierRateAdapter(),
    PricingPattern.ZONE_MATRIX: ZoneMatrixAdapter(),
    PricingPattern.COLD_CHAIN_RATE: ColdChainAdapter(),
    # STATE_ZONE_MAPPING is handled separately (produces ZoneMapping, not rates).
}

__all__ = ["REGISTRY"]
