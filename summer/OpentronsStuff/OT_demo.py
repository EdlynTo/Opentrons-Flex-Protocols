from opentrons import protocol_api
from opentrons import types
import math

metadata = {
    "protocolName": "Opentrons quick demo",
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
    falcon_tube_rack = protocol.load_labware("opentrons_10_tuberack_falcon_4x50ml_6x15ml_conical", "B3","falcon rack")
    heater_shaker = protocol.load_module("heaterShakerModuleV1", "D1")
    sample_plate = heater_shaker.load_labware("thermofisher_96_wellplate_250ul", label="Sample Plate (Thermo 450)")
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
    falcon_tube_rack["A1"].load_liquid(water1, 10000)
    reservoir["A1"].load_liquid(water2, 10000)


    # return tips
    def drop(pip):
        pip.drop_tip() if not dry_run else pip.return_tip()

    # using 1000 uL tips, aspirate water from falcon tube and multidispense 250uL into 1/2 column of NEST96 twice
    falcon_tube = falcon_tube_rack.wells_by_name()["A1"]

    heater_shaker.close_labware_latch()
    left_pipette.pick_up_tip()
    left_pipette.aspirate(1000, location=falcon_tube.meniscus(z=-1, target="start"),end_location=falcon_tube.meniscus(z=-1, target="end"))
    for char in "ABCD":
        well_name = f'{char}1'
        left_pipette.dispense(250, well_plate[well_name])
    left_pipette.prepare_to_aspirate()
    left_pipette.aspirate(1000, location=falcon_tube.meniscus(z=-1, target="start"),end_location=falcon_tube.meniscus(z=-1, target="end"))
    for char in "EFGH":
        well_name = f'{char}1'
        left_pipette.dispense(250, well_plate[well_name])

    # drop/return tip
    drop(left_pipette)

    # 8 channel dispense 50 uL into 4 columns of the thermo well plate on the heater shaker
    right_pipette.pick_up_tip()
    right_pipette.aspirate(200, well_plate["A1"].bottom(z=1))
    for i in range(1,5):
        well_name = f'A{i}'
        right_pipette.dispense(50, sample_plate[well_name])
    drop(right_pipette)

    #shake for 10 seconds
    heater_shaker.set_and_wait_for_shake_speed(500)

    # dynamic mix inside the 12 well reservoir using 1000 uL tips
    left_pipette.pick_up_tip()
    left_pipette.dynamic_mix(
        aspirate_start_location = types.Location(
            reservoir["A1"].from_center_cartesian(x=0, y=-0.9, z=-0.8), reservoir["A1"]
        ),
        aspirate_end_location = types.Location(
            reservoir["A1"].from_center_cartesian(x=0, y=0.9, z=-0.8), reservoir["A1"]
        ),
        dispense_start_location = types.Location(
            reservoir["A1"].from_center_cartesian(x=0, y=0.9, z=0), reservoir["A1"]
        ),
        dispense_end_location = types.Location(
            reservoir["A1"].from_center_cartesian(x=0, y=-0.9, z=0), reservoir["A1"]
        ),
        repetitions = 2,
        volume = 1000
    )
    drop(left_pipette)

    # stop shaking
    heater_shaker.deactivate_shaker()

    # 8 channel dispense and mix inside the thermofisher well plate and repeat the 150 uL dispense 4 times total for all the columns
    right_pipette.pick_up_tip()
    for i in range(1, 5):
        well_name = f'A{i}'
        right_pipette.aspirate(150, reservoir["A1"])
        right_pipette.dispense(150, sample_plate[well_name])
        right_pipette.mix(2, 200, sample_plate[well_name])
    drop(right_pipette)


    heater_shaker.open_labware_latch()

    # use the gripper to move it to the magnetic plate
    protocol.move_labware(sample_plate, mag_block, use_gripper=True)
    