from opentrons import protocol_api
import math
import urllib.request
import json
from opentrons import types
import time
from datetime import datetime

metadata = {
    "protocolName": "Mixing water",
    "author": "Edlyn To",
    "description": "mixing water dynamically",
}

requirements = {"robotType": "Flex", "apiLevel": "2.27"}

def run(protocol: protocol_api.ProtocolContext):
    tips1000 = [protocol.load_labware("opentrons_flex_96_filtertiprack_1000uL", "A3")]
    chute = protocol.load_waste_chute()
    left_pipette = protocol.load_instrument("flex_1channel_1000", "left", tip_racks=tips1000)
    right_pipette = protocol.load_instrument("flex_8channel_1000", "right", tip_racks=tips1000)

    wellPlate = protocol.load_labware("nest_96_wellplate_2ml_deep", "B2")
    reservoir = protocol.load_labware("nest_12_reservoir_15ml", "D2")
    width = reservoir["A1"].width
    falcon_tube_rack = protocol.load_labware("opentrons_10_tuberack_falcon_4x50ml_6x15ml_conical", "C2","falcon rack")

    left_pipette.pick_up_tip()

    # its empty
    wellPlate.load_empty(wellPlate.wells())
    reservoir.load_empty(reservoir.wells())

    # the liquid is water
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


    # load liquid
    falcon_tube_rack["A4"].load_liquid(liquid=water1, volume=7500)
    falcon_tube_rack["B4"].load_liquid(liquid=water2, volume=7500)
    reservoir["A1"].load_liquid(liquid=water3, volume=10000)


    # Aspirate and dispense 500 µL in well plate 
    left_pipette.aspirate(500, falcon_tube_rack["A4"])
    left_pipette.dispense(500, wellPlate["A1"])
    left_pipette.blow_out(wellPlate["A1"].top(-2))


    left_pipette.aspirate(500, falcon_tube_rack["B4"])
    left_pipette.dispense(500, wellPlate["A2"])
    left_pipette.blow_out(wellPlate["A2"].top(-2))

    # find meniscus 
    left_pipette.measure_liquid_height(wellPlate["A1"])
    left_pipette.measure_liquid_height(wellPlate["A2"])
    print("meniscus height: " + str(wellPlate["A1"].meniscus))


    # Aspirate and dispense 1 mL in well plate 
    left_pipette.aspirate(1000, falcon_tube_rack["A4"])
    left_pipette.dispense(
        volume = 1000,
        location = wellPlate["A1"].meniscus(z=-1, target="start"),
        end_location = wellPlate["A1"].meniscus(z=-1, target="end"),
        push_out=7
    )
    left_pipette.aspirate(1000, falcon_tube_rack["B4"])
    left_pipette.dispense(
        volume = 1000,
        location = wellPlate["A2"].meniscus(z=-1, target="start"),
        end_location = wellPlate["A2"].meniscus(z=-1, target="end"),
        push_out=7
    )

    # Aspirate and dispense 1 mL from well plate to reservoir
    left_pipette.prepare_to_aspirate()
    left_pipette.aspirate(
        volume = 1000,
        location=wellPlate["A1"].meniscus(z=-1, target="start"),
        end_location=wellPlate["A1"].meniscus(z=-1, target="end")
    )
    left_pipette.dispense(
        volume = 1000,
        location = types.Location(reservoir["A1"].from_center_cartesian(x=0, y=0.9, z=-0.5), reservoir["A1"]),
        end_location = types.Location(reservoir["A1"].from_center_cartesian(x=0, y=-0.9, z=-0.5), reservoir["A1"]),
        push_out=7
    )
    left_pipette.prepare_to_aspirate()
    left_pipette.aspirate(
        volume = 1000,
        location = wellPlate["A2"].meniscus(z=-1, target="start"),
        end_location = wellPlate["A2"].meniscus(z=-1, target="end")
    )
    left_pipette.dispense(
        volume = 1000,
        location = types.Location(reservoir["A1"].from_center_cartesian(x=0, y=0.9, z=-0.5), reservoir["A1"]),  # dispense while moving along width
        end_location = types.Location(reservoir["A1"].from_center_cartesian(x=0, y=-0.9, z=-0.5), reservoir["A1"]),
        push_out=7
    )

    # Mix in reservoir by moving along the width of the reservoir while aspirating and dispensing
    left_pipette.prepare_to_aspirate()

    # finding liquid height in reservoir
    h = left_pipette.measure_liquid_height(reservoir["A1"])
    halfDepth = reservoir["A1"].depth/2
    hFraction = ((h-halfDepth)/halfDepth) - 0.1
    hFractionSet = 0.5
    print("liquid height fraction: " + str(hFraction))
    left_pipette.dynamic_mix(
        aspirate_start_location = types.Location(
            reservoir["A1"].from_center_cartesian(x=0, y=-0.9, z=-0.8), reservoir["A1"]
        ),
        aspirate_end_location = types.Location(
            reservoir["A1"].from_center_cartesian(x=0, y=0.9, z=-0.8), reservoir["A1"]
        ),
        dispense_start_location = types.Location(
            reservoir["A1"].from_center_cartesian(x=0, y=0.9, z=hFractionSet), reservoir["A1"]
        ),
        dispense_end_location = types.Location(
            reservoir["A1"].from_center_cartesian(x=0, y=-0.9, z=hFractionSet), reservoir["A1"]
        ),
        repetitions = 2,
        volume = 1000
    )
    left_pipette.prepare_to_aspirate()
    left_pipette.dynamic_mix(
        aspirate_start_location = types.Location(
            reservoir["A1"].from_center_cartesian(x=0, y=-0.9, z=-0.8), reservoir["A1"]
        ),
        aspirate_end_location = types.Location(
            reservoir["A1"].from_center_cartesian(x=0, y=0.9, z=hFractionSet), reservoir["A1"]
        ),
        dispense_start_location = types.Location(
            reservoir["A1"].from_center_cartesian(x=0, y=-0.9, z=hFractionSet), reservoir["A1"]
        ),
        dispense_end_location = types.Location(
            reservoir["A1"].from_center_cartesian(x=0, y=0.9, z=-0.8), reservoir["A1"]
        ),
        repetitions = 2,
        volume = 1000
    )



    left_pipette.return_tip()
    # left_pipette.mix(3, 300, reservoir["A2"])
    # left_pipette.drop_tip(chute)