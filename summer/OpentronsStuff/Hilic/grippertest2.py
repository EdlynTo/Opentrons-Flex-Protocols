from opentrons import protocol_api

metadata = {'protocolName': 'Gripper Test 2'}
requirements = {"robotType": "Flex", "apiLevel": "2.24"}

def run(ctx):
    mag = ctx.load_module('magneticBlockV1', 'C1')
    hs = ctx.load_module('heaterShakerModuleV1', 'D1')
    plate = ctx.load_labware('thermofisher_96_wellplate_250ul', 'A3', label='Test Plate')

    ### Starting Protocol ###
    ctx.comment('\n---Beginning Protocol---\n')
    hs.open_labware_latch()
    ctx.move_labware(plate, hs, use_gripper=True)
    ctx.move_labware(plate, mag, use_gripper=True)
    ctx.comment('\nProtocol Complete\n')
