from opentrons import protocol_api
from opentrons import types
import math

metadata = {
    "protocolName": "Move PCR Plate Test",
    "author": "Edlyn",
    "description": "moving water",
}

requirements = {"robotType": "Flex", "apiLevel": "2.27"}

def add_parameters(parameters: protocol_api.Parameters):

    parameters.add_int(
        variable_name="numSamples",
        display_name="Number of Samples",
        description="Number of samples",
        default=8,
        minimum=1,
        maximum=96,
        unit="samples",
    )

    parameters.add_bool(
        variable_name="dry_run",
        display_name="Dry Run",
        description="Skip incubation delays and return tips.",
        default=True,
    )

def run(protocol: protocol_api.ProtocolContext):
    dry_run = protocol.params.dry_run

    tips200 = [protocol.load_labware("opentrons_flex_96_filtertiprack_200uL", "A1")]
    tips1000 = [protocol.load_labware("opentrons_flex_96_filtertiprack_1000uL", "A2")]
    chute = protocol.load_waste_chute()
    left_pipette = protocol.load_instrument("flex_1channel_1000", "left", tip_racks=tips1000)
    right_pipette = protocol.load_instrument("flex_8channel_1000", "right", tip_racks=tips200)
    well_plate = protocol.load_labware("nest_96_wellplate_2ml_deep", "D2")
    reservoir = protocol.load_labware("nest_12_reservoir_15ml", "C2")
    # falcon_tube_rack = protocol.load_labware("opentrons_10_tuberack_falcon_4x50ml_6x15ml_conical", "B3","falcon rack")
    heater_shaker = protocol.load_module("heaterShakerModuleV1", "D1")
    sample_plate = heater_shaker.load_labware("thermofisher_96_wellplate_250ul", label="Sample Plate (Thermo 450)")
    pcr_plate = protocol.load_labware(
        "opentrons_96_wellplate_200ul_pcr_full_skirt", "A3", "sample stock plate"
    )
    mag_block = protocol.load_module("magneticBlockV1", "C1")

    # its empty
    well_plate.load_empty(well_plate.wells())
    reservoir.load_empty(reservoir.wells())

    water1 = protocol.define_liquid(
        name="water 1",
        description="Red water",
        display_color="#F95353"
    )
    water2 = protocol.define_liquid(
        name="water 2",
        description="Green water",
        display_color="#90FA66"
    )
    water3 = protocol.define_liquid(
        name="water 3",
        description="Regular water",
        display_color="#6690FA"
    )

    # load liquids
    reservoir["A1"].load_liquid(water2, 10000)


    # return tips
    def drop(pip):
        pip.drop_tip() if not dry_run else pip.return_tip()

    protocol.move_labware(pcr_plate, "B3", use_gripper=True)

    # 8 channel dispense 50 uL into 4 columns of the thermo well plate on the heater shaker
    right_pipette.pick_up_tip()
    right_pipette.aspirate(100, reservoir["A1"].bottom(z=1))
    right_pipette.dispense(100, pcr_plate["A1"].top(z=-1))
    right_pipette.aspirate(50, reservoir["A1"].bottom(z=1))
    right_pipette.dispense(50, pcr_plate["A1"].bottom(z=1))
    drop(right_pipette)
    heater_shaker.open_labware_latch()
    