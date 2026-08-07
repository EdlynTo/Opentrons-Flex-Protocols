from opentrons import protocol_api
from opentrons import types
import math

metadata = {'protocolName': 'New Tube Rack Test'}
requirements = {"robotType": "Flex","apiLevel": "2.27"}

def run(protocol):
    tips200 = [
        protocol.load_labware("opentrons_flex_96_filtertiprack_200uL", "A3"),
    ]
    left_pipette = protocol.load_instrument("flex_1channel_1000", "left", tip_racks=tips200)
    right_pipette = protocol.load_instrument("flex_8channel_1000", "right", tip_racks=tips200)

    nest_reservoir = protocol.load_labware("nest_96_wellplate_2ml_deep", location="B2")
    tube_rack = protocol.load_labware("tuberack_eppendorf_12x2ml_falcon_6x15ml_conical", "C2", "tube rack")

    left_pipette.tip_racks = tips200
    left_pipette.pick_up_tip()

    left_pipette.aspirate(100, tube_rack['A1'])
    left_pipette.dispense(100, nest_reservoir['A1'])

    left_pipette.aspirate(100, tube_rack['A4'])
    left_pipette.dispense(100, nest_reservoir['A4'])

    left_pipette.return_tip()


