from opentrons import protocol_api
import math
import urllib.request
import json
from opentrons import types
import time
from datetime import datetime

metadata = {
    "protocolName": "SP3 HILIC protocol- API V2.28",
    "author": "Nico / Calvin",
    "description": "HILIC SP3 protocol large plate Jun2026.",
}

requirements = {"robotType": "Flex", "apiLevel": "2.28"}


def add_parameters(parameters: protocol_api.Parameters):

    parameters.add_int(
        variable_name="numSamples",
        display_name="Number of Samples",
        description="Number of samples",
        default=28,
        minimum=1,
        maximum=96,
        unit="samples",
    )
    # Default true
    parameters.add_bool(
        variable_name="reduction_alkylation",
        display_name="Reduction and Alkylation",
        description="Use Walter to reduce and alkylate",
        default=True,
    )

    parameters.add_int(
        variable_name="incubation_time",
        display_name="Incubation Time",
        choices=[
            {"display_name": "2 hrs", "value": 2},
            {"display_name": "1 hrs", "value": 1},
        ],
        description="1 or 2 hours digestion",
        default=1,
    )

    # parameters.add_bool(
    #     variable_name="dry_run",
    #     display_name="Dry Run",
    #     description="Skip incubation delays and return tips. Don't modify this value unless you're testing stuff.",
    #     default=False,
    # )

    parameters.add_int(
        display_name="Run Type",
        variable_name="run_type",
        default=1,
        choices=[
            {'display_name':'Sample Run','value':1},
            {'display_name':'Water Run','value':2},
            {'display_name':'Dry Run','value':3}
        ],
        description="What type of run is this going to be?")


def send_email(msg):
    url = "http://NicoTo.pythonanywhere.com/send-email"
    data = {
        # "subject": "Test Subject",
        "body": msg,
        "to_email": "nico.luu.to@gmail.com",
    }
    data_encoded = json.dumps(data).encode("utf-8")

    req = urllib.request.Request(
        url, data=data_encoded, headers={"Content-Type": "application/json"}
    )

    try:
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                print(" command sent successfully")
            else:
                print(f"Failed to send command")
    except urllib.error.URLError as e:
        print(f"Failed to send  command. Error: {e.reason}")


def get_height_15ml_falcon(volume):
    """
    Get's the height of the liquid in the tube
    Volume: volume of liquid in tube in ul
    Return: height in mm from the bottom of tube that pipette should go to
    """
    volume = volume / 1000
    if volume <= 1:  # cone part aaa
        # print(-3.33*(volume**2)+15.45*volume+9.50)
        height = -3.33 * (volume**2) + 15.45 * volume + 9.50 - 1  # −3.33x2+15.45x+9.50
    else:
        height = 6.41667 * volume + 15.1667 - 5
    if height < 0.1:
        height = 0.1
    return height


def get_height_50ml_falcon(volume):
    """
    Get's the height of the liquid in the tube
    Volume: volume of liquid in tube in µl
    Return: hieght from bottom of tube in millimeters
    """
    height = (1.8 * (volume / 1000)) + 12 - 3
    if height < 0.1:
        height = 0.1
    return height


def get_vol_15ml_falcon(height):
    """
    Get's the volume of the liquid in the tube
    Height: height in mm from the bottom of tube that pipette should go to
    Return: volume of liquid in tube in ul
    """
    if height <= 20.62:  # cone part
        volume = (((15.45 + math.sqrt(351.9225 - (13.32 * height)))) / 6.66) * 1000
        return volume
    else:
        volume = ((height - 10.1667) / 6.41667) * 1000
        return volume


def get_vol_50ml_falcon(height):
    """
    Get's the volume of the liquid in the tube
    Height: height of liquid in tube in mm (start from tube bottom)
    Return: volume of liquid in tube in µl
    """
    volume = (1000 * (height - 9)) / 1.8
    return volume




