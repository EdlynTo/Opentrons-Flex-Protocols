from opentrons.types import AxisType, Point
from opentrons.protocol_api import DISPENSE_ACTION, PLUNGER_TOP
from opentrons.protocol_api import COLUMN, ALL



metadata = {
    'protocolName': 'Evotip Testing Partial Tip Pick Up',
    'author': 'Edlyn',
    'description': 'Testing partial tip pick up with 96 channel pipette',
}

requirements = {
    "robotType": "Flex",
    "apiLevel": "2.24",
}

def add_parameters(parameters):
    parameters.add_bool(variable_name="test",
                        display_name="Test Run",
                        description=("Protocol paused at several check points "),
                        default=True
                       )
    parameters.add_str(variable_name="labware_sample",
                       display_name="Sample Labware",
                       description=" ",
                       default='opentrons_96_wellplate_200ul_pcr_full_skirt',
                       choices=[
                               {"display_name": "200µL PCR 96-well Plate", "value": 'opentrons_96_wellplate_200ul_pcr_full_skirt'},
                               {"display_name": "500µL 96-Well Plate ", "value": 'eppendorf_96_wellplate_500ul_lobind'}
                               ]
                      )
    parameters.add_int(variable_name="slot_sample",
                       display_name="Sample Location",
                       description=" ",
                       default=4,
                       choices=[
                               {"display_name": "Slot A1", "value": 0},
                               {"display_name": "Slot B1", "value": 1},
                               {"display_name": "Slot C1", "value": 2},
                               {"display_name": "Slot D1", "value": 3},
                               {"display_name": "Slot B3", "value": 4},
                               {"display_name": "Slot C3", "value": 5}
                               ]
                       )
    parameters.add_str(variable_name="labware_solvent",
                       display_name="Solvent A Labware",
                       description=" ",
                       default='nest_1_reservoir_195ml',
                       choices=[
                               {"display_name": "195mL Reservoir", "value": 'nest_1_reservoir_195ml'},
                               {"display_name": "500µL 96-Well Plate ", "value": 'eppendorf_96_wellplate_500ul_lobind'}
                               ]
                      )
    parameters.add_int(variable_name="slot_solvent",
                       display_name="Solvent A Location",
                       description=" ",
                       default=0,
                       choices=[
                               {"display_name": "Slot A1", "value": 0},
                               {"display_name": "Slot B1", "value": 1},
                               {"display_name": "Slot C1", "value": 2},
                               {"display_name": "Slot D1", "value": 3},
                               {"display_name": "Slot B3", "value": 4},
                               {"display_name": "Slot C3", "value": 5}
                               ]
                       ) 
    parameters.add_str(variable_name="labware_rinse",
                       display_name="Solvent B Labware",
                       description="If rinsing Evotips with Solvent B......",
                       default='',
                       choices=[
                               {"display_name": "N/A", "value": ''},
                               {"display_name": "195mL Reservoir", "value": 'nest_1_reservoir_195ml'},
                               {"display_name": "500µL 96-Well Plate ", "value": 'eppendorfdeepwellplate96500l_96_wellplate_500ul'}
                               ]
                      )
    parameters.add_int(variable_name="slot_rinse",
                       display_name="Solvent B Location",
                       description="If rinsing Evotips with Solvent B......",
                       default=-1,
                       choices=[
                               {"display_name": "N/A", "value": -1},
                               {"display_name": "Slot A1", "value": 0},
                               {"display_name": "Slot B1", "value": 1},
                               {"display_name": "Slot C1", "value": 2},
                               {"display_name": "Slot D1", "value": 3},
                               {"display_name": "Slot B3", "value": 4},
                               {"display_name": "Slot C3", "value": 5}
                               ]
                       )  
    parameters.add_int(variable_name="time_soaking",
                       display_name="Soaking Time",
                       description=" ",
                       default=30,
                       minimum=10,
                       maximum=60,
                       unit="seconds"
                       ) 
    parameters.add_int(variable_name="slot_soaking",
                       display_name="Soaking Plate Location",
                       description=" ",
                       default=5,
                       choices=[
                               {"display_name": "Slot A1", "value": 0},
                               {"display_name": "Slot B1", "value": 1},
                               {"display_name": "Slot C1", "value": 2},
                               {"display_name": "Slot D1", "value": 3},
                               {"display_name": "Slot B3", "value": 4},
                               {"display_name": "Slot C3", "value": 5}
                               ]
                       ) 
    parameters.add_int(variable_name="type_dumpster",
                       display_name="Tip Disposal", 
                       description=" ",
                       default=2,
                       choices=[
                               {"display_name": "Trash Bin", "value": 1},
                               {"display_name": "Waste Chute", "value": 2},
                               {"display_name": "Returned to tiprack", "value": 3}
                               ]
                       )


