# Version 1 - August 21, 2024

from opentrons import protocol_api
from opentrons.protocol_api import ROW, ALL
from opentrons import types
# points syntax
#p96.aspirate(100, well.bottom(2).move(types.Point(x=-2, y=2, z =-1)))
import math

metadata = {
    'protocolName': 'Partial Row Tip Pick Up',
    'description': 'Testing partial row tip pick up and return with 96 channel pipette'
}
requirements = {"robotType": "Flex", "apiLevel": "2.28"}

def add_parameters(parameters: protocol_api.Parameters): 

    parameters.add_int(
        variable_name="tiprack",
        display_name="Select Tiprack",
        description="Select tiprack for 96-ch partial pickup test",
        default=1,
        choices=[
            {"display_name": "50 µL tiprack", "value": 0},
            {"display_name": "200 µL tiprack", "value": 1},
            {"display_name": "1000 µL tiprack", "value": 2},
        ]
    )

    parameters.add_int(
        display_name="How many rows to run?",
        variable_name="rows",
        default=3,minimum=1,maximum=8,
        description="Select total rows to pick up, one at a time from the tiprack.")

    parameters.add_int(
        display_name="Empty rows",
        variable_name="skip",
        description="Select the number of empty tip rows to skip before picking up tips",
        default=0,
        choices=[
            {"display_name": "0", "value": 0},
            {"display_name": "1", "value": 1},
            {"display_name": "2", "value": 2},
            {"display_name": "3", "value": 3},
            {"display_name": "4", "value": 4},
            {"display_name": "5", "value": 5},
            {"display_name": "6", "value": 6},
            {"display_name": "7", "value": 7},
            ]
        )

def run(protocol: protocol_api.ProtocolContext):

    tiprack = ["opentrons_flex_96_filtertiprack_50ul",
               "opentrons_flex_96_filtertiprack_200ul",
               "opentrons_flex_96_filtertiprack_1000ul"][protocol.params.tiprack]
    
    rack = tiprack.split("_")[-1]


    tips = protocol.load_labware(tiprack, "C2", label = rack)
    used_tips = protocol.load_labware(tiprack, "C3", label = f"{rack} (returned)")

    used_tips.set_empty()

    p96 = protocol.load_instrument('flex_96channel_1000', 'left')

    p96.configure_nozzle_layout(
        style=ROW,
        start="H1",
        tip_racks=[tips, used_tips])

    rows = "ABCDEFGH"
    for i, rowLetter in enumerate(rows[protocol.params.skip:protocol.params.skip+protocol.params.rows]):
        p96.pick_up_tip(tips[f"{rowLetter}1"])
        protocol.delay(1)
        p96.drop_tip(used_tips[f"{rows[protocol.params.skip + i]}1"])
