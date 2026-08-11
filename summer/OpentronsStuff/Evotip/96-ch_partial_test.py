# Version 1 - August 21, 2024

from opentrons import protocol_api
from opentrons.protocol_api import COLUMN, ALL
from opentrons import types
# points syntax
#p96.aspirate(100, well.bottom(2).move(types.Point(x=-2, y=2, z =-1)))
import math

metadata = {
    'protocolName': 'Partial Tip Pick Up',
    'description': 'Testing partial tip pick up and return with 96 channel pipette'
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
        display_name="How many columns to run?",
        variable_name="columns",
        default=3,minimum=1,maximum=12,
        description="Select total columns to pick up, one at a time from the tiprack.")

    parameters.add_int(
        display_name="Empty columns",
        variable_name="skip",
        description="Select the number of empty tip columns to skip before picking up tips",
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
                {"display_name": "8", "value": 8},
                {"display_name": "9", "value": 9},
                {"display_name": "10", "value": 10},
                {"display_name": "11", "value": 11}
                ]
        )

    # parameters.add_str(
    #         display_name="Empty columns",
    #         variable_name="start",
    #         description="Select the number of empty tip columns to skip before picking up tips",
    #         default="A1",
    #         choices=[
    #                 {"display_name": "0", "value": "A1"},
    #                 {"display_name": "1", "value": "A2"},
    #                 {"display_name": "2", "value": "A3"},
    #                 {"display_name": "3", "value": "A4"},
    #                 {"display_name": "4", "value": "A5"},
    #                 {"display_name": "5", "value": "A6"},
    #                 {"display_name": "6", "value": "A7"},
    #                 {"display_name": "7", "value": "A8"},
    #                 {"display_name": "8", "value": "A9"},
    #                 {"display_name": "9", "value": "A10"},
    #                 {"display_name": "10", "value": "A11"},
    #                 {"display_name": "11", "value": "A12"}
    #                 ]
    #         )

def run(protocol: protocol_api.ProtocolContext):

    tiprack = ["opentrons_flex_96_filtertiprack_50ul",
               "opentrons_flex_96_filtertiprack_200ul",
               "opentrons_flex_96_filtertiprack_1000ul"][protocol.params.tiprack]
    
    rack = tiprack.split("_")[-1]


    tips = protocol.load_labware(tiprack, "C2", label = rack)
    used_tips = protocol.load_labware(tiprack, "B2", label = f"{rack} (returned)")

    used_tips.set_empty()

    p96 = protocol.load_instrument('flex_96channel_1000', 'left')

    p96.configure_nozzle_layout(
        style=COLUMN,
        start="A1",
        tip_racks=[tips, used_tips])

    for i in range(protocol.params.columns):
        p96.pick_up_tip(tips[f"A{12 - protocol.params.skip - i}"])
        protocol.delay(1)
        p96.drop_tip(used_tips[f"A{protocol.params.skip + i + 1}"])
    