EVOSEP_TEMPORARY_OFFSET = 0
DELAY = 15
DELAY_RINSE = 30


def run(ctx):
    
    global test
    global labware_sample
    global slot_sample
    global labware_solvent
    global slot_solvent
    global labware_rinse
    global slot_rinse
    global time_soaking
    global slot_soaking
    # global vol_extra
    global type_dumpster
    global h_tip_in_well

    test = ctx.params.test
    labware_sample = ctx.params.labware_sample
    slot_sample = ctx.params.slot_sample
    labware_solvent = ctx.params.labware_solvent
    slot_solvent= ctx.params.slot_solvent
    labware_rinse = ctx.params.labware_rinse
    slot_rinse = ctx.params.slot_rinse
    time_soaking = ctx.params.time_soaking
    slot_soaking = ctx.params.slot_soaking
    # vol_extra = ctx.params.vol_extra
    type_dumpster= ctx.params.type_dumpster


    if test: h_tip_in_well = 3
    else: h_tip_in_well = -43


    open_slot = ['A1', 'B1', 'C1', 'D1', 'B3', 'C3']

    sample_plate = ctx.load_labware(labware_sample, open_slot[slot_sample], 'Samples')
    sample = sample_plate.wells()[0]

    sol_a_plate = ctx.load_labware(labware_solvent, open_slot[slot_solvent], 'Solvent A')
    sol_a = sol_a_plate.wells()[0]

    if slot_rinse != -1 and labware_rinse != '':
        sol_b_plate = ctx.load_labware(labware_rinse, open_slot[slot_rinse], 'Solvent B')
        sol_b = sol_b_plate.wells()[0]

    soak_plate = ctx.load_adapter('ev_resin_tips_flex_short_adapter', open_slot[slot_soaking])

    if type_dumpster == 1: ctx.load_trash_bin('D3')
    elif type_dumpster == 2: ctx.load_waste_chute()


    evotips_adapter = ctx.load_adapter('ev_resin_tips_flex_96_tiprack_adapter', 'D2')
    evosep_tips_labware = evotips_adapter.load_labware('ev_resin_tips_flex_96_labware', 'Evotips')
    evotip = evosep_tips_labware.wells()[0]


    if slot_rinse != -1 and labware_rinse != '':
        tipbox_slot = ['A3', 'C2', 'B2']
    else:
        tipbox_slot = ['C2', 'B2']

    tips_200 = ctx.load_labware('opentrons_flex_96_tiprack_200ul', 'A2', '200uL tips', adapter='opentrons_flex_96_tiprack_adapter')
    tips_50 = [ctx.load_labware('opentrons_flex_96_tiprack_50ul', slot, '50uL tips', adapter='opentrons_flex_96_tiprack_adapter')
                               for slot in tipbox_slot]
                               
    p1k_96 = ctx.load_instrument('flex_96channel_1000') 


    robot_api = ctx.robot
    #### adding 15 uL and then 20 uL

    p1k_96.tip_racks = tips_50


