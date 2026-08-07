from opentrons import protocol_api
import math
import urllib.request
import json
from opentrons import types
import time
from datetime import datetime

metadata = {
    "protocolName": "Dead Volume Test",
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

    protein_sample_amt = 60
    dtt_conc = 110  # mM
    dtt_final_conc = 10  # mM
    pipette_min = 5  # 5ul is the minimum volume for the pipette
    amt_extra_in_2ml_reservoir = 30
    bead_amt_extra_in_2ml_reservoir = 20
    pipette_max = 200 - 5

    # Creating DTT Dilution
    dtt_working_stock_conc = (dtt_final_conc * protein_sample_amt) / pipette_min # DTT working stock concentration so that 5ul is 20 mM
    dtt_working_vol = pipette_min * num_samples + 8 * amt_extra_in_2ml_reservoir + 50
    dtt_stock_vol = (dtt_working_stock_conc * dtt_working_vol) / dtt_conc # amt of stock that needs to be transfered to create working dtt solution

    physical_fill_vol = 5 * num_samples + 450

    #bead
    protein_stock_conc = 50
    bead_amt = max(protein_stock_conc / 4, 5)  # µl #currently 12.5ul
    protein_sample_amt = 60  # Includes DTT + IAA + protein sample + buffer


    protocol.comment(f"num samples = {num_samples}")
    protocol.comment(f"amt of stock that needs to be transfered to create working dtt solution: {dtt_stock_vol:.1f} uL")
    protocol.comment(f"actual amount in falcon tube: {physical_fill_vol:.1f} uL")

    tips200 = [
        protocol.load_labware("opentrons_flex_96_filtertiprack_200uL", "A3"),
        protocol.load_labware("opentrons_flex_96_filtertiprack_200uL", "B3")
    ]
    chute = protocol.load_waste_chute()
    left_pipette = protocol.load_instrument(
        "flex_1channel_1000", "left", tip_racks=tips200
    )
    right_pipette = protocol.load_instrument(
        "flex_8channel_1000", "right", tip_racks=tips200
    )

    falcon_tube_rack = protocol.load_labware(
        "opentrons_10_tuberack_falcon_4x50ml_6x15ml_conical", "C2", "falcon rack"
    )
    digestion_buffer_reservoir = protocol.load_labware(
        "nest_96_wellplate_2ml_deep", "B2"
    )
    sample_plate = protocol.load_labware(
        "opentrons_96_wellplate_200ul_pcr_full_skirt", "A1", "sample stock plate"
    )
    reagent_plate = protocol.load_labware(
        "thermofisher_96_wellplate_250ul", "A2", "reagent plate large"
    ) 

    # defining liquids
    bead_sol = protocol.define_liquid(
        "HILIC Bead Solution", "An alloquat of the HILIC bead solution", "#000000"
    )
    dtt_stock = protocol.define_liquid("DTT Stock", "DTT Stock", "#ff8503")
    # Loading Liquids
    falcon_tube_rack["A1"].load_liquid(bead_sol, bead_amt * num_samples * 1.2 + 200)
    bead_storage = falcon_tube_rack["A1"]
    dtt_stock_storage = falcon_tube_rack["B1"]
    iaa_stock_storage = falcon_tube_rack["C1"]
    
    # falcon_tube_rack["B1"].load_liquid(dtt_stock, physical_fill_vol)
    falcon_tube_rack["B1"].load_liquid(dtt_stock, dtt_stock_vol)
    dtt_working_storage = dtt_stock_storage

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
    
    # DTT TO NEST 96 DEEP WELL PLATE
    # left_pipette.pick_up_tip()
    # for i in range(0, 8):
    #     if i < num_samples % 8:
    #         amt_in_well = 5 * math.ceil(num_samples / 8) + amt_extra_in_2ml_reservoir
    #     else:
    #         amt_in_well = 5 * math.floor(num_samples / 8) + amt_extra_in_2ml_reservoir

    #     transfer_large_amt(
    #         amt_in_well,
    #         dtt_working_storage,
    #         digestion_buffer_reservoir.wells()[i + 8],
    #         left_pipette,
    #         0.5,
    #         dispense_height=1,
    #     )
    # remove_tip(left_pipette,protocol.params.dry_run)

    # # ADDING DTT TO PLATE
    # for i in range(0, math.ceil(num_samples / 8)):
    #     right_pipette.pick_up_tip()
    #     right_pipette.aspirate(5, digestion_buffer_reservoir["A2"].bottom(0.1), 0.2)
    #     right_pipette.dispense(5, sample_plate["A" + str(i + 1)].bottom(1), 0.5)
    #     right_pipette.mix(
    #         3,
    #         protein_sample_amt - 20,
    #         sample_plate["A" + str(i + 1)].bottom(1),
    #         0.2,
    #     )
    #     right_pipette.blow_out(sample_plate["A" + str(i + 1)].top())
    #     remove_tip(right_pipette, protocol.params.dry_run)
    # pipette_max = 195
    # # num_transfers = math.ceil((bead_amt * num_samples) / (pipette_max))
    # # well_counter = 0
    # change_tip_after = 3

    # beads OLD
    # protocol.comment("\nTransfering 25µl HILIC beads into well plate")
    # total_bead_amt = bead_amt * num_samples
    # left_pipette.pick_up_tip()
    # bead_amt_mix = total_bead_amt
    # for i in range (0, num_samples):
    #     # bead_amt = bead_amt_list[i]
    #     if i % 3 == 0:
    #         if i !=0:
    #             remove_tip(left_pipette)
    #             left_pipette.pick_up_tip()
    #         left_pipette.mix(3, min(200, bead_amt_mix), bead_storage, 0.5)
    #         left_pipette.blow_out(bead_storage)
            
    #     left_pipette.aspirate(bead_amt, bead_storage.bottom(0.1), 0.1)
    #     left_pipette.dispense(
    #         bead_amt, reagent_plate.wells()[i], 0.1
    #     )
    #     left_pipette.blow_out(reagent_plate.wells()[i].top())
    #     bead_amt_mix -= bead_amt
    # remove_tip(left_pipette)

    # BEADS 8-CHANNEL
    # protocol.comment("\nTransfering HILIC beads into NEST 96 Deep well plate")
    # total_bead_amt = bead_amt * num_samples
    # bead_amt_mix = total_bead_amt


    # left_pipette.pick_up_tip()
    # for i in range(0, 8):
    #     if i < num_samples % 8:
    #         amt_in_well = 12.5 * math.ceil(num_samples / 8) + bead_amt_extra_in_2ml_reservoir
    #     else:
    #         amt_in_well = 12.5 * math.floor(num_samples / 8) + bead_amt_extra_in_2ml_reservoir
    #     if i%2 == 0:
    #         left_pipette.mix(3, min(200, bead_amt_mix), bead_storage, 0.5)
    #         left_pipette.blow_out(bead_storage)
    #     transfer_large_amt(
    #         amt_in_well,
    #         bead_storage,
    #         digestion_buffer_reservoir.wells()[i + 48],
    #         left_pipette,
    #         0.5,
    #         dispense_height=1,
    #     )
    #     bead_amt_mix -= amt_in_well
    # remove_tip(left_pipette,protocol.params.dry_run)

    # # Adding beads to plate
    # for i in range(0, math.ceil(num_samples / 8)):
    #     right_pipette.pick_up_tip()
    #     right_pipette.mix(
    #         3,
    #         amt_in_well,
    #         digestion_buffer_reservoir["A7"].bottom(1),
    #         0.5,
    #     )
    #     right_pipette.aspirate(bead_amt, digestion_buffer_reservoir["A7"].bottom(0.1), 0.2)
    #     right_pipette.dispense(bead_amt, reagent_plate["A" + str(i + 1)].bottom(1), 0.5)
    #     right_pipette.blow_out(reagent_plate["A" + str(i + 1)].top())
    #     remove_tip(right_pipette)
    #     amt_in_well -= bead_amt

    # replace_tips_manually(num_samples)


# MENISCUS TRACKING
    # protocol.comment("\nTransfering HILIC beads into NEST 96 Deep well plate dynamically")

    # total_bead_amt = bead_amt * num_samples
    # bead_amt_mix = total_bead_amt

    # left_pipette.pick_up_tip()

    # for i in range(0, 8):
    #     if i < num_samples % 8:
    #         amt_in_well = 12.5 * math.ceil(num_samples / 8) + bead_amt_extra_in_2ml_reservoir
    #     else:
    #         amt_in_well = 12.5 * math.floor(num_samples / 8) + bead_amt_extra_in_2ml_reservoir
    #     if i%2 == 0:
    #         left_pipette.prepare_to_aspirate()
    #         left_pipette.dynamic_mix(
    #             aspirate_start_location = bead_storage.meniscus(z=-1, target="start"),
    #             aspirate_end_location = bead_storage.bottom(z=1),
    #             repetitions = 3,
    #             volume = min(200, bead_amt_mix),
    #             dispense_start_location = bead_storage.meniscus(z=-1, target="end"),
    #             rate = 0.5
    #         )
    #         left_pipette.blow_out(bead_storage)
    #     transfer_large_amt(
    #         amt_in_well,
    #         bead_storage,
    #         digestion_buffer_reservoir.wells()[i + 48],
    #         left_pipette,
    #         0.5,
    #         dispense_height=1,
    #     )
    #     bead_amt_mix -= amt_in_well
    #     if i==3:
    #         remove_tip(left_pipette,protocol.params.dry_run)
    #         left_pipette.pick_up_tip()

    # remove_tip(left_pipette,protocol.params.dry_run)

    # # Adding beads to plate
    # right_pipette.pick_up_tip()
    # for i in range(0, math.ceil(num_samples / 8)):
    #     right_pipette.mix(
    #         3,
    #         amt_in_well,
    #         digestion_buffer_reservoir["A7"].bottom(1),
    #         0.5,
    #     )
    #     right_pipette.aspirate(bead_amt, digestion_buffer_reservoir["A7"].bottom(0.1), 0.2)
    #     right_pipette.dispense(bead_amt, reagent_plate["A" + str(i + 1)].bottom(1), 0.5)
    #     right_pipette.blow_out(reagent_plate["A" + str(i + 1)].top())
    #     amt_in_well -= bead_amt
    # remove_tip(right_pipette)