def run(protocol: protocol_api.ProtocolContext):
    run_type = protocol.params.run_type
    sample_run = True if run_type == 1 else False
    water_run = True if run_type == 2 else False
    dry_run = True if run_type == 3 else False
    
    # defining variables
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
    bead_amt_extra_in_2ml_reservoir = 25

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
    # lid = protocol.load_lid_stack(
    #     load_name="opentrons_tough_pcr_auto_sealing_lid", location="C3", quantity=1
    # )
    lid = protocol.load_lid_stack(
        load_name="opentrons_tough_universal_lid", location="C3", quantity=1
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

    # Functions
    def remove_tip(pipette):
        if dry_run or water_run:
            pipette.return_tip()
        else:
            pipette.drop_tip(chute)

    def remove_tip_dispense_trash(pipette, amt):
        if trash_storage.current_liquid_volume() > 13000 and trash_storage2.current_liquid_volume() < 13000:
            pipette.dispense(amt, trash_storage2.top(0))
        elif trash_storage2.current_liquid_volume() > 13000 and trash_storage3.current_liquid_volume() < 13000:
            pipette.dispense(amt, trash_storage3.top(0))
        elif trash_storage3.current_liquid_volume() > 13000:
            pipette.dispense(amt, trash_storage4.top(0))
        else:
            pipette.dispense(amt, trash_storage.top(0))

        if dry_run or water_run:
            pipette.return_tip()
        else:
            pipette.drop_tip(chute)        

    def aspirate_spuernatent_to_trash(
        pipette, amt, speed=0.05, discard_tip=True, height=0.5
    ):
        """amt: amount ot aspirirate out"""
        protocol.comment("\nAspriating supernatant to trash")
        pick_up(pipette)
        for i in range(0, math.ceil(num_samples / 8)):
                # print("hi")
                # pipette.pick_up_tip()
            pipette.aspirate(
                amt, reagent_plate["A" + str(i + 1)].bottom(height), rate=speed
            )
            # pipette.air_gap(volume=10)

            if trash_storage.current_liquid_volume() > 13000 and trash_storage2.current_liquid_volume() < 13000:
                pipette.dispense(amt, trash_storage2.top(0))
                pipette.blow_out(trash_storage2.top(0))
            elif trash_storage2.current_liquid_volume() > 13000 and trash_storage3.current_liquid_volume() < 13000:
                pipette.dispense(amt, trash_storage3.top(0))
                pipette.blow_out(trash_storage3.top(0))
            elif trash_storage3.current_liquid_volume() > 13000:
                pipette.dispense(amt, trash_storage4.top(0))
                pipette.blow_out(trash_storage4.top(0))
            else:
                pipette.dispense(amt, trash_storage.top(0))
                pipette.blow_out(trash_storage.top(0))

            # if discard_tip:
            #     remove_tip(pipette)
                
        if pipette.has_tip == True:
            remove_tip(pipette)

    def pick_up(pip):
        nonlocal tips200
        nonlocal staging_racks
        nonlocal count

        try:
            # print(tips200)
            pip.tip_racks = tips200
            # print(pip.tip_racks)
            pip.pick_up_tip()

        except protocol_api.labware.OutOfTipsError:
            print("\nout of tips\n")
            check_tips()
            pick_up(pip)

    def check_tips():
        nonlocal tips200
        nonlocal staging_racks
        nonlocal count
        # tip_box = protocol.load_labware('opentrons_flex_96_filtertiprack_1000uL', 'A3')
        for i in range(0, len(tip_box_slots)):
            bottom_right_well = tips200[i].wells_by_name()["H12"]
            top_right_well = tips200[i].wells_by_name()["A12"]
            # print(bottom_right_well.has_tip)
            # except:
            # print("ESCEPT")
            # bottom_right_well = tips200[0].wells_by_name()['A1']
            if (bottom_right_well.has_tip and top_right_well.has_tip) or protocol.deck[
                "D4"
            ] == None:
                # print("AAA" + str(protocol.deck['D4']))
                protocol.comment(
                    "A tip is present in the bottom-right corner (H12). or all staging slots are empty"
                )
                if protocol.deck["D4"] == None:
                    protocol.comment("No tip box detected in slot D4.")
                    staging_slots = ["A4", "B4", "C4", "D4"]
                    staging_racks = [
                        protocol.load_labware(
                            "opentrons_flex_96_filtertiprack_200uL", slot
                        )
                        for slot in staging_slots
                    ]
                continue
            else:
                print("starting moving phase")
                protocol.move_labware(
                    labware=tips200[i], new_location=chute, use_gripper=True if sample_run else False
                )
                rack_num = 0
                for slot in ["A4", "B4", "C4", "D4"]:
                    labware = protocol.deck[slot]
                    if labware and labware.is_tiprack:
                        tips200[i] = staging_racks[rack_num]
                        # print(tips200[i])
                        # print(tip_box_slots[i])
                        protocol.move_labware(
                            labware=staging_racks[rack_num],
                            new_location=tip_box_slots[i],
                            use_gripper=True,
                        )
                        break
                        # protocol.comment(f"A tip box is present in slot {slot}.")
                    else:
                        protocol.comment(f"No tip box detected in slot {slot}.")
                        rack_num += 1
                        pass

    def find_aspirate_height(pip, source_well):
        """
        returns: aspirate height from bottom in mm
        """
        lld_height = (
            pip.measure_liquid_height(source_well) - source_well.bottom().point.z
        )
        aspirate_height = max(lld_height - 5, 1)
        return aspirate_height

    def mix_sides(pipette, num_mixes, vol, plate, rate=0.3):
        pipette.mix(
            num_mixes, vol, plate.bottom().move(types.Point(x=0, y=1.5, z=1.5)), rate=rate
            )
        pipette.mix(
            num_mixes,
            vol,
            plate.bottom().move(types.Point(x=0, y=-1.5, z=1.5)),
            rate=rate,
            )
        pipette.mix(
            num_mixes, vol, plate.bottom().move(types.Point(x=1.5, y=0, z=1.5)), rate=rate
            )
        pipette.mix(
            num_mixes,
            vol,
            plate.bottom().move(types.Point(x=-1.5, y=0, z=1.5)),
            rate=rate,
            )
        pipette.mix(1, vol, plate.bottom(1), rate=0.1)
    
    
    def fancy_mix_sides(pipette, num_mixes, vol, plate, rate=0.3, num_points = 4):
        radius = 3.2  # mm
        # num_points = 8  # change to 12 or more for finer circle
        z_offset = 1.5  # mm, height above the bottom of the well
    
        for i in range(num_points):
            angle_rad = 2 * math.pi * i / num_points
            x = radius * math.cos(angle_rad)
            y = radius * math.sin(angle_rad)
            for a in range (0, num_mixes):
                pipette.aspirate(vol, plate.bottom(1), rate=rate)
                pipette.dispense(vol, plate.bottom().move(types.Point(x=x, y=y, z=z_offset)), rate=rate)
            # pipette.mix(
            #     num_mixes,
            #     vol,
            #     plate.bottom().move(types.Point(x=x, y=y, z=z_offset)),
            #     rate=rate,
            # )

        # Final central mix
        pipette.mix(1, vol, plate.bottom(z=z_offset), rate=0.1)

    def delay(seconds, msg=""):
        if dry_run:
            return
        # start_time = datetime.now()
        # protocol.comment(f"Delaying for {seconds} seconds")
        check_tips()
        protocol.delay(seconds=seconds, msg=msg)

    def transfer_large_amt(
        vol, start_loc, end_loc, pipette, rate, aspirate_height=0, dispense_height=0, meniscus=False
    ):
        """
        vol: volume to transfer (ul)
        start_loc: location to aspirate from
        end_loc: location to dispense to
        pipette: pipette to use
        rate: rate to aspirate and dispense
        """
        for i in range(0, math.ceil(vol / pipette_max)):
            if i != math.ceil(vol / pipette_max) - 1:
                # print(aspirate_height)
                if meniscus:
                    pipette.aspirate(
                        pipette_max, start_loc.meniscus(z=-1, target="end"), rate=rate
                    )
                else:
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
    def load_beads():
        if not load_beads:
            return
        pipette_max = 195
        # num_transfers = math.ceil((bead_amt * num_samples) / (pipette_max))
        # well_counter = 0
        change_tip_after = 3
        protocol.comment("\nTransfering 25µl HILIC beads into well plate")
        total_bead_amt = bead_amt * num_samples
        bead_amt_mix = total_bead_amt + 8 * bead_amt_extra_in_2ml_reservoir

        pick_up(left_pipette)

        for i in range(0, 8):
            if i < num_samples % 8:
                amt_in_well = 12.5 * math.ceil(num_samples / 8) + bead_amt_extra_in_2ml_reservoir
            else:
                amt_in_well = 12.5 * math.floor(num_samples / 8) + bead_amt_extra_in_2ml_reservoir
            if i%2 == 0:
                left_pipette.prepare_to_aspirate()
                left_pipette.dynamic_mix(
                    aspirate_start_location = bead_storage.meniscus(z=-1, target="start"),
                    aspirate_end_location = bead_storage.bottom(z=1.5),
                    repetitions = 3,
                    volume = min(200, bead_amt_mix),
                    dispense_start_location = bead_storage.meniscus(z=-1, target="end"),
                    rate = 0.5
                )
                left_pipette.blow_out(bead_storage)
            transfer_large_amt(
                amt_in_well,
                bead_storage,
                digestion_buffer_reservoir.wells()[i + 48],
                left_pipette,
                0.5,
                dispense_height=1,
            )
            bead_amt_mix -= amt_in_well
            if i==3:
                remove_tip(left_pipette)
                left_pipette.pick_up_tip()

        remove_tip(left_pipette)

        # Adding beads to plate
        right_pipette.pick_up_tip()
        for i in range(0, math.ceil(num_samples / 8)):
            right_pipette.mix(
                3,
                amt_in_well,
                digestion_buffer_reservoir["A7"].bottom(1),
                0.5,
            )
            right_pipette.aspirate(bead_amt, digestion_buffer_reservoir["A7"].bottom(0.1), 0.2)
            right_pipette.dispense(bead_amt, reagent_plate["A" + str(i + 1)].bottom(1), 0.5)
            right_pipette.blow_out(reagent_plate["A" + str(i + 1)].top())
            amt_in_well -= bead_amt
        remove_tip(right_pipette)
 
    
    # --------------PROTOCOL STARTS HERE----------------


    # LOADING BUFFERS
    hs_mod.open_labware_latch()
    start = 1
    # binding buffer
    #start = 4
    bbReservoirs = ["A4", "A5", "A6"]
    for i in range(0, math.ceil(binding_buffer_amt / 10)):
        if i == math.ceil(binding_buffer_amt / 10) - 1:  # on last iteration
            amt_to_transfer = (binding_buffer_amt % 10) * 1000 + 500
            # print(amt_to_transfer)
        else:
            amt_to_transfer = 10500
        working_reagent_reservoir[bbReservoirs[i]].load_liquid(
            binding_buffer, amt_to_transfer
        )
        start += 1
    # wash buffer
    start = 4
    wbReservoirs = ["A7", "A8", "A9"]
    for i in range(0, math.ceil(wash_buffer_amt / 10)):
        if i == math.ceil(wash_buffer_amt / 10) - 1:  # on last iteration
            amt_to_transfer = (wash_buffer_amt % 10) * 1000 + 500
            # print(amt_to_transfer)
        else:
            amt_to_transfer = 10500
        working_reagent_reservoir[wbReservoirs[i]].load_liquid(
            wash_buffer, amt_to_transfer
        )
        start += 1

    pipette_max = 200 - 5

    for i in range (0, num_samples):
        if protocol.params.reduction_alkylation:
            sample_plate.wells()[i].load_liquid(sample, protein_sample_amt - 10)
        else:
            sample_plate.wells()[i].load_liquid(sample, protein_sample_amt)
                
    if protocol.params.reduction_alkylation:
        hs_mod.set_target_temperature(56)  # pre-heat shaker
        dtt_final_conc = 10  # 10 mM
        iaa_final_conc = 30  # 30 mM
        pipette_min = 5  # 5ul is the minimum volume for the pipette
        protocol.comment("-------------Reduction and Alkylation ---------------")
        # Creating DTT Dilution
        dtt_working_stock_conc = (
            dtt_final_conc * protein_sample_amt
        ) / pipette_min  # DTT working stock concentration so that 5ul is 20 mM
        print("DTT working stock concentration: " + str(dtt_working_stock_conc))
        dtt_working_vol = (
            pipette_min * num_samples + 8 * amt_extra_in_2ml_reservoir + 50
        )
        dtt_stock_vol = (
            dtt_working_stock_conc * dtt_working_vol
        ) / dtt_conc  # amt of stock that needs to be transfered to create working dtt solution

        falcon_tube_rack["B1"].load_liquid(dtt_stock, dtt_stock_vol)
        dtt_working_storage = dtt_stock_storage

        pick_up(left_pipette)
        for i in range(0, 8):
            if i < num_samples % 8:
                amt_in_well = (
                    5 * math.ceil(num_samples / 8) + amt_extra_in_2ml_reservoir
                )
            else:
                amt_in_well = (
                    5 * math.floor(num_samples / 8) + amt_extra_in_2ml_reservoir
                )
            # print(amt_in_well)
            transfer_large_amt(
                amt_in_well,
                dtt_working_storage,
                digestion_buffer_reservoir.wells()[i + 8],
                left_pipette,
                0.5,
                dispense_height=1,
            )
        remove_tip(left_pipette)
        # ADDING DTT TO PLATE
        for i in range(0, math.ceil(num_samples / 8)):
            pick_up(right_pipette)
            right_pipette.aspirate(5, digestion_buffer_reservoir["A2"].bottom(0.1), 0.2)
            right_pipette.dispense(5, sample_plate["A" + str(i + 1)].bottom(1), 0.5)
            right_pipette.mix(
                3,
                protein_sample_amt - 20,
                sample_plate["A" + str(i + 1)].bottom(1),
                0.2,
            )
            right_pipette.blow_out(sample_plate["A" + str(i + 1)].top())
            remove_tip(right_pipette)
        hs_mod.open_labware_latch()
        # 56 C for 30 minutes
        protocol.move_labware(sample_plate, hs_mod, use_gripper=True)
        hs_mod.close_labware_latch()
        hs_mod.open_labware_latch()
        try:
            protocol.move_lid(source_location=lid, new_location=sample_plate, use_gripper=True)
        except:
            protocol.pause("Please place the lid on the sample plate and press RESUME")
        hs_mod.close_labware_latch()

        hs_mod.set_and_wait_for_shake_speed(400)  # 400 rpm
        # hs_mod.set_and_wait_for_temperature(56)
        start_time = datetime.now()

        # PREPARING IAA
        iaa_working_stock_conc = (
            iaa_final_conc * protein_sample_amt
        ) / pipette_min  # IAA working stock concentration so that 5ul is 20 mM
        print("IAA working stock concentration: " + str(iaa_working_stock_conc))
        iaa_working_vol = (
            pipette_min * num_samples + 8 * amt_extra_in_2ml_reservoir + 50
        )
        iaa_stock_vol = (
            iaa_working_stock_conc * iaa_working_vol
        ) / iaa_conc  # amt of stock that needs to be transfered to create working dtt solution
        iaa_working_storage = iaa_stock_storage
        falcon_tube_rack["C1"].load_liquid(iaa_stock, iaa_stock_vol)

        pick_up(left_pipette)
        for i in range(0, 8):
            if i < num_samples % 8:
                amt_in_well = (
                    5 * math.ceil(num_samples / 8) + amt_extra_in_2ml_reservoir
                )
            else:
                amt_in_well = (
                    5 * math.floor(num_samples / 8) + amt_extra_in_2ml_reservoir
                )
            # print(amt_in_well)
            transfer_large_amt(
                amt_in_well,
                iaa_working_storage,
                digestion_buffer_reservoir.wells()[i + 16],
                left_pipette,
                0.5,
                dispense_height=1,
            )
        remove_tip(left_pipette)
        check_tips()

        # 20 min incubation
        time_elasped = (datetime.now() - start_time).seconds
        delay(seconds=1200 - time_elasped, msg="20 minute DTT incubation at 56 C")
        # moving plate and adding IAA to plate
        hs_mod.deactivate_heater()
        hs_mod.deactivate_shaker()
        hs_mod.open_labware_latch()
        lid = protocol.move_lid(source_location=sample_plate, new_location="C3", use_gripper=True)

        protocol.move_labware(sample_plate, "A1", use_gripper=True)
        
        delay(seconds=10*60, msg="Waiting 10 minutes for heat shaker to cool down")
        for i in range(0, math.ceil(num_samples / 8)):
            pick_up(right_pipette)
            right_pipette.aspirate(5, digestion_buffer_reservoir["A3"].bottom(0.1), 0.2)
            right_pipette.dispense(5, sample_plate["A" + str(i + 1)].bottom(1), 0.5)
            right_pipette.mix(
                3,
                protein_sample_amt - 20,
                sample_plate["A" + str(i + 1)].bottom(1),
                0.2,
            )
            right_pipette.blow_out(sample_plate["A" + str(i + 1)].top())
            remove_tip(right_pipette)

        # 45 minute IAA incubation at RT
        hs_mod.open_labware_latch()
        protocol.move_labware(sample_plate, hs_mod, use_gripper=True)
        hs_mod.close_labware_latch()
        hs_mod.open_labware_latch()
        try:
            protocol.move_lid(source_location=lid, new_location=sample_plate, use_gripper=True)
        except:
            protocol.pause("Please place the lid on the sample plate and press RESUME")
        hs_mod.close_labware_latch()
        hs_mod.set_and_wait_for_shake_speed(400)  # 400 rpm
        start_time = datetime.now()
        
        load_beads() #adds 12.5ul beads
        check_tips()
        time_elasped = (datetime.now() - start_time).seconds
        delay(seconds=1800-time_elasped, msg="30 minute IAA incubation at room temperature")
        hs_mod.deactivate_shaker()
        hs_mod.deactivate_heater()
        hs_mod.open_labware_latch()
        try:
            lid = protocol.move_lid(source_location=sample_plate, new_location="C3", use_gripper=True)
        except:
            protocol.pause("Please move lid")
        protocol.move_labware(sample_plate, "A1", use_gripper=True)

    hs_mod.open_labware_latch()
    hs_mod.close_labware_latch()
        
    if protocol.params.reduction_alkylation == False:
        load_beads()


    protocol.comment(
        "\n\n---------------Protein Binding Procedure------------------\n\n\n\n"
    )
    protocol.comment(
        "\nAdding "
        + str(protein_sample_amt)
        + "µl binding buffer to "
        + str(protein_sample_amt)
        + "µl protein sample"
    )
    for i in range(0, math.ceil(num_samples / 8)):
        pick_up(right_pipette)
        binding_buffer_amt -= (protein_sample_amt / 1000) * 8
        right_pipette.aspirate(
            protein_sample_amt,
            binding_buffer_storage[math.ceil(binding_buffer_amt / 10.5) - 1].bottom(1),
            0.4,
        )
        right_pipette.dispense(
            protein_sample_amt, sample_plate["A" + str(i + 1)].bottom(1), 0.5
        )
        right_pipette.mix(
            4,
            protein_sample_amt - 15,
            sample_plate["A" + str(i + 1)].bottom(1),
            rate=0.1,
        )
        right_pipette.blow_out(sample_plate["A" + str(i + 1)].top())
        remove_tip(right_pipette)
    check_tips()

    protocol.comment(
        "\nPlacing tube on magnetic separator and allowing 10s for microparticles to clear"
    )
    hs_mod.open_labware_latch()
    protocol.move_labware(reagent_plate, magnetic_block, use_gripper=True)
    protocol.delay(
        seconds=bead_settle_time + 5, msg="waiting for beads to settle (20 sec)"
    )
    aspirate_spuernatent_to_trash(
        right_pipette, wash_volume, discard_tip=False
    )
    
    hs_mod.open_labware_latch()
    protocol.move_labware(reagent_plate, hs_mod, use_gripper=True)
    hs_mod.close_labware_latch()

    protocol.comment("\nAdding binding buffer and protein sample to well plate")
    for i in range(0, math.ceil(num_samples / 8)):
        pick_up(right_pipette)
        right_pipette.aspirate(
            protein_added_to_beads + 10, sample_plate["A" + str(i + 1)], rate=0.1
        )
        right_pipette.dispense(
            protein_added_to_beads, reagent_plate["A" + str(i + 1)].bottom(2), rate=0.1
        )
        mix_sides(right_pipette, 2, 50, reagent_plate["A" + str(i + 1)])
        # right_pipette.mix(3, 30, reagent_plate['A' + str(i+1)].bottom(0.5), rate=0.1)
        # right_pipette.dispense(10, reagent_plate["A" + str(i + 1)].top(1), rate=0.1)
        right_pipette.blow_out(reagent_plate["A" + str(i + 1)].top())
        right_pipette.touch_tip()
        right_pipette.blow_out(reagent_plate["A" + str(i + 1)].top())
        remove_tip(right_pipette)

    protocol.comment(
        "\nAllow proteins to bind to microparticles for 30 min. Mix gently and continuously"
    )
    start_time = time.time()
    protocol.comment("\n\n\n\n\n" + str(start_time))
    hs_mod.open_labware_latch()
    hs_mod.close_labware_latch()
    hs_mod.set_and_wait_for_shake_speed(1550)  # 1100 rpm
    protocol.comment("\n\n" * 20)

    start_time = datetime.now()
    time_elasped = (datetime.now() - start_time).seconds
    # 30 minute incubation
    delay(1800 - time_elasped)

    hs_mod.deactivate_shaker()
    hs_mod.open_labware_latch()
    protocol.move_labware(reagent_plate, magnetic_block, use_gripper=True)
    protocol.delay(seconds=bead_settle_time, msg="waiting for beads to settle (20 sec)")
    aspirate_spuernatent_to_trash(right_pipette, wash_volume - 15)

    protocol.comment(
        "\nResuspend beads in "
        + str(wash_volume)
        + "µl wash buffer and mix thoroughly for 1 minute. times: "
        + str(num_washes)
    )  # TO-DO: PUT THIS INTO A FRICKEN FUNCTION!
    wash_buffer_resuspend_amt = wash_volume
    for wash_num in range(0, num_washes):
        protocol.comment("Resuspend number: " + str(i + 1))
        hs_mod.open_labware_latch()
        protocol.move_labware(reagent_plate, new_location=hs_mod, use_gripper=True)
        hs_mod.close_labware_latch()
        pick_up(right_pipette)
        for i in range(0, math.ceil(num_samples / 8)):
            wash_buffer_amt -= wash_buffer_resuspend_amt / 1000 * 8
            right_pipette.aspirate(
                wash_buffer_resuspend_amt,
                wash_buffer_storage[math.ceil(wash_buffer_amt / 10.5) - 1].bottom(2),
                0.4,
            )

            right_pipette.dispense(
                wash_buffer_resuspend_amt,
                reagent_plate["A" + str(i + 1)].top(),
                rate=0.5,
            )
            right_pipette.blow_out(reagent_plate["A" + str(i + 1)].top())
        remove_tip(right_pipette)
        
        for i in range(0, math.ceil(num_samples / 8)):
            pick_up(right_pipette)
            fancy_mix_sides(
                right_pipette,
                3,
                130,
                reagent_plate["A" + str(i + 1)], num_points=8
            )

            # right_pipette.mix(4, wash_buffer_resuspend_amt-10, reagent_plate['A' + str(i+1)].bottom(2),rate= 3)
            right_pipette.blow_out(reagent_plate["A" + str(i + 1)].top())
            right_pipette.blow_out(reagent_plate["A" + str(i + 1)].top())
            right_pipette.touch_tip()
            remove_tip(right_pipette)

        protocol.comment("Gentle agitation for 1 minute (" + str(shake_speed) + "rpm)")
        hs_mod.set_and_wait_for_shake_speed(1000)  # 1300 rpm
        delay(60)
        hs_mod.deactivate_shaker()
        hs_mod.open_labware_latch()
        protocol.move_labware(reagent_plate, magnetic_block, use_gripper=True)
        protocol.delay(
            seconds=bead_settle_time, msg="waiting for beads to settle"
        )
        if wash_num == num_washes - 1:  # last wash
            aspirate_spuernatent_to_trash(
                right_pipette, wash_buffer_resuspend_amt + 10
            )
        elif wash_num == 0:  # first wash
            aspirate_spuernatent_to_trash(
                right_pipette, wash_buffer_resuspend_amt + 10
            )

    hs_mod.open_labware_latch()
    protocol.move_labware(reagent_plate, new_location=hs_mod, use_gripper=True)
    hs_mod.close_labware_latch()

    protocol.comment(
        "\n\n--------------------Protein Digestion Procedure-----------------------"
    )
    protocol.comment(
        "Resuspending microparticles with protein in 100 digestion buffer"
    )
    protocol.pause("Add trypsin/digestion buffer to A2 in Slot C2.")



    transfer_vol = (math.ceil(num_samples / 8)) * 100 + 50  # transfer into each well
    total_dig_buffer = transfer_vol * 8
    pipette_max = 200
    num_transfers = math.ceil((total_dig_buffer) / (pipette_max))
    well_counter = 0
    left_pipette.pick_up_tip()
    for well_counter in range(0, 8):
        if (num_samples % 8) > well_counter:
            transfer_vol = (
                math.ceil(num_samples / 8)
            ) * 100 + 50  # transfer into each well
        else:
            transfer_vol = (
                math.floor(num_samples / 8)
            ) * 100 + 50  # transfer into each well
        transfer_large_amt(
            transfer_vol,
            dig_buffer_location,
            digestion_buffer_reservoir.wells()[well_counter],
            left_pipette,
            0.25,
            2,
            meniscus = True
        )

    remove_tip(left_pipette)

    # aspirate_spuernatent_to_trash(right_pipette, wash_buffer_resuspend_amt)

    # DO THE MATH AND FIX THIS PART LATER
    pick_up(right_pipette)
    for i in range(0, math.ceil(num_samples / 8)):
        right_pipette.aspirate(
            digestion_buffer_per_sample_amt, digestion_buffer_reservoir["A1"], 0.1
        )
        right_pipette.dispense(
            digestion_buffer_per_sample_amt,
            reagent_plate["A" + str(i + 1)].top(-2),
            0.5,
        )
        right_pipette.blow_out(reagent_plate["A" + str(i + 1)].top(-2))
        right_pipette.touch_tip(reagent_plate["A" + str(i + 1)])
        right_pipette.blow_out(reagent_plate["A" + str(i + 1)].top(-2))
    remove_tip(right_pipette)

    # MIXING DIGESTION BUFFER
    # for i in range(0, math.ceil(num_samples / 8)):
    #     pick_up(right_pipette)
    #     fancy_mix_sides(
    #         right_pipette,
    #         3,
    #         125,
    #         reagent_plate["A" + str(i + 1)], num_points = 8
    #     )
    #     right_pipette.blow_out(reagent_plate["A" + str(i + 1)].top())
    #     right_pipette.blow_out(reagent_plate["A" + str(i + 1)].top())
    #     # right_pipette.blow_out(reagent_plate['A' + str(i+1)].top(1))
    #     remove_tip(right_pipette)

    protocol.comment(
        "\nIncubating sample at 47°C for ___ hours. Mix continuously at "
        + str(shake_speed)
        + " rpm"
    )
    hs_mod.open_labware_latch()
    protocol.move_lid(source_location=lid, new_location=reagent_plate, use_gripper=True)

    #protocol.move_labware(lid, reagent_plate, use_gripper=True)
    # protocol.pause("Please move lid")
    # try:
    #     protocol.move_lid(source_location=lid, new_location=reagent_plate, use_gripper=True)
    # except:
    #     protocol.pause("Please place the lid on the reagent plate and press RESUME")

    hs_mod.close_labware_latch()
    hs_mod.set_and_wait_for_shake_speed(1450)  # 1000 rpm
    hs_mod.set_and_wait_for_temperature(47)  #47C
    start_time = datetime.now()
    
    check_tips()
    time_elasped = (datetime.now() - start_time).seconds
    delay(protocol.params.incubation_time * 60 * 60 - time_elasped, msg="Incubation at 47°C for " + str(protocol.params.incubation_time) + " hours")

    hs_mod.deactivate_shaker()
    hs_mod.deactivate_heater()
    hs_mod.open_labware_latch()
    
    lid = protocol.move_lid(source_location=reagent_plate, new_location="C3", use_gripper=True)
    
    protocol.move_labware(reagent_plate, new_location=magnetic_block, use_gripper=True)

    # hs_mod.close_labware_latch()

    protocol.comment(
        "\nPellet beads and transfer peptides"
    )

    if num_samples<=24:
        for i in range(0, num_samples):
            pick_up(left_pipette)
            left_pipette.aspirate(
                amt_of_sample_to_collect,
                reagent_plate.wells()[i].bottom(0.4),
                0.1,
            )
            left_pipette.dispense(
                amt_of_sample_to_collect,
                final_tube_rack.wells()[i].bottom(0.2),
                0.4,
            )
            left_pipette.blow_out(final_tube_rack.wells()[i].top(-5))
            left_pipette.touch_tip()
            remove_tip(left_pipette)
        
    else:
        for i in range (0, math.ceil(num_samples/8)):
            pick_up(right_pipette)
            right_pipette.aspirate(
                amt_of_sample_to_collect,
                reagent_plate["A" + str(i+1)].bottom(0.4),
                0.05,
            )
            right_pipette.dispense(
                amt_of_sample_to_collect,
                final_tube_rack["A" + str(i+1)].bottom(0.2),
                0.1,
            )
            remove_tip(right_pipette)
        
    add_formic_acid = True
    if add_formic_acid:
        if num_samples < 24:
        #setup formic acid to multiplex
            for i in range(0, num_samples):
            # protocol.comment("hi")
                pick_up(left_pipette)
                left_pipette.aspirate(10, formic_acid_storage.bottom(0.1), 0.2)
                left_pipette.dispense(10, final_tube_rack.wells()[i].bottom(1), 0.2)
                remove_tip(left_pipette)

        else:
            pick_up(right_pipette)
            for i in range(0, math.ceil(num_samples / 8)):
                right_pipette.aspirate(10, formic_acid_storage.bottom(0.1), 0.2)
                right_pipette.dispense(10, final_tube_rack["A"+str(i+1)].bottom(0.5), 0.1)
            remove_tip(right_pipette)
