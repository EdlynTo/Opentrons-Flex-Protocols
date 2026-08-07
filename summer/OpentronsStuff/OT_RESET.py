
from opentrons import protocol_api
import math
import urllib.request
import json
from opentrons import types

# from datetime import datetime, timedelta
import time
from datetime import datetime

metadata = {
    "protocolName": "Heater Shaker Reset",
    "author": "Calvin Chan",
    "description": "Reset.",
}

requirements = {"robotType": "Flex", "apiLevel": "2.20"}


#Setup Parameters that will be prompted at the start of protocol


# Define Experiment Variables
def run(protocol: protocol_api.ProtocolContext):
    tips200 = [
            protocol.load_labware("opentrons_flex_96_filtertiprack_200uL", "A3"),
            protocol.load_labware("opentrons_flex_96_filtertiprack_200uL", "B3"),
        ]
    chute = protocol.load_waste_chute()
    left_pipette = protocol.load_instrument(
        "flex_1channel_1000", "left", tip_racks=tips200
    )
    right_pipette = protocol.load_instrument(
        "flex_8channel_1000", "right", tip_racks=tips200
    )
    magnetic_block = protocol.load_module(module_name="magneticBlockV1", location="C1")
    hs_mod = protocol.load_module(
        module_name="heaterShakerModuleV1", location="D1"
    )  # heat shaker module
    
    sample_plate = protocol.load_labware("opentrons_96_wellplate_200ul_pcr_full_skirt", "C2", "sample plate")
    digestion_plate = protocol.load_labware("opentrons_96_wellplate_200ul_pcr_full_skirt", "D2", "digestion plate"
    )
    working_reagent_reservoir = protocol.load_labware("nest_12_reservoir_15ml", "A2")

    lid = protocol.load_labware("opentrons_tough_pcr_auto_sealing_lid", location="C3")

    hs_mod.close_labware_latch()
    hs_mod.deactivate_shaker()
    hs_mod.deactivate_heater()
    hs_mod.open_labware_latch()
