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
        default=0,
        choices=[
            {"display_name": "50 µL tiprack", "value": 0},
            {"display_name": "200 µL tiprack", "value": 1},
            {"display_name": "1000 µL tiprack", "value": 2},
        ]
    )

    parameters.add_int(
        display_name="How many columns?",
        variable_name="columns",
        default=3,minimum=1,maximum=12,
        description="Select total columns to pick up, one at a time (pick up -> wait -> return), from the tiprack.")



def run(protocol: protocol_api.ProtocolContext):

    tiprack = ["opentrons_flex_96_filtertiprack_50ul",
               "opentrons_flex_96_filtertiprack_200ul",
               "opentrons_flex_96_filtertiprack_1000ul"][protocol.params.tiprack]
    
    rack = tiprack.split("_")[-1]


    tips = protocol.load_labware(tiprack, "C2", label = rack)
    used_tips = protocol.load_labware(tiprack, "B2", label = f"{rack} (returned)")
    # This rack is physically empty even though it's the same labware type,
    # so tell the API's automatic tip tracking not to treat it as full.
    used_tips.set_empty()

    p96 = protocol.load_instrument('flex_96channel_1000', 'left')

    p96.configure_nozzle_layout(
        style=COLUMN,
        start="A1",
        tip_racks=[tips, used_tips])

    for i in range(protocol.params.columns):
        protocol.comment(f"----> Picking up column {i + 1} of {protocol.params.columns}")
        p96.pick_up_tip()
        p96.home()
        protocol.delay(1)
        p96.drop_tip(used_tips[f"A{i + 1}"])
    