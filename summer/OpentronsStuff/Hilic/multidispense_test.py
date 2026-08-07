from opentrons import protocol_api
import math
import urllib.request
import json
from opentrons import types
import time
from datetime import datetime

metadata = {
    "protocolName": "Multidispense Test",
    "description": "Testing multidispense of formic acid in HILIC protocol",
    "author": "Edlyn",
}

requirements = {"robotType": "Flex", "apiLevel": "2.28"}

def add_parameters(parameters: protocol_api.Parameters):
    parameters.add_int(
        variable_name="numSamples",
        display_name="Number of Samples",
        description="Number of samples",
        default=96,
        minimum=1,
        maximum=96,
        unit="samples",
    )
    parameters.add_bool(
        variable_name="dry_run",
        display_name="Dry Run",
        description="Skip incubation delays and return tips. Don't modify this value unless you're testing stuff.",
        default=True,
    )

def run(protocol: protocol_api.ProtocolContext):
    num_samples = protocol.params.numSamples
    dry_run = protocol.params.dry_run

    wash_volume = 150  # protocol.params.wash_volume   #µl
    shake_speed = 1400  # protocol.params.shake_speed   #rpm
    num_washes = 2
    num_samples = protocol.params.numSamples
    bead_settle_time = 10  # seconds
    dtt_conc = 110 #mM
    iaa_conc = 360 #mM
    incubation_temp = 47 #C
    load_buffers = False
    load_beads = True

    protein_stock_conc = 50
    bead_amt = max(protein_stock_conc / 4, 5)  # µl #currently 12.5ul
    protein_sample_amt = 60  # Includes DTT + IAA + protein sample + buffer
    protein_added_to_beads = protein_sample_amt * 2  # ul (includes binding buffer)
    binding_buffer_amt = (60 * 8 * (math.ceil(num_samples / 8)) + 1000) / 1000  # ml
    wash_buffer_amt = (300 * 8 * (math.ceil(num_samples / 8)) + 1000) / 1000  # ml
    digestion_buffer_per_sample_amt = 100
    
    #FINAL STEP
    amt_of_sample_to_collect = digestion_buffer_per_sample_amt-30
    amt_final_buffer_to_add = 10  #try 10%FA
    amt_extra_in_2ml_reservoir = 30
    bead_amt_extra_in_2ml_reservoir = 20

     # loading tips
    tip_box_slots = ["A3", "B3"]
    if load_buffers:
        tips200 = [
            protocol.load_labware("opentrons_flex_96_filtertiprack_1000uL", "A3"),
            protocol.load_labware("opentrons_flex_96_filtertiprack_200uL", "B3"),
        ]
    else:
        tips200 = [
            protocol.load_labware("opentrons_flex_96_filtertiprack_200uL", "A3"),
            protocol.load_labware("opentrons_flex_96_filtertiprack_200uL", "B3"),
        ]


    chute = protocol.load_waste_chute()
    left_pipette = protocol.load_instrument(
        "flex_1channel_1000", "left", tip_racks=tips200
    )
    right_pipette = protocol.load_instrument(
        "flex_8channel_1000", "right", tip_racks=tips200
    )
    magnetic_block = protocol.load_module(module_name="magneticBlockV1", location="C1")
    hs_mod = protocol.load_module(
        module_name="heaterShakerModuleV1", location="D1"
    )  # heat shaker module
    # tube_rack = protocol.load_labware("opentrons_24_tuberack_eppendorf_1.5ml_safelock_snapcap", "A2", "bead + final solution rack")
    sample_plate = protocol.load_labware(
        "opentrons_96_wellplate_200ul_pcr_full_skirt", "A1", "sample stock plate"
    )
    reagent_plate = protocol.load_labware(
            "thermofisher_96_wellplate_250ul", "A2", "reagent plate large"
        ) #Large plate only
    digestion_buffer_reservoir = protocol.load_labware(
        "nest_96_wellplate_2ml_deep", location="B2"
    )  ## change deck location
    working_reagent_reservoir = protocol.load_labware("nest_12_reservoir_15ml", "D2")

    if num_samples > 24:
        final_tube_rack = protocol.load_labware(
            "opentrons_96_wellplate_200ul_pcr_full_skirt",
            "B1",
            "final solution rack",
        )
    # if num_samples > 24:
    #     final_tube_rack = protocol.load_labware(
    #         "opentrons_96_aluminumblock_generic_pcr_strip_200ul",
    #         "B1",
    #         "final solution rack",
    #     )
    else:
        final_tube_rack = protocol.load_labware(
            "opentrons_24_tuberack_eppendorf_1.5ml_safelock_snapcap",
            "B1",
            "final solution rack",
        )
    falcon_tube_rack = protocol.load_labware(
        "opentrons_10_tuberack_falcon_4x50ml_6x15ml_conical", "C2", "falcon rack"
    )
    lid = protocol.load_lid_stack(
        load_name="opentrons_tough_pcr_auto_sealing_lid", location="C3", quantity=1
    )
    
    # defining liquids
    bead_sol = protocol.define_liquid(
        "HILIC Bead Solution", "An alloquat of the HILIC bead solution", "#000000"
    )
    dtt_stock = protocol.define_liquid("DTT Stock", "DTT Stock", "#ff8503")
    iaa_stock = protocol.define_liquid("IAA Stock", "IAA Stock", "#df02f7")
    empty_tube = protocol.define_liquid("Empty Tube", "Empty 1.5ml snapcap", "#8a8a8a")
    binding_buffer = protocol.define_liquid(
        "Binding Buffer", "200mM ammonium acetate, pH 4.5, 30%% acetonitrile", "#8d32a8"
    )
    wash_buffer = protocol.define_liquid(
        "Wash Buffer", "95%% acetonitrile (5% water)", "#05a1f5"
    )
    digestion_buffer = protocol.define_liquid(
        "Digestion Buffer", "", "#fafa02"
    )  
    # protein_buffer = protocol.define_liquid("Protein Buffer", "", "#03ff35")
    sample = protocol.define_liquid("sample", "", "#ff2503")
    
    formic_acid = protocol.define_liquid("Formic Acid", "10%% Formic acid", "#b36476")

    empty_trash_storage = protocol.define_liquid("Trash", "Trash (starts empty)", "#ffffff")
    
    # Loading Liquids
    falcon_tube_rack["A1"].load_liquid(bead_sol, bead_amt * num_samples + 200)
    bead_storage = falcon_tube_rack["A1"]
    dtt_stock_storage = falcon_tube_rack["B1"]
    iaa_stock_storage = falcon_tube_rack["C1"]
    formic_acid_storage = working_reagent_reservoir["A1"]
    formic_acid_storage.load_liquid(formic_acid, 10*num_samples + 1000)
    falcon_tube_rack["A2"].load_liquid(
        digestion_buffer, digestion_buffer_per_sample_amt * num_samples + 50 * 8
    )
    dig_buffer_location = falcon_tube_rack["A2"]
    binding_stock_buffer_storage = falcon_tube_rack["B3"]
    wash_stock_buffer_storage = falcon_tube_rack["B4"]

    binding_buffer_storage = [
        working_reagent_reservoir["A4"],
        working_reagent_reservoir["A5"],
        working_reagent_reservoir["A6"],
    ]

    wash_buffer_storage = [
        working_reagent_reservoir["A7"],
        working_reagent_reservoir["A8"],
        working_reagent_reservoir["A9"],
    ]

    trash_storage = working_reagent_reservoir["A10"]
    trash_storage2 = working_reagent_reservoir["A11"]
    trash_storage3 = working_reagent_reservoir["A12"]
    trash_storage4 = working_reagent_reservoir["A6"]

    trash_storage.load_liquid(empty_trash_storage, 0)
    trash_storage2.load_liquid(empty_trash_storage, 0)
    trash_storage3.load_liquid(empty_trash_storage, 0)
    trash_storage4.load_liquid(empty_trash_storage, 0)

    # trash1=trash_reservoir.wells()[0].bottom(7)
    staging_slots = ["A4", "B4", "C4", "D4"]
    staging_racks = [
        protocol.load_labware("opentrons_flex_96_filtertiprack_200uL", slot)
        for slot in staging_slots
    ]
    pipette_max = 1000 - 5

    # REPLENISHING TIPS
    count = 0

    def remove_tip(pipette, is_dry_run=protocol.params.dry_run):
        if is_dry_run:
            pipette.return_tip()
        else:
            pipette.drop_tip(chute)

    def transfer_large_amt(vol, start_loc, end_loc, pipette, rate, aspirate_height=0, dispense_height=0):
        for i in range(0, math.ceil(vol / pipette_max)):
            if i != math.ceil(vol / pipette_max) - 1:
                pipette.aspirate(
                    pipette_max, start_loc.bottom(aspirate_height), rate=rate
                )
                pipette.dispense(
                    pipette_max, end_loc.bottom(dispense_height), rate=rate
                )
            else:
                pipette.aspirate(
                    vol - (pipette_max * i),
                    start_loc.bottom(aspirate_height),
                    rate=rate,
                )
                pipette.dispense(
                    vol - (pipette_max * i), end_loc.bottom(dispense_height), rate=rate
                )

    def replace_tips_manually(num_samples):
        if num_samples <= 48:
            return
        
        nonlocal tips200
        possible_slots = ["A3", "B3", "A4", "B4", "C4", "D4"]

        for slot in possible_slots:
            rack = protocol.deck[slot]
            if rack is None or any(w.has_tip for w in rack.wells()):
                continue

            protocol.pause(f"Tip rack in {slot} is empty.\nReplace with a new 200uL tip rack.")
            protocol.move_labware(labware=rack, new_location=protocol_api.OFF_DECK, use_gripper=False)
            new_rack = protocol.load_labware("opentrons_flex_96_filtertiprack_200uL", protocol_api.OFF_DECK)
            protocol.move_labware(labware=new_rack, new_location=slot, use_gripper=False)

            if slot == "A3":
                tips200[0] = new_rack
            elif slot == "B3":
                tips200[1] = new_rack
   
    
    num_columns = math.ceil(num_samples / 8)
    dispense_vol = 10
    reserve_vol = 20 

    right_pipette.pick_up_tip()
    
    right_pipette.aspirate(
        dispense_vol * num_columns + reserve_vol, formic_acid_storage.bottom(0.1), rate=0.2
    )
    for i in range(0, num_columns):
        right_pipette.dispense(dispense_vol, final_tube_rack["A"+str(i+1)].bottom(0.5), rate=0.1)
    right_pipette.dispense(reserve_vol, formic_acid_storage.bottom(0.1), rate=0.1)
    remove_tip(right_pipette, protocol.params.dry_run)
