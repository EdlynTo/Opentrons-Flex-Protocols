from opentrons import protocol_api
import math
import urllib.request
import json
from opentrons import types
import time
from datetime import datetime

metadata = {
    "protocolName": "Refill tips test",
    "author": "Edlyn",
}

requirements = {"robotType": "Flex", "apiLevel": "2.28"}

def add_parameters(parameters: protocol_api.Parameters):
    parameters.add_int(
        variable_name="numSamples",
        display_name="Number of Samples",
        description="Number of samples",
        default=100,
        minimum=1,
        maximum=100,
        unit="samples",
    )
    parameters.add_bool(
        variable_name="dry_run",
        display_name="Dry Run",
        description="Skip incubation delays and return tips. Don't modify this value unless you're testing stuff.",
        default=True,
    )

def run(protocol: protocol_api.ProtocolContext):

    def replace_tips_manually(num_samples):
        if num_samples <= 48:
            return
        nonlocal tips200

        protocol.pause(f"Replace empty 200uL tip rack.")
        protocol.move_labware(labware=tips200, new_location=protocol_api.OFF_DECK, use_gripper=False)
        protocol.move_labware(labware=new_tips200, new_location="A3", use_gripper=False)

    num_samples = protocol.params.numSamples
    dry_run = protocol.params.dry_run

    new_tips200 = protocol.load_labware("opentrons_flex_96_filtertiprack_200uL", protocol_api.OFF_DECK)

    tips200 = protocol.load_labware(
        load_name="opentrons_flex_96_filtertiprack_200uL",
        location="A3"
    )

    chute = protocol.load_waste_chute()
    
    right_pipette = protocol.load_instrument(
        "flex_8channel_1000", "right", tip_racks=[tips200, new_tips200]
    )

    def remove_tip(pipette, is_dry_run=protocol.params.dry_run):
        if is_dry_run:
            pipette.return_tip()
        else:
            pipette.drop_tip(chute)

    for i in range(0,12):
        right_pipette.pick_up_tip()
        remove_tip(right_pipette)

    # replace_tips_manually(num_samples)
    # protocol.pause(f"Replace empty 200uL tip rack.")
    protocol.move_labware(labware=tips200, new_location=protocol_api.OFF_DECK, use_gripper=False)
    protocol.move_labware(labware=new_tips200, new_location="A3", use_gripper=False)

    right_pipette.pick_up_tip()
    remove_tip(right_pipette)