from opentrons import protocol_api
import math
import urllib.request
import json
from opentrons import types
import time
from datetime import datetime

metadata = {
    "protocolName": "HS gripper test HILIC",
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

    parameters.add_bool(
        variable_name="dry_run",
        display_name="Dry Run",
        description="Skip incubation delays and return tips. Don't modify this value unless you're testing stuff.",
        default=False,
    )


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
    dry_run = protocol.params.dry_run
    
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
    def remove_tip(pipette, is_dry_run=protocol.params.dry_run):
        if is_dry_run:
            pipette.return_tip()
        else:
            pipette.drop_tip(chute)

    def remove_tip_dispense_trash(pipette, amt, is_dry_run=protocol.params.dry_run):
        if trash_storage.current_liquid_volume() > 13000 and trash_storage2.current_liquid_volume() < 13000:
            pipette.dispense(amt, trash_storage2.top(0))
        elif trash_storage2.current_liquid_volume() > 13000 and trash_storage3.current_liquid_volume() < 13000:
            pipette.dispense(amt, trash_storage3.top(0))
        elif trash_storage3.current_liquid_volume() > 13000:
            pipette.dispense(amt, trash_storage4.top(0))
        else:
            pipette.dispense(amt, trash_storage.top(0))

        if is_dry_run:
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
            #     remove_tip(pipette, protocol.params.dry_run)
                
        if pipette.has_tip == True:
            remove_tip(pipette, protocol.params.dry_run)

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
                    labware=tips200[i], new_location=chute, use_gripper=True if not dry_run else False
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
        if protocol.params.dry_run:
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
                    aspirate_end_location = bead_storage.bottom(z=1),
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
                remove_tip(left_pipette,protocol.params.dry_run)
                left_pipette.pick_up_tip()

        remove_tip(left_pipette,protocol.params.dry_run)

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


    hs_mod.open_labware_latch()
    # 56 C for 30 minutes
    protocol.move_labware(sample_plate, hs_mod, use_gripper=True)
    hs_mod.close_labware_latch()
    hs_mod.open_labware_latch()
    try:
        protocol.move_lid(source_location=lid, new_location=sample_plate, use_gripper=True)
    except:
        protocol.pause("Please place the lid on the sample plate and press RESUME")

    lid = protocol.move_lid(source_location=sample_plate, new_location="C3", use_gripper=True)

    protocol.move_labware(sample_plate, "A1", use_gripper=True)

    protocol.move_labware(reagent_plate, magnetic_block, use_gripper=True)
    protocol.move_labware(reagent_plate, hs_mod, use_gripper=True)
    protocol.move_lid(source_location=lid, new_location=reagent_plate, use_gripper=True)
    lid = protocol.move_lid(source_location=reagent_plate, new_location="C3", use_gripper=True